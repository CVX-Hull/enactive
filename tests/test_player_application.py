"""Current player journal composition over an explicit receiver double."""
from pathlib import Path
import json
import uuid
import pytest

from harness.application import Application
from harness.player.journal import Journal
from harness.player.contracts import PlayerError
from test_computer_runtime import make_runtime, key


def test_hint_identity_sources_collection_and_conflicts(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path)
    journal = Journal(tmp_path/'player.sqlite3')
    app = Application(runtime, journal, tmp_path/'contexts', knowledge=Path(__file__).with_name('fixtures')/'empty-delivered-knowledge.json')
    try:
        frame, _ = runtime.observe(actor['actor_id'])
        source_id = frame['source']['source_id']
        request_id = uuid.uuid4().hex
        args = dict(text='A fallible hint', source_ids=[source_id], intent='record observation', cites=['citation'])
        first, _ = app.call(actor['token'], 'player_hint', args, request_id)
        assert app.call(actor['token'], 'player_hint', args, request_id)[0] == first
        assert journal.read_source(source_id)[1] == channel.png
        assert journal.hints() == [first] and first['id'] == request_id
        result, _ = app.call(actor['token'], 'player_result', dict(operation_id=request_id, intent='collect'), uuid.uuid4().hex)
        assert result == dict(schema='player-service-result/2', operation_id=request_id, actor_id=actor['actor_id'], kind='player_hint', status='completed', value=first, grants_authority=False)
        with pytest.raises(PlayerError, match='conflicts'):
            app.call(actor['token'], 'player_hint', dict(args, text='different'), request_id)
        assert app.submission_status(actor['actor_id'], request_id) == 'uncertain'
    finally:
        runtime.close(); journal.close()


def test_calls_do_not_imply_submission_and_native_retries_do_not_dispatch(tmp_path):
    runtime, channel, actor = make_runtime(tmp_path)
    journal = Journal(tmp_path/'player.sqlite3')
    app = Application(runtime, journal, tmp_path/'contexts', knowledge=Path(__file__).with_name('fixtures')/'empty-delivered-knowledge.json')
    try:
        missing = uuid.uuid4().hex
        with pytest.raises(ValueError):
            app.call(actor['token'], 'player_hint', dict(text='x', source_ids=['missing'], intent='remember'), missing)
        assert app.submission_status(actor['actor_id'], missing) == 'none'
        request_id = uuid.uuid4().hex
        args = dict(actions=[key()], intent='move')
        first, _ = app.call(actor['token'], 'computer_input', args, request_id)
        count = len(channel.calls)
        assert app.call(actor['token'], 'computer_input', args, request_id)[0] == first
        assert len(channel.calls) == count
        with pytest.raises(PlayerError, match='conflicts'):
            app.call(actor['token'], 'player_hint', dict(text='x', intent='remember'), request_id)
    finally:
        runtime.close(); journal.close()


def test_handoff_packet_is_summary_hint_and_final_actor_is_refused(tmp_path):
    runtime, _, actor = make_runtime(tmp_path)
    journal = Journal(tmp_path/'player.sqlite3')
    app = Application(runtime, journal, tmp_path/'contexts', knowledge=Path(__file__).with_name('fixtures')/'empty-delivered-knowledge.json')
    try:
        app.final_actor = actor['actor_id']
        with pytest.raises(PlayerError, match='final actor'):
            app.call(actor['token'], 'player_handoff', dict(summary='unfinished', intent='handoff'), uuid.uuid4().hex)
        assert list((tmp_path/'contexts').iterdir()) == []
        app.final_actor = None
        result, _ = app.call(actor['token'], 'player_handoff', dict(summary='unfinished', intent='handoff'), uuid.uuid4().hex)
        packet = json.loads((tmp_path/'contexts'/f"{result['handoff']['context_id']}.json").read_text())
        assert packet['schema'] == 'player-handoff-context/2' and packet['summary_is_hint'] is True
        assert packet['summary'] == 'unfinished' and 'knowledge' not in packet
    finally:
        runtime.close(); journal.close()


@pytest.mark.parametrize('args', [{}, {'intent': ''}, {'intent': 'x\ny'}, {'intent': 'x'*513}, {'intent': 'x', 'cites': ['a','a']}, {'intent': 'x', 'cites': ['a']*17}])
def test_common_metadata_is_required_and_validated(tmp_path, args):
    runtime, channel, actor = make_runtime(tmp_path)
    journal = Journal(tmp_path/'player.sqlite3')
    app = Application(runtime, journal, tmp_path/'contexts', knowledge=Path(__file__).with_name('fixtures')/'empty-delivered-knowledge.json')
    try:
        with pytest.raises(PlayerError):
            app.call(actor['token'], 'computer_observe', args, uuid.uuid4().hex)
        assert channel.calls == [] and journal.calls() == []
    finally:
        runtime.close(); journal.close()


def test_advertised_schemas_have_stable_required_metadata():
    from jsonschema import Draft202012Validator
    from harness.player_tools import tool_specs

    for _ in range(2):
        for _, schema in tool_specs().values():
            Draft202012Validator.check_schema(schema)
            assert schema['required'].count('intent') == 1
            assert 'cites' in schema['properties']
