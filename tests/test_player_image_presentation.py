"""Synthetic image presentation checks; no native/gameplay acceptance."""
from copy import deepcopy
import asyncio
import base64
import hashlib
import json
from pathlib import Path
import sys
import unittest

from harness.gameplay.contracts import canonical
from harness.player_tools import DETAIL_SECTIONS, PlayerTools
from harness.player_mcp import make_server
from tests.test_gameplay_evidence import black_png, observation, png


class ImageClient:
    def __init__(self):
        self.image = png()
        self.observed = observation()
        self.reference = dict(observation_id="source", session=self.observed["session"],
            revision=self.observed["revision"], frame_sha256=hashlib.sha256(self.image).hexdigest(),
            frame_path="original.png", timestamp_ms=self.observed["timestamp_ms"],
            boundary_kind="normal_play", turn=4)
        self.mission = dict(mission_id="mission", player_id="player", actor_id="player", epoch=1,
            phase="active", pause_cause=None, clock_valid=True, current_source=self.reference,
            prompt_phase=None, lifecycle_phase=None, activity_phase=None,
            configuration={"source_commit": "original"}, metrics={"primitives": 1},
            progress={"unknown": True}, last_receipt={"transport_disposition": "unknown"},
            remaining_limits={"inputs": 10, "wall_seconds": 30}, cleanup_reserve={"inputs": 1},
            unresolved_effects=["original-unknown"], unreconciled=[])
        self.native = dict(state=deepcopy(self.observed), frozen=False, pause_requested=False,
            pause_generation=2, operator_pause_generation=1, pending=None, control_pending=None,
            connection="fresh", error="")
        self.disposition = "retained"
        self.envelope = dict(transport="delivered", settled=True, operation_id="operation",
            response=dict(operation=dict(id="operation", state="completed",
                result={"original": True}, receipts=[{"unknown": True}]),
                context={"limits": {"inputs": 1}, "grants_authority": False}))
        self.calls = []

    def status(self):
        self.calls.append("status")
        return deepcopy(dict(mission=self.mission, **self.native))

    def source(self, mission_id, source_id):
        self.calls.append(("source", mission_id, source_id))
        return deepcopy(dict(reference=self.reference, observation=self.observed,
            disposition=self.disposition, grants_authority=False)), self.image

    def collect(self, **arguments):
        self.calls.append(("collect", arguments))
        return deepcopy(self.envelope)


class ImagePresentationTests(unittest.TestCase):
    def setUp(self):
        self.client = ImageClient()
        self.player = PlayerTools(self.client)

    def result(self):
        return self.player.call("enactive_result", dict(mission_id="mission",
            operation_id="operation", wait_seconds=0))

    def test_repeated_result_omits_only_image_and_preserves_exact_handles_and_details(self):
        first, first_image = self.result()
        original = canonical(first)
        handles = deepcopy((self.player.snapshots, self.player.sources))
        second, second_image = self.result()
        self.assertEqual(first_image, self.client.image)
        self.assertIsNone(second_image)
        note = second.pop("image_presentation")
        self.assertIn("pixels are unchanged", note)
        self.assertIn("enactive_snapshot", note)
        self.assertIn("enactive_source", note)
        self.assertIn("not a source-read", note)
        self.assertNotIn(hashlib.sha256(first_image).hexdigest(), note)
        self.assertEqual(second["response"], first["response"])
        self.assertEqual(second["next_snapshot"]["mission"], first["next_snapshot"]["mission"])
        self.assertEqual(second["next_snapshot"]["source"], first["next_snapshot"]["source"])
        self.assertEqual(canonical(first), original)
        for identity, cached in handles[0].items():
            self.assertEqual(canonical(self.player.snapshots[identity]), canonical(cached))
        self.assertEqual(self.player.sources, handles[1])
        current = second["next_snapshot"]
        self.assertEqual(canonical(self.player.snapshots[current["snapshot_id"]]), canonical(current))
        for section in DETAIL_SECTIONS:
            detail, image = self.player.call("enactive_detail", dict(
                snapshot_id=current["snapshot_id"], section=section))
            expected = (current["mission"] if section == "mission" else current.get(section)
                if section in ("native", "source") else current["mission"].get(
                    "last_receipt" if section == "receipt" else section))
            self.assertEqual(canonical({"detail": detail["detail"]}), canonical({"detail": expected}))
            self.assertIsNone(image)
        self.assertEqual([call for call in self.client.calls if isinstance(call, tuple) and call[0] == "source"],
            [("source", "mission", "source"), ("source", "mission", "source")])

    def test_changed_actual_bytes_and_return_to_earlier_image_always_resend(self):
        self.assertEqual(self.result()[1], png())
        self.assertIsNone(self.result()[1])
        # Keep the advertised hash fixed: presentation must compare actual bytes.
        self.client.image = black_png()
        self.assertEqual(self.result()[1], black_png())
        self.assertIsNone(self.result()[1])
        self.client.image = png()
        self.assertEqual(self.result()[1], png())

    def test_explicit_snapshot_always_returns_pixels_and_can_establish_context(self):
        first, image = self.player.call("enactive_snapshot", {})
        self.assertEqual(image, png())
        self.assertEqual(self.player.snapshots[first["snapshot_id"]], first)
        self.assertIsNone(self.result()[1])
        for _ in range(2):
            current, image = self.player.call("enactive_snapshot", {})
            self.assertEqual(image, png())
            self.assertNotIn("image_presentation", current)

    def test_explicit_historical_source_always_returns_pixels_and_invalidates_context(self):
        self.result()
        self.assertIsNone(self.result()[1])
        for _ in range(2):
            source, image = self.player.call("enactive_source", dict(
                mission_id="historical-mission", source_id="source"))
            self.assertEqual(image, png())
            self.assertFalse(source["grants_authority"])
            self.assertNotIn("image_presentation", source)
        self.assertEqual(self.result()[1], png())
        self.assertIsNone(self.result()[1])

    def test_mission_player_and_epoch_changes_always_resend(self):
        self.result()
        for field, value in (("mission_id", "next-mission"), ("player_id", "successor"), ("epoch", 2)):
            with self.subTest(field=field):
                self.client.mission[field] = value
                if field == "player_id":
                    self.client.mission["actor_id"] = value
                self.assertEqual(self.result()[1], png())
                self.assertIsNone(self.result()[1])

    def test_current_state_and_control_changes_resend_even_with_identical_pixels(self):
        for field, value in (("revision", 2), ("session", "new-session"),
                             ("scene", None), ("ui", {"visible": "changed"})):
            with self.subTest(field=field):
                self.result()
                self.assertIsNone(self.result()[1])
                self.client.observed[field] = value
                self.client.native["state"][field] = value
                if field in ("session", "revision"):
                    self.client.reference[field] = value
                self.assertEqual(self.result()[1], png())
        self.client.native["pause_generation"] += 1
        self.assertEqual(self.result()[1], png())
        self.client.mission["phase"] = "paused"
        self.assertEqual(self.result()[1], png())

    def test_capture_identity_changes_do_not_hide_new_source_metadata(self):
        first, _ = self.result()
        self.client.observed.update(id="capture", frame="new.png", timestamp_ms=1_000_001)
        self.client.native["state"].update(self.client.observed)
        self.client.reference.update(observation_id="new-source", timestamp_ms=1_000_001,
            frame_path="new.png")
        current, image = self.result()
        self.assertIsNone(image)
        self.assertEqual(current["next_snapshot"]["source"]["reference"]["observation_id"], "new-source")
        self.assertEqual(first["next_snapshot"]["source"]["reference"]["observation_id"], "source")
        self.assertIn(("source", "mission", "new-source"), self.client.calls)

    def test_unknown_context_resends_and_invalidates_previous_comparison(self):
        cases = (
            lambda c: c.mission.pop("player_id"),
            lambda c: c.mission.pop("epoch"),
            lambda c: c.mission.update(epoch=True),
            lambda c: c.mission.update(actor_id="different-player"),
            lambda c: c.mission.update(clock_valid=False),
            lambda c: c.native.update(connection="disconnected"),
            lambda c: c.native.update(state=None),
            lambda c: c.native.update(error="Original transport failure"),
            lambda c: c.native["state"].update(revision=99),
            lambda c: setattr(c, "disposition", "disputed"),
            lambda c: c.observed.update(frame_ok=False),
        )
        for change in cases:
            with self.subTest(change=change):
                self.setUp()
                self.result()
                before = deepcopy(self.client.__dict__)
                change(self.client)
                for _ in range(2):
                    unknown, image = self.result()
                    self.assertEqual(image, png())
                    self.assertNotIn("image_presentation", unknown)
                self.client.__dict__.update(before)
                self.assertEqual(self.result()[1], png())

    def test_missing_image_clears_previous_comparison_without_changing_error(self):
        self.result()
        source = self.client.source
        def unavailable(*arguments):
            raise OSError("Exact original unavailable")
        self.client.source = unavailable
        failed, image = self.result()
        self.assertIsNone(image)
        self.assertEqual(failed["next_snapshot"]["source_error"], "Exact original unavailable")
        self.assertNotIn("image_presentation", failed)
        self.client.source = source
        self.assertEqual(self.result()[1], png())


class ImageSDKTests(unittest.TestCase):
    def test_repeated_same_response_forwards_one_actual_image_then_explicit_rereads(self):
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters

        async def exercise():
            parameters = StdioServerParameters(command=sys.executable,
                args=["-m", "tests.test_player_image_presentation", "--stdio-fixture"],
                cwd=str(Path(__file__).resolve().parents[1]))
            async with Client(parameters) as client:
                results = []
                for _ in range(6):
                    result = await client.call_tool("enactive_result", dict(
                        mission_id="mission", operation_id="operation"))
                    self.assertFalse(result.is_error)
                    self.assertIsNone(result.structured_content)
                    self.assertEqual(json.loads(result.content[0].text)["response"], ImageClient().envelope["response"])
                    results.append(result)
                images = [part for result in results for part in result.content if part.type == "image"]
                self.assertEqual(len(images), 1)  # Six identical retained PNGs previously yielded six image parts.
                self.assertEqual(base64.b64decode(images[0].data), png())
                self.assertEqual(images[0].mime_type, "image/png")
                self.assertEqual([len(result.content) for result in results], [2, 1, 1, 1, 1, 1])
                for result in results[1:]:
                    self.assertIn("pixels are unchanged", json.loads(result.content[0].text)["image_presentation"])
                for tool, arguments in (("enactive_snapshot", {}),
                        ("enactive_source", dict(mission_id="mission", source_id="source"))):
                    for _ in range(2):
                        result = await client.call_tool(tool, arguments)
                        self.assertFalse(result.is_error)
                        self.assertIsNone(result.structured_content)
                        self.assertEqual(base64.b64decode(result.content[1].data), png())
                        self.assertNotIn("image_presentation", json.loads(result.content[0].text))
                # A source image has no actor/epoch context, even in this mission.
                result = await client.call_tool("enactive_result", dict(
                    mission_id="mission", operation_id="operation"))
                self.assertEqual(base64.b64decode(result.content[1].data), png())
        asyncio.run(exercise())


async def _stdio_fixture():
    from mcp.server.stdio import stdio_server
    server = make_server(PlayerTools(ImageClient()))
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    if "--stdio-fixture" in sys.argv:
        asyncio.run(_stdio_fixture())
    else:
        unittest.main()
