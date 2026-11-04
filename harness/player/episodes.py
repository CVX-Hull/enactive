"""Episode claims: their stored form, trust, and the status and stall derived from them at read time.

Pure functions over `player-record/1` dictionaries; no storage, process or provider imports. An episode is one
`claim` record whose `data` follows `player-episode/2` and which only the custodian's settle path writes.
Status and stall are never stored on a Work record: they are recomputed from the trusted claims on every read.
"""
from __future__ import annotations

import math
from typing import Any

from .contracts import EPISODE_CONTRACT, OBSERVATION_STATUSES, SETTLE_WRITERS


def _integer(value: object) -> bool:
    return type(value) is int


def _number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def claim_data(*, session: str, actor_id: str, first_position: int, last_position: int, subgoal_id: str | None,
               settled: str, **fields: Any) -> dict[str, Any]:
    """The `data` of one episode claim; `writer` follows from how the episode settled, never from a caller."""
    return dict(level='episode', level_contract=EPISODE_CONTRACT, settled=settled, writer=SETTLE_WRITERS[settled],
                session=session, actor_id=actor_id, first_position=first_position, last_position=last_position,
                subgoal_id=subgoal_id, **fields)


def episode(record: dict) -> dict[str, Any] | None:
    """A trusted episode claim's fields, or None for any record that is not one.

    Trusted means the episode contract and a `writer` stamp consistent with how the claim settled. The general
    append path refuses both keys, so only the custodian can have written such a record, in any session.
    """
    data = record.get('data')
    if record.get('kind') != 'claim' or type(data) is not dict or data.get('level') != 'episode':
        return None
    if data.get('level_contract') != EPISODE_CONTRACT or SETTLE_WRITERS.get(data.get('settled')) != data.get('writer'):
        return None
    first, last, subgoal = data.get('first_position'), data.get('last_position'), data.get('subgoal_id')
    if not (_integer(first) and _integer(last) and 1 <= first <= last) or not (subgoal is None or type(subgoal) is str):
        return None
    if type(data.get('session')) is not str or type(data.get('actor_id')) is not str:
        return None
    view = dict(record_id=record['id'], created_wall=record.get('created_wall'), sources=list(record.get('sources', [])),
                **{k: data[k] for k in ('settled', 'writer', 'session', 'actor_id', 'first_position', 'last_position',
                                        'subgoal_id')})
    if data['settled'] == 'recorded':
        marks, confidence = data.get('observation_marks'), data.get('confidence')
        summary = data.get('summary_sources')
        if (type(marks) is not list or type(summary) is not list
                or any(type(mark) is not dict or set(mark) != {'status', 'sources'}
                       or mark['status'] not in OBSERVATION_STATUSES or type(mark['sources']) is not list
                       or not (0 if mark['status'] == 'unassessable' else 1) <= len(mark['sources']) <= 2
                       or any(type(source) is not str or source not in view['sources'] for source in mark['sources'])
                       or len(set(mark['sources'])) != len(mark['sources']) for mark in marks)
                or not 1 <= len(summary) <= 4
                or any(type(source) is not str or source not in view['sources'] for source in summary)
                or not _number(confidence)
                or not 0 <= confidence <= 1
                or any(type(data.get(k)) is not str for k in ('attempted', 'counterpart', 'residual', 'changed'))):
            return None
        view.update({k: data[k] for k in ('attempted', 'counterpart', 'residual', 'changed', 'observation_marks',
                                          'confidence')})
        view.update(sources=list(summary), observation_status=[mark['status'] for mark in marks])
    else:
        if type(data.get('reason')) is not str:
            return None
        view['reason'] = data['reason']
        if data['settled'] == 'abstained':
            view['reason_code'] = data.get('reason_code')
    return view


def derive(subgoal: dict, views: list[dict], *, stall_settles: int, floor: float) -> dict[str, Any]:
    """The subgoal's observation status, stall and counts, from episode views committed after it (oldest first).

    `views` are `episode()` results, so already trusted. Only those whose pushed subgoal id is this subgoal's
    count; any other is ignored, so marks are
    never attributed to the wrong subgoal. Marks count only from `recorded` claims with confidence at least
    `floor` and a correctly sized mark vector. Only these eligible observations affect the stall streak:
    newly seen progress resets it. Without progress, increment only when an unresolved slot existed
    before this claim and every such slot was assessable. Missing evidence is neutral but stays
    in the operational counts.
    """
    texts = subgoal['data'].get('expected_observations') or []
    status = ['not_yet'] * len(texts)
    marker: list[dict | None] = [None] * len(texts)
    contradicted_by: list[list[dict]] = [[] for _ in texts]
    settles = [view for view in views if view['subgoal_id'] == subgoal['id']]
    counts = dict(episodes=len(settles), recorded=0, abstained=0, failed=0, dropped=0, counted=0)
    counted: list[dict] = []
    streak = 0
    for view in settles:
        counts[view['settled']] += 1
        newly = False
        eligible = (view['settled'] == 'recorded' and view['confidence'] >= floor
                    and len(view['observation_status']) == len(texts))
        if eligible:
            counts['counted'] += 1
            counted.append(view)
            marks = view['observation_status']
            unresolved = [index for index, state in enumerate(status) if state != 'seen']
            for index, mark in enumerate(marks):
                if mark == 'seen':
                    newly = newly or status[index] != 'seen'
                    status[index], marker[index] = 'seen', view
                elif mark == 'contradicted':
                    status[index], marker[index] = 'contradicted', view
                    contradicted_by[index].append(view)
            if newly:
                streak = 0
            elif unresolved and all(marks[index] != 'unassessable' for index in unresolved):
                streak += 1
    # For each observation now contradicted: every counted claim that marks it contradicted (not only the
    # latest), since a keep may cite the source of any of them.
    contradicting = [dict(index=i, claim_id=marker[i]['record_id'], claim_ids=[v['record_id'] for v in contradicted_by[i]],
                          sources=list(dict.fromkeys(s for v in contradicted_by[i] for s in v['observation_marks'][i]['sources'])))
                     for i, s in enumerate(status) if s == 'contradicted']
    seen_by = [marker[i] for i, s in enumerate(status) if s == 'seen']
    deciding_sources = list(dict.fromkeys(source for i, state in enumerate(status) if state == 'seen'
                                         for source in marker[i]['observation_marks'][i]['sources']))
    return dict(observations=[dict(text=t['predicate'], status=s) for t, s in zip(texts, status, strict=True)],
                all_seen=bool(texts) and all(s == 'seen' for s in status), stalled=streak >= stall_settles,
                no_progress_settles=streak, stall_settles=stall_settles, confidence_floor=floor,
                counts=dict(counts, seen=status.count('seen'), contradicted=status.count('contradicted')),
                counted=counted, deciding=seen_by, deciding_sources=deciding_sources, contradicting=contradicting)


def closure_evidence(derived: dict, limit: int = 16) -> tuple[list[str], list[str]]:
    """The claim ids a software closure `supports` and the sources it cites, each capped at `limit`.

    The claims that last made each observation seen come first, so the evidence for the closure is never the
    part cut; the rest fill the claim cap newest first. Closure sources come from the deciding marks.
    """
    counted = derived['counted']
    chosen = {v['record_id']: v for v in derived['deciding']}
    for view in reversed(counted):
        if len(chosen) >= limit:
            break
        chosen.setdefault(view['record_id'], view)
    order = {v['record_id']: i for i, v in enumerate(counted)}
    supports = sorted(chosen, key=order.__getitem__)[:limit]
    return supports, derived['deciding_sources'][:limit]
