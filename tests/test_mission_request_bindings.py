"""Real controller/writer/ledger checks with synthetic UI, not native acceptance.

Deciding002 supplied an old boundary alongside the correct immutable source.
Its original failed record is never repaired by these temporary fixtures.
"""
import copy
from dataclasses import replace
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from tests import test_mission_runtime as runtime_fixtures
from tests import test_mission_confirmation_validation as confirmation_fixtures
from tests import test_mission_activity_recovery as activity_fixtures
from tests import test_mission_exit as exit_fixtures
from tests.test_mission_creation import MissionCreationFixture


class RequestBindingTests(unittest.TestCase):
    setUp = runtime_fixtures.MissionRuntimeTests.setUp
    wait = runtime_fixtures.MissionRuntimeTests.wait
    request = runtime_fixtures.MissionRuntimeTests.request
    result = runtime_fixtures.MissionRuntimeTests.result
    settled = runtime_fixtures.MissionRuntimeTests.settled
    start = runtime_fixtures.MissionRuntimeTests.start
    navigation = runtime_fixtures.MissionRuntimeTests.navigation
    control = runtime_fixtures.MissionRuntimeTests.control
    open_direction = runtime_fixtures.MissionRuntimeTests.open_direction
    native_choices = runtime_fixtures.MissionRuntimeTests.native_choices

    def assert_local_rejection(self, request, root):
        phase, lease = self.runtime._prompt_phase, self.runtime._lease
        current = self.runtime._current
        generation = self.runtime._store.authority_generation()
        before = self.runtime.status()
        deadline = self.runtime._ledger.request(root['request_id'])['deadline']
        delivered = copy.deepcopy(self.bridge.delivered)
        with (patch.object(self.runtime, '_observe_native', wraps=self.runtime._observe_native) as observe,
              patch.object(self.runtime, '_dispatch', wraps=self.runtime._dispatch) as dispatch,
              patch.object(self.runtime, '_rotate', wraps=self.runtime._rotate) as rotate):
            self.assertEqual(self.runtime.command(request)['status'], 'accepted')
            result = self.settled(request['request_id'])
        self.assertEqual(result['state'], 'blocked', result)
        self.assertIn('No input or refresh was attempted', result['result']['reason'])
        self.assertFalse(result['result']['grants_authority'])
        observe.assert_not_called()
        dispatch.assert_not_called()
        rotate.assert_not_called()
        self.assertIs(self.runtime._prompt_phase, phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime._current, current)
        self.assertEqual(self.runtime._store.authority_generation(), generation)
        self.assertEqual(self.runtime.status()['epoch'], before['epoch'])
        self.assertEqual(self.runtime.status()['phase'], 'active')
        self.assertEqual(self.runtime.status()['metrics']['primitives'], before['metrics']['primitives'])
        self.assertEqual(self.runtime.status()['metrics']['archive'], before['metrics']['archive'])
        self.assertEqual(self.runtime._ledger.request(root['request_id'])['deadline'], deadline)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertFalse(any(p['request_id'] == request['request_id'] for p in self.runtime._ledger.primitive_records()))
        return result

    def test_fresh_metadata_errors_preserve_scope_and_new_corrected_id_executes(self):
        root, _ = self.native_choices()
        last = None
        for field, value in [('expected_session', 'copied-old-session'),
                             ('expected_revision', 10000), ('expected_boundary_id', 'copied-old-boundary')]:
            with self.subTest(field=field):
                bad = self.control('menu', dict(purpose='Choose', label='Two', outcome='focused'),
                    phase_id=root['request_id'], request_id='bad-' + field, **{field: value})
                last = self.assert_local_rejection(bad, root)
        original = self.runtime._ledger.request(bad['request_id'])
        self.assertEqual(self.runtime.command(bad)['operation'], original)
        corrected = self.control('menu', dict(purpose='Choose', label='Two', outcome='focused'),
            phase_id=root['request_id'], request_id='corrected')
        self.assertEqual(self.runtime.command({**corrected, 'request_id': bad['request_id']})['status'], 'rejected')
        self.runtime.command(corrected)
        result = self.settled('corrected')
        self.assertEqual(result['state'], 'completed', result)
        self.assertEqual(result['result']['verified_focus_steps'], 1)
        self.assertEqual(self.runtime.status()['spent_inputs'], 2)
        self.assertEqual(self.runtime._ledger.request(bad['request_id'])['result'], last['result'])

    def test_aged_interpreted_metadata_error_does_not_refresh_and_correction_revalidates(self):
        root, _ = self.native_choices()
        source = self.runtime._current
        view = dict(kind='menu', source_id=source.observation_id, basis='player_interpretation',
            control='vertical', rows=[dict(label=label, enabled=True) for label in ('One', 'Two', 'Three')],
            selected=0, question='')
        bad = self.control('menu', dict(purpose='Choose', label='Two', outcome='focused'),
            phase_id=root['request_id'], perception=view, request_id='aged-bad',
            expected_boundary_id='copied-old-boundary')
        threading.Event().wait(3.05)
        self.assertFalse(self.runtime._store.inspect_current_boundary(**self.runtime._clocks())[1])
        self.assert_local_rejection(bad, root)
        corrected = self.control('menu', bad['goal'], phase_id=root['request_id'], perception=view,
                                 request_id='aged-corrected')
        self.runtime.command(corrected)
        result = self.settled('aged-corrected')
        self.assertEqual(result['state'], 'partial', result)
        self.assertIsNotNone(result['result']['revalidation'])
        self.assertEqual(self.runtime.status()['spent_inputs'], 2)
        self.assertEqual(self.bridge.value['ui']['selected'], 'row-1')

    def test_navigation_metadata_error_has_no_primitive_and_new_request_moves(self):
        self.start()
        bad = self.navigation(expected_boundary_id='copied-old-boundary')
        before = copy.deepcopy(self.bridge.delivered)
        self.runtime.command(bad)
        self.assertIn('No input or refresh', self.settled(bad['request_id'])['result']['reason'])
        self.assertEqual(self.bridge.delivered, before)
        self.assertEqual(self.runtime.status()['spent_inputs'], 0)
        corrected = self.navigation(request_id='corrected-navigation')
        self.runtime.command(corrected)
        self.assertEqual(self.settled('corrected-navigation')['state'], 'completed')
        self.assertEqual(self.runtime.status()['spent_inputs'], 1)

    def test_native_row_validation_retains_its_existing_metadata_equivalence(self):
        root, _ = self.native_choices()
        bad = self.control('menu', dict(purpose='Choose', label='Two', outcome='focused'),
            phase_id=root['request_id'], expected_boundary_id='copied-old-boundary')
        native_frame = 'frame-' + self.runtime._current.session + '-999999.png'
        (self.controller.bridge / native_frame).write_bytes(b'\x89PNG\r\n\x1a\nchanged-cosmetic-pixels')
        with self.controller.data_lock:
            self.controller.state['frame'] = native_frame
        # Native rows use native_state equivalence; image interpretations do not.
        self.assert_local_rejection(bad, root)

    def test_malformed_request_does_not_bypass_actual_scope_or_budget_failures(self):
        faults = ('takeover', 'native_drift', 'wrong_owner', 'game_cap', 'input_reserve',
                  'root_input', 'source_loss', 'capacity_tail', 'changed_pixels')
        for fault in faults:
            with self.subTest(fault=fault):
                case = RequestBindingTests('test_navigation_metadata_error_has_no_primitive_and_new_request_moves')
                case.setUp()
                try:
                    if fault == 'input_reserve':
                        case.a = replace(case.a, limits=replace(case.a.limits, inputs=2),
                                         cleanup_reserve=replace(case.a.cleanup_reserve, inputs=1))
                    elif fault == 'capacity_tail':
                        case.a = replace(case.a, limits=replace(case.a.limits, frames=5),
                                         cleanup_reserve=replace(case.a.cleanup_reserve, frames=1))
                    root, _ = case.native_choices(**({'limits': dict(primitives=1, wall_seconds=120,
                        game_seconds=1200)} if fault == 'root_input' else {}))
                    bad = case.control('menu', dict(purpose='Choose', label='Two', outcome='focused'),
                        phase_id=root['request_id'], expected_boundary_id='copied-old-boundary')
                    delivered, spent = copy.deepcopy(case.bridge.delivered), case.runtime.status()['spent_inputs']
                    if fault in ('takeover', 'native_drift'):
                        with case.controller.data_lock:
                            if fault == 'takeover':
                                case.controller.state['takeover_generation'] += 1
                            else:
                                case.controller.state['revision'] += 1
                    elif fault == 'wrong_owner':
                        case.runtime._prompt_phase = replace(case.runtime._prompt_phase, actor_id='wrong-actor')
                    elif fault == 'game_cap':
                        case.runtime._game_cost = case.a.limits.game_seconds
                    elif fault == 'source_loss':
                        Path(case.runtime._current.frame_path).unlink()
                    elif fault == 'capacity_tail':
                        self.assertEqual(case.a.limits.frames - case.a.cleanup_reserve.frames
                                         - case.runtime._store.usage()['frames'], 1)
                    elif fault == 'changed_pixels':
                        bad['perception'] = dict(kind='menu', basis='player_interpretation',
                            source_id=case.runtime._current.observation_id, control='vertical',
                            rows=[dict(label=label, enabled=True) for label in ('One', 'Two', 'Three')],
                            selected=0, question='')
                        native_frame = 'frame-' + case.runtime._current.session + '-999999.png'
                        (case.controller.bridge / native_frame).write_bytes(b'\x89PNG\r\n\x1a\nchanged-visible-pixels')
                        with case.controller.data_lock:
                            case.controller.state['frame'] = native_frame
                    case.runtime.command(bad)
                    result = case.settled(bad['request_id'])
                    self.assertEqual(result['state'], 'blocked', result)
                    self.assertNotIn('No input or refresh was attempted', result['result']['reason'])
                    self.assertEqual(case.bridge.delivered, delivered)
                    self.assertEqual(case.runtime.status()['spent_inputs'], spent)
                    self.assertIsNone(case.runtime._prompt_phase)
                    self.assertIsNone(case.controller._mission_lease)
                finally:
                    case.doCleanups()

    def test_unknown_delivery_is_not_correctable_metadata(self):
        root, _ = self.native_choices(effect=lambda bridge, request: request.get('action') != 'UILIST.DOWN')
        first = self.control('menu', dict(purpose='Choose', label='Two', outcome='focused'),
                             phase_id=root['request_id'], request_id='unknown-focus')
        self.runtime.command(first)
        self.assertEqual(self.settled(first['request_id'])['state'], 'unknown')
        delivered = copy.deepcopy(self.bridge.delivered)
        primitives = copy.deepcopy(self.runtime._ledger.primitive_records())
        self.assertIsNone(self.runtime.status()['current_source'])
        self.assertEqual(self.runtime.status()['phase'], 'paused')
        self.assertEqual(self.runtime.status()['unreconciled'], 1)
        bad = {**copy.deepcopy(first), 'epoch': self.runtime.status()['epoch'],
               'request_id': 'bad-after-unknown', 'expected_boundary_id': 'copied-old-boundary'}
        response = self.runtime.command(bad)
        if response['status'] == 'accepted':
            self.assertNotIn('No input or refresh was attempted', self.settled(bad['request_id'])['result']['reason'])
        self.assertEqual(self.runtime._ledger.primitive_records(), primitives)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertIsNone(self.controller._mission_lease)

    def test_malformed_request_cannot_renew_expired_root_or_rollback_clock(self):
        for fault in ('root-deadline', 'clock-rollback'):
            with self.subTest(fault=fault):
                case = RequestBindingTests('test_user_pause_precedes_malformed_request')
                case.setUp()
                original_wall = case.runtime._wall
                try:
                    root, _ = case.native_choices()
                    bad = case.control('menu', dict(purpose='Choose', label='Two', outcome='focused'),
                        phase_id=root['request_id'], expected_boundary_id='copied-old-boundary')
                    deadline = case.runtime._ledger.request(root['request_id'])['deadline']
                    before = copy.deepcopy(case.bridge.delivered)
                    spent = case.runtime.status()['spent_inputs']
                    if fault == 'root-deadline':
                        case.runtime._wall = lambda: deadline + .01
                    else:
                        last = case.runtime.status()['last_wall']
                        case.runtime._wall = lambda: last - 1
                    response = case.runtime.command(bad)
                    self.assertEqual(response['status'], 'rejected', response)
                    self.assertIn('deadline' if fault == 'root-deadline' else 'rollback', response['reason'])
                    self.assertEqual(case.bridge.delivered, before)
                    self.assertEqual(case.runtime.status()['spent_inputs'], spent)
                    self.assertEqual(case.runtime._ledger.request(root['request_id'])['deadline'], deadline)
                finally:
                    if fault == 'clock-rollback':
                        case.runtime._wall = original_wall
                    case.doCleanups()

    def test_user_pause_precedes_malformed_request(self):
        root, _ = self.native_choices()
        bad = self.control('menu', dict(purpose='Choose', label='Two', outcome='focused'),
            phase_id=root['request_id'], expected_boundary_id='copied-old-boundary')
        self.runtime.pause('User Pause')
        before = copy.deepcopy(self.bridge.delivered)
        self.runtime.command(bad)
        self.wait(lambda: not self.runtime._handles)
        self.assertEqual(self.runtime.status()['pause_cause'], 'user')
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertIsNone(self.controller._mission_lease)
        self.assertEqual(self.bridge.delivered, before)


class LifecycleBindingTests(MissionCreationFixture, unittest.TestCase):
    confirmation = confirmation_fixtures.ConfirmationValidationTests.confirmation

    def test_lifecycle_binding_error_preserves_original_phase_before_new_question(self):
        root, question, _ = self.confirmation('world')
        phase, lease = self.runtime._registered_lifecycle.phase, self.runtime._lease
        deadline = self.runtime._ledger.request(root)['deadline']
        delivered = copy.deepcopy(self.bridge.delivered)
        bad = self.control('bad-boundary', 'Yes', parent=root, question=question)
        bad['expected_boundary_id'] = 'copied-old-boundary'
        with patch.object(self.runtime, '_observe_native', wraps=self.runtime._observe_native) as observe:
            result = self.run_request(bad)
        self.assertIn('No input or refresh', result['result']['reason'])
        observe.assert_not_called()
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.bridge.delivered, delivered)
        corrected = self.run_request(self.control('new-boundary', 'Yes', parent=root, question=question))
        self.assertEqual(corrected['state'], 'partial', corrected)
        self.assertEqual(self.runtime._ledger.request(root)['deadline'], deadline)


class ActivityBindingTests(unittest.TestCase):
    setUp = activity_fixtures.ActivityRecoveryTests.setUp
    wait = activity_fixtures.ActivityRecoveryTests.wait
    request = activity_fixtures.ActivityRecoveryTests.request
    result = activity_fixtures.ActivityRecoveryTests.result
    settled = activity_fixtures.ActivityRecoveryTests.settled
    start = activity_fixtures.ActivityRecoveryTests.start
    control = activity_fixtures.ActivityRecoveryTests.control
    begin = activity_fixtures.ActivityRecoveryTests.begin
    prepare = activity_fixtures.ActivityRecoveryTests.prepare
    recovery = activity_fixtures.ActivityRecoveryTests.recovery
    return_normal = activity_fixtures.ActivityRecoveryTests.return_normal

    def test_paused_activity_binding_error_preserves_no_lease_phase_then_answers(self):
        self.prepare()
        self.recovery('interrupt')
        phase = self.runtime._registered_activity.phase
        self.assertFalse(phase.needs_observation)
        delivered = copy.deepcopy(self.bridge.delivered)
        bad = self.control('activity', {**self.goal, 'step': 'answer_interrupt', 'answer': 'YES',
            'interrupt_request_id': phase.interrupt_id}, phase_id='rest-root', request_id='bad-answer',
            expected_boundary_id='copied-old-boundary')
        result = self.runtime.command(bad)
        self.assertEqual(result['status'], 'accepted')
        result = self.settled('bad-answer')
        self.assertIn('No input or refresh', result['result']['reason'])
        self.assertIs(self.runtime._registered_activity.phase, phase)
        self.assertIsNone(self.runtime._lease)
        self.assertEqual(self.bridge.delivered, delivered)
        answer = self.recovery('answer_interrupt', identity='corrected-answer')
        self.assertEqual(answer['state'], 'partial', answer)
        self.assertFalse(self.runtime._registered_activity.phase.needs_observation)
        self.assertEqual(self.runtime.status()['activity_phase']['stage'], 'awaiting_readmission')
        self.assertIsNone(self.runtime._lease)
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(primitive['state'], 'returned')
        self.assertIsNone(primitive['result']['source_after'])
        self.assertEqual(primitive['result']['control']['result']['status'], 'answer_delivered')
        self.assertFalse(primitive['result']['control']['result']['state']['frame_ok'])
        spent, delivered = self.runtime.status()['spent_inputs'], len(self.bridge.delivered)
        # A valid frameless-answer continuation still uses its existing adapter.
        self.assertEqual(self.recovery('resume')['state'], 'partial')
        self.assertEqual(self.runtime.status()['spent_inputs'], spent + 1)
        self.assertEqual(len(self.bridge.delivered), delivered + 1)
        self.assertIsNone(self.runtime._registered_activity.phase)
        self.assertIsNotNone(self.runtime._lease)


class ExitBindingTests(unittest.TestCase):
    setUp = exit_fixtures.MissionExitTests.setUp
    fake_launch = exit_fixtures.MissionExitTests.fake_launch
    start = exit_fixtures.MissionExitTests.start
    settled = exit_fixtures.MissionExitTests.settled
    request = exit_fixtures.MissionExitTests.request
    launch = exit_fixtures.MissionExitTests.launch
    ready = exit_fixtures.MissionExitTests.ready
    behavior = exit_fixtures.MissionExitTests.behavior
    exit_request = exit_fixtures.MissionExitTests.exit_request
    run_request = exit_fixtures.MissionExitTests.run_request
    begin_exit = exit_fixtures.MissionExitTests.begin_exit
    confirmation = exit_fixtures.MissionExitTests.confirmation

    def test_owned_exit_binding_error_preserves_phase_then_new_no_returns(self):
        self.ready()
        self.begin_exit()
        phase, lease = self.runtime._exit_phase, self.runtime._lease
        deadline = self.runtime._ledger.request('exit')['deadline']
        delivered = copy.deepcopy(self.bridge.delivered)
        bad = self.confirmation(label='No', expected_boundary_id='copied-old-boundary')
        with patch.object(self.runtime, '_observe_native', wraps=self.runtime._observe_native) as observe:
            result = self.run_request(bad)
        self.assertIn('No input or refresh', result['result']['reason'])
        observe.assert_not_called()
        self.assertIs(self.runtime._exit_phase, phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.bridge.delivered, delivered)
        corrected = self.run_request(self.confirmation(label='No', identity='corrected-no'))
        self.assertEqual(corrected['state'], 'partial', corrected)
        self.assertEqual(self.runtime._ledger.request('exit')['deadline'], deadline)
        self.assertEqual(self.runtime.status()['spent_inputs'], 3)
