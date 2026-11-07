"""Regenerate the spectator fixtures from the real viewer's responses (run by hand; tests never call it).

    python tests/fixtures/spectator/refresh.py --archive http://127.0.0.1:8765 --live http://127.0.0.1:8766

`--archive` is a viewer over the archived runs (the cross-run routes and the run list come from it).
`--live` is a viewer started with `--run <copy of an archived run>` and a scratch `--root`, so that run
is evaluated as `live`: its per-run routes and the Pause conditions come from it. Responses are verbatim
except for these edits, all made so a finished run can stand in for a live one:
- the live run keeps the archived id `ceil09` and its archived labels, and its row in the run list says `live`;
- the Pause condition `feed_alive` reads a fresh 4 s instead of the age of a finished run, and the
  summary's answer and `met` list follow;
- lists are trimmed (calls to 120 rows, eviction markers to every fourth, context parts to 60).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import urllib.request

HERE = Path(__file__).resolve().parent
RUN = 'ceil09'


def get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=60) as response:
        return json.load(response)


def write(name: str, value: dict) -> None:
    (HERE / name).write_text(json.dumps(value, indent=1) + '\n')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--live', required=True)
    parser.add_argument('--live-id', default='liverun', help='the run id the live viewer gives its run')
    args = parser.parse_args(argv)
    live = f'/api/view/run/{args.live_id}'

    runs = get(args.archive, '/api/view/runs?limit=500')
    for row in runs['items']:
        if row['run'] == RUN:
            row['state'] = 'live'
            row['versions']['state'] = 'live'
    write('runs.json', runs)

    summary = get(args.live, f'{live}/summary')
    summary['run'] = RUN
    row = next(r for r in runs['items'] if r['run'] == RUN)
    summary['labels'] = summary['facts']['labels'] = row['labels']
    pause = summary['pause']
    for condition in pause['conditions']:
        if condition['id'] == 'feed_alive':
            condition.update(value=4.0, met=False)
    pause['met'] = [c['name'] for c in pause['conditions'] if c['met']]
    pause['answer'] = 'yes' if pause['met'] else 'no'
    write('summary.json', summary)

    write('steps.json', get(args.live, f'{live}/steps?limit=500'))
    requests = get(args.live, f'{live}/requests?limit=500')
    requests['markers'] = [m for m in requests['markers'] if m['kind'] != 'context_eviction'] + \
        [m for m in requests['markers'] if m['kind'] == 'context_eviction'][::4]
    write('requests.json', requests)
    write('tools.json', get(args.live, f'{live}/tools'))
    calls = get(args.live, f'{live}/calls?limit=500')
    refused = [c for c in calls['items'] if c['status'] != 'ok']
    calls['items'] = refused + [c for c in calls['items'] if c['status'] == 'ok'][:120 - len(refused)]
    calls['items'].sort(key=lambda c: c['id'])
    write('calls.json', calls)
    last = requests['items'][-1]
    context = get(args.live, f"{live}/context/{last['request_id']}?actor={last['actor']}")
    context['parts'] = context['parts'][:60]
    write('context.json', context)
    write('memory.json', get(args.live, f'{live}/memory'))
    write('handoffs.json', get(args.live, f'{live}/handoffs'))

    programs = {'schema': 'spectator-view/1', 'programs': [], 'runs': [], 'saves': [], 'provenance': 'player_claim'}
    for row in runs['items']:
        found = get(args.archive, f"/api/view/run/{row['run']}/programs")
        if found['programs'] or found['runs']:
            programs = found
            break
    write('programs.json', programs)

    write('improve-changes.json', get(args.archive, '/api/view/improve/changes'))
    write('improve-failures.json', get(args.archive, '/api/view/improve/failures'))
    write('compare-arm.json', get(args.archive, '/api/view/compare?group=arm'))
    write('compare-start.json', get(args.archive, '/api/view/compare?group=start'))
    write('explore.json', get(args.archive, '/api/view/explore'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
