"""Replay matched CDDA development observations without a model or live source reader."""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path

from tools.recurrence_research.belief import active_alternatives, evidence_views, revision_state


def exposed_input(case: dict, checkpoint: dict) -> dict:
    """Project only the named prefix, omitting adjudication and all other observations."""
    through = checkpoint['through']
    if type(through) is not int or not 0 <= through <= len(case['exposure']):
        raise ValueError('checkpoint outside the assigned exposure')
    prefix = case['exposure'][:through]
    observations = []
    visible = set()
    for source in prefix:
        if source in visible:
            raise ValueError(f'duplicate exposure {source}')
        visible.add(source)
        observation = case['observations'][source]
        reports = []
        for report in observation.get('reports', ()):
            origin, event, polarity = (report[key] for key in ('origin', 'event', 'polarity'))
            if origin not in visible or polarity not in ('support', 'refute', 'unknown'):
                raise ValueError(f'invalid exposed report for {source}')
            reports.append(dict(origin=origin, event=event, polarity=polarity))
        observations.append(dict(source_id=source, detail=observation['detail'], reports=reports))
    withdrawn = checkpoint.get('withdrawn_origins', [])
    if not set(withdrawn) <= visible:
        raise ValueError('withdrawal references an unexposed origin')
    return dict(question=case['question'], scope=case['scope'], dependence_group=case['dependence_group'],
                applicable_events=list(case['applicable_events']), required_support=list(case.get('required_support', ())),
                observations=observations,
                withdrawn_origins=list(withdrawn))


def _readout(state: str, sources: list[str]) -> dict:
    return dict(state=state, answer={'support-only': True, 'refutation-only': False}.get(state), source_ids=sources)


def compare(shared: dict) -> dict:
    """Give both methods the same projected extraction and use unit fixture weights."""
    events = {}
    withdrawn = set(shared['withdrawn_origins'])
    applicable = set(shared['applicable_events'])
    active = [row['source_id'] for row in shared['observations'] if row['source_id'] not in withdrawn]
    for row in shared['observations']:
        for report in row['reports']:
            event = report['event']
            if event not in applicable:
                continue
            origin, polarity = report['origin'], report['polarity']
            identity = (origin, polarity)
            if event not in events and origin != row['source_id']:
                raise ValueError(f'missing original report for event {event}')
            if events.setdefault(event, identity) != identity:
                raise ValueError(f'inconsistent origin or polarity for event {event}')
    support = {event: origin for event, (origin, polarity) in events.items() if polarity == 'support'}
    refute = [(origin,) for origin, polarity in events.values() if polarity == 'refute']
    required = shared['required_support']
    if required:
        support_alternatives = [tuple(support[event] for event in required)] if set(required) <= support.keys() else []
    else:
        support_alternatives = [(origin,) for origin in support.values()]
    applicable_origins = {origin for origin, _ in events.values()}
    sources = [origin for origin in active if origin in applicable_origins]

    qualitative_state = revision_state(support_alternatives, refute, active)
    r = len(set().union(*active_alternatives(support_alternatives, active)))
    s = len(set().union(*active_alternatives(refute, active)))
    numerical_state = {(True, False): 'support-only', (False, True): 'refutation-only',
                       (True, True): 'conflicting', (False, False): 'unknown'}[bool(r), bool(s)]
    numbers = evidence_views(r, s, 2, Fraction(1, 2))
    return dict(input=shared, qualitative=_readout(qualitative_state, sources),
                numerical=_readout(numerical_state, sources), fixture_counts=dict(r=r, s=s), fixture_views=numbers)


def replay(document: dict) -> dict:
    if document.get('schema') != 'belief-replay-fixture/1':
        raise ValueError('unsupported development replay fixture')
    return dict(scope='deterministic development fixture', cases=[
        dict(id=case['id'], checkpoints=[
            dict(id=checkpoint['id'], **compare(exposed_input(case, checkpoint))) for checkpoint in case['checkpoints']
        ]) for case in document['cases']
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture', type=Path)
    args = parser.parse_args()
    result = replay(json.loads(args.fixture.read_text(encoding='utf-8')))
    # In fixture views the only non-JSON values are exact rational numbers.
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
