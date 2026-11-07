"""What an actor sent in one request (docs/contracts/player-host.md, Context manifest).

`replay_manifests` rebuilds the ordered parts of every request from the host's delta-encoded
`context-manifest` events, exactly, by the replay rule: `parts(M) = parts(base(M))[0:reused_prefix_parts]
++ M.parts` and `omitted(M) = M.omitted_image_indexes` if present, else `omitted(base(M))`.

`reconstruct_context` is for traces recorded before the manifest existed. It rebuilds the parts from the
actor's frozen inputs (`context.txt`, `prompt.txt`, which carries any handoff context) plus the recorded tool
calls and results before the request, and marks image parts omitted from the projection event's omissions
(a preview capped at 16). It cannot see the assistant's text or reasoning, so it is flagged `exact: false`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from .records import EvaluationError
from .sources import HostEvent

PART_FIELDS = ('index', 'role', 'kind', 'bytes', 'sha256', 'tool_call_id', 'tool', 'state', 'image_index', 'source_id')


def replay_manifests(events: Sequence[HostEvent]) -> dict[str, dict]:
    """`request_id -> {parts, omitted_image_indexes, part_count, reused_prefix_parts, base_request_id}`
    for every manifest of one host, in trace order. A manifest that breaks the rule is an error."""
    replayed: dict[str, dict] = {}
    for event in events:
        if event.type != 'context-manifest':
            continue
        fields = event.fields
        request_id = fields.get('request_id')
        base_id = fields.get('base_request_id')
        reused = fields.get('reused_prefix_parts', 0)
        if base_id is None:
            base_parts, base_omitted = [], []
        elif base_id in replayed:
            base_parts, base_omitted = replayed[base_id]['parts'], replayed[base_id]['omitted_image_indexes']
        else:
            raise EvaluationError(f'host trace line {event.line}: manifest {request_id} names unknown base {base_id}')
        if type(reused) is not int or not 0 <= reused <= len(base_parts):
            raise EvaluationError(f'host trace line {event.line}: manifest {request_id} reuses {reused} of {len(base_parts)} parts')
        parts = [*base_parts[:reused], *(fields.get('parts') or ())]
        if len(parts) != fields.get('part_count') or any(p.get('index') != i for i, p in enumerate(parts)):
            raise EvaluationError(f'host trace line {event.line}: manifest {request_id} does not replay to its part count')
        omitted = fields['omitted_image_indexes'] if 'omitted_image_indexes' in fields else base_omitted
        replayed[request_id] = dict(request_id=request_id, parts=parts, omitted_image_indexes=list(omitted),
            part_count=len(parts), reused_prefix_parts=reused, base_request_id=base_id)
    return replayed


def _actor_directory(run_dir: Path, actor: str) -> Path | None:
    root = run_dir / 'actors'
    for directory in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else ():
        try:
            if json.loads((directory / 'actor.json').read_text()).get('actor_id') == actor:
                return directory
        except (OSError, ValueError):
            continue
    return None


def _read(directory: Path | None, name: str) -> str | None:
    try:
        return (directory / name).read_text() if directory is not None else None
    except OSError:
        return None


def _text_part(index: int, role: str, name: str, text: str | None) -> dict:
    return dict(index=index, role=role, kind='text', bytes=None if text is None else len(text.encode('utf-8')),
        sha256=None, name=name, available=text is not None)


def reconstruct_context(run_dir: Path, actor: str, events: Sequence[HostEvent], request_id: str) -> dict:
    """Best-effort parts for `request_id` from the frozen inputs and recorded tool traffic. `exact` is False."""
    directory = _actor_directory(Path(run_dir), actor)
    parts = [_text_part(0, 'system', 'context.txt', _read(directory, 'context.txt')),
        _text_part(1, 'user', 'prompt.txt', _read(directory, 'prompt.txt'))]
    omissions: dict[tuple[str, int], str] = {}
    omitted_count = 0
    starts: dict[str, HostEvent] = {}
    seen_request = False
    for event in events:
        if event.type == 'request-start' and event.fields.get('request_id') == request_id:
            seen_request = True
        if event.type == 'context-image-projection' and event.fields.get('request_id') == request_id:
            omitted_count = event.fields.get('omitted_images') or 0
            omissions = {(o['tool_call_id'], o['image_index']): o.get('sha256') for o in event.fields.get('omissions') or ()
                if isinstance(o, dict)}
        if seen_request:
            break
    if not seen_request:
        raise EvaluationError(f'actor {actor}: no request {request_id} in the host trace')
    for event in events:
        if event.type == 'request-start' and event.fields.get('request_id') == request_id:
            break
        if event.type == 'tool-start':
            starts[event.fields.get('tool_call_id')] = event
            arguments = json.dumps(event.fields.get('arguments') or {}, separators=(',', ':'), ensure_ascii=False)
            parts.append(dict(index=len(parts), role='assistant', kind='tool_call', bytes=len(arguments.encode('utf-8')),
                sha256=None, tool_call_id=event.fields.get('tool_call_id'), tool=event.fields.get('tool')))
        elif event.type == 'tool-result':
            call_id = event.fields.get('tool_call_id')
            content = (event.fields.get('result') or {}).get('content') or []
            texts = [c['text'] for c in content if isinstance(c, dict) and isinstance(c.get('text'), str)]
            parts.append(dict(index=len(parts), role='tool', kind='tool_result_text',
                bytes=sum(len(t.encode('utf-8')) for t in texts), sha256=None, tool_call_id=call_id, tool=event.fields.get('tool')))
            source_id = None
            for text in texts:
                try:
                    source = json.loads(text).get('source')
                except (ValueError, AttributeError):
                    continue
                if isinstance(source, dict) and isinstance(source.get('source_id'), str):
                    source_id = source['source_id']
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'image_reference':
                    index = item.get('image_index', 0)
                    omitted = (call_id, index) in omissions
                    parts.append(dict(index=len(parts), role='tool', kind='image', bytes=item.get('bytes'),
                        sha256=item.get('sha256'), tool_call_id=call_id, tool=event.fields.get('tool'),
                        state='omitted' if omitted else 'sent', image_index=index, source_id=source_id))
    omitted_indexes = [p['index'] for p in parts if p.get('state') == 'omitted']
    return dict(request_id=request_id, parts=parts, omitted_image_indexes=omitted_indexes, part_count=len(parts),
        missing=['assistant_text', 'reasoning'], omissions_capped=omitted_count > len(omissions))


def request_context(run_dir: Path, actor: str, events: Sequence[HostEvent], request_id: str) -> dict:
    """The exact replayed parts if the host recorded a manifest for `request_id`, else a reconstruction."""
    manifests = replay_manifests(events)
    if request_id in manifests:
        value = manifests[request_id]
        return dict(exact=True, actor=actor, **value)
    return dict(exact=False, actor=actor, **reconstruct_context(run_dir, actor, events, request_id))
