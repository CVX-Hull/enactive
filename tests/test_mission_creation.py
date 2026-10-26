"""Real mission writer/SQLite/transport with synthetic UI; not CDDA acceptance.

These tests never patch identity adoption, lifecycle guards or receipt validation.
The fake bridge supplies controlled visible boundaries and expected session loss.
"""
import copy
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from harness.mission_runtime import MissionRuntime
from harness.gameplay.lifecycle import adopted_timeline
from harness.gameplay.evidence import EvidenceError
from harness.gameplay.mission_contracts import LearningPolicy, LibrarySource
from tests import test_mission_launch as launch_fixtures
from tests import test_procedure_library as library_fixtures
from tests.test_gameplay_evidence import observation
from tests.test_mission_contracts import claim


@contextmanager
def expire_selected_at_dispatch(runtime, selected):
    """Age only the selected capture through the real freshness validator."""
    expired = threading.Event()
    freshness, dispatch = runtime._store._fresh, runtime._dispatch

    def source_age(entry, now_monotonic, now_timestamp_ms):
        if entry.reference == selected:
            age = 3.05 if expired.is_set() else 2.95
            now_monotonic = selected.received_monotonic + max(0, age - entry.initial_lag_seconds)
            now_timestamp_ms = selected.timestamp_ms + round(age * 1000)
        return freshness(entry, now_monotonic, now_timestamp_ms)

    def cross_boundary(*args, **kwargs):
        expired.set()
        return dispatch(*args, **kwargs)

    with patch.object(runtime._store, "_fresh", side_effect=source_age), \
            patch.object(runtime, "_dispatch", side_effect=cross_boundary):
        yield


class MissionCreationFixture:
    setUp = launch_fixtures.MissionLaunchTests.setUp
    start = launch_fixtures.MissionLaunchTests.start
    settled = launch_fixtures.MissionLaunchTests.settled
    launch = launch_fixtures.MissionLaunchTests.launch
    request = launch_fixtures.MissionLaunchTests.request

    def fake_launch(self, *, deadline_monotonic, cancelled):
        self.assertFalse(cancelled())
        self.assertGreater(deadline_monotonic, time.monotonic())
        self.launch_count = getattr(self, "launch_count", 0) + 1
        self.process_state.update(launch_id=f"owned-launch-{self.launch_count}", pid=1234,
            running=True, returncode=None, outcome="running")
        self.bridge.value.update(session=f"menu-{self.launch_count}", paused=True, pause_origin="startup")
        self.menu("MAIN_MENU", ["CONFIRM", "QUIT"])
        return copy.deepcopy(self.process_state)

    def menu(self, category, actions, *, in_game=False):
        self.bridge.value.update(category=category, actions=actions, scene=None, ui=None, in_game=in_game)
        self.bridge.value["boundary"]["kind"] = "menu"
        self.bridge.value["boundary"]["id"] = f'{category}-{self.bridge.value["revision"]}'

    def normal(self, session, *, paused=False):
        scene = observation()["scene"]
        scene.update(turn=self.turn, provenance="player-visible input boundary")
        self.bridge.value.update(session=session, category="DEFAULTMODE", scene=scene, ui=None, in_game=True,
            paused=paused, pause_origin="world_change" if paused else "none",
            actions=["player_data", "save", "UP", "DOWN", "LEFT", "RIGHT"])
        self.bridge.value["boundary"].update(kind="normal_play", id=f'normal-{self.bridge.value["revision"]}')

    def behavior(self, bridge, request):
        action, category = request.get("action"), bridge.value["category"]
        if request["kind"] in ("observe", "resume"):
            return True
        if category == "MAIN_MENU" and action == "QUIT":
            self.stage = "exit"
            self.menu("YESNO", ["YES", "NO"])
        elif category == "MAIN_MENU" and action == "CONFIRM":
            if self.stage == "world":
                self.menu("WORLDGEN_CONFIRM_DIALOG", ["UP", "DOWN", "CONFIRM", "FINALIZE"])
            elif self.stage == "load-world":
                self.stage = "load"
                self.menu("UILIST", ["UILIST.UP", "UILIST.DOWN", "CONFIRM", "UILIST.QUIT"])
                rows = [
                    dict(id="row-0", text=self.a.scenario.character, enabled=True, hotkey=None),
                    dict(id="row-1", text="<- Back to Main Menu", enabled=True, hotkey="q")]
                bridge.value["ui"] = dict(purpose="uilist", title="",
                    rows=copy.deepcopy(getattr(self, "load_rows", rows)),
                    selected=getattr(self, "load_selected", "row-0"),
                    filter=None, count=None, coverage="rendered_rows_only")
            else:
                self.menu("NEW_CHAR_DESCRIPTION", ["PREV_TAB", "NEXT_TAB", "CONFIRM"])
        elif category == "WORLDGEN_CONFIRM_DIALOG" and action == "FINALIZE":
            self.stage = "world-confirmation"
            self.menu("YESNO", ["YES", "NO"])
        elif category in ("WORLDGEN_CONFIRM_DIALOG", "NEW_CHAR_DESCRIPTION") and action == "CONFIRM":
            self.editor_parent = category
            self.bridge.editor_text = "Old"
            self.menu("STRING_INPUT", ["TEXT.CLEAR", "TEXT.CONFIRM", "TEXT.QUIT"])
        elif category == "STRING_INPUT":
            if action == "TEXT.CLEAR":
                self.bridge.editor_text = ""
            elif request["kind"] == "key":
                self.bridge.editor_text += request["key"]
            elif action == "TEXT.CONFIRM":
                actions = (["UP", "DOWN", "CONFIRM", "FINALIZE"] if self.editor_parent == "WORLDGEN_CONFIRM_DIALOG"
                    else ["PREV_TAB", "NEXT_TAB", "CONFIRM"])
                self.menu(self.editor_parent, actions)
        elif category == "UILIST" and action == "CONFIRM" and self.stage == "load":
            self.normal(f"normal-{self.launch_count}", paused=True)
            return False
        elif category == "UILIST" and action == "UILIST.QUIT" and self.stage == "load":
            self.stage = "load-world"
            self.menu("MAIN_MENU", ["CONFIRM", "QUIT"])
        elif category == "NEW_CHAR_DESCRIPTION" and action == "NEXT_TAB":
            self.stage = "points-confirmation" if getattr(self, "spare_points", False) else "character-confirmation"
            self.menu("YESNO", ["YES", "NO"])
        elif category == "YESNO" and action == "YES":
            if self.stage == "points-confirmation":
                self.stage = "character-confirmation"
                self.menu("YESNO", ["YES", "NO"])
            elif self.stage == "world-confirmation":
                self.stage = "character"
                self.menu("MAIN_MENU", ["CONFIRM", "QUIT"])
            elif self.stage == "character-confirmation":
                self.normal(f"normal-{self.launch_count}", paused=True)
                return False
            elif self.stage == "save":
                bridge.value.update(session=f"saved-menu-{self.launch_count}", paused=True, pause_origin="world_change")
                self.menu("MAIN_MENU", ["CONFIRM", "QUIT"])
                return False
            elif self.stage == "exit":
                self.process_state.update(running=False, returncode=0, outcome="exited")
                return False
        elif category == "DEFAULTMODE" and action == "player_data":
            self.menu("PLAYER_INFO", ["QUIT", "CONFIRM"], in_game=True)
        elif category == "PLAYER_INFO" and action == "QUIT":
            self.normal(f"normal-{self.launch_count}")
        elif category == "DEFAULTMODE" and action == "save":
            self.stage = "save"
            self.menu("YESNO", ["YES", "NO"], in_game=True)
        elif category == "YESNO" and action == "NO" and self.stage == "save":
            self.normal(f"normal-{self.launch_count}")
        return True

    def ready(self):
        self.turn, self.stage = 10, "world"
        self.bridge.behavior = self.behavior
        self.process.wait_exit.side_effect = lambda **_: copy.deepcopy(self.process_state)
        self.start()
        self.assertEqual(self.launch()["state"], "completed")

    def run_request(self, data):
        response = self.runtime.command(data)
        self.assertEqual(response["status"], "accepted", response)
        return self.settled(data["request_id"])

    def current(self):
        reference = self.runtime._current
        return reference, self.runtime._store.observation(reference)

    def lifecycle(self, identity, operation="create", *, parent=None, claims=None):
        ref, observed = self.current()
        return self.request(identity=identity, operation=operation, phase_id=parent,
            sources=[ref.observation_id], expected_session=ref.session, expected_revision=ref.revision,
            expected_boundary_id=observed["boundary"]["id"], identity_claim_ids=claims or [],
            limits=dict(primitives=32, wall_seconds=120, game_seconds=1000))

    def control(self, identity, label, *, parent="create", kind="menu", question=None, purpose=None):
        ref, observed = self.current()
        perception = dict(source_id=ref.observation_id, basis="player_interpretation")
        if kind == "inspect":
            perception = None
            goal = dict(purpose="character_identity")
        elif question is not None:
            perception.update(kind="confirmation", question=question)
            goal = dict(purpose=purpose or "Answer actual lifecycle confirmation", label=label, outcome="activated")
        elif label == "Cancel":
            perception.update(kind="dismissal", question="Return from character information")
            goal = dict(purpose="Return", label="Cancel", outcome="dismissed")
        else:
            perception.update(kind="menu", control="vertical", rows=[dict(label=label, enabled=True)], selected=0, question="")
            goal = dict(purpose=purpose or "Select visible setup option", label=label, outcome="activated")
        return dict(schema="mission/11", kind="skill", request_id=identity, mission_id=self.a.mission_id,
            epoch=self.runtime.status()["epoch"], skill_kind=kind, phase_id=parent, work_id=None,
            sources=[ref.observation_id], expected_session=ref.session, expected_revision=ref.revision,
            expected_boundary_id=observed["boundary"]["id"], perception=perception, goal=goal,
            limits=dict(primitives=8, wall_seconds=30, game_seconds=100), procedure=None)

    def remember_identity(self, identity, subject, ref, epoch, *, value=None):
        entry = claim(id=identity, key=dict(subject=subject, property="identity", unit="name",
            coverage_id="visible-world-menu" if subject == "world" else "visible-character-screen"),
            value=dict(quantity=None, state=value or getattr(self.a.scenario, subject)),
            scope=dict(mission_id=self.a.mission_id, session=ref.session, coordinate_epoch=epoch),
            observed_time=dict(revision=ref.revision, turn=ref.turn), received_time=int(time.time() * 1000),
            sources=[ref.observation_id], supports=[dict(sources=[ref.observation_id], claims=[])])
        operation = self.run_request(dict(schema="mission/11", kind="remember", request_id=f"remember-{identity}",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"], entry_type="claim", entry=entry))
        self.assertEqual(operation["state"], "completed", operation)
        return entry["id"]

    def finish_identity(self, root, world_source, epoch=0, *, diagnostic_observe=False):
        kind = "create" if epoch == 0 and self.a.scenario.mode == "fresh" else "load"
        operation = self.run_request(self.lifecycle(f"{root}-reconcile", kind, parent=root))
        self.assertEqual(operation["state"], "completed", operation)
        self.assertEqual(self.runtime.status()["lifecycle_phase"]["stage"], "awaiting_identity")
        self.assertIsNone(self.runtime.status()["metrics"]["game_seconds"])
        self.assertIsNone(self.runtime._map)
        self.assertEqual(self.runtime._bindings, {})
        if diagnostic_observe:
            self.observe(f"{root}-identity-observe")
        readmit = self.run_request(self.lifecycle(f"{root}-readmit", kind, parent=root))
        self.assertEqual(readmit["state"], "completed", readmit)
        inspection = self.run_request(self.control(f"{root}-inspect", "Character", kind="inspect", parent=root))
        self.assertEqual(inspection["state"], "completed", inspection)
        screen = self.runtime._current
        world_id = self.remember_identity(f"{root}-world", "world", world_source, epoch)
        character_id = self.remember_identity(f"{root}-character", "character", screen, epoch)
        returned = self.run_request(self.control(f"{root}-return", "Cancel", parent=root))
        self.assertEqual(returned["state"], "partial", returned)
        adopted = self.run_request(self.lifecycle(f"{root}-adopt", kind, parent=root,
            claims=[world_id, character_id]))
        self.assertEqual(adopted["state"], "completed", adopted)
        return adopted

    def create(self):
        self.ready()
        self.assertEqual(self.run_request(self.lifecycle("create"))["state"], "partial")
        self.assertEqual(self.run_request(self.control("world-form", "Create World"))["state"], "partial")
        world = self.runtime._current
        self.assertEqual(self.run_request(self.lifecycle("world-finalize", parent="create"))["state"], "partial")
        self.assertEqual(self.run_request(self.control("world-yes", "Yes", question="Are you SURE you're finished?"))["state"], "partial")
        self.assertEqual(self.run_request(self.control("character-menu", "Custom Character"))["state"], "partial")
        self.assertEqual(self.run_request(self.lifecycle("character-finish", parent="create"))["state"], "partial")
        if getattr(self, "spare_points", False):
            points = self.run_request(self.control("points-yes", "Yes",
                question="Remaining points will be discarded, are you sure you want to proceed?"))
            self.assertEqual(points["state"], "partial", points)
            self.assertIsNone(self.runtime._registered_lifecycle.candidate)
        entered = self.run_request(self.control("character-yes", "Yes", question="Are you SURE you're finished?"))
        self.assertEqual(entered["state"], "unknown", entered)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNotNone(self.runtime._registered_lifecycle.candidate)
        observed = self.run_request(dict(schema="mission/11", kind="observe", request_id="create-observe",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"]))
        self.assertEqual(observed["state"], "completed", observed)
        return self.finish_identity("create", world)

    def observe(self, identity):
        operation = self.run_request(dict(schema="mission/11", kind="observe", request_id=identity,
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"]))
        self.assertEqual(operation["state"], "completed", operation)
        return operation

    def save(self):
        begun = self.run_request(self.lifecycle("save", "save"))
        self.assertEqual(begun["state"], "partial", begun)
        answered = self.run_request(self.control("save-yes", "Yes", parent="save", question="Save and quit?"))
        self.assertEqual(answered["state"], "unknown", answered)
        self.observe("save-observe-first")
        first = self.runtime._current
        self.observe("save-observe-second")
        self.assertNotEqual(first, self.runtime._current)
        request = self.lifecycle("save-reconcile", "save", parent="save")
        request["sources"].append(first.observation_id)
        operation = self.run_request(request)
        self.assertEqual(operation["state"], "completed", operation)
        return operation

    def exit(self, root="exit"):
        begun = self.run_request(self.lifecycle(root, "exit"))
        self.assertEqual(begun["state"], "partial", begun)
        finished = self.run_request(self.control(f"{root}-yes", "Yes", parent=root, question="Really quit?"))
        self.assertEqual(finished["state"], "completed", finished)
        return finished


class MissionCreationTests(MissionCreationFixture, unittest.TestCase):
    def test_shared_collection_diagnostic_preserves_original_settled_operation(self):
        self.start()
        request = self.request("collection-diagnostic-launch")
        self.runtime.command(request)
        original = self.settled(request["request_id"])
        deadline = self.runtime._ledger.request(request["request_id"])["deadline"]
        inputs = self.runtime.status()["spent_inputs"]
        command = self.runtime.command
        reads = []

        def delayed_cache_read(data):
            response = command(data)
            reads.append(data["operation_id"])
            if len(reads) == 1:
                response = {**response, "operation": None}
            return response

        # Change only the borrowed collector's clock, never the runtime clock or
        # execution deadline. One unavailable cache read crosses its diagnostic
        # threshold; the next collects the same completed original operation.
        clock = iter((0, 0, 4, 4))
        with patch.object(launch_fixtures, "time", SimpleNamespace(monotonic=lambda: next(clock))), \
                patch.object(self.runtime, "command", side_effect=delayed_cache_read), \
                self.assertWarnsRegex(RuntimeWarning, "Functional collection exceeded 3 seconds"):
            collected = self.settled(request["request_id"])
        self.assertEqual(reads, [request["request_id"]] * 2)
        self.assertEqual(collected, original)
        self.assertEqual(self.collection_checkpoints[request["request_id"]]["ledger"]["state"], "completed")
        self.assertFalse(self.collection_checkpoints[request["request_id"]]["cached_result"])
        self.assertEqual(self.runtime._ledger.request(request["request_id"])["deadline"], deadline)
        self.assertEqual(self.runtime.status()["spent_inputs"], inputs)

    def test_premature_stage_commit_preserves_create_for_player_control(self):
        self.ready()
        self.assertEqual(self.run_request(self.lifecycle("create"))["state"], "partial")
        phase, lease = self.runtime._registered_lifecycle.phase, self.runtime._lease
        deadline = self.runtime._ledger.request("create")["deadline"]
        delivered = len(self.bridge.delivered)
        refused = self.run_request(self.lifecycle("premature-create", parent="create"))
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertIn("No input was sent", refused["result"]["reason"])
        self.assertIs(self.runtime._registered_lifecycle.phase, phase)
        self.assertIs(self.runtime._lease, lease)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertEqual(self.runtime._ledger.request("create")["deadline"], deadline)
        self.assertEqual(self.run_request(self.control("world-form", "Create World"))["state"], "partial")
        committed = self.run_request(self.lifecycle("world-finalize", parent="create"))
        self.assertEqual(committed["state"], "partial", committed)
        self.assertEqual(self.current()[1]["category"], "YESNO")

    def unexpected_setup_input(self, *, changed_session=True, returned=False, root_primitives=32):
        self.ready()
        root = self.lifecycle("create")
        root["limits"]["primitives"] = root_primitives
        self.assertEqual(self.run_request(root)["state"], "partial")
        original = self.behavior

        def unexpected(bridge, request):
            if request["kind"] == "observe" and bridge.value["paused"]:
                bridge.value["pause_origin"] = "host"
            if request.get("action") == "CONFIRM":
                if changed_session or returned:
                    self.normal("unregistered-normal" if changed_session else "menu-1", paused=True)
                else:
                    self.menu("WORLDGEN_CONFIRM_DIALOG", ["CONFIRM", "FINALIZE"])
                return returned
            return original(bridge, request)

        self.bridge.behavior = unexpected
        operation = self.run_request(self.control("unregistered-selection", "Explore an unfamiliar option"))
        self.assertEqual(operation["state"], "blocked" if returned else "unknown", operation)
        return operation

    def test_diagnostic_only_transition_does_not_offer_same_root_reconciliation(self):
        self.unexpected_setup_input()
        candidate = self.runtime._registered_lifecycle.candidate
        primitives = copy.deepcopy(self.runtime._ledger.primitive_records())
        response = self.runtime.command(self.control("unsupported-child", "Cancel"))
        self.assertEqual(response["status"], "rejected", response)
        self.assertIn("diagnostic-only", response["reason"])
        self.assertIn("cannot establish transition reconciliation", response["reason"])
        self.assertNotIn("still requires same-root reconciliation", response["reason"])
        self.assertIs(self.runtime._registered_lifecycle.candidate, candidate)
        self.assertEqual(self.runtime._ledger.primitive_records(), primitives)
        self.assertIsNone(self.runtime._lease)

    def test_unexpected_published_setup_transition_is_retained_only_as_diagnostic(self):
        original = self.unexpected_setup_input()
        primitive = self.runtime._ledger.primitive_records()[-1]
        root = self.runtime._ledger.request("create")
        deadline = self.runtime._mission_deadline
        costs = self.runtime.status()["spent_inputs"]
        epoch = self.runtime.status()["epoch"]
        candidate = self.runtime._registered_lifecycle.candidate
        self.assertIsNotNone(candidate)
        self.assertTrue(candidate.diagnostic_only)
        self.assertIsNone(self.runtime.status()["lifecycle_phase"])
        self.assertNotIn("phase", original["result"])
        self.assertEqual(candidate.logical_id, primitive["logical_id"])
        self.assertEqual(candidate.phase.root_id, "create")
        first = None
        for identity in ("unexpected-first", "unexpected-second"):
            observed = self.observe(identity)
            reference = self.runtime._current
            self.assertEqual(reference.session, "unregistered-normal")
            self.assertEqual(Path(reference.frame_path).read_bytes(), self.bridge.visible_bytes(self.bridge.value))
            self.assertIn(reference.observation_id, observed["result"]["source_ids"])
            self.assertIn("diagnostic", observed["result"]["reason"].lower())
            self.assertNotIn("phase", observed["result"])
            self.assertFalse(observed["result"]["grants_authority"])
            self.assertEqual(self.runtime._ledger.primitive(primitive["logical_id"]), primitive)
            self.assertEqual(self.runtime._ledger.request("create"), root)
            self.assertEqual(self.runtime._ledger.request("unregistered-selection"), original)
            self.assertEqual(self.runtime.status()["epoch"], epoch)
            self.assertEqual(self.runtime.status()["spent_inputs"], costs)
            self.assertEqual(self.runtime._mission_deadline, deadline)
            self.assertIsNone(self.runtime.status()["metrics"]["game_seconds"])
            self.assertIsNone(self.runtime._map)
            self.assertEqual(self.runtime._bindings, {})
            self.assertIsNone(self.runtime._lease)
            self.assertEqual(self.runtime._ledger.memory_records("claim"), ())
            self.assertIsNone(self.runtime.status()["lifecycle_phase"])
            if first is None:
                first = reference
            else:
                self.assertNotEqual(first, reference)
                self.assertIn(first.observation_id, observed["result"]["source_ids"])
                self.assertEqual(self.runtime._registered_lifecycle.candidate.first_after, first)
        records = [event["outcome"] for event in self.controller.events
            if event["request"]["kind"] == "mission_lifecycle_diagnostic"]
        self.assertTrue(records)
        self.assertTrue(all(record["origin_request_id"] == "create"
            and record["logical_action_id"] == primitive["logical_id"]
            and record["native_request_id"] == primitive["native_id"]
            and record["source_before"] == primitive["intent"]["source_before"] for record in records))
        self.assertIsNone(self.runtime._store._reservation)
        self.assertEqual(sum(row.get("action") == "CONFIRM" for row in self.bridge.delivered), 1)
        rejected = self.run_request(self.lifecycle("diagnostic-reconcile", parent="create"))
        self.assertEqual(rejected["state"], "blocked", rejected)
        self.assertNotIn("lifecycle_transition", rejected["result"])
        self.assertIsNone(self.runtime._ledger.primitive(primitive["logical_id"])["effect"])

    def test_unknown_same_session_setup_input_remains_explicitly_observable(self):
        self.unexpected_setup_input(changed_session=False)
        operation = self.observe("same-session-diagnostic")
        self.assertEqual(self.runtime._current.session, "menu-1")
        self.assertIn("Diagnostic-only", operation["result"]["reason"])
        self.assertNotIn("phase", operation["result"])
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)

    def test_unknown_same_session_editor_key_is_diagnostic_without_advancing_stage(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.run_request(self.control("world-form", "Create World"))
        self.run_request(self.control("world-name-field", "World name"))
        original = self.behavior

        def missing_key_ack(bridge, request):
            result = original(bridge, request)
            if request["kind"] == "observe" and bridge.value["paused"]:
                bridge.value["pause_origin"] = "host"
            return False if request["kind"] == "key" else result

        self.bridge.behavior = missing_key_ack
        request = self.control("unknown-editor", "World name")
        request.update(skill_kind="edit", goal=dict(purpose="world_name", text=self.a.scenario.world, commit=False),
            perception=dict(kind="editor", source_id=self.runtime._current.observation_id,
                basis="player_interpretation", purpose="world_name", label="World name",
                visible_text="Old", whole_value=True, focused=True))
        self.assertEqual(self.run_request(request)["state"], "unknown")
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(primitive["intent"]["kind"], "key")
        observed = self.observe("editor-diagnostic")
        self.assertIn("Diagnostic-only", observed["result"]["reason"])
        self.assertEqual(self.current()[1]["category"], "STRING_INPUT")
        self.assertEqual(Path(self.runtime._current.frame_path).read_bytes(), self.bridge.visible_bytes(self.bridge.value))
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._ledger.primitive(primitive["logical_id"])["effect"])
        self.assertEqual(sum(row["kind"] == "key" for row in self.bridge.delivered), 1)

    def test_known_returned_unexpected_normal_remains_diagnostic(self):
        self.unexpected_setup_input(changed_session=False, returned=True)
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(primitive["state"], "returned")
        self.assertIsNotNone(primitive["result"]["native_ack"])
        self.observe("known-unexpected-observe")
        self.assertEqual(self.runtime._ledger.primitive(primitive["logical_id"]), primitive)
        self.assertIsNone(self.runtime.status()["metrics"]["game_seconds"])

    def test_known_returned_capture_failure_releases_reservation_once_and_retains_correlation(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        original = self.behavior

        def unexpected(bridge, request):
            if request.get("action") == "CONFIRM":
                self.normal("menu-1", paused=True)
                return True
            return original(bridge, request)

        self.bridge.behavior = unexpected
        with patch.object(self.runtime._store, "retain_terminal", side_effect=EvidenceError("capture lost")), \
                patch.object(self.runtime._store, "release", wraps=self.runtime._store.release) as released:
            operation = self.run_request(self.control("known-capture-loss", "An unfamiliar option"))
        self.assertEqual(operation["state"], "blocked", operation)
        released.assert_called_once()
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual(primitive["state"], "returned")
        self.assertIsNone(self.runtime._registered_lifecycle.candidate.reservation)
        self.assertIsNone(self.runtime._store._reservation)
        self.observe("known-capture-loss-observe")
        self.assertEqual(self.runtime._ledger.primitive(primitive["logical_id"]), primitive)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)

    def test_exhausted_original_primitive_allowance_still_permits_diagnostic_observe(self):
        self.unexpected_setup_input(root_primitives=2)
        root = self.runtime._ledger.request("create")
        self.assertEqual(self.runtime._ledger._phase_primitive_count("create"), 2)
        observed = self.observe("exhausted-input-diagnostic")
        self.assertIn("Diagnostic-only", observed["result"]["reason"])
        self.assertEqual(self.runtime._ledger.request("create"), root)
        self.assertEqual(self.runtime.status()["spent_inputs"], 2)
        self.assertIsNone(self.runtime._lease)

    def reject_diagnostic_observation(self):
        current = self.runtime._current
        delivered = len(self.bridge.delivered)
        response = self.runtime.command(dict(schema="mission/11", kind="observe", request_id="denied-diagnostic",
            mission_id=self.a.mission_id, epoch=self.runtime.status()["epoch"]))
        if response["status"] == "accepted":
            operation = self.settled("denied-diagnostic")
        else:
            self.assertEqual(response["status"], "rejected", response)
            operation = dict(state="blocked", result=response)
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertEqual(self.runtime._current, current)
        self.assertEqual(len(self.bridge.delivered), delivered)
        self.assertIsNone(self.runtime._lease)
        return operation

    def test_diagnostic_observe_cannot_cross_foreign_owned_process(self):
        self.unexpected_setup_input()
        self.process_state["launch_id"] = "foreign-launch"
        self.assertIn("child", self.reject_diagnostic_observation()["result"]["reason"])

    def test_diagnostic_observe_cannot_cross_operator_pause(self):
        self.unexpected_setup_input()
        self.runtime.pause("Operator revokes diagnostic custody")
        self.reject_diagnostic_observation()

    def test_diagnostic_observe_cannot_cross_native_takeover(self):
        self.unexpected_setup_input()
        self.bridge.value["takeover_generation"] += 1
        self.reject_diagnostic_observation()

    def test_diagnostic_observe_cannot_cross_original_root_deadline(self):
        self.unexpected_setup_input()
        deadline = self.runtime._ledger.request("create")["deadline"]
        with patch.object(self.runtime, "_wall", return_value=deadline + 0.01):
            self.assertIn("deadline", self.reject_diagnostic_observation()["result"]["reason"])

    def test_diagnostic_observe_cannot_consume_cleanup_frame_reserve(self):
        self.unexpected_setup_input()
        usage = self.runtime._store.usage()
        admission = replace(self.runtime._admission, limits=replace(self.a.limits,
            frames=usage["frames"] + self.a.cleanup_reserve.frames))
        with patch.object(self.runtime, "_admission", admission):
            self.assertIn("reserve", self.reject_diagnostic_observation()["result"]["reason"])

    def test_diagnostic_observe_rejects_mismatched_private_dispatch(self):
        self.unexpected_setup_input()
        candidate = self.runtime._registered_lifecycle.candidate
        self.runtime._registered_lifecycle.candidate = replace(candidate,
            native_request={**candidate.native_request, "id": "foreign-dispatch"})
        self.assertIn("dispatch", self.reject_diagnostic_observation()["result"]["reason"])

    def test_diagnostic_observe_rejects_mismatched_private_reservation(self):
        self.unexpected_setup_input()
        candidate = self.runtime._registered_lifecycle.candidate
        self.runtime._registered_lifecycle.candidate = replace(candidate,
            reservation=replace(candidate.reservation, token="foreign-reservation"))
        self.assertIn("reservation", self.reject_diagnostic_observation()["result"]["reason"])

    def test_unpublished_setup_input_cannot_create_diagnostic_candidate(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.assertIsNone(self.runtime._registered_lifecycle.candidate)
        self.bridge.value["actions"].append("CHANGED")
        operation = self.run_request(self.control("unpublished-option", "An unfamiliar option"))
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertIsNone(self.runtime._registered_lifecycle.candidate)
        self.assertEqual(sum(row.get("action") == "CONFIRM" for row in self.bridge.delivered), 0)

    def test_creation_adopts_and_retrieves_with_real_pinned_library(self):
        archive = library_fixtures.ProcedureLibraryTests()
        archive.root = self.controller.root
        archive.environment = library_fixtures.procedure()["environment"]
        _, _, record, pin = archive.archive()
        self.a = replace(self.a, learning=LearningPolicy(archive.environment, (LibrarySource(**pin),)))
        adopted = self.create()
        self.assertEqual(adopted["result"]["normal_adoption"]["scope"]["coordinate_epoch"], 0)
        timeline = adopted_timeline(self.runtime._ledger, self.runtime._store)
        self.assertEqual((timeline.elapsed_seconds, timeline.coordinate_epoch), (0, 0))
        self.assertEqual(len(timeline.segments), 1)
        self.assertIsNotNone(self.runtime._map)
        response = self.runtime.command(dict(schema="mission/11", kind="context", handoff=None,
            mission_id=self.a.mission_id, scope=adopted["result"]["normal_adoption"]["scope"],
            query="water", max_bytes=32768))
        self.assertEqual(response["status"], "accepted", response)
        self.assertEqual(response["context"]["packet"]["procedures"], [record])
        self.assertFalse(response["context"]["grants_authority"])

    def test_world_finish_refusal_preserves_phase_for_registered_stage_commit(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.run_request(self.control("world-form", "Create World"))
        original_behavior = self.bridge.behavior

        def actual_finish(bridge, request):
            # Actual008's CONFIRM at the interpreted selected Finish row opens
            # YESNO, not the name editor supplied by the general fixture.
            if bridge.value["category"] == "WORLDGEN_CONFIRM_DIALOG" and request.get("action") == "CONFIRM":
                self.stage = "world-confirmation"
                self.menu("YESNO", ["YES", "NO"])
                return True
            return original_behavior(bridge, request)

        self.bridge.behavior = actual_finish
        phase = self.runtime._registered_lifecycle.phase
        root = self.runtime._ledger.request("create")
        spent = self.runtime.status()["spent_inputs"]
        delivered = len(self.bridge.delivered)
        refused = self.run_request(self.control("uncommitted-world-finish", "Finish"))
        self.assertEqual(refused["state"], "blocked", refused)
        self.assertEqual(refused["result"]["proposals"], 0)
        self.assertIn("create stage commit", refused["result"]["reason"])
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertFalse(any(r["kind"] != "observe" for r in self.bridge.delivered[delivered:]))
        self.assertEqual(self.current()[1]["category"], "WORLDGEN_CONFIRM_DIALOG")
        current = self.runtime._registered_lifecycle.phase
        self.assertEqual((current.root_id, current.stage, current.actor_id, current.epoch),
                         (phase.root_id, phase.stage, phase.actor_id, phase.epoch))
        self.assertEqual(self.runtime._ledger.request("create")["deadline"], root["deadline"])
        committed = self.run_request(self.lifecycle("registered-world-finish", parent="create"))
        self.assertEqual(committed["state"], "partial", committed)
        self.assertEqual(self.current()[1]["category"], "YESNO")
        self.assertEqual(self.bridge.delivered[-1]["action"], "FINALIZE")
        answered = self.run_request(self.control("world-yes", "Yes", question="Are you SURE you're finished?"))
        self.assertEqual(answered["state"], "partial", answered)
        self.assertEqual(self.current()[1]["category"], "MAIN_MENU")

    def test_fresh_editor_source_is_revalidated_before_it_can_expire_at_dispatch(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.run_request(self.control("world-form", "Create World"))
        self.run_request(self.control("world-name-field", "World name"))
        before, _ = self.current()
        data = self.control("edit-near-freshness-boundary", "World name")
        data.update(skill_kind="edit", goal=dict(purpose="world_name", text=self.a.scenario.world, commit=False),
            perception=dict(kind="editor", source_id=before.observation_id, basis="player_interpretation",
                purpose="world_name", label="World name", visible_text="Old", whole_value=True, focused=True))
        data["limits"]["primitives"] = 16
        original = copy.deepcopy(data)
        root_deadline = self.runtime._ledger.request("create")["deadline"]
        mission_deadline = self.runtime._mission_deadline
        spent = self.runtime.status()["spent_inputs"]
        with expire_selected_at_dispatch(self.runtime, before):
            operation = self.run_request(data)
        self.assertEqual(operation["state"], "partial", operation)
        self.assertEqual(operation["request"], original)
        self.assertEqual(self.bridge.editor_text, self.a.scenario.world)
        self.assertEqual(sum(r.get("action") == "TEXT.CLEAR" for r in self.bridge.delivered), 1)
        relation = operation["result"]["revalidation"]
        self.assertEqual(relation["rule"], "exact_png_bytes")
        self.assertEqual(relation["original"]["source_id"], before.observation_id)
        self.assertNotEqual(relation["current"]["source_id"], before.observation_id)
        primitives = [p for p in self.runtime._ledger.primitive_records() if p["request_id"] == data["request_id"]]
        self.assertEqual(len(primitives), 1 + len(self.a.scenario.world))
        self.assertTrue(all(p["state"] == "returned" for p in primitives))
        self.assertEqual(primitives[0]["intent"]["source_before"], relation["current"]["source_id"])
        self.assertEqual(self.runtime.status()["spent_inputs"], spent + len(primitives))
        self.assertEqual(self.runtime._ledger.request("create")["deadline"], root_deadline)
        self.assertEqual(self.runtime._mission_deadline, mission_deadline)

    def test_fresh_initial_resume_revalidates_before_selected_source_expires(self):
        self.ready()
        before = self.runtime._current
        data = self.lifecycle("create")
        with expire_selected_at_dispatch(self.runtime, before):
            operation = self.run_request(data)
        self.assertEqual(operation["state"], "partial", operation)
        primitive, = self.runtime._ledger.primitive_records()
        self.assertEqual((primitive["intent"]["kind"], primitive["state"]), ("resume", "returned"))
        self.assertEqual(len({before.observation_id, primitive["intent"]["source_before"],
                              primitive["intent"]["preflight_source"]}), 3)
        self.assertEqual(operation["request"], data)

    def test_fresh_stage_commit_revalidates_before_selected_source_expires(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.run_request(self.control("world-form", "Create World"))
        before = self.runtime._current
        data = self.lifecycle("world-finalize", parent="create")
        deadline = self.runtime._ledger.request("create")["deadline"]
        with expire_selected_at_dispatch(self.runtime, before):
            operation = self.run_request(data)
        self.assertEqual(operation["state"], "partial", operation)
        primitive = self.runtime._ledger.primitive_records()[-1]
        self.assertEqual((primitive["intent"]["value"], primitive["state"]), ("FINALIZE", "returned"))
        self.assertEqual(primitive["intent"]["revalidation"]["original"]["source_id"], before.observation_id)
        self.assertEqual(self.runtime._ledger.request("create")["deadline"], deadline)

    def test_new_entry_capture_still_expires_at_final_preflight(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        before = self.runtime._current
        data = self.control("expired-replacement", "Create World")
        spent = self.runtime.status()["spent_inputs"]
        freshness, dispatch = self.runtime._store._fresh, self.runtime._dispatch
        preflight = threading.Event()

        def expired_replacement(entry, now_monotonic, now_timestamp_ms):
            if preflight.is_set() and entry.reference != before:
                now_monotonic = entry.reference.received_monotonic + 3.05
                now_timestamp_ms = entry.reference.timestamp_ms + 3050
            return freshness(entry, now_monotonic, now_timestamp_ms)

        def expire_before_dispatch(*args, **kwargs):
            preflight.set()
            return dispatch(*args, **kwargs)

        with patch.object(self.runtime._store, "_fresh", side_effect=expired_replacement), \
                patch.object(self.runtime, "_dispatch", side_effect=expire_before_dispatch):
            operation = self.run_request(data)
        self.assertTrue(preflight.is_set())
        self.assertEqual(operation["state"], "unknown", operation)
        self.assertIn("stale", operation["result"]["reason"])
        self.assertIsNotNone(operation["result"]["revalidation"])
        self.assertEqual(operation["result"]["proposals"], 1)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertFalse(any(p["request_id"] == data["request_id"]
                             for p in self.runtime._ledger.primitive_records()))
        self.assertFalse(any(r.get("action") == "CONFIRM" for r in self.bridge.delivered))

    def test_aged_explicit_world_commit_refreshes_before_finalize(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.run_request(self.control("world-form", "Create World"))
        data = self.lifecycle("world-finalize", parent="create")
        original, before = copy.deepcopy(data), self.runtime._current
        root_deadline = self.runtime._ledger.request("create")["deadline"]
        time.sleep(3.05)
        operation = self.run_request(data)
        self.assertEqual(operation["state"], "partial", operation)
        self.assertEqual(operation["request"], original)
        primitive = self.runtime._ledger.primitive_records()[-1]
        relation = primitive["intent"]["revalidation"]
        self.assertEqual((primitive["intent"]["value"], primitive["state"]), ("FINALIZE", "returned"))
        self.assertEqual(relation["original"]["source_id"], before.observation_id)
        self.assertEqual(relation["current"]["source_id"], primitive["intent"]["source_before"])
        self.assertEqual(relation["rule"], "exact_png_bytes")
        self.assertEqual(self.runtime._ledger.request("create")["deadline"], root_deadline)
        self.assertEqual(sum(r.get("action") == "FINALIZE" for r in self.bridge.delivered), 1)

    def test_aged_normal_save_refreshes_without_replacing_original_time_anchor(self):
        self.create()
        data = self.lifecycle("save", "save")
        original, before = copy.deepcopy(data), self.runtime._current
        time.sleep(3.05)
        operation = self.run_request(data)
        self.assertEqual(operation["state"], "partial", operation)
        self.assertEqual(operation["request"], original)
        primitive = self.runtime._ledger.primitive_records()[-1]
        relation = primitive["intent"]["revalidation"]
        self.assertEqual((primitive["intent"]["value"], primitive["state"]), ("save", "returned"))
        self.assertEqual(relation["original"]["source_id"], before.observation_id)
        self.assertEqual(relation["current"]["source_id"], primitive["intent"]["source_before"])
        self.assertEqual(relation["rule"], "native_state")
        self.assertEqual(self.runtime._registered_lifecycle.phase.first_normal, before)
        self.assertEqual(sum(r.get("action") == "save" for r in self.bridge.delivered), 1)

    def test_fresh_explicit_commit_refresh_rejects_changed_pixels_without_finalize(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.run_request(self.control("world-form", "Create World"))
        data = self.lifecycle("world-finalize", parent="create")
        spent = self.runtime.status()["spent_inputs"]
        self.bridge.editor_text = "Changed visible world configuration"
        operation = self.run_request(data)
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        self.assertFalse(any(r.get("action") == "FINALIZE" for r in self.bridge.delivered))

    def test_user_pause_during_save_refresh_prevents_rotation_and_save(self):
        self.create()
        data = self.lifecycle("save", "save")
        spent, observe = self.runtime.status()["spent_inputs"], self.runtime._observe_native
        def pause_after_observation(*args, **kwargs):
            result = observe(*args, **kwargs)
            self.runtime.pause("User Pause during normal save refresh")
            return result
        with patch.object(self.runtime, "_observe_native", side_effect=pause_after_observation), \
                patch.object(self.runtime, "_rotate", wraps=self.runtime._rotate) as rotate:
            operation = self.run_request(data)
        self.assertEqual(operation["state"], "paused", operation)
        self.assertEqual(self.runtime.status()["spent_inputs"], spent)
        rotate.assert_not_called()
        self.assertIsNone(self.controller._mission_lease)
        self.assertFalse(any(r.get("action") == "save" for r in self.bridge.delivered))

    def test_aged_creation_source_refreshes_before_resume_without_manual_observe(self):
        self.ready()
        data = self.lifecycle("create")
        original = copy.deepcopy(data)
        before = self.runtime._current
        operator_mark = self.controller.operator_pause_generation
        mission_deadline = self.runtime._mission_deadline
        time.sleep(3.05)
        operation = self.run_request(data)
        self.assertEqual(operation["state"], "partial", operation)
        self.assertEqual(operation["request"], original)
        primitive, = self.runtime._ledger.primitive_records()
        self.assertEqual((primitive["intent"]["kind"], primitive["state"]), ("resume", "returned"))
        self.assertEqual(len({before.observation_id, primitive["intent"]["source_before"],
                              primitive["intent"]["preflight_source"]}), 3)
        self.assertEqual(self.controller.operator_pause_generation, operator_mark)
        self.assertEqual(self.runtime._mission_deadline, mission_deadline)
        self.assertEqual(self.runtime.status()["spent_inputs"], 1)
        self.assertIsNone(self.runtime._map)
        self.assertEqual(self.runtime._ledger.memory_records("claim"), ())

    def test_resume_refresh_cannot_adopt_changed_pixels(self):
        self.ready()
        data = self.lifecycle("create")
        self.bridge.editor_text = "Changed visible content without a changed action list"
        operation = self.run_request(data)
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertEqual(self.runtime._ledger.primitive_records(), ())
        self.assertFalse(any(row["kind"] == "resume" for row in self.bridge.delivered))
        self.assertIsNone(self.controller._mission_lease)

    def test_user_pause_during_resume_refresh_sends_no_input(self):
        self.ready()
        data = self.lifecycle("create")
        observe = self.runtime._observe_native
        def pause_after_observation(*args, **kwargs):
            result = observe(*args, **kwargs)
            self.runtime.pause("User Pause during initial lifecycle refresh")
            return result
        with patch.object(self.runtime, "_observe_native", side_effect=pause_after_observation):
            operation = self.run_request(data)
        self.assertEqual(operation["state"], "paused", operation)
        self.assertEqual(self.runtime.status()["pause_cause"], "user")
        self.assertEqual(self.controller.operator_pause_generation, 1)
        self.assertEqual(self.runtime._ledger.primitive_records(), ())
        self.assertFalse(any(row["kind"] == "resume" for row in self.bridge.delivered))

    def test_lifecycle_child_refresh_is_bounded_by_its_original_child_deadline(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        root_deadline = self.runtime._ledger.request("create")["deadline"]
        data, before = self.control("world-form", "Create World"), self.runtime._current
        data["limits"]["wall_seconds"] = 5
        observe = self.runtime._observe_native
        inspect = self.runtime._store.inspect_current_boundary
        deadlines = []
        def expired_original(**kwargs):
            reference, fresh = inspect(**kwargs)
            # Expire the child's selected entry, not every later checkpoint.
            # The returned ACK and independently current post-input capture
            # still pass through the real evidence validator.
            return reference, False if reference == before else fresh
        def bounded_observe(work, *, deadline_monotonic=None):
            child = self.runtime._ledger.request(work.request["request_id"])
            remaining = child["deadline"] - self.runtime._wall()
            self.assertLessEqual(deadline_monotonic, self.runtime._clock() + remaining + 0.005)
            deadlines.append(child["deadline"])
            return observe(work, deadline_monotonic=deadline_monotonic)
        with patch.object(self.runtime._store, "inspect_current_boundary", side_effect=expired_original), \
                patch.object(self.runtime, "_observe_native", side_effect=bounded_observe):
            operation = self.run_request(data)
        self.assertEqual(operation["state"], "partial", operation)
        self.assertEqual(deadlines, [operation["deadline"]])
        self.assertLess(operation["deadline"], root_deadline)
        self.assertEqual(self.runtime._ledger.request("create")["deadline"], root_deadline)
        self.assertEqual(self.runtime._registered_lifecycle.phase.checkpoint, self.runtime._current)
        self.assertNotEqual(self.runtime._current, before)
        self.assertEqual(self.runtime._ledger.primitive_records()[-1]["state"], "returned")

    def test_new_lifecycle_child_does_not_spend_wall_budget_before_admission(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        original = self.runtime._current
        root_deadline = self.runtime._ledger.request("create")["deadline"]
        time.sleep(1.05)
        self.assertGreater(self.runtime._clock() - original.received_monotonic, 1)
        child = self.control("new-child-old-image", "Create World")
        child["limits"]["wall_seconds"] = 1
        result = self.run_request(child)
        self.assertEqual(result["state"], "partial", result)
        self.assertAlmostEqual(result["deadline"] - result["admitted_at"], 1, places=5)
        self.assertLess(result["deadline"], root_deadline)
        self.assertEqual(self.runtime._ledger.request("create")["deadline"], root_deadline)
        self.assertEqual(result["result"]["revalidation"]["original"]["source_id"], original.observation_id)

    def test_spare_points_is_separate_from_final_character_confirmation(self):
        self.spare_points = True
        self.create()
        self.assertEqual(sum(p.get("action") == "YES" for p in self.bridge.delivered), 3)

    def test_creation_name_editor_is_admitted_only_under_its_owned_root(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.run_request(self.control("world-form", "Create World"))
        self.run_request(self.control("world-name-field", "World name"))
        def editor(identity, visible, *, commit, root="create", text=None):
            source, _ = self.current()
            request = self.control(identity, "World name", parent=root)
            request.update(skill_kind="edit", goal=dict(purpose="world_name",
                text=text or self.a.scenario.world, commit=commit),
                perception=dict(kind="editor", source_id=source.observation_id, basis="player_interpretation",
                    purpose="world_name", label="World name", visible_text=visible, whole_value=True, focused=True))
            request["limits"]["primitives"] = 16
            return request
        rejected = self.runtime.command(editor("unowned-editor", "Old", commit=False, root="other"))
        self.assertEqual(rejected["status"], "rejected", rejected)
        edited = self.run_request(editor("edit-world-name", "Old", commit=False))
        self.assertEqual(edited["state"], "partial", edited)
        self.assertEqual(self.bridge.editor_text, self.a.scenario.world)
        committed = self.run_request(editor("commit-world-name", self.a.scenario.world, commit=True))
        self.assertEqual(committed["state"], "partial", committed)
        self.assertEqual(self.runtime._store.observation(self.runtime._current)["category"], "WORLDGEN_CONFIRM_DIALOG")

    def test_save_exit_new_child_load_preserves_exact_time_and_identity(self):
        self.create()
        saved = self.save()["result"]["saved_checkpoint"]
        finished = self.exit()["result"]["normal_exit"]
        self.assertFalse(finished["no_save_required"])
        self.assertIn(saved["menu_source_id"], finished["source_ids"])
        self.assertIsNone(self.controller.pending)
        self.assertFalse(self.process_state["running"])
        self.assertEqual(self.launch(identity="second-launch")["state"], "completed")
        self.stage = "load-world"
        begun = self.run_request(self.lifecycle("load", "load"))
        self.assertEqual(begun["state"], "partial", begun)
        world = self.runtime._current
        # Match the pinned native flow: MAIN_MENU world -> UILIST character.
        # There is no visible "Load Game" row to arm a private transition.
        selected = self.run_request(self.control("load-world", f"{self.a.scenario.world} (1)", parent="load"))
        self.assertEqual(selected["state"], "partial", selected)
        selection = self.control("load-entry", self.a.scenario.character, parent="load")
        selection["perception"] = None
        entered = self.run_request(selection)
        self.assertEqual(entered["state"], "unknown", entered)
        self.assertIsNotNone(self.runtime._registered_lifecycle.candidate)
        self.observe("load-observe")
        adopted = self.finish_identity("load", world, 1)
        self.assertEqual(adopted["result"]["normal_adoption"]["saved_checkpoint_request_id"], "save-reconcile")
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 0)
        # Cached result settlement does not make the writer connection idle.
        with self.runtime._ledger._mutex:
            self.runtime._ledger._verify(self.a)

    def reload_picker(self):
        self.create()
        self.save()
        self.exit()
        self.assertEqual(self.launch(identity="second-launch")["state"], "completed")
        self.stage = "load-world"
        self.assertEqual(self.run_request(self.lifecycle("load", "load"))["state"], "partial")
        selected = self.run_request(self.control("load-world", f"{self.a.scenario.world} (1)", parent="load"))
        self.assertEqual(selected["state"], "partial", selected)
        self.assertEqual(self.runtime._registered_lifecycle.phase.stage, "load_selection")

    def reject_reload_row(self, rows, selected, target):
        self.load_rows, self.load_selected = rows, selected
        self.reload_picker()
        delivered = len([row for row in self.bridge.delivered if row["kind"] == "action"])
        request = self.control("invalid-load-entry", target, parent="load")
        request["perception"] = None
        result = self.run_request(request)
        self.assertEqual(result["state"], "blocked", result)
        self.assertEqual(len([row for row in self.bridge.delivered if row["kind"] == "action"]), delivered)
        self.assertIsNone(self.runtime._registered_lifecycle.candidate)

    def test_reload_other_selected_character_is_rejected_before_input(self):
        self.reject_reload_row([
            dict(id="row-0", text=self.a.scenario.character, enabled=True, hotkey=None),
            dict(id="row-1", text="Other", enabled=True, hotkey=None)], "row-1", "Other")

    def test_reload_missing_admitted_character_is_rejected_before_input(self):
        self.reject_reload_row([dict(id="row-0", text="Other", enabled=True, hotkey=None)], "row-0", "Other")

    def test_reload_disabled_admitted_character_is_rejected_before_input(self):
        self.reject_reload_row([
            dict(id="row-0", text=self.a.scenario.character, enabled=False, hotkey=None),
            dict(id="row-1", text="Other", enabled=True, hotkey=None)], "row-1", "Other")

    def test_reload_duplicate_admitted_character_is_rejected_before_input(self):
        self.reject_reload_row([
            dict(id=f"row-{index}", text=self.a.scenario.character, enabled=True, hotkey=None)
            for index in range(2)], "row-0", self.a.scenario.character)

    def test_return_from_reload_picker_retires_selection_stage(self):
        self.reload_picker()
        result = self.run_request(self.control("load-back", "Cancel", parent="load"))
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(self.runtime._registered_lifecycle.phase.stage, "awaiting_control")
        self.assertIsNone(self.runtime._registered_lifecycle.candidate)

    def test_creation_uses_durable_identity_without_a_gate_mock(self):
        adopted = self.create()
        self.assertEqual(adopted["result"]["normal_adoption"]["scope"]["coordinate_epoch"], 0)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNotNone(self.runtime._map)
        self.assertTrue(self.runtime._bindings)
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 0)
        unknown = [p for p in self.runtime._ledger.primitive_records() if p["state"] == "unknown"]
        self.assertEqual(len(unknown), 1)
        self.assertIsNotNone(unknown[0]["effect"])
        self.assertEqual(sum(p.get("action") == "YES" for p in self.bridge.delivered), 2)
        self.assertEqual(self.runtime.status()["spent_inputs"], 10)

    def test_provisional_normal_rejects_inventory_before_identity(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        request = self.control("invalid-inventory", "Inventory", kind="inspect")
        request["goal"]["purpose"] = "inventory"
        count = len(self.bridge.delivered)
        operation = self.run_request(request)
        self.assertEqual(operation["state"], "blocked", operation)
        self.assertEqual(len(self.bridge.delivered), count)
        self.assertIsNone(self.runtime._map)
        self.assertEqual(self.runtime._bindings, {})

    def test_user_pause_revokes_creation_phase_without_reacquiring_consent(self):
        self.ready()
        self.run_request(self.lifecycle("create"))
        self.runtime.pause()
        count = len(self.bridge.delivered)
        response = self.runtime.command(self.lifecycle("try-create", parent="create"))
        self.assertIn(response["status"], ("accepted", "rejected"), response)
        if response["status"] == "accepted":
            self.assertEqual(self.settled("try-create")["state"], "blocked")
        self.assertEqual(len(self.bridge.delivered), count)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)

    def test_reopen_restores_historical_game_time_without_live_handles(self):
        self.create()
        self.runtime.close()
        self.runtime = MissionRuntime(self.controller)
        self.runtime.command(dict(schema="mission/11", kind="start", request_id="reopened-start", admission=self.a.to_dict()))
        self.assertEqual(self.settled("reopened-start")["state"], "completed")
        self.assertEqual(self.runtime.status()["metrics"]["game_seconds"], 0)
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._registered_lifecycle.lineage)
        self.assertIsNone(self.runtime._native)
        self.assertEqual(self.runtime._bindings, {})
        self.assertIsNone(self.runtime._map)
        self.assertIsNone(self.controller._mission_lease)

    def test_pause_after_adoption_commit_preserves_result_without_closing_writer(self):
        original = self.runtime._registered_lifecycle.after_commit
        def pause_at_publication(work, disposition, result):
            if "normal_adoption" in result:
                self.runtime.pause()
            return original(work, disposition, result)
        with patch.object(self.runtime._registered_lifecycle, "after_commit", side_effect=pause_at_publication):
            self.create()
        self.assertFalse(self.runtime._closed.is_set())
        self.assertEqual(self.runtime._ledger.request("create-adopt")["state"], "completed")
        self.assertIsNone(self.runtime._registered_lifecycle.phase)
        self.assertIsNone(self.runtime._map)
        self.assertEqual(self.runtime._bindings, {})
        self.assertTrue(self.controller.pause_requested)


if __name__ == "__main__":
    unittest.main()
