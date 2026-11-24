#!/usr/bin/env python3
"""Read-only recount of the sealed `#896-b` curator history (#936). `$0`; never writes.

  python tools/curator_history_recount.py [--evidence DIR] [--json | --markdown]

Inputs, all under the sealed evidence store (default: the main checkout's `.runtime/evidence`):

- `seven-day-896-b-admission-10/knowledge/cdda`: the curator Git repository. Every tag `vN` is read with
  `git --no-optional-locks show vN:<path>`, so Git takes no lock and writes nothing.
- `seven-day-896-b-admission-10/knowledge/cdda.state`: `gate.jsonl` (one verdict per gated submission) and
  `sessions/<id>/` (`manifest.json`, `close-out.json`, `host-output.log`, `submissions/<name>/submission.json`).
- `seven-day-896-b-admission-NN/`: the runner's `examined.jsonl` (each admission session's outcome and stop) and
  `status.json` (its final state, stop reason and unexamined backlog), and `grooming/grooming-summary.json` (the
  grooming outcome and its spend-proxy summary).

Counting rules, stated where they are applied:

- A submission counts only when `gate.jsonl` records it as published; a written submission without a verdict is
  reported as lost.
- A restatement is a published `supersede_fact`. It reused every old citation when the new fact's `citations`
  hold every citation of every fact it replaces; otherwise it omitted at least one.
- An article revision is a published `revise_article`. A claim is one `body` entry; it is byte-identical when the
  same `{text, facts}` appears in the old body. Claims changed = max(new claims not in the old body, old claims not
  in the new body), so an edited claim counts once; the sum of the two, which counts an edit twice, is reported
  beside it.
- A revision drops a fact when the old article cites it and the new one does not. The drop is accounted for when
  the fact was superseded in the same or an earlier submission. Otherwise it is `cited_elsewhere` when another
  current article at that version still cites the fact, and `orphaned` (a silent loss) when none does.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))

LINEAGE = 'seven-day-896-b'
FINAL = f'{LINEAGE}-admission-10'
ADMISSIONS = range(1, 11)
ADMISSION = re.compile(rf'{re.escape(LINEAGE)}-a(\d\d)-')


def _admission(name: str | None) -> int | None:
    match = ADMISSION.search(name or '')
    return int(match.group(1)) if match else None


class Repository:
    """The sealed curator repository, read at tags only."""

    def __init__(self, path: Path):
        self.path = path

    def git(self, *arguments: str) -> str:
        env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
        result = subprocess.run(['git', '--no-optional-locks', '-C', str(self.path), *arguments],
                                capture_output=True, text=True, timeout=60, env=env, check=False)
        if result.returncode:
            raise RuntimeError(f'git {" ".join(arguments)}: {result.stderr.strip()}')
        return result.stdout

    def versions(self) -> list[str]:
        tags = [t for t in self.git('tag', '--list', 'v*').split() if re.fullmatch(r'v(0|[1-9][0-9]*)', t)]
        return sorted(tags, key=lambda t: int(t[1:]))

    def show(self, version: str, path: str) -> str | None:
        try:
            return self.git('show', f'{version}:{path}')
        except RuntimeError:
            return None

    def records(self, version: str) -> list[dict]:
        text = self.show(version, 'facts.jsonl') or ''
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def types(self, version: str) -> list[dict]:
        text = self.show(version, 'ontology/types.json')
        return json.loads(text) if text else []


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def _read_json(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def _claim(claim: dict) -> str:
    return json.dumps(claim, sort_keys=True, separators=(',', ':'))


def store_counts(repository: Repository, gate: list[dict], sessions: Path) -> dict:
    versions = repository.versions()
    last = versions[-1]
    records = repository.records(last)
    facts = [r for r in records if r['record'] == 'fact']
    articles = [r for r in records if r['record'] == 'article']
    current_facts = [f for f in facts if 'superseded_by' not in f]
    current_articles = [a for a in articles if 'superseded_by' not in a]
    by_id = {r['id']: r for r in records}

    series = []
    for version in versions:
        rows = repository.records(version)
        series.append(dict(version=version,
                           facts=sum(r['record'] == 'fact' and 'superseded_by' not in r for r in rows),
                           articles=sum(r['record'] == 'article' and 'superseded_by' not in r for r in rows),
                           types=len(repository.types(version))))

    statuses = Counter(v['status'] for v in gate)
    published = [v for v in gate if v['status'] == 'published']
    order = {(v['session'], v['submission']): i for i, v in enumerate(published)}
    operations: list[tuple[int, str, dict]] = []
    for (session, name), position in sorted(order.items(), key=lambda kv: kv[1]):
        submission = _read_json(sessions / session / 'submissions' / name / 'submission.json')
        if submission is None:
            raise ValueError(f'{session}/{name}: published submission is missing')
        operations += [(position, published[position]['version'], change) for change in submission['changes']]
    kinds = Counter(change['op'] for _, _, change in operations)

    superseded_at: dict[str, int] = {}
    superseded_in: dict[str, str] = {}
    restatements = []
    for position, version, change in operations:
        if change['op'] != 'supersede_fact':
            continue
        old = [by_id[i] for i in change['ids']]
        before = set().union(*(set(o['citations']) for o in old))
        after = set(change['fact']['citations'])
        restatements.append(dict(version=version, replaces=len(old), reused_all=before <= after,
                                 omitted=len(before - after), kept=len(before & after)))
        for i in change['ids']:
            superseded_at[i] = position
            superseded_in[i] = version

    revisions, drops, unaccounted = [], Counter(dict.fromkeys(('superseded', 'cited_elsewhere', 'orphaned'), 0)), []
    at_version: dict[str, list[dict]] = {}
    for position, version, change in operations:
        if change['op'] != 'revise_article':
            continue
        old, new = by_id[change['id']], change['article']
        before, after = Counter(map(_claim, old['body'])), Counter(map(_claim, new['body']))
        same = sum((before & after).values())
        changed = max(sum((after - before).values()), sum((before - after).values()))
        old_facts = {f for c in old['body'] for f in c['facts']}
        new_facts = {f for c in new['body'] for f in c['facts']}
        for fact in sorted(old_facts - new_facts):
            if fact in superseded_at and superseded_at[fact] <= position:
                drops['superseded'] += 1
                continue
            rows = at_version.setdefault(version, repository.records(version))
            elsewhere = sorted(a['id'] for a in rows if a['record'] == 'article' and 'superseded_by' not in a
                               and any(fact in c['facts'] for c in a['body']))
            kind = 'cited_elsewhere' if elsewhere else 'orphaned'
            drops[kind] += 1
            unaccounted.append(dict(version=version, revised=change['id'], to=new['id'], fact=fact, kind=kind,
                                    cited_by=elsewhere, superseded_later_in=superseded_in.get(fact)))
        revisions.append(dict(version=version, claims=sum(after.values()), identical=same, changed=changed,
                              changed_sum=sum((after - before).values()) + sum((before - after).values())))

    citing = Counter(f for a in current_articles for f in {f for c in a['body'] for f in c['facts']})
    fanout = Counter(citing.values())
    retyped = [event for f in facts for event in f.get('retyped', [])]
    ever_types = {f['type'] for f in facts} | {e['from'] for e in retyped} | {e['to'] for e in retyped}
    claims = sum(r['claims'] for r in revisions)
    return dict(
        versions=dict(tags=len(versions), first=versions[0], last=last, published=len(versions) - 1),
        gate=dict(verdicts=len(gate), statuses=dict(statuses), with_diagnostics=sum(bool(v['diagnostics']) for v in gate),
                  restored=sum(v['restored_from'] is not None for v in gate)),
        operations=dict(sorted(kinds.items())),
        facts=dict(stored=len(facts), current=len(current_facts), superseded=len(facts) - len(current_facts),
                   scope=dict(Counter(f['scope']['level'] for f in current_facts)),
                   types_current=len({f['type'] for f in current_facts}), types_ever=len(ever_types),
                   types_registered=series[-1]['types'], retype_events=len(retyped),
                   retyped_facts=sum(bool(f.get('retyped')) for f in facts),
                   uncited_current=sum(f['id'] not in citing for f in current_facts)),
        restatements=dict(count=len(restatements), replaced=sum(r['replaces'] for r in restatements),
                          merges=sum(r['replaces'] > 1 for r in restatements),
                          by_replaced=dict(sorted(Counter(r['replaces'] for r in restatements).items())),
                          reused_all=sum(r['reused_all'] for r in restatements),
                          omitted_some=sum(not r['reused_all'] for r in restatements),
                          omitted_citations=sum(r['omitted'] for r in restatements)),
        articles=dict(stored=len(articles), current=len(current_articles), revisions=len(revisions),
                      revisions_changing_at_most_3=sum(r['changed'] <= 3 for r in revisions),
                      revisions_added_plus_removed_at_most_3=sum(r['changed_sum'] <= 3 for r in revisions),
                      changed_median=statistics.median(r['changed'] for r in revisions) if revisions else None,
                      claims=claims, identical_claims=sum(r['identical'] for r in revisions),
                      identical_share=round(sum(r['identical'] for r in revisions) / claims, 3) if claims else None,
                      dropped_facts=dict(sorted(drops.items())), dropped_total=sum(drops.values()),
                      unaccounted_drops=unaccounted),
        fanout=dict(cited_current_facts=len(citing), by_articles=dict(sorted(fanout.items())),
                    shared=sum(n for k, n in fanout.items() if k > 1), max=max(citing.values(), default=0)),
        series=dict(first=series[1] if len(series) > 1 else series[0], last=series[-1],
                    types_min=min(s['types'] for s in series[1:]) if len(series) > 1 else 0,
                    types_max=max(s['types'] for s in series)),
    )


def _host_log(path: Path) -> dict:
    events = _read_jsonl(path)
    ends = [e for e in events if e.get('type') == 'request-end']
    host = next((e for e in events if e.get('type') == 'host-end'), {})
    prompts = [e['prompt_tokens'] for e in ends if e.get('prompt_tokens')]
    reads = [e.get('bytes') or 0 for e in events if e.get('type') == 'tool-call' and e.get('name') == 'read_file']
    return dict(requests=len(ends), statuses=dict(Counter(e.get('status') for e in ends)),
                failed_status=next((e['status'] for e in ends if e.get('status') != 200), None),
                prompt_tokens=sum(prompts), completion_tokens=sum(e.get('completion_tokens') or 0 for e in ends),
                max_prompt_tokens=max(prompts, default=None), last_prompt_tokens=prompts[-1] if prompts else None,
                read_file_bytes=sum(reads), largest_three_read_bytes=sum(sorted(reads)[-3:]),
                end=host.get('reason'))


def session_counts(sessions: Path, evidence: Path, gate: list[dict], repository: Repository) -> dict:
    published = {(v['session'], v['submission']) for v in gate if v['status'] == 'published'}
    examined = {}
    for n in ADMISSIONS:
        for event in _read_jsonl(evidence / f'{LINEAGE}-admission-{n:02d}' / 'run' / 'curator-runner' / 'examined.jsonl'):
            if event.get('event') == 'end':
                examined[event['session_id']] = event
    rows = []
    for directory in sorted(p for p in sessions.iterdir() if p.is_dir()):
        manifest = _read_json(directory / 'manifest.json') or {}
        inputs, lifecycle = manifest.get('inputs', {}), manifest.get('lifecycle', {})
        kind = inputs.get('session_kind')
        written = sorted(p.parent.name for p in (directory / 'submissions').glob('*/submission.json'))
        log = _host_log(directory / 'host-output.log')
        admission = _admission((inputs.get('window') or {}).get('session')) or _admission(directory.name)
        rows.append(dict(id=directory.name, kind=kind, admission=admission, state=lifecycle.get('state'),
                         started=lifecycle.get('started_wall'), base=manifest.get('pinned', {}).get('knowledge_version'),
                         max_requests=manifest.get('pinned', {}).get('host', {}).get('max_requests'),
                         written=len(written), published=sum((directory.name, w) in published for w in written),
                         stop=(examined.get(directory.name) or {}).get('stop'), **log))
    rows.sort(key=lambda r: r['started'] or 0)

    groomings = []
    for n in ADMISSIONS:
        summary = _read_json(evidence / f'{LINEAGE}-admission-{n:02d}' / 'grooming' / 'grooming-summary.json')
        session = next((r for r in rows if r['kind'] == 'grooming' and r['admission'] == n), None)
        if summary is None and session is None:
            continue
        proxy = (summary or {}).get('proxy', {})
        base_bytes = session and len((repository.show(session['base'], 'facts.jsonl') or '').encode())
        groomings.append(dict(
            admission=n, status=(summary or {}).get('status'), reason=(summary or {}).get('reason'),
            state=session and session['state'], end=session and session['end'],
            versions=None if summary is None else f'{summary["published_before"]}→{summary["published_after"]}',
            published=session and session['published'], requests=session and session['requests'],
            max_requests=session and session['max_requests'], failed_status=session and session['failed_status'],
            max_prompt_tokens=session and session['max_prompt_tokens'], read_file_bytes=session and session['read_file_bytes'],
            facts_jsonl_bytes=base_bytes,
            largest_three_read_bytes=session and session['largest_three_read_bytes'],
            largest_three_over_facts_jsonl=session and session['largest_three_read_bytes'] - base_bytes,
            cost_usd=(summary or {}).get('cost_usd'), cap_usd=(summary or {}).get('cap_usd'),
            max_reserved_usd=proxy.get('max_reserved_usd'), refusals=proxy.get('refusals'),
            refusal_reasons=proxy.get('refusal_reasons')))

    admissions = [r for r in rows if r['kind'] == 'admission']
    aborted = [r for r in rows if r['state'] != 'sealed']
    per_admission = {}
    for n in ADMISSIONS:
        mine = [r for r in admissions if r['admission'] == n]
        runner = _read_json(evidence / f'{LINEAGE}-admission-{n:02d}' / 'run' / 'curator-runner' / 'status.json') or {}
        per_admission[n] = dict(sessions=len(mine), aborted=sum(r['state'] != 'sealed' for r in mine),
                                grooming=any(g['admission'] == n for g in groomings),
                                runner_state=runner.get('state'), runner_stop=runner.get('stop_reason'),
                                runner_backlog=runner.get('backlog'))
    prompt = sum(r['prompt_tokens'] for r in admissions)
    completion = sum(r['completion_tokens'] for r in admissions)
    return dict(
        sessions=len(rows), admissions=len(admissions), groomings=len(groomings), per_admission=per_admission,
        aborted=[dict(id=r['id'], kind=r['kind'], admission=r['admission'], base=r['base'], end=r['end'],
                      failed_status=r['failed_status'], stop=r['stop'], requests=r['requests'],
                      max_requests=r['max_requests'], written=r['written'], published=r['published'],
                      max_prompt_tokens=r['max_prompt_tokens']) for r in aborted],
        lost_submissions=sum(r['written'] - r['published'] for r in rows),
        admission_tokens=dict(prompt=prompt, completion=completion,
                              ratio=round(prompt / completion, 1) if completion else None),
        grooming=groomings)


def label_exposure(evidence: Path) -> dict:
    """How often the delivered `v91` files of the tenth admission name the lineage label, and where."""
    found = {}
    for name, relative in (('actor', 'run/actors/001/knowledge/v91.json'),
                           ('runner', 'run/curator-runner/delivered/v91.json')):
        path = evidence / FINAL / relative
        if not path.exists():
            continue
        value = json.loads(path.read_text())
        count = lambda v: json.dumps(v).count(LINEAGE)  # noqa: E731
        found[name] = dict(path=relative, total=path.read_text().count(LINEAGE),
                           fact_seen=sum(count(f['seen']) for f in value['facts']),
                           article_last_confirmed=sum(count(a['last_confirmed']) for a in value['articles']),
                           coverage=count(value['coverage']), coverage_session=(value['coverage'] or {}).get('session'))
    return found


def recount(evidence: Path) -> dict:
    knowledge = evidence / FINAL / 'knowledge'
    gate = _read_jsonl(knowledge / 'cdda.state' / 'gate.jsonl')
    sessions = knowledge / 'cdda.state' / 'sessions'
    repository = Repository(knowledge / 'cdda')
    return dict(schema='curator-history-recount/1', store=f'{FINAL}/knowledge',
                **store_counts(repository, gate, sessions),
                **session_counts(sessions, evidence, gate, repository), label_exposure=label_exposure(evidence))


def _c(value: object) -> str:
    return '—' if value is None else f'`{value}`'


def markdown(r: dict) -> str:
    f, a, s, fan = r['facts'], r['articles'], r['restatements'], r['fanout']
    out = [f'# Curator history recount (`{r["schema"]}`)', '', f'Store: `{r["store"]}`.', '',
           '| Measure | Count |', '| --- | --- |',
           f'| Tags | {_c(r["versions"]["tags"])} (`{r["versions"]["first"]}` to `{r["versions"]["last"]}`) |',
           f'| Published versions | {_c(r["versions"]["published"])} |',
           f'| Gate verdicts | {_c(r["gate"]["verdicts"])}: ' + ', '.join(f'{k} `{v}`' for k, v in r['gate']['statuses'].items())
           + f'; with diagnostics `{r["gate"]["with_diagnostics"]}`; restored `{r["gate"]["restored"]}` |',
           '| Published operations | ' + ', '.join(f'`{k}` {v}' for k, v in r['operations'].items()) + ' |',
           f'| Facts stored / current / superseded | `{f["stored"]}` / `{f["current"]}` / `{f["superseded"]}` |',
           '| Current facts by scope | ' + ', '.join(f'`{k}` {v}' for k, v in f['scope'].items()) + ' |',
           f'| Types: current facts / ever used / registered at last tag | `{f["types_current"]}` / `{f["types_ever"]}` / '
           f'`{f["types_registered"]}` |',
           f'| Registered types at `{r["series"]["first"]["version"]}` / over versions (min / max) | '
           f'`{r["series"]["first"]["types"]}` / `{r["series"]["types_min"]}` / `{r["series"]["types_max"]}` |',
           f'| Retype events / facts retyped | `{f["retype_events"]}` / `{f["retyped_facts"]}` |',
           f'| Restatements (`supersede_fact`) / facts replaced / merges | `{s["count"]}` / `{s["replaced"]}` / `{s["merges"]}` |',
           '| Restatements by facts replaced (replaced: restatements) | '
           + ', '.join(f'{k}: `{v}`' for k, v in s['by_replaced'].items()) + ' |',
           f'| Restatements reusing every old citation / omitting some | `{s["reused_all"]}` / `{s["omitted_some"]}` '
           f'(`{s["omitted_citations"]}` citations omitted) |',
           f'| Articles stored / current / revisions | `{a["stored"]}` / `{a["current"]}` / `{a["revisions"]}` |',
           f'| Revisions changing at most 3 claims / median changed | `{a["revisions_changing_at_most_3"]}` / '
           f'`{a["changed_median"]}` |',
           f'| Revisions with added plus removed claims at most 3 | `{a["revisions_added_plus_removed_at_most_3"]}` |',
           f'| Revised claims byte-identical | `{a["identical_claims"]}` of `{a["claims"]}` (`{a["identical_share"]}`) |',
           f'| Facts dropped by a revision | `{a["dropped_total"]}`: '
           + ', '.join(f'{k} `{v}`' for k, v in a['dropped_facts'].items()) + ' |',
           *(f'| Unaccounted drop at `{d["version"]}` | `{d["fact"]}` from `{d["revised"]}` to `{d["to"]}`: `{d["kind"]}`'
             + (' by ' + ', '.join(f'`{x}`' for x in d['cited_by']) if d['cited_by'] else '')
             + f'; superseded later in {_c(d["superseded_later_in"])} |'
             for d in a['unaccounted_drops']),
           f'| Current facts cited / uncited | `{fan["cited_current_facts"]}` / `{f["uncited_current"]}` |',
           '| Citing-article fanout (articles: facts) | ' + ', '.join(f'{k}: `{v}`' for k, v in fan['by_articles'].items())
           + f'; max `{fan["max"]}` |',
           f'| Curator sessions / admissions / groomings | `{r["sessions"]}` / `{r["admissions"]}` / `{r["groomings"]}` |',
           f'| Aborted sessions / lost written submissions | `{len(r["aborted"])}` / `{r["lost_submissions"]}` |',
           f'| Admission prompt / completion tokens | `{r["admission_tokens"]["prompt"]}` / '
           f'`{r["admission_tokens"]["completion"]}` (`{r["admission_tokens"]["ratio"]}` to 1) |',
           '', '## Sessions per admission', '',
           '| Admission | Admission sessions | Aborted | Grooming | Runner state / stop | Runner backlog |',
           '| --- | --- | --- | --- | --- | --- |']
    for n, row in r['per_admission'].items():
        out.append(f'| `a{n:02d}` | {_c(row["sessions"])} | {_c(row["aborted"])} | {"yes" if row["grooming"] else "no"} | '
                   f'{_c(row["runner_state"])} / {_c(row["runner_stop"])} | {_c(row["runner_backlog"])} |')
    out += ['', '## Groomings', '',
            '| Admission | Status | Versions | Published | Requests / cap | HTTP stop | Max prompt tokens | read_file bytes '
            '| Three largest reads | Base facts.jsonl bytes | Three largest minus base | Cost / cap USD | Max reserved USD '
            '| Refusals |',
            '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for g in r['grooming']:
        out.append(f'| `a{g["admission"]:02d}` | `{g["status"]}` ({g["end"]}) | {_c(g["versions"])} | {_c(g["published"])} | '
                   f'`{g["requests"]}` / `{g["max_requests"]}` | {_c(g["failed_status"])} | {_c(g["max_prompt_tokens"])} | '
                   f'{_c(g["read_file_bytes"])} | {_c(g["largest_three_read_bytes"])} | {_c(g["facts_jsonl_bytes"])} | '
                   f'{_c(g["largest_three_over_facts_jsonl"])} | `{g["cost_usd"]}` / `{g["cap_usd"]}` | '
                   f'{_c(g["max_reserved_usd"])} | `{g["refusals"]}` ' + ', '.join(g['refusal_reasons'] or []) + ' |')
    out += ['', '## Aborted sessions', '',
            '| Session | Kind | Admission | Base | End | HTTP | Runner stop | Requests / cap | Written / published | '
            'Max prompt tokens |', '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for x in r['aborted']:
        out.append(f'| `{x["id"]}` | `{x["kind"]}` | `a{x["admission"]:02d}` | `{x["base"]}` | `{x["end"]}` | '
                   f'{_c(x["failed_status"])} | {_c(x["stop"])} | `{x["requests"]}` / `{x["max_requests"]}` | '
                   f'`{x["written"]}` / `{x["published"]}` | {_c(x["max_prompt_tokens"])} |')
    out += ['', '## Lineage label in the tenth admission\'s delivered `v91`', '',
            '| File | Total | In fact `seen` | In article `last_confirmed` | In `coverage` | `coverage.session` |',
            '| --- | --- | --- | --- | --- | --- |']
    for name, x in r['label_exposure'].items():
        out.append(f'| `{x["path"]}` | `{x["total"]}` | `{x["fact_seen"]}` | `{x["article_last_confirmed"]}` | `{x["coverage"]}` | '
                   f'{_c(x["coverage_session"])} |')
    return '\n'.join(out) + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--evidence', type=Path, help='the sealed evidence store (default: the main checkout\'s)')
    output = parser.add_mutually_exclusive_group()
    output.add_argument('--json', action='store_true')
    output.add_argument('--markdown', action='store_true')
    args = parser.parse_args(argv)
    if args.evidence is None:
        from tools.evidence import default_store
        args.evidence = default_store()
    result = recount(args.evidence)
    print(json.dumps(result, indent=2) if args.json else markdown(result), end='\n' if args.json else '')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
