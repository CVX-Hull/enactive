"""Current MCP invocation over real SDK staging; synthetic evidence, no native play."""
from copy import deepcopy
import asyncio
import json
from pathlib import Path
import tempfile
import threading
import sys
import unittest
from unittest.mock import patch

from mcp import Client

from harness.mission_client import MissionClientError
from harness.player_mcp import make_server
from harness.player_tools import PlayerTools, tool_specs
from tests.test_player_claims import StagingClient
from tests.test_mission_request_producer import bundle, snapshot
from tests.test_reflection_tools import AdvisoryClient, SCOPE, submit_args


class InvocationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / '.runtime').mkdir()
        self.backend = StagingClient(self.root)
        self.player = PlayerTools(self.backend)
        self.source = bundle(7)
        scope = dict(mission_id='mission-test', session=self.source['reference']['session'], coordinate_epoch=4)
        self.selected = dict(snapshot_id='chosen', mission=snapshot(coordinate_scope=scope),
            source=self.source, native={})
        self.player.snapshots['chosen'] = deepcopy(self.selected)

    def claim(self):
        return dict(snapshot_id='chosen', intent=dict(entry_type='claim', entry=dict(
            key=dict(property='supply', subject='water', unit='charges', coverage_id='page-1'),
            value=dict(quantity=18, state=None), text='Visible count', coverage='menu page',
            status='last_seen', grounding=dict(kind='source', source_id=None, coordinate_epoch=None),
            supports=[dict(primary=True, sources=[], claims=[])])))

    def run_client(self, exercise, player=None):
        async def run():
            async with Client(make_server(player or self.player)) as client:
                await exercise(client)
        asyncio.run(run())

    @staticmethod
    def value(result):
        return json.loads(result.content[0].text)

    def test_model_write_assigns_once_and_preserves_exact_intent_binding_and_stage(self):
        async def exercise(client):
            reply = await client.call_tool('enactive_remember', self.claim())
            self.assertFalse(reply.is_error)
            result = self.value(reply)
            identity = result['operation_id']
            self.assertTrue(identity.startswith('op-'))
            self.assertEqual(len(self.backend.writes), 1)
            request = self.backend.writes[0]
            self.assertEqual(self.backend.staged_request('mission-test', identity), request)
            self.assertEqual(request['request_id'], identity)
            self.assertEqual(request['epoch'], self.selected['mission']['epoch'])
            self.assertEqual(request['entry']['scope'], self.selected['mission']['coordinate_scope'])
            self.assertEqual(request['entry']['sources'], [self.source['reference']['observation_id']])
            self.assertEqual(request['entry']['value'], self.claim()['intent']['entry']['value'])
            self.assertEqual(len(reply.content), 1)
            self.assertIsNone(reply.structured_content)
        self.run_client(exercise)

    def test_removed_model_fields_refuse_before_staging_and_unchanged_sdk_remains_explicit(self):
        async def exercise(client):
            for obsolete in (dict(request_id='old'), dict(wait_seconds=0)):
                result = await client.call_tool('enactive_remember', self.claim() | obsolete)
                self.assertTrue(result.is_error)
            self.assertEqual(self.backend.writes, [])
            self.assertFalse((self.root / '.runtime/mission-requests').exists())
        self.run_client(exercise)
        result, _ = self.player.call('enactive_remember', self.claim() | dict(request_id='sdk-owned', wait_seconds=0))
        self.assertEqual(result['operation_id'], 'sdk-owned')

    def test_model_navigation_derives_selected_scope_and_rejects_old_nested_copy(self):
        self.player.snapshots['chosen']['mission']['phase'] = 'active'
        args = dict(snapshot_id='chosen', scope='new_root', source_id=None, supporting_source_ids=[],
            limits=dict(primitives=1, wall_seconds=7, game_seconds=10),
            intent=dict(skill_kind='navigate', goal=dict(target=[1, 0, 0]), work_id=None, perception=None, procedure=None))
        before = deepcopy(args)
        async def exercise(client):
            result = await client.call_tool('enactive_skill', args)
            self.assertFalse(result.is_error)
            request = self.backend.writes[-1]
            self.assertEqual(request['goal'], dict(scope=self.selected['mission']['coordinate_scope'], target=[1, 0, 0]))
            self.assertEqual(request['expected_revision'], self.source['reference']['revision'])
            self.assertEqual(request['limits'], args['limits'])
            old = deepcopy(args)
            old['intent']['goal']['scope'] = self.selected['mission']['coordinate_scope']
            self.assertTrue((await client.call_tool('enactive_skill', old)).is_error)
            self.assertEqual(len(self.backend.writes), 1)
            self.player.snapshots['chosen']['mission']['coordinate_scope'] = None
            events = deepcopy(self.backend.events)
            self.assertTrue((await client.call_tool('enactive_skill', args)).is_error)
            self.assertEqual(self.backend.events, events)
            self.assertEqual(len(self.backend.writes), 1)
        self.run_client(exercise)
        self.assertEqual(args, before)

    def test_model_activity_derives_selected_owner_and_rejects_old_nested_copy(self):
        source = bundle(kind='interrupt_confirmation')
        source['observation']['boundary'].update(interrupt_request_id='owned-interrupt', recovery_operations=['answer_interrupt'])
        phase = dict(origin_request_id='activity-root', checkpoint_id=source['reference']['observation_id'],
            stage='interrupt_confirmation', answered=False, interrupt_request_id='owned-interrupt')
        self.player.snapshots['chosen'] = dict(snapshot_id='chosen',
            mission=snapshot(phase='paused', activity_phase=phase), source=source, native={})
        args = dict(snapshot_id='chosen', scope='activity', source_id=None, supporting_source_ids=[],
            limits=dict(primitives=1, wall_seconds=7, game_seconds=60), intent=dict(skill_kind='activity',
                goal=dict(operation='rest', target='Rest', game_seconds=60, interrupt_allowed=True,
                    step='answer_interrupt', answer='NO'), work_id=None, perception=None, procedure=None))
        async def exercise(client):
            reply = await client.call_tool('enactive_skill', args)
            self.assertFalse(reply.is_error, reply)
            request = self.backend.writes[-1]
            self.assertEqual(request['goal'], {**args['intent']['goal'], 'interrupt_request_id': 'owned-interrupt'})
            self.assertEqual(request['phase_id'], 'activity-root')
            old = deepcopy(args)
            old['intent']['goal']['interrupt_request_id'] = None
            self.assertTrue((await client.call_tool('enactive_skill', old)).is_error)
            self.assertEqual(len(self.backend.writes), 1)
            self.player.snapshots['chosen']['mission']['activity_phase']['answered'] = True
            events = deepcopy(self.backend.events)
            self.assertTrue((await client.call_tool('enactive_skill', args)).is_error)
            self.assertEqual(self.backend.events, events)
        self.run_client(exercise)

    def test_lost_submission_returns_original_id_and_fresh_adapter_only_collects_it(self):
        original_json = self.backend._json
        def lose_post(path, *, data=None, **options):
            request = json.loads(data)
            if request['kind'] != 'result':
                self.backend.writes.append(request)
                raise MissionClientError('Submission response lost')
            return original_json(path, data=data, **options)
        self.backend._json = lose_post
        original = {}
        async def submit(client):
            result = self.value(await client.call_tool('enactive_remember', self.claim()))
            self.assertFalse(result['settled'])
            self.assertEqual(result['transport'], 'uncertain')
            original['id'] = result['operation_id']
        self.run_client(submit)
        self.assertEqual(len(self.backend.writes), 1)
        self.assertIsNotNone(self.backend.staged_request('mission-test', original['id']))
        fresh = StagingClient(self.root)
        def collect(path, *, data=None, **options):
            request = json.loads(data)
            self.assertEqual(request['kind'], 'result')
            self.assertEqual(request['operation_id'], original['id'])
            retained = fresh.staged_request(request['mission_id'], request['operation_id'])
            return dict(status='accepted', operation=dict(request=retained, state='unknown',
                result=dict(reason='Original retained unknown, not replayed')))
        def unavailable_transport(*args, **kwargs):
            raise MissionClientError('Collection unavailable')
        fresh._json = unavailable_transport
        async def unavailable(client):
            result = self.value(await client.call_tool('enactive_result', dict(
                mission_id='mission-test', operation_id=original['id'])))
            self.assertFalse(result['settled'])
            self.assertEqual(result['operation_id'], original['id'])
            self.assertEqual(result['transport'], 'uncertain')
        self.run_client(unavailable, PlayerTools(fresh))
        fresh._json = collect
        async def read(client):
            reply = await client.call_tool('enactive_result', dict(mission_id='mission-test', operation_id=original['id']))
            result = self.value(reply)
            self.assertFalse(reply.is_error)
            self.assertEqual(result['response']['operation']['state'], 'unknown')
            self.assertEqual(result['operation_id'], original['id'])
        self.run_client(read, PlayerTools(fresh))
        self.assertEqual(fresh.writes, [])
        self.assertEqual(len(self.backend.writes), 1)

    def test_cancelled_caller_keeps_stage_and_does_not_schedule_replacement(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def delayed_post(path, *, data=None, **options):
            request = json.loads(data)
            self.assertNotEqual(request['kind'], 'result')
            self.backend.writes.append(request)
            entered.set()
            if not release.wait(2):
                raise AssertionError('Cancelled test did not release original submission')
            return dict(status='accepted', operation=dict(request=request, state='completed', result=dict(status='ok')))
        self.backend._json = delayed_post
        async def exercise(client):
            task = asyncio.create_task(client.call_tool('enactive_remember', self.claim()))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 1))
                task.cancel()
            finally:
                release.set()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.run_client(exercise)
        self.assertEqual(len(self.backend.writes), 1)
        original = self.backend.writes[0]
        self.assertEqual(self.backend.staged_request('mission-test', original['request_id']), original)

    def test_dispatch_and_presentation_errors_keep_original_collection_scope(self):
        for failure in ('stage', 'presentation'):
            with self.subTest(failure=failure):
                if failure == 'stage':
                    target = patch.object(self.backend, '_stage', side_effect=MissionClientError('Stage failed'))
                else:
                    target = patch('harness.player_mcp.decision_view', side_effect=ValueError('Presentation failed'))
                async def exercise(client):
                    reply = await client.call_tool('enactive_remember', self.claim())
                    self.assertTrue(reply.is_error)
                    result = self.value(reply)
                    collection = result['original_collection']
                    self.assertEqual(collection['tool'], 'enactive_result')
                    self.assertEqual(collection['arguments']['mission_id'], 'mission-test')
                    self.assertTrue(collection['arguments']['operation_id'].startswith('op-'))
                    if failure == 'presentation':
                        self.assertEqual(collection['arguments']['operation_id'], self.backend.writes[-1]['request_id'])
                with target:
                    self.run_client(exercise)
        self.assertEqual(len(self.backend.writes), 1)

    def test_malformed_post_stage_operation_keeps_identity_through_unexpected_type_error(self):
        def malformed_reply(path, *, data=None, **options):
            request = json.loads(data)
            self.backend.writes.append(request)
            return dict(status='accepted', operation=[])
        self.backend._json = malformed_reply
        async def exercise(client):
            reply = await client.call_tool('enactive_remember', self.claim())
            self.assertTrue(reply.is_error)
            result = self.value(reply)
            identity = result['original_collection']['arguments']['operation_id']
            self.assertEqual(result['original_collection']['arguments']['mission_id'], 'mission-test')
            self.assertEqual(len(self.backend.writes), 1)
            self.assertEqual(self.backend.staged_request('mission-test', identity), self.backend.writes[0])
        self.run_client(exercise)

    def test_frozen_scope_and_execution_limits_are_not_chosen_or_refreshed(self):
        specs = {s.name: s for s in tool_specs()}
        args = dict(snapshot_id='chosen', scope='new_root', source_id=None, supporting_source_ids=[],
            limits=dict(primitives=1, wall_seconds=7, game_seconds=10),
            intent=dict(skill_kind='direct', goal=dict(input=dict(type='key', key='ESC', modifiers=[]),
                intent='Dismiss visible menu', expected='Menu closes', interrupt_allowed=False),
                work_id=None, procedure=None, perception=None))
        before = deepcopy((args, self.player.snapshots))
        with patch.object(self.backend, 'status', side_effect=AssertionError('No implicit refresh')):
            arguments, collection = self.player.model_arguments('enactive_skill', args)
        self.assertEqual(arguments['limits'], args['limits'])
        self.assertEqual(arguments['snapshot_id'], args['snapshot_id'])
        self.assertIsNone(arguments['source_id'])
        self.assertEqual(arguments['wait_seconds'], 15)
        self.assertEqual((args, self.player.snapshots), before)
        self.assertEqual(collection['arguments']['operation_id'], arguments['request_id'])
        for spec in specs.values():
            self.assertNotIn('request_id', spec.schema['properties'])
            self.assertNotIn('wait_seconds', spec.schema['properties'])

    def test_reflection_wait_and_deterministic_claim_survive_repeated_next(self):
        backend = AdvisoryClient()
        player = PlayerTools(backend)
        data, collection = player.model_arguments('enactive_reflect_next', SCOPE)
        self.assertEqual(data['wait_seconds'], 40)
        self.assertIsNone(collection)
        first, _ = player.call('enactive_reflect_next', data)
        second, _ = player.call('enactive_reflect_next', data)
        self.assertEqual(first['claim']['command_id'], second['claim']['command_id'])
        args = {k: v for k, v in submit_args().items() if k not in ('request_id', 'wait_seconds')}
        prepared, collection = player.model_arguments('enactive_reflect_submit', args)
        self.assertEqual(prepared['wait_seconds'], 15)
        self.assertEqual(collection, dict(tool='enactive_reflect_result', arguments=dict(
            **SCOPE, command_id=prepared['request_id'])))

    def test_actual_stdio_generated_uncertainty_and_error_collect_after_restart(self):
        from mcp.client.stdio import StdioServerParameters
        parameters = StdioServerParameters(command=sys.executable,
            args=['-m', 'tests.test_player_invocations', '--stdio-fixture', str(self.root)],
            cwd=str(Path(__file__).resolve().parents[1]))
        identities = []
        async def exercise():
            async with Client(parameters) as client:
                uncertain = await client.call_tool('enactive_remember', self.claim())
                self.assertFalse(uncertain.is_error)
                result = self.value(uncertain)
                self.assertEqual(result['transport'], 'uncertain')
                self.assertFalse(result['settled'])
                identities.append(result['operation_id'])
                draft = self.claim()
                draft['intent']['entry']['text'] = 'Malformed response fixture'
                failed = await client.call_tool('enactive_remember', draft)
                self.assertTrue(failed.is_error)
                collection = self.value(failed)['original_collection']
                self.assertEqual(collection['tool'], 'enactive_result')
                self.assertEqual(collection['arguments']['mission_id'], 'mission-test')
                identities.append(collection['arguments']['operation_id'])
                self.assertNotEqual(*identities)
                collected = await client.call_tool(collection['tool'], collection['arguments'])
                self.assertFalse(collected.is_error)
                self.assertEqual(self.value(collected)['operation_id'], identities[-1])
                self.assertEqual(self.value(collected)['response']['operation']['state'], 'unknown')
            # A new process receives only retained operation IDs, with empty
            # producer caches. Neither collection can stage another write.
            restarted = StdioServerParameters(command=sys.executable,
                args=[*parameters.args, '--recover-only'], cwd=parameters.cwd)
            async with Client(restarted) as client:
                for identity in identities:
                    reply = await client.call_tool('enactive_result', dict(
                        mission_id='mission-test', operation_id=identity))
                    self.assertFalse(reply.is_error)
                    result = self.value(reply)
                    self.assertEqual(result['operation_id'], identity)
                    self.assertEqual(result['response']['operation']['state'], 'unknown')
        asyncio.run(exercise())
        stages = list((self.root / '.runtime/mission-requests').glob('*.json'))
        self.assertEqual(len(stages), 2)
        self.assertEqual({json.loads(p.read_bytes())['request_id'] for p in stages}, set(identities))


class InterruptedClient(StagingClient):
    """Actual SDK stage/submit/collect, synthetic transport faults only."""
    def _json(self, path, *, data=None, **options):
        request = json.loads(data)
        if request['kind'] == 'result':
            original = self.staged_request(request['mission_id'], request['operation_id'])
            operation = None if original is None else dict(request=original, state='unknown',
                result=dict(reason='Retained unknown; collection did not replay input'))
            return dict(status='accepted', operation=operation)
        if request['entry']['text'] == 'Malformed response fixture':
            return dict(status='accepted', operation=[])
        raise MissionClientError('Submission response lost')


async def _stdio_fixture(root: Path, *, recover_only=False):
    from mcp.server.stdio import stdio_server
    player = PlayerTools(InterruptedClient(root))
    if not recover_only:
        source = bundle(7)
        scope = dict(mission_id='mission-test', session=source['reference']['session'], coordinate_epoch=4)
        player.snapshots['chosen'] = dict(snapshot_id='chosen', mission=snapshot(coordinate_scope=scope),
            source=source, native={})
    server = make_server(player)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '--stdio-fixture':
        import anyio
        anyio.run(lambda: _stdio_fixture(Path(sys.argv[2]), recover_only='--recover-only' in sys.argv[3:]))
    else:
        unittest.main()
