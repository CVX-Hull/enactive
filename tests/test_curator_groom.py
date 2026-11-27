"""Boundary grooming close-out, `curator-boundary-grooming/2`: the stale-citation rule and its failure order.

Portable: real Git knowledge repositories published by the real gate; the grooming session itself is a stand-in.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.curator.gate import COVERAGE, gate
from harness.curator.knowledge import Repository
from tests.curator_trace import SESSION_ID, make_long_session
from tools.curator_host import groom, shadow

FRAME = SESSION_ID + '-1'
RUN = 'live-admission'
FACT = dict(schema='curator-fact/6', record='fact', id='control', statement_kind='observation',
            tags=['control'], text='An observed control.', scope={}, links=[], citations=[FRAME])
ARTICLE = dict(schema='curator-fact/6', record='article', slug='guide', title='Controls', lead='How to operate the screens.',
               body=[dict(text='A control exists.', facts=['control'])], links=[], tags=[])
ADMISSION = [dict(op='add_fact', fact=FACT), dict(op='add_article', article=ARTICLE)]
RESTATE = [dict(op='supersede_fact', ids=['control'], reason_kind='restated',
                fact={key: value for key, value in FACT.items() if key != 'scope'} | dict(id='control-restated', citations=[]))]
REMAP = [{'op': 'remap_citations', 'from': ['control'], 'to': 'control-restated', 'in': ['guide']}]
CONTRADICT = [dict(op='add_fact', fact=FACT | dict(id='control-absent', text='The control is absent.',
                                                   links=[dict(rel='contradicts', target='control')]))]


def publish(tmp_path: Path, repo: Repository, base: str, changes: list, kind: str = 'admission') -> dict:
    directory = tmp_path/'submissions'/f'{kind}-{base}'
    directory.mkdir(parents=True)
    (directory/'submission.json').write_text(json.dumps(dict(
        schema='curator-submission/3', base_version=base, summary='test', changes=changes)))
    frames = {FRAME: dict(session=RUN, actor='001', step=1, order=[1, '001', 1])} if kind == 'admission' else {}
    return gate(repo, directory, session_id=f'{kind}-{base}', window_frames=frames, session_kind=kind,
                coverage=dict(schema=COVERAGE, session=RUN, actor='001', last_step=1))


@pytest.fixture
def boundary(tmp_path, monkeypatch):
    """A sealed admission run, its runner configuration and an empty knowledge repository at v0."""
    runtime = tmp_path/'runtime'
    run = make_long_session(tmp_path/'runs', RUN, steps=1, actors=('001',))
    config = tmp_path/'runner.json'
    config.write_text(json.dumps(dict(schema='curator-runner-config/1', knowledge_root=str(runtime/'knowledge'/'live'),
                                      arm='terra', cap_usd='1', upstream='http://127.0.0.1:1')))
    repo = Repository(runtime/'knowledge'/'live', shadow.GAME)
    repo.ensure()
    out = runtime/'grooming'
    monkeypatch.setattr(shadow, 'host_tools', lambda: dict(test_host=True))
    monkeypatch.setattr(shadow, 'route_key', lambda upstream, root: shadow.LOOPBACK_KEY)
    args = ['--run', str(run), '--config', str(config), '--runtime-root', str(runtime), '--out', str(out), '--cap-usd', '0.25']
    return repo, out, args


def sealed_session(published_after: str | None, **changes) -> dict:
    return dict(dict(run_state='completed', session_state='sealed', verdicts=[], published_after=published_after,
                     proxy=dict(settled=True, revoked=False, breaches=0), sandbox=dict(survivors=[], stopped=None),
                     cost_usd='0.01'), **changes)


def stand_in(monkeypatch, behave):
    """Replace the grooming session with `behave(repo)`, which may publish and returns the session summary."""
    def run_one(**kwargs):
        assert kwargs['session_kind'] == 'grooming'
        return behave(kwargs['repo'])
    monkeypatch.setattr(shadow, 'run_one', run_one)


def result(out: Path) -> dict:
    return json.loads((out/groom.SUMMARY).read_text())


def test_stale_records_counts_current_records_with_stale_citations_at_a_version(tmp_path):
    repo = Repository(tmp_path/'knowledge', 'game')
    repo.ensure()
    assert publish(tmp_path, repo, 'v0', ADMISSION)['status'] == 'published'
    assert publish(tmp_path, repo, 'v1', RESTATE)['status'] == 'published'
    assert [groom.stale_records(repo, version) for version in ('v0', 'v1', 'v2')] == [0, 0, 1]
    assert publish(tmp_path, repo, 'v2', REMAP, kind='grooming')['status'] == 'published'
    # The superseded revision guide@v1 keeps its stored stale list, but only current records count.
    assert any(row['stale_citations'] for row in repo.records('v3'))
    assert groom.stale_records(repo, 'v3') == 0
    assert groom.stale_records(repo, None) is None
    assert groom.stale_records(repo, 'v9') is None
    assert groom.stale_records(Repository(tmp_path/'missing', 'game'), 'v0') is None


GOOD = dict(run_state='completed', proxy=dict(settled=True, revoked=False, breaches=0), session_state='sealed',
            sandbox=dict(survivors=[], stopped=None), stale_records=0)


@pytest.mark.parametrize('changes, reason', [
    ({}, None),
    (dict(stale_records=2), 'stale-citations-remain'),
    (dict(stale_records=None), 'stale-citations-unreadable'),
    # Every earlier failure is reported before the stale-citation rule.
    (dict(run_state='error: RuntimeError: boom', stale_records=2), 'error: RuntimeError: boom'),
    (dict(unresolved=True, stale_records=2), 'unresolved-result'),
    (dict(proxy=dict(settled=False, revoked=False, breaches=0), stale_records=2), 'proxy-unsettled'),
    (dict(proxy=dict(settled=True, revoked=False, breaches=1), stale_records=2), 'proxy-revoked-or-breached'),
    (dict(stopped_by_cap=True, stale_records=2), 'cap-reached'),
    (dict(session_state='aborted', stale_records=2), 'session-not-sealed'),
    (dict(sandbox=dict(survivors=[], stopped='provider-error'), stale_records=2), 'provider-error'),
    (dict(sandbox=dict(survivors=[], stopped='provider-error'), stale_records=0), 'provider-error'),
    (dict(sandbox=dict(survivors=[7], stopped=None), stale_records=None), 'cleanup-unconfirmed'),
])
def test_failure_reason_checks_stale_citations_after_every_session_failure(changes, reason):
    assert groom.failure_reason(GOOD | changes) == reason


def test_a_missing_stale_count_is_unreadable():
    assert groom.failure_reason({key: value for key, value in GOOD.items() if key != 'stale_records'}) == 'stale-citations-unreadable'


@pytest.mark.parametrize('session', ['no-submission', 'rejected'])
def test_grooming_fails_while_the_base_keeps_stale_citations(tmp_path, boundary, monkeypatch, capsys, session):
    repo, out, args = boundary
    publish(tmp_path, repo, 'v0', ADMISSION)
    publish(tmp_path, repo, 'v1', RESTATE)
    verdicts = [] if session == 'no-submission' else [dict(operation='submission', status='rejected', diagnostics=['test'])]
    stand_in(monkeypatch, lambda _repo: sealed_session('v2', verdicts=verdicts))
    assert groom.main(args) == 1
    summary = result(out)
    assert summary['schema'] == 'curator-boundary-grooming/2'
    assert (summary['status'], summary['reason'], summary['stale_records']) == ('failed', 'stale-citations-remain', 1)
    assert summary['published_before'] == summary['published_after'] == 'v2' and summary['verdicts'] == verdicts
    assert 'stale-citations-remain' in capsys.readouterr().err


def test_a_published_repair_that_clears_every_stale_citation_completes(tmp_path, boundary, monkeypatch):
    repo, out, args = boundary
    publish(tmp_path, repo, 'v0', ADMISSION)
    publish(tmp_path, repo, 'v1', RESTATE)

    def repair(session_repo):
        verdict = publish(tmp_path, session_repo, 'v2', REMAP, kind='grooming')
        return sealed_session(session_repo.published(), verdicts=[verdict])

    stand_in(monkeypatch, repair)
    assert groom.main(args) == 0
    summary = result(out)
    assert (summary['status'], summary['reason'], summary['stale_records']) == ('completed', None, 0)
    assert (summary['published_before'], summary['published_after']) == ('v2', 'v3')


def test_a_provider_error_is_reported_before_remaining_stale_citations(tmp_path, boundary, monkeypatch):
    repo, out, args = boundary
    publish(tmp_path, repo, 'v0', ADMISSION)
    publish(tmp_path, repo, 'v1', RESTATE)
    stand_in(monkeypatch, lambda _repo: sealed_session('v2', sandbox=dict(survivors=[], stopped='provider-error')))
    assert groom.main(args) == 1
    summary = result(out)
    assert (summary['status'], summary['reason'], summary['stale_records']) == ('failed', 'provider-error', 1)


def test_advisory_review_flags_without_stale_citations_complete(tmp_path, boundary, monkeypatch):
    repo, out, args = boundary
    publish(tmp_path, repo, 'v0', ADMISSION)
    publish(tmp_path, repo, 'v1', CONTRADICT)
    rows = {row['id']: row for row in repo.records()}
    assert rows['guide@v1']['lifecycle_state'] == 'contested' and rows['guide@v1']['needs_review'] is True
    assert not any(row['stale_citations'] for row in rows.values())
    stand_in(monkeypatch, lambda _repo: sealed_session('v2'))
    assert groom.main(args) == 0
    summary = result(out)
    assert (summary['status'], summary['reason'], summary['stale_records']) == ('completed', None, 0)


def test_an_unreadable_published_after_fails_as_unreadable(tmp_path, boundary, monkeypatch):
    repo, out, args = boundary
    publish(tmp_path, repo, 'v0', ADMISSION)
    stand_in(monkeypatch, lambda _repo: sealed_session('v9'))
    assert groom.main(args) == 1
    summary = result(out)
    assert (summary['status'], summary['reason'], summary['stale_records']) == ('failed', 'stale-citations-unreadable', None)


def test_a_session_error_without_a_readable_version_reports_the_error_first(tmp_path, boundary, monkeypatch):
    repo, out, args = boundary
    publish(tmp_path, repo, 'v0', ADMISSION)
    stand_in(monkeypatch, lambda _repo: dict(run_state='error: RuntimeError: proxy closed early', published_after=None))
    assert groom.main(args) == 1
    summary = result(out)
    assert (summary['status'], summary['reason'], summary['stale_records']) == (
        'failed', 'error: RuntimeError: proxy closed early', None)


def test_a_repository_without_a_published_admission_is_skipped_with_its_stale_count(boundary, monkeypatch, capsys):
    repo, out, args = boundary
    stand_in(monkeypatch, lambda _repo: pytest.fail('a skipped grooming starts no session'))
    assert groom.main(args) == 0
    summary = result(out)
    assert summary == dict(schema='curator-boundary-grooming/2', status='skipped', reason='no-published-admission',
                           run=RUN, knowledge_root=str(repo.path.parent), published_before='v0', published_after='v0',
                           stale_records=0, cost_usd='0', summary=None)
    assert 'skipped' in capsys.readouterr().out
