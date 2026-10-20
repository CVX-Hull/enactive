"""HTTP/core composition with explicit trusted identity fixture, never native acceptance.

The production-Start test uses the real gate. Core skill tests separately mock that
unimplemented lifecycle boundary; they establish no creation/load/identity result.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

from harness.controller import Controller
from harness.server import Server
from tests.test_mission_contracts import admission, claim
from tests.test_mission_runtime import VisibleBridge, bootstrap_core_fixture


class MissionHTTPTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.controller = Controller(Path(temporary.name), timeout=1)
        self.addCleanup(self.controller.close)
        self.bridge = VisibleBridge(self.controller)
        self.bridge.value["actions"].append("open")
        self.bridge.__enter__()
        self.addCleanup(self.bridge.__exit__, None, None, None)
        self.server = Server(self.controller, 0)
        self.addCleanup(self.server.server_close)
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.port}"
        self.opener = build_opener(ProxyHandler({}))
        self.a = admission()
        self.assertEqual(self.raw("observe")["status"], "ready")
        self.assertEqual(self.raw("resume")["status"], "ready")

    def request(self, path, value=None):
        request = Request(self.base + path, data=None if value is None else json.dumps(value).encode(),
            headers={"Content-Type": "application/json", "X-CDDA-Token": self.controller.token})
        try:
            with self.opener.open(request, timeout=6) as response: return json.load(response)
        except HTTPError as error:
            with error: return json.load(error)

    def raw(self, kind):
        return self.request("/api/command", dict(kind=kind))

    def status(self):
        return self.request("/api/status")["mission"]

    def record(self, kind, **changes):
        result = dict(schema="mission/7", kind=kind, request_id=kind + "-1",
            mission_id=self.a.mission_id, epoch=self.status()["epoch"])
        return result | changes

    def submit(self, value):
        result = self.request("/api/mission", value)
        self.assertEqual(result["status"], "accepted", result)
        return result

    def settled(self, identity):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = self.submit(dict(schema="mission/7", kind="result", mission_id=self.a.mission_id,
                                     operation_id=identity))["operation"]
            if result["result"] is not None: return result
            threading.Event().wait(.01)
        self.fail(f"Mission operation did not settle: {self.status()}")

    def start(self):
        self.assertIsNone(self.status())
        runtime = self.server.mission
        with patch.object(runtime, "_bootstrap", side_effect=lambda work: bootstrap_core_fixture(runtime, work)):
            self.submit(dict(schema="mission/7", kind="start", request_id="start-1", admission=self.a.to_dict()))
            self.assertEqual(self.settled("start-1")["state"], "completed")

    def test_production_start_cannot_adopt_unowned_normal_play_or_dispatch(self):
        delivered = deepcopy(self.bridge.delivered)
        self.submit(dict(schema="mission/7", kind="start", request_id="start-1", admission=self.a.to_dict()))
        operation = self.settled("start-1")
        self.assertTrue(operation["result"]["lifecycle_needed"])
        self.assertEqual(self.status()["phase"], "admitted")
        self.assertIsNone(self.status()["current_source"])
        self.assertIsNone(self.controller._mission_lease)
        self.submit(self.record("observe"))
        self.settled("observe-1")
        self.assertIsNone(self.status()["current_source"])
        self.assertEqual(self.bridge.delivered, delivered)
        record = self.record("skill", skill_kind="navigate", work_id=None, phase_id=None, perception=None,
            goal=dict(scope=dict(mission_id=self.a.mission_id, session="game-test", coordinate_epoch=0), target=[1,0,0]),
            sources=["unowned-frame"], expected_session="game-test", expected_revision=self.bridge.value["revision"],
            expected_boundary_id=self.bridge.value["boundary"]["id"], limits=dict(primitives=1,wall_seconds=10,game_seconds=10))
        self.submit(record)
        self.assertEqual(self.settled("skill-1")["state"], "blocked")
        self.assertEqual(self.bridge.delivered, delivered)
        self.assertEqual(self.status()["spent_inputs"], 0)

    def skill(self, kind="navigate", **changes):
        ref = self.status()["current_source"]
        boundary = self.request("/api/status")["state"]["boundary"]["id"]
        return self.record("skill", skill_kind=kind, work_id=None, phase_id=None, perception=None,
            goal=dict(scope=dict(mission_id=self.a.mission_id, session=ref["session"], coordinate_epoch=0), target=[1, 0, 0]),
            sources=[ref["observation_id"]], expected_session=ref["session"], expected_revision=ref["revision"],
            expected_boundary_id=boundary, limits=dict(primitives=8, wall_seconds=120, game_seconds=1200)) | changes

    def test_semantic_navigation_context_memory_and_single_ingress(self):
        self.start()
        before = self.status()["current_source"]
        scope = dict(mission_id=self.a.mission_id, session=before["session"], coordinate_epoch=0)
        entry = claim(scope=scope, sources=[before["observation_id"]],
            supports=[dict(sources=[before["observation_id"]], claims=[])],
            observed_time=dict(revision=before["revision"], turn=before["turn"]))
        self.submit(self.record("remember", entry_type="claim", entry=entry))
        self.assertEqual(self.settled("remember-1")["state"], "completed")
        context = self.submit(dict(schema="mission/7", kind="context", handoff=None, mission_id=self.a.mission_id,
            scope=scope, query="water", max_bytes=32768))["context"]
        self.assertEqual(context["packet"]["claims"][0]["id"], entry["id"])
        self.assertEqual(self.status()["memory_context"], context["packet"])
        source = self.status()["current_source"]
        for _ in range(4): self.assertEqual(self.status()["current_source"], source)
        request = self.skill()
        self.submit(request)
        outcome = self.settled(request["request_id"])
        self.assertEqual(outcome["state"], "completed", outcome)
        self.assertEqual(outcome["result"]["verified_steps"], 1)
        # A newly observed frontier can support the direction change; unknown
        # diagonal cells cannot be preloaded as traversable to force a longer route.
        second = self.skill(request_id="skill-2", goal=dict(scope=scope, target=[1, 1, 0]))
        self.submit(second)
        self.assertEqual(self.settled("skill-2")["state"], "completed")
        self.assertEqual(self.status()["spent_inputs"], 2)
        self.assertEqual(self.status()["memory_context"], context["packet"], "Preview is historical, not recomputed")
        self.assertIn("typed mission", self.raw("observe")["error"])
        self.assertNotIn("gameplay", self.request("/api/status"))
        self.assertIn("Unknown endpoint", self.request("/api/gameplay", {})["error"])

    def test_owned_editor_dismissal_through_actual_mission_http(self):
        self.start()
        normal = deepcopy(self.bridge.value["scene"])
        def editor(bridge, request):
            if request.get("action") == "open":
                bridge.value.update(scene=None, ui=None, category="STRING_INPUT", actions=["TEXT.QUIT"])
                bridge.value["boundary"].update(kind="menu", id="filter-editor")
            elif request.get("action") == "TEXT.QUIT":
                bridge.value.update(scene=normal, category="DEFAULTMODE", actions=["UP", "DOWN", "LEFT", "RIGHT"])
                bridge.value["boundary"].update(kind="normal_play", id="editor-return")
            return True
        self.bridge.behavior = editor
        self.submit(self.skill("interact", goal=dict(action="open", intent="Open", desired_outcome="Inspect")))
        self.assertEqual(self.settled("skill-1")["state"], "partial")
        ref = self.status()["current_source"]
        child = self.skill("menu", request_id="dismiss", phase_id="skill-1",
            goal=dict(purpose="Cancel filter", label="Cancel", outcome="dismissed"),
            perception=dict(kind="dismissal", basis="player_interpretation", source_id=ref["observation_id"], question="Filter"))
        self.submit(child)
        result = self.settled("dismiss")
        self.assertEqual(result["state"], "partial", result)
        self.assertEqual(result["result"]["phase"]["stage"], "complete")
        self.assertEqual(self.status()["spent_inputs"], 2)

    def test_http_pause_remains_available_during_prepublication_storage_wait(self):
        self.start()
        entered, release = threading.Event(), threading.Event()
        store = self.server.mission._store
        retain = store.retain_equivalent
        def blocked(*args, **kwargs):
            entered.set()
            if not release.wait(3): raise AssertionError("Test storage gate timed out")
            return retain(*args, **kwargs)
        with patch.object(store, "retain_equivalent", side_effect=blocked):
            self.submit(self.skill())
            try:
                self.assertTrue(entered.wait(1))
                self.assertEqual(self.raw("pause")["status"], "pause_requested")
                self.assertEqual(self.status()["pause_cause"], "user")
            finally: release.set()
            self.settled("skill-1")
        self.assertEqual(self.status()["spent_inputs"], 0)
        self.assertFalse([r for r in self.bridge.delivered if r["kind"] == "action"])
