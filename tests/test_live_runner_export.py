"""Live export uses the verified target and reports provider failures without stopping curation."""
from decimal import Decimal
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

import pytest

from harness.player.knowledge import Knowledge
from harness.trace.projection import _arguments, _session_labels
from tests.curator_trace import SESSION_ID, record_package
from tests.synthetic_knowledge_repo import build_two_world_two_lineage_repo
from tools.curator_host import live_runner


@pytest.mark.parametrize('revoked', [False, True])
def test_session_forwards_provider_error_alongside_terminal_proxy_stop(tmp_path, monkeypatch, revoked):
    sessions = live_runner.Sessions.__new__(live_runner.Sessions)
    sessions.out, sessions.repo, sessions.key = tmp_path, None, 'offline-fixture'
    sessions.tools = object()
    sessions.config_path = sessions.config_dir = sessions.model_config = None
    sessions.prices = live_runner.shadow.load_prices(live_runner.shadow.DEFAULT_PRICES)
    sessions.spent = Decimal(0)
    sessions.config = dict(cap=Decimal(1), session_cap=None, arm='terra', upstream='fixture',
                           host=dict(wall_seconds=1, max_output_tokens=100))
    summary = dict(proxy=dict(revoked=revoked), sandbox=dict(stopped='provider-error', survivors=[]),
                   stopped_by_cap=False, session_id='fixture', session_state='failed', run_state='completed',
                   cost_usd='0')
    monkeypatch.setattr(live_runner.shadow, 'run_one', lambda **kwargs: summary)
    monkeypatch.setattr(live_runner, 'counted_spend', lambda path: Decimal(0))
    outcome = sessions(SimpleNamespace(directory=Path('fixture')), None, 'window')
    assert outcome.provider_error is True
    assert outcome.stop == ('proxy-revoked' if revoked else None)


def test_live_delivery_uses_verified_context_and_blinds_positions(tmp_path):
    fixture = build_two_world_two_lineage_repo(tmp_path/'repository')
    world = fixture['worlds'][0]
    lineage = fixture['lineages'][0]
    context = {'ruleset': 'standard', 'difficulty': 'hard'}
    run = tmp_path/'admission'
    run.mkdir()
    labels = dict(world=world, lineage=lineage, admission=1)
    record_package(run, labels=labels, context=context, live=True)
    assert _session_labels(run, SESSION_ID) == dict(labels, context=context, label_check=None, label_error=None)
    enabled, selected_world, selected_lineage, selected_context, session = live_runner.delivery_target(run)
    assert (enabled, selected_world, selected_lineage, selected_context, session) == (
        True, world, lineage, context, SESSION_ID)

    version = fixture['version']
    runner = SimpleNamespace(lock=Lock(), publications=lambda: ([dict(version=version)], [], None),
                             versions={version: dict(restored_from=None)}, last=None,
                             coverage=lambda: dict(covered_prefix=dict(end=None)))
    out = tmp_path/'runner'
    out.mkdir()
    live_runner.Delivery(out, fixture['repo_path'], selected_world, session=session,
                         lineage=selected_lineage, context=selected_context)(runner)
    path = out/'delivered'/f'{version}.json'
    delivered = Knowledge(path)
    assert delivered.read('hard-only-rule', by='id')['resolution'] == 'current'
    assert delivered.read('alpha-crate', by='id')['records'][0]['branch_relation'] == 'same'
    for label in (*fixture['worlds'], *fixture['lineages'], *fixture['session_names'].values()):
        assert label.encode() not in path.read_bytes()
    assert delivered.value['coverage']['session'].startswith('s')

    with (run/'manifest.json').open('ab') as stream:
        stream.write(b'\n')
    with pytest.raises(ValueError, match='SHA-256 differs'):
        live_runner.delivery_target(run)


@pytest.mark.parametrize('context', [{'game': 'reserved'}, {'world': 'reserved'}, {'Upper': 'bad'},
                                    {'axis': 'é'}, {'axis': ''}, {'axis': 'x' * 65},
                                    {f'axis_{i}': 'x' for i in range(9)}])
def test_invalid_target_context_is_refused_by_live_and_trace_readers(tmp_path, context):
    record_package(tmp_path, labels=dict(world=None, lineage=None, admission=None), context=context, live=True)
    with pytest.raises(ValueError, match='invalid context'):
        live_runner.delivery_target(tmp_path)
    projected = _session_labels(tmp_path, SESSION_ID)
    assert projected['context'] == {} and projected['label_check'] == 'manifest-schema'


def test_trace_keeps_the_read_identifier_mode():
    assert _arguments('player_knowledge_read', dict(id_or_title='fact', by='id', operator='private')) == dict(
        id_or_title='fact', by='id')
