"""Current MCP invocation over real SDK staging; synthetic evidence, no native play."""
from copy import deepcopy
import asyncio
import json
from pathlib import Path
import tempfile
import threading
import sys
import unittest
import uuid
from unittest.mock import Mock, patch

from mcp import Client

from harness.mission_client import MissionClientError
from harness.gameplay.contracts import ContractError
from harness.gameplay.mission_contracts import MAX_HANDOFF_SOURCES
from harness.player_mcp import make_server
from harness.player_tools import PlayerTools, tool_specs, _validate_arguments
from tests.test_player_claims import StagingClient
from tests.test_mission_request_producer import activity_root, bundle, snapshot
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

    def handoff_claim(self, procedure_sources):
        binding = dict(pause_generation=2, takeover_generation=3, session=self.source['reference']['session'],
            revision=7, boundary_id='issued-boundary', pause_origin='host')
        self.backend.collect = Mock(return_value=dict(transport='delivered', response=dict(operation=dict(
            state='completed', request=dict(kind='handoff'), result=binding))))
        return dict(snapshot_id='chosen', intent=dict(handoff_id='issued-handoff', player_id='fresh-player',
            actor_role='campaign-player', packet_ids=['issued-packet'], read_source_ids=[self.source['reference']['observation_id']],
            read_procedure_sources=procedure_sources))

    def readable_sources(self, qualified):
        sources = {(mission, source['reference']['observation_id']): source for mission, source in qualified}
        self.backend.source = Mock(side_effect=lambda mission, source: (deepcopy(sources[(mission, source)]), b'pixels'))
        return [dict(mission_id=mission, source_id=source['reference']['observation_id']) for mission, source in qualified]

    def test_actual_shaped_thirty_seven_source_reads_with_overlap_submit_one_claim(self):
        local = [('mission-test', bundle(index)) for index in range(7, 13)]
        historical = [('history-mission', bundle(index)) for index in range(100, 131)]
        reads = self.readable_sources(local + historical)
        declared = [*reads[6:27], reads[0], *reads[27:]]
        args = self.handoff_claim(declared)
        args['intent']['read_source_ids'] = [source['source_id'] for source in reads[:6]]
        async def exercise(client):
            for source in reads:
                self.assertFalse((await client.call_tool('enactive_source', source)).is_error)
            reply = await client.call_tool('enactive_claim', args)
            self.assertFalse(reply.is_error, self.value(reply))
        self.run_client(exercise)
        self.assertEqual(len(self.player.sources), 37)
        self.assertEqual(self.backend.source.call_count, 37)
        self.backend.collect.assert_called_once_with('mission-test', 'issued-handoff', wait_seconds=0)
        self.assertEqual(len(self.backend.writes), 1)
        request = self.backend.writes[0]
        self.assertEqual(request['read_procedure_sources'], declared)
        self.assertEqual(request['read_source_ids'], args['intent']['read_source_ids'])
        self.assertEqual(request['packet_ids'], ['issued-packet'])
        self.assertEqual(request['player_id'], 'fresh-player')

    def test_unread_or_evicted_exact_source_is_unsubmitted_then_explicit_reread_works(self):
        qualified = [('history-mission', bundle(index)) for index in range(MAX_HANDOFF_SOURCES + 1)]
        reads = self.readable_sources(qualified)
        args = self.handoff_claim([reads[0]])
        async def exercise(client):
            for fault in ('unread', 'evicted'):
                if fault == 'evicted':
                    for source in reads:
                        await client.call_tool('enactive_source', source)
                reply = await client.call_tool('enactive_claim', args)
                value = self.value(reply)
                self.assertTrue(reply.is_error)
                self.assertEqual(value['submission'], 'not_submitted')
                self.assertNotIn('original_collection', value)
                self.assertEqual(self.backend.writes, [])
                self.backend.collect.assert_not_called()
                self.assertFalse((self.root / '.runtime/mission-requests').exists())
            await client.call_tool('enactive_source', reads[0])
            self.assertFalse((await client.call_tool('enactive_claim', args)).is_error)
        self.run_client(exercise)
        self.assertEqual(len(self.backend.writes), 1)

    def test_full_handoff_source_bound_submits_only_explicit_declarations(self):
        reads = self.readable_sources([('history-mission', bundle(index)) for index in range(MAX_HANDOFF_SOURCES)])
        args = self.handoff_claim(reads)
        for source in reads:
            self.player.source(source['mission_id'], source['source_id'])
        async def exercise(client):
            reply = await client.call_tool('enactive_claim', args)
            self.assertFalse(reply.is_error, self.value(reply))
        self.run_client(exercise)
        self.assertEqual(len(self.backend.writes), 1)
        self.assertEqual(self.backend.writes[0]['read_procedure_sources'], reads)
        self.assertEqual(self.backend.source.call_count, MAX_HANDOFF_SOURCES)
        self.assertEqual(len(self.player.sources), MAX_HANDOFF_SOURCES)

    def test_invalid_explicit_snapshot_preserves_schema_error_without_io(self):
        args = self.claim()
        args.update(request_id='invalid-explicit', wait_seconds=0, snapshot_id=[])
        with patch.object(self.backend, 'staged_request', side_effect=AssertionError('No valid mission binding')):
            with self.assertRaisesRegex(ContractError, 'snapshot_id'):
                self.player.call('enactive_remember', args)
        self.assertEqual(self.backend.writes, [])
        self.assertFalse((self.root / '.runtime/mission-requests').exists())

    def test_new_schema_snapshot_claim_and_busy_refusals_have_no_original_collection(self):
        async def exercise(client):
            for fault in ('schema', 'snapshot', 'grounding', 'busy', 'issuance'):
                args = self.claim()
                name = 'enactive_remember'
                if fault == 'schema':
                    args['intent']['entry']['status'] = 'invented'
                elif fault == 'snapshot':
                    args['snapshot_id'] = 'unavailable'
                elif fault == 'grounding':
                    args['intent']['entry']['grounding']['source_id'] = 'unread'
                elif fault == 'issuance':
                    args = self.handoff_claim([])
                    self.backend.collect.return_value = dict(transport='uncertain', response=None)
                    name = 'enactive_claim'
                if fault == 'busy':
                    self.player._lock.acquire()
                try:
                    reply = await client.call_tool(name, args)
                finally:
                    if fault == 'busy':
                        self.player._lock.release()
                value = self.value(reply)
                self.assertTrue(reply.is_error, fault)
                self.assertEqual(value['submission'], 'not_submitted', (fault, value))
                self.assertNotIn('original_collection', value)
                self.assertFalse((self.root / '.runtime/mission-requests').exists())
                self.assertEqual(self.backend.writes, [])
        self.run_client(exercise)

    def test_existing_or_corrupt_stage_preparation_errors_keep_original_and_never_repost(self):
        fixed = uuid.UUID(int=1)
        async def exercise(client):
            first = await client.call_tool('enactive_remember', self.claim())
            self.assertFalse(first.is_error)
            identity = self.value(first)['operation_id']
            self.assertEqual(identity, 'op-' + fixed.hex)
            original = self.backend.staged_request('mission-test', identity)
            # Identical semantic duplicate uses SDK's original collection fence.
            await client.call_tool('enactive_remember', self.claim())
            self.assertEqual(len(self.backend.writes), 1)
            self.assertEqual(len(self.backend.reads), 1)
            path, = (self.root / '.runtime/mission-requests').glob('*.json')
            before = path.read_bytes()
            for fault in ('source', 'busy', 'schema', 'corrupt-stage'):
                args = self.claim()
                if fault in ('source', 'corrupt-stage'):
                    args['intent']['entry']['grounding']['source_id'] = 'unread'
                if fault == 'schema':
                    # Model validation has no assigned identity yet; use the
                    # explicit SDK tool schema after model argument binding.
                    def sdk_schema_failure(name, data, schema):
                        if 'request_id' in data:
                            raise ContractError('SDK preparation schema')
                        return _validate_arguments(name, data, schema)
                    with patch('harness.player_tools._validate_arguments', side_effect=sdk_schema_failure):
                        reply = await client.call_tool('enactive_remember', args)
                else:
                    if fault == 'busy': self.player._lock.acquire()
                    if fault == 'corrupt-stage': path.write_bytes(b'{')
                    try:
                        reply = await client.call_tool('enactive_remember', args)
                    finally:
                        if fault == 'busy': self.player._lock.release()
                value = self.value(reply)
                self.assertTrue(reply.is_error)
                self.assertNotIn('submission', value)
                self.assertEqual(value['original_collection'], dict(tool='enactive_result',
                    arguments=dict(mission_id='mission-test', operation_id=identity)))
                self.assertEqual(len(self.backend.writes), 1)
                self.assertEqual(len(self.backend.reads), 1)
            path.write_bytes(before)
            self.assertEqual(self.backend.staged_request('mission-test', identity), original)
        with patch('harness.player_tools.uuid.uuid4', return_value=fixed):
            self.run_client(exercise)

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

    def activity_arguments(self, *, scope="activity", step="answer_interrupt"):
        source = bundle(kind='activity_poll' if step == 'poll' else 'interrupt_confirmation')
        if step != 'poll':
            source['observation']['boundary'].update(interrupt_request_id='owned-interrupt', recovery_operations=['answer_interrupt'])
        phase = dict(origin_request_id='original-root', checkpoint_id=source['reference']['observation_id'],
            stage='interrupt_confirmation', answered=False, interrupt_request_id='owned-interrupt')
        self.player.snapshots['chosen'] = dict(snapshot_id='chosen',
            mission=snapshot(phase='paused', **{scope + '_phase': phase}), source=source, native={})
        return dict(snapshot_id='chosen', scope=scope, source_id=None, supporting_source_ids=[],
            limits=dict(primitives=1, wall_seconds=7, game_seconds=60), intent=dict(skill_kind='activity',
                goal=dict(step=step, **(dict(answer='NO') if step == 'answer_interrupt' else {})),
                work_id=None, perception=None, procedure=None))

    def root_collection(self, root):
        original_json = self.backend._json
        def collect(path, *, data=None, **options):
            body = json.loads(data)
            if body['kind'] == 'result':
                self.backend.reads.append(body)
                return dict(status='accepted', operation=dict(request=deepcopy(root), state='partial', result={}))
            return original_json(path, data=data, **options)
        return collect

    def test_model_activity_derives_selected_root_and_owner_and_rejects_copied_fields(self):
        root = activity_root()
        args = self.activity_arguments()
        self.backend._json = self.root_collection(root)
        async def exercise(client):
            reply = await client.call_tool('enactive_skill', args)
            self.assertFalse(reply.is_error, reply)
            request = self.backend.writes[-1]
            self.assertEqual(request['goal'], {**root['goal'], **args['intent']['goal'],
                'interrupt_request_id': 'owned-interrupt'})
            self.assertEqual(request['phase_id'], 'original-root')
            self.assertEqual(self.backend.reads, [dict(schema='mission/11', kind='result',
                mission_id='mission-test', operation_id='original-root')])
            for key, value in root['goal'].items():
                if key == 'step' or key == 'answer':
                    continue
                old = deepcopy(args)
                old['intent']['goal'][key] = value
                self.assertTrue((await client.call_tool('enactive_skill', old)).is_error)
            self.assertEqual(len(self.backend.writes), 1)
            self.assertEqual(len(self.backend.reads), 1)
            self.player.snapshots['chosen']['mission']['activity_phase']['answered'] = True
            with patch.object(self.backend, '_stage', wraps=self.backend._stage) as stage:
                reply = await client.call_tool('enactive_skill', args)
                self.assertTrue(reply.is_error)
                self.assertEqual(self.value(reply)['submission'], 'not_submitted')
                stage.assert_not_called()
            self.assertEqual(len(self.backend.writes), 1)
        self.run_client(exercise)

    def test_model_activity_prompt_and_activity_children_collect_the_exact_original(self):
        async def exercise(client):
            for kind in ('activity', 'direct', 'program'):
                root = activity_root(kind)
                self.backend._json = self.root_collection(root)
                for scope, steps in (('prompt', ('poll', 'interrupt')), ('activity', ('resume', 'answer_interrupt'))):
                    for step in steps:
                        with self.subTest(kind=kind, scope=scope, step=step):
                            args = self.activity_arguments(scope=scope, step=step)
                            reply = await client.call_tool('enactive_skill', args)
                            self.assertFalse(reply.is_error, reply)
                            request = self.backend.writes[-1]
                            self.assertEqual(request['phase_id'], root['request_id'])
                            self.assertEqual(request['limits'], args['limits'])
                            self.assertEqual(request['goal']['target'], root['goal'].get('target', root['goal'].get('expected')))
                            self.assertEqual(request['goal']['interrupt_request_id'],
                                'owned-interrupt' if step == 'answer_interrupt' else None)
            self.assertEqual(len(self.backend.writes), 12)
            self.assertEqual(len(self.backend.reads), 12)
        self.run_client(exercise)

    def test_missing_mismatched_or_noncanonical_original_never_stages_or_submits_child(self):
        root = activity_root()
        invalid_roots = (None, {}, {**root, 'mission_id': 'other'}, {**root, 'request_id': 'other'},
            {**root, 'schema': 'mission/10'}, {**root, 'phase_id': 'ancestor'},
            {**root, 'skill_kind': 'inspect', 'goal': dict(purpose='needs')})
        async def exercise(client):
            for root_result in invalid_roots:
                self.backend._json = self.root_collection(root_result)
                args = self.activity_arguments(scope='prompt', step='interrupt')
                with self.subTest(root=root_result), patch.object(self.backend, '_stage', wraps=self.backend._stage) as stage:
                    reply = await client.call_tool('enactive_skill', args)
                    self.assertTrue(reply.is_error)
                    value = self.value(reply)
                    self.assertEqual(value['submission'], 'not_submitted')
                    self.assertNotIn('original_collection', value)
                    stage.assert_not_called()
            self.assertEqual(self.backend.writes, [])
            self.assertEqual(list((self.root / '.runtime' / 'mission-requests').glob('*')), [])
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
        for failure in ('stage', 'submit-contract', 'finish-contract', 'presentation', 'presentation-contract'):
            with self.subTest(failure=failure):
                if failure == 'stage':
                    target = patch.object(self.backend, '_stage', side_effect=MissionClientError('Stage failed'))
                elif failure == 'submit-contract':
                    target = patch.object(self.backend, 'submit', side_effect=ContractError('SDK submit failed'))
                elif failure == 'finish-contract':
                    target = patch.object(self.player, '_compact', side_effect=ContractError('Finish failed'))
                elif failure == 'presentation-contract':
                    target = patch('harness.player_mcp.decision_view', side_effect=ContractError('Presentation failed'))
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
                    if failure in ('finish-contract', 'presentation', 'presentation-contract'):
                        self.assertEqual(collection['arguments']['operation_id'], self.backend.writes[-1]['request_id'])
                with target:
                    self.run_client(exercise)
        self.assertEqual(len(self.backend.writes), 3)

    def test_open_prompt_refusal_exposes_observe_without_staging_or_claiming_closure(self):
        self.selected['mission'].update(phase='active', active_operation=None,
            prompt_phase=dict(origin_request_id='spent-root',
                checkpoint_id=self.source['reference']['observation_id']),
            remaining_limits=dict(inputs=1896))
        self.player.snapshots['chosen'] = deepcopy(self.selected)
        args = dict(snapshot_id='chosen', scope='new_root', source_id=None, supporting_source_ids=[],
            limits=dict(primitives=32, wall_seconds=180, game_seconds=120),
            intent=dict(operation='save', world='test-world', character='test-character',
                identity_claim_ids=[], work_id=None))
        before = deepcopy(self.player.snapshots)
        async def exercise(client):
            result = await client.call_tool('enactive_lifecycle', args)
            self.assertTrue(result.is_error)
            value = self.value(result)
            self.assertEqual(value['submission'], 'not_submitted')
            self.assertIn('enactive_observe', value['error'])
            self.assertIn('may report macro_closure', value['error'])
            self.assertIn('not the local root', value['error'])
            self.assertNotIn('original_collection', value)
            self.assertEqual(self.backend.writes, [])
            self.assertEqual(self.player.snapshots, before)
            self.assertFalse((self.root / '.runtime/mission-requests').exists())
        self.run_client(exercise)

    def test_proven_composition_refusals_do_not_send_player_to_nonexistent_collection(self):
        args = dict(snapshot_id='chosen', scope='lifecycle', source_id=None, supporting_source_ids=[],
            limits=dict(primitives=4, wall_seconds=7, game_seconds=10),
            intent=dict(operation='exit', world='test-world', character='test-character',
                identity_claim_ids=[], work_id=None))
        async def exercise(client):
            for missing_source in (False, True):
                if missing_source:
                    self.player.snapshots['chosen']['source'] = None
                result = await client.call_tool('enactive_lifecycle', args)
                self.assertTrue(result.is_error)
                value = self.value(result)
                self.assertEqual(value['submission'], 'not_submitted')
                self.assertNotIn('original_collection', value)
                self.assertIn('No authority', value['next_step'])
                self.assertEqual(self.backend.writes, [])
                self.assertFalse((self.root / '.runtime/mission-requests').exists())
        self.run_client(exercise)

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
