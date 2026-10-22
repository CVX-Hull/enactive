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
from tests import test_mission_items as item_fixtures
from tests.test_mission_creation import MissionCreationFixture
from tests.test_mission_ledger import intent


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
        bindings = copy.deepcopy(self.runtime._bindings)
        rotation = self.runtime._rotation
        primitives = self.runtime._ledger.primitive_records()
        before = self.runtime.status()
        deadline = self.runtime._ledger.request(root['request_id'])['deadline']
        delivered = copy.deepcopy(self.bridge.delivered)
        with (patch.object(self.runtime, '_observe_native', wraps=self.runtime._observe_native) as observe,
              patch.object(self.runtime, '_dispatch', wraps=self.runtime._dispatch) as dispatch,
              patch.object(self.runtime, '_rotate', wraps=self.runtime._rotate) as rotate,
              patch.object(self.runtime._store, 'reserve_dispatch', wraps=self.runtime._store.reserve_dispatch) as reserve):
            self.assertEqual(self.runtime.command(request)['status'], 'accepted')
            result = self.settled(request['request_id'])
        self.assertEqual(result['state'], 'blocked', result)
        self.assertIn('No input or refresh was attempted', result['result']['reason'])
        self.assertFalse(result['result']['grants_authority'])
        observe.assert_not_called()
        dispatch.assert_not_called()
        rotate.assert_not_called()
        reserve.assert_not_called()
        self.assertIs(self.runtime._prompt_phase, phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.runtime._current, current)
        self.assertEqual(self.runtime._store.authority_generation(), generation)
        self.assertEqual(self.runtime._bindings, bindings)
        self.assertEqual(self.runtime._rotation, rotation)
        self.assertEqual(self.runtime._ledger.primitive_records(), primitives)
        self.assertEqual(self.runtime.status()['epoch'], before['epoch'])
        self.assertEqual(self.runtime.status()['phase'], 'active')
        self.assertEqual(self.runtime.status()['metrics']['primitives'], before['metrics']['primitives'])
        self.assertEqual(self.runtime.status()['metrics']['archive'], before['metrics']['archive'])
        self.assertEqual(self.runtime._ledger.request(root['request_id'])['deadline'], deadline)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertFalse(any(p['request_id'] == request['request_id'] for p in self.runtime._ledger.primitive_records()))
        return result

    def completed_prompt(self):
        normal = copy.deepcopy(self.bridge.value["scene"])
        def return_normal(bridge, request):
            if request.get("action") == "pause":
                bridge.value.update(category="DEFAULTMODE", scene=normal, ui=None,
                    actions=["open", "UP", "DOWN", "LEFT", "RIGHT"])
                bridge.value["boundary"].update(kind="normal_play", id="returned-normal")
            return True
        root, _ = self.open_direction(effect=return_normal)
        old = self.runtime._current
        child = self.control("menu", dict(purpose="Direction", label="Here", outcome="activated"),
            phase_id=root["request_id"], request_id="complete-prompt", perception=dict(kind="direction",
                basis="player_interpretation", source_id=old.observation_id, question="Where?"))
        self.runtime.command(child)
        self.assertEqual(self.settled(child["request_id"])["state"], "partial")
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertNotEqual(self.runtime._bindings[old.observation_id][1].pause_generation,
                            self.runtime._bindings[self.runtime._current.observation_id][1].pause_generation)
        return root, old

    def test_missing_native_rows_in_ordinary_prompt_allows_explicit_interpreted_choice(self):
        root, _ = self.open_direction()
        bad = self.control('menu', dict(purpose='Direction', label='Here', outcome='activated'),
            phase_id=root['request_id'], request_id='wrong-native-direction')
        self.assert_local_rejection(bad, root)
        corrected = self.control('menu', dict(purpose='Direction', label='Here', outcome='activated'),
            phase_id=root['request_id'], request_id='interpreted-direction', perception=dict(
                kind='direction', basis='player_interpretation', source_id=self.runtime._current.observation_id,
                question='Where?'))
        self.runtime.command(corrected)
        self.assertEqual(self.settled(corrected['request_id'])['state'], 'partial')

    def test_missing_native_rows_in_ordinary_prompt_cannot_hide_changed_pixels(self):
        root, _ = self.open_direction()
        bad = self.control('menu', dict(purpose='Direction', label='Here', outcome='activated'),
            phase_id=root['request_id'], request_id='native-draft-changed-pixels')
        name = f'frame-{self.runtime._current.session}-999999.png'
        (self.controller.bridge / name).write_bytes(b'\x89PNG\r\n\x1a\nchanged-visible-pixels')
        with self.controller.data_lock:
            self.controller.state['frame'] = name
        spent, delivered = self.runtime.status()['spent_inputs'], copy.deepcopy(self.bridge.delivered)
        self.runtime.command(bad)
        refused = self.settled(bad['request_id'])
        self.assertEqual(refused['state'], 'blocked', refused)
        self.assertNotIn('No input or refresh was attempted', refused['result']['reason'])
        self.assertEqual(self.runtime.status()['spent_inputs'], spent)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._prompt_phase)

    def test_expired_or_unknown_extra_support_rejects_only_draft_and_new_id_executes(self):
        root, old = self.completed_prompt()
        for number, extra in enumerate((old.observation_id, "unpublished-source")):
            bad = self.control("interact", dict(action="open", intent="Open", desired_outcome="Inspect"),
                request_id=f"bad-extra-{number}")
            bad["sources"].append(extra)
            result = self.assert_local_rejection(bad, root)
            self.assertIn("historical support belongs in memory", result["result"]["reason"])
            self.assertEqual(result["request"], bad)
            self.assertEqual(self.runtime.command(bad)["operation"], self.runtime._ledger.request(bad["request_id"]))
        corrected = self.control("interact", dict(action="open", intent="Open", desired_outcome="Inspect"),
            request_id="new-current-source-root")
        self.runtime.command(corrected)
        self.assertEqual(self.settled(corrected["request_id"])["state"], "partial")
        self.assertEqual(self.runtime.status()["spent_inputs"], 3)
        self.assertEqual(self.runtime._prompt_phase.root_id, corrected["request_id"])

    def test_bad_extra_cannot_mask_current_faults_or_mixed_support_loss(self):
        for fault in ("takeover", "native_drift", "current_binding", "current_loss", "extra_loss",
                      "extra_corrupt", "extra_disputed", "mixed_loss", "input_reserve", "game_cap"):
            with self.subTest(fault=fault):
                case = RequestBindingTests("test_navigation_metadata_error_has_no_primitive_and_new_request_moves")
                case.setUp()
                try:
                    if fault == "input_reserve":
                        case.a = replace(case.a, limits=replace(case.a.limits, inputs=3),
                                         cleanup_reserve=replace(case.a.cleanup_reserve, inputs=1))
                    root, old = case.completed_prompt()
                    bad = case.control("interact", dict(action="open", intent="Open", desired_outcome="Inspect"),
                        request_id="bad-extra-real-fault")
                    bad["sources"].append(old.observation_id)
                    if fault in ("takeover", "native_drift"):
                        with case.controller.data_lock:
                            case.controller.state["takeover_generation" if fault == "takeover" else "revision"] += 1
                    elif fault == "current_binding":
                        identity = case.runtime._current.observation_id
                        ref, binding = case.runtime._bindings[identity]
                        case.runtime._bindings[identity] = (ref, replace(binding, actor_id="wrong-actor"))
                    elif fault in ("current_loss", "extra_loss"):
                        Path((case.runtime._current if fault == "current_loss" else old).frame_path).unlink()
                    elif fault == "extra_corrupt":
                        Path(old.frame_path).chmod(0o600)
                        Path(old.frame_path).write_bytes(b"changed retained image")
                    elif fault == "extra_disputed":
                        case.runtime._store._disputed.append(old.observation_id)
                    elif fault == "mixed_loss":
                        # One expired extra plus another retained-but-unbound
                        # source whose bytes are missing must still stop.
                        extra = next(ref for ref in case.runtime._store.historical_references
                            if ref.observation_id not in bad["sources"])
                        case.runtime._bindings.pop(extra.observation_id, None)
                        bad["sources"].append(extra.observation_id)
                        Path(extra.frame_path).unlink()
                    elif fault == "game_cap":
                        case.runtime._game_cost = case.a.limits.game_seconds
                    spent, delivered = case.runtime.status()["spent_inputs"], copy.deepcopy(case.bridge.delivered)
                    case.runtime.command(bad)
                    refused = case.settled(bad["request_id"])
                    self.assertEqual(refused["state"], "blocked", refused)
                    self.assertNotIn("No input or refresh was attempted", refused["result"]["reason"])
                    self.assertEqual(case.runtime.status()["spent_inputs"], spent)
                    self.assertEqual(case.bridge.delivered, delivered)
                    self.assertIsNone(case.runtime._lease)
                finally:
                    case.doCleanups()

    def test_historical_sole_source_still_stops(self):
        _, old = self.completed_prompt()
        bad = self.control("interact", dict(action="open", intent="Open", desired_outcome="Inspect"),
            request_id="sole-old-source", sources=[old.observation_id])
        spent = self.runtime.status()["spent_inputs"]
        self.runtime.command(bad)
        result = self.settled(bad["request_id"])
        self.assertEqual(result["state"], "blocked")
        self.assertNotIn("No input or refresh was attempted", result["result"]["reason"])
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertIsNone(self.runtime._lease)

    def test_older_support_in_same_authority_remains_eligible(self):
        self.bridge.value["actions"].append("open")
        self.start()
        first = self.runtime._current
        self.runtime.command(self.request("observe", request_id="same-authority-observe"))
        self.assertEqual(self.settled("same-authority-observe")["state"], "completed")
        self.assertNotEqual(self.runtime._current, first)
        good = self.control("interact", dict(action="open", intent="Open", desired_outcome="Inspect"),
            request_id="same-authority-support")
        good["sources"].append(first.observation_id)
        self.runtime.command(good)
        result = self.settled(good["request_id"])
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)

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

    def test_new_native_and_interpreted_children_use_admission_deadline_after_refresh(self):
        for interpreted in (False, True):
            with self.subTest(interpreted=interpreted):
                case = RequestBindingTests("test_navigation_metadata_error_has_no_primitive_and_new_request_moves")
                case.setUp()
                try:
                    root, _ = case.native_choices()
                    source = case.runtime._current
                    deadline = case.runtime._ledger.request(root['request_id'])['deadline']
                    view = dict(kind='menu', source_id=source.observation_id, basis='player_interpretation',
                        control='vertical', rows=[dict(label=label, enabled=True) for label in ('One', 'Two', 'Three')],
                        selected=0, question='') if interpreted else None
                    threading.Event().wait(1.05)
                    self.assertGreater(case.runtime._clock() - source.received_monotonic, 1)
                    child = case.control('menu', dict(purpose='Choose', label='Two', outcome='focused'),
                        phase_id=root['request_id'], perception=view, request_id='new-child-old-image',
                        limits=dict(primitives=1, wall_seconds=1, game_seconds=100))
                    self.assertEqual(case.runtime.command(child)['status'], 'accepted')
                    result = case.settled(child['request_id'])
                    self.assertEqual(result['state'], 'partial' if interpreted else 'completed', result)
                    self.assertAlmostEqual(result['deadline'] - result['admitted_at'], 1, places=5)
                    self.assertEqual(case.runtime._ledger.request(root['request_id'])['deadline'], deadline)
                    self.assertEqual(case.bridge.value['ui']['selected'], 'row-1')
                    self.assertEqual(result['result']['revalidation']['original']['source_id'], source.observation_id)
                finally:
                    case.doCleanups()

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
                        # Bootstrap, entry refresh, preflight and ACK retain four
                        # frames. Leave exactly one usable frame, still too few
                        # for another dispatch reservation; keep its assertion.
                        case.a = replace(case.a, limits=replace(case.a.limits, frames=6),
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

    def test_missing_native_rows_refuses_draft_without_refresh_then_explicit_view_proceeds(self):
        self.ready()
        self.assertEqual(self.run_request(self.lifecycle('create'))['state'], 'partial')
        phase = self.runtime._registered_lifecycle.phase
        root = self.runtime._ledger.request('create')['request']
        bad = self.control('missing-native-rows', 'Create World')
        bad['perception'] = None
        result = RequestBindingTests.assert_local_rejection(self, bad, root)
        self.assertIn('visible-control interpretation', result['result']['reason'])
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        self.assertEqual(self.runtime._current, phase.checkpoint)
        corrected = self.run_request(self.control('explicit-visible-world', 'Create World'))
        self.assertEqual(corrected['state'], 'partial', corrected)
        self.assertEqual(self.current()[1]['category'], 'WORLDGEN_CONFIRM_DIALOG')

    def test_missing_native_rows_cannot_mask_authority_evidence_or_budget_faults(self):
        for fault in ('takeover', 'native_drift', 'changed_pixels', 'source_loss', 'wrong_actor',
                      'root_input', 'input_reserve', 'game_cap'):
            with self.subTest(fault=fault):
                case = LifecycleBindingTests(
                    'test_missing_native_rows_refuses_draft_without_refresh_then_explicit_view_proceeds')
                case.setUp()
                try:
                    if fault == 'input_reserve':
                        case.a = replace(case.a, limits=replace(case.a.limits, inputs=2),
                                         cleanup_reserve=replace(case.a.cleanup_reserve, inputs=1))
                    case.ready()
                    root = case.lifecycle('create')
                    if fault == 'root_input':
                        root['limits']['primitives'] = 1
                    self.assertEqual(case.run_request(root)['state'], 'partial')
                    bad = case.control('bad-native-with-real-fault', 'Create World')
                    bad['perception'] = None
                    if fault in ('takeover', 'native_drift'):
                        with case.controller.data_lock:
                            case.controller.state['takeover_generation' if fault == 'takeover' else 'revision'] += 1
                    elif fault == 'changed_pixels':
                        name = f'frame-{case.runtime._current.session}-999999.png'
                        (case.controller.bridge / name).write_bytes(b'\x89PNG\r\n\x1a\nchanged-visible-pixels')
                        with case.controller.data_lock:
                            case.controller.state['frame'] = name
                    elif fault == 'source_loss':
                        Path(case.runtime._current.frame_path).unlink()
                    elif fault == 'wrong_actor':
                        owner = case.runtime._registered_lifecycle.phase
                        case.runtime._registered_lifecycle.phase = replace(owner, actor_id='other-actor')
                    elif fault == 'game_cap':
                        case.runtime._game_cost = case.a.limits.game_seconds
                    spent, delivered = case.runtime.status()['spent_inputs'], copy.deepcopy(case.bridge.delivered)
                    refused = case.run_request(bad)
                    self.assertEqual(refused['state'], 'blocked', refused)
                    self.assertNotIn('No input or refresh was attempted', refused['result']['reason'])
                    self.assertEqual(case.runtime.status()['spent_inputs'], spent)
                    self.assertEqual(case.bridge.delivered, delivered)
                    self.assertIsNone(case.runtime._lease)
                    self.assertIsNone(case.runtime._registered_lifecycle.phase)
                finally:
                    case.doCleanups()

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
        self.assertNotIn(self.runtime._current.observation_id, self.runtime._bindings)
        bad_extra = self.control('bad-extra', 'Yes', parent=root, question=question)
        bad_extra['sources'].append('unpublished-source')
        spent = self.runtime.status()['spent_inputs']
        result = self.run_request(bad_extra)
        self.assertIn('historical support belongs in memory', result['result']['reason'])
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.runtime.status()['spent_inputs'], spent)
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
        self.assertNotIn(self.runtime._current.observation_id, self.runtime._bindings)
        bad_extra = self.control('activity', {**self.goal, 'step': 'answer_interrupt', 'answer': 'YES',
            'interrupt_request_id': phase.interrupt_id}, phase_id='rest-root', request_id='bad-extra-answer')
        bad_extra['sources'].append('unpublished-source')
        spent = self.runtime.status()['spent_inputs']
        self.runtime.command(bad_extra)
        result = self.settled('bad-extra-answer')
        self.assertIn('historical support belongs in memory', result['result']['reason'])
        self.assertIs(self.runtime._registered_activity.phase, phase)
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.runtime.status()['spent_inputs'], spent)
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


class ItemControlDraftTests(unittest.TestCase):
    setUp = item_fixtures.MissionItemTests.setUp
    wait = item_fixtures.MissionItemTests.wait
    request = item_fixtures.MissionItemTests.request
    result = item_fixtures.MissionItemTests.result
    settled = item_fixtures.MissionItemTests.settled
    start = item_fixtures.MissionItemTests.start
    control = item_fixtures.MissionItemTests.control
    send = item_fixtures.MissionItemTests.send
    open_items = item_fixtures.MissionItemTests.open_items
    inventory = item_fixtures.MissionItemTests.inventory
    editor = item_fixtures.MissionItemTests.editor
    select = item_fixtures.MissionItemTests.select
    edit = item_fixtures.MissionItemTests.edit
    open_consumption_selector = item_fixtures.MissionItemTests.open_consumption_selector
    consumption_selection = item_fixtures.MissionItemTests.consumption_selection
    assert_local_rejection = RequestBindingTests.assert_local_rejection

    def bad_menu(self, request_id="wrong-item-menu", *, interpreted=False):
        source = self.runtime._current.observation_id
        perception = None if not interpreted else dict(kind="menu", basis="player_interpretation",
            source_id=source, control="vertical", rows=[dict(label=self.root["goal"]["label"], enabled=True)],
            selected=0, question="")
        return self.control("menu", dict(purpose="Choose visible item", label=self.root["goal"]["label"],
            outcome="activated"), phase_id=self.root["request_id"], perception=perception, request_id=request_id)

    def test_consume_wrong_menu_draft_then_typed_selection_keeps_original_root(self):
        self.open_consumption_selector()
        bad = self.bad_menu()
        refused = self.assert_local_rejection(bad, self.root)
        self.assertIn("typed quantity/selection", refused["result"]["reason"])
        self.assertEqual(self.runtime.command(bad)["operation"], refused)
        corrected = self.consumption_selection("corrected-consume")
        self.assertEqual(self.runtime.command({**corrected, "request_id": bad["request_id"]})["status"], "rejected")
        selected = self.send(corrected)
        self.assertEqual(selected["state"], "partial", selected)
        self.assertEqual(selected["result"]["phase"]["origin_request_id"], self.root["request_id"])
        self.assertEqual(selected["result"]["phase"]["stage"], "activity_poll")
        self.assertEqual(self.runtime._ledger.request(bad["request_id"]), refused)

    def test_consume_wrong_menu_draft_then_explicit_cancel_keeps_original_root(self):
        self.open_consumption_selector()
        self.assert_local_rejection(self.bad_menu(interpreted=True), self.root)
        cancelled = self.send(self.control("menu", dict(purpose="Close consume selector", label="Cancel",
            outcome="dismissed"), phase_id=self.root["request_id"], request_id="cancel-consume",
            perception=dict(kind="dismissal", basis="player_interpretation",
                source_id=self.runtime._current.observation_id, question="Consume item")))
        self.assertEqual(cancelled["result"]["phase"]["stage"], "complete", cancelled)
        self.assertEqual(cancelled["result"]["phase"]["origin_request_id"], self.root["request_id"])
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual([r["intent"]["value"] for r in self.runtime._ledger.primitive_records()], ["eat", "QUIT"])

    def test_premature_editor_then_real_count_opening_and_correct_count(self):
        self.open_items()
        premature = self.edit()
        premature["perception"]["visible_text"] = ""
        self.assert_local_rejection(premature, self.root)
        self.assertEqual(self.send(self.select())["state"], "partial")
        self.assertTrue(self.runtime._prompt_phase.quantity_editor)
        self.assert_local_rejection(self.edit(text="3", request_id="wrong-count"), self.root)
        self.assert_local_rejection(self.edit(purpose="filter", request_id="wrong-purpose"), self.root)
        self.assertEqual(self.send(self.edit(request_id="correct-count"))["state"], "partial")
        self.assertEqual(self.send(self.edit(commit=True, request_id="commit-count"))["state"], "partial")
        completed = self.send(self.select(step="commit"))
        self.assertEqual(completed["result"]["phase"]["stage"], "complete", completed)
        self.assertEqual([r["intent"]["value"] for r in self.runtime._ledger.primitive_records()],
            ["pickup", "MARK_WITH_COUNT", "TEXT.CLEAR", "2", "TEXT.CONFIRM", "CONFIRM"])

    def test_bad_consume_draft_allows_ordinary_escape_without_typed_effect_credit(self):
        self.a = replace(self.a, allowed_skills=(*self.a.allowed_skills, "direct"))
        self.open_consumption_selector()
        refused = self.assert_local_rejection(self.bad_menu(), self.root)
        self.assertIn("ordinary direct input remains available", refused["result"]["reason"])
        self.assertFalse(self.runtime._prompt_phase.quantity_editor)
        spent = self.runtime.status()["spent_inputs"]
        delivered = len(self.bridge.delivered)
        key = dict(type="key", key="ESC", modifiers=[])
        escaped = self.send(self.control("direct", dict(input=key, intent="Close the visible item selector",
            expected="Return to normal play", interrupt_allowed=False), phase_id=self.root["request_id"],
            request_id="ordinary-escape"))
        self.assertEqual(escaped["state"], "partial", escaped)
        self.assertEqual(escaped["result"]["basis"], "ordinary_input")
        self.assertTrue(escaped["result"]["verification_required"])
        self.assertEqual(escaped["result"]["phase"]["origin_request_id"], self.root["request_id"])
        self.assertEqual(escaped["result"]["phase"]["stage"], "complete")
        self.assertIsNone(self.runtime._prompt_phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent + 1)
        self.assertEqual(self.bridge.delivered[delivered:][0]["input"], key)
        self.assertEqual(len(self.bridge.delivered[delivered:]), 1)
        self.assertEqual([p["intent"]["kind"] for p in self.runtime._ledger.primitive_records()], ["action", "direct"])
        self.assertFalse([r for r in self.runtime._ledger.memory_records("claim")
            if r["entry"]["key"]["property"] == "supply"])

    def test_ordinary_input_survives_unfamiliar_menus_changing_after_prior_steps(self):
        # The fixture models changing visible behavior, not a semantic adapter.
        # No production category/action mapping knows these generated screens.
        for change_after in (1, 3):
            with self.subTest(change_after=change_after):
                case = ItemControlDraftTests("test_consume_wrong_menu_draft_then_typed_selection_keeps_original_root")
                case.setUp()
                try:
                    case.a = replace(case.a, allowed_skills=(*case.a.allowed_skills, "direct"))
                    case.open_consumption_selector()
                    case.assert_local_rejection(case.bad_menu(), case.root)
                    deadline = case.runtime._ledger.request(case.root["request_id"])["deadline"]
                    spent = case.runtime.status()["spent_inputs"]
                    original_behavior, steps = case.bridge.behavior, []
                    def behavior(bridge, request):
                        if request["kind"] == "direct" and request["input"]["key"] == "x":
                            steps.append(request)
                            if len(steps) >= change_after:
                                bridge.value.update(category=f"UNSEEN_VIEW_{change_after}_{len(steps)}",
                                    actions=["ANY_INPUT"], ui=None)
                                bridge.editor_text = f"Changed labels/layout {len(steps)}"
                                bridge.value["boundary"]["id"] = f"unseen-{len(steps)}"
                            return True
                        return original_behavior(bridge, request)
                    case.bridge.behavior = behavior
                    for step in range(4):
                        result = case.send(case.control("direct", dict(
                            input=dict(type="key", key="x", modifiers=[]),
                            intent="Try ordinary input on the currently visible screen",
                            expected="Inspect the returned screen; no semantic outcome certified",
                            interrupt_allowed=False), phase_id=case.root["request_id"],
                            request_id=f"try-ordinary-{step}"))
                        self.assertEqual(result["state"], "partial", result)
                        self.assertTrue(result["result"]["verification_required"])
                        self.assertEqual(case.runtime._prompt_phase.root_id, case.root["request_id"])
                        self.assertFalse(case.runtime._prompt_phase.quantity_editor)
                        self.assertEqual(case.runtime._ledger.request(case.root["request_id"])["deadline"], deadline)
                    self.assertEqual(len(steps), 4)
                    self.assertTrue(case.runtime._store.observation(case.runtime._current)["category"].startswith("UNSEEN_VIEW_"))
                    cancelled = case.send(case.control("direct", dict(
                        input=dict(type="key", key="ESC", modifiers=[]),
                        intent="Cancel the current unfamiliar screen", expected="Inspect return",
                        interrupt_allowed=False), phase_id=case.root["request_id"], request_id="ordinary-cancel"))
                    self.assertEqual(cancelled["state"], "partial", cancelled)
                    self.assertIsNone(case.runtime._prompt_phase)
                    self.assertEqual(case.runtime.status()["phase"], "active")
                    self.assertEqual(case.runtime.status()["spent_inputs"], spent + 5)
                    self.assertEqual(case.runtime._current.boundary_kind, "normal_play")
                finally:
                    case.doCleanups()

    def age_source(self, source):
        freshness = self.runtime._store._fresh
        def aged(entry, now_monotonic, now_timestamp_ms):
            if entry.reference == source:
                now_monotonic, now_timestamp_ms = source.received_monotonic + 4, source.timestamp_ms + 4000
            return freshness(entry, now_monotonic, now_timestamp_ms)
        return patch.object(self.runtime._store, "_fresh", side_effect=aged)

    def test_aged_unchanged_item_draft_does_not_refresh_and_new_selection_revalidates(self):
        self.open_items()
        original = self.runtime._current
        with self.age_source(original):
            self.assertFalse(self.runtime._store.inspect_current_boundary(**self.runtime._clocks())[1])
            self.assert_local_rejection(self.bad_menu(), self.root)
            selected = self.send(self.select())
        self.assertEqual(selected["state"], "partial", selected)
        self.assertEqual(selected["result"]["revalidation"]["original"]["source_id"], original.observation_id)
        self.assertTrue(self.runtime._prompt_phase.quantity_editor)

    def test_aged_changed_pixels_stop_item_draft_even_without_perception(self):
        self.open_items()
        bad = self.bad_menu()
        source = self.runtime._current
        name = f"frame-{source.session}-999999.png"
        (self.controller.bridge / name).write_bytes(b"\x89PNG\r\n\x1a\nchanged visible item selector")
        with self.controller.data_lock:
            self.controller.state["frame"] = name
        before, spent = copy.deepcopy(self.bridge.delivered), self.runtime.status()["spent_inputs"]
        with self.age_source(source):
            refused = self.send(bad)
        self.assertIn("changed native pixels", refused["result"]["reason"])
        self.assertNotIn("No input or refresh was attempted", refused["result"]["reason"])
        self.assertEqual(self.bridge.delivered, before)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertIsNone(self.runtime._lease)
        self.assertIsNone(self.runtime._prompt_phase)

    def test_item_draft_cannot_conceal_authority_evidence_or_budget_faults(self):
        faults = ("takeover", "native_drift", "wrong_actor", "wrong_epoch", "lease", "operator_pause",
            "checkpoint", "binding", "source_loss", "source_disputed", "game_cap", "game_unknown",
            "input_reserve", "root_input", "capacity_tail", "deadline", "unsettled")
        for fault in faults:
            with self.subTest(fault=fault):
                case = ItemControlDraftTests("test_consume_wrong_menu_draft_then_typed_selection_keeps_original_root")
                case.setUp()
                try:
                    if fault == "input_reserve":
                        case.a = replace(case.a, limits=replace(case.a.limits, inputs=2),
                            cleanup_reserve=replace(case.a.cleanup_reserve, inputs=1))
                    elif fault == "capacity_tail":
                        case.a = replace(case.a, limits=replace(case.a.limits, frames=6),
                            cleanup_reserve=replace(case.a.cleanup_reserve, frames=1))
                    case.open_items(primitives=2 if fault == "root_input" else 16)
                    if fault == "root_input":
                        self.assertEqual(case.send(case.select())["state"], "partial")
                    bad = case.bad_menu()
                    phase, current = case.runtime._prompt_phase, case.runtime._current
                    if fault in ("takeover", "native_drift", "operator_pause"):
                        with case.controller.data_lock:
                            if fault == "operator_pause":
                                case.controller.operator_pause_generation += 1
                            else:
                                case.controller.state["takeover_generation" if fault == "takeover" else "revision"] += 1
                    elif fault in ("wrong_actor", "wrong_epoch"):
                        case.runtime._prompt_phase = replace(phase, **({"actor_id": "other-player"} if fault == "wrong_actor"
                            else {"epoch": phase.epoch + 1}))
                    elif fault == "lease":
                        case.runtime._lease = None
                    elif fault == "checkpoint":
                        case.runtime._prompt_phase = replace(phase, checkpoint=phase.game_anchor)
                    elif fault == "binding":
                        ref, binding = case.runtime._bindings[current.observation_id]
                        case.runtime._bindings[current.observation_id] = (ref, replace(binding,
                            store_generation=binding.store_generation + 1))
                    elif fault == "source_loss":
                        Path(current.frame_path).unlink()
                    elif fault == "source_disputed":
                        case.runtime._store._disputed.append(current.observation_id)
                    elif fault in ("game_cap", "game_unknown"):
                        case.runtime._game_cost = None if fault == "game_unknown" else case.a.limits.game_seconds
                    elif fault == "capacity_tail":
                        self.assertEqual(case.a.limits.frames - case.a.cleanup_reserve.frames
                            - case.runtime._store.usage()["frames"], 1)
                    elif fault == "deadline":
                        case.runtime._mission_deadline = case.runtime._wall() + case.a.cleanup_reserve.wall_seconds
                    elif fault == "unsettled":
                        pending = case.select()
                        pending["request_id"] = "pending-item-selection"
                        case.runtime._ledger.begin_request(pending, now=case.runtime._wall())
                        reservation = case.runtime._store.reserve_dispatch(current, **case.runtime._clocks())
                        case.runtime._ledger.prepare_primitive(pending["request_id"], "pending-item-input", intent(
                            source_before=current.observation_id, preflight_source=current.observation_id,
                            expected_session=current.session, expected_revision=current.revision,
                            expected_boundary_id=bad["expected_boundary_id"], reservation_id=reservation.token),
                            now=case.runtime._wall())
                    # The unsettled fixture charges a real prepared primitive
                    # directly; the cached published status has not seen it yet.
                    delivered = copy.deepcopy(case.bridge.delivered)
                    spent = case.runtime._ledger.snapshot(now=case.runtime._wall())["spent_inputs"]
                    refused = case.send(bad)
                    self.assertEqual(refused["state"], "blocked", refused)
                    self.assertNotIn("No input or refresh was attempted", refused["result"]["reason"])
                    self.assertEqual(case.bridge.delivered, delivered)
                    self.assertEqual(case.runtime.status()["spent_inputs"], spent)
                    self.assertIsNone(case.runtime._lease)
                    self.assertIsNone(case.runtime._prompt_phase)
                finally:
                    case.doCleanups()


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
