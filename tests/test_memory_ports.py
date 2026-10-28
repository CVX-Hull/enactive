"""Memory ports with independent passive data; no second-game qualification."""
from copy import deepcopy
from dataclasses import dataclass, asdict
import unittest
from harness.gameplay.campaign_memory import CampaignMemory
from harness.gameplay.contracts import ContractError
from harness.gameplay.memory_contracts import validate_memory_entry
from harness.gameplay.mission_contracts import validate_memory_entry as validate_cdda_entry


@dataclass(frozen=True)
class Source:
    observation_id: str = "visible-avatar"
    session: str = "room"
    revision: int = 4
    turn: int = 70  # Opaque observed counter, not elapsed seconds.
    timestamp_ms: int = 1000
    received_monotonic: float = 1.0
    frame_sha256: str = "f" * 64
    boundary_kind: str = "normal_play"

    def to_dict(self):
        return asdict(self)


class Sources:
    historical_references = (Source(),)
    retained = True

    def source_status(self, reference):
        return "retained" if self.retained else "disputed"

    def inspect_current(self, **clocks):
        return self.historical_references[0], self.retained


class Repository:
    mission_id = "foreign-fixture"
    learning = None

    def __init__(self):
        self.rows = []
        self.admitted = None

    def validate_application(self, request):
        if request != self.admitted:
            raise ContractError("Application differs from the fixture's exact admission")
        return deepcopy(request)

    def memory_records(self, kind):
        return tuple(deepcopy(row) for row in self.rows if row["entry_type"] == kind)

    def primitive_records(self):
        return ()

    def append_memory(self, event_id, entry_type, entry, *, now, candidate=False):
        self.rows.append(dict(sequence=len(self.rows) + 1, event_id=event_id,
            entry_type=entry_type, entry=deepcopy(entry)))
        return len(self.rows)


def entry():
    return dict(schema="campaign-memory/6", record_type="Claim", id="avatar-name", kind="interpretation",
        key=dict(subject="avatar", property="identity", unit="label", coverage_id="visible-avatar"),
        value=dict(quantity=None, state="Nia"), text="avatar identity",
        scope=dict(mission_id="foreign-fixture", session="room", coordinate_epoch=0),
        observed_time=dict(revision=4, turn=70), received_time=1000,
        coverage="visible nameplate", sources=["visible-avatar"],
        supports=[dict(sources=["visible-avatar"], claims=[])], status="current", supersedes=[])


class MemoryPortTests(unittest.TestCase):
    def test_shared_memory_accepts_binding_data_without_world_character_or_visible_schema(self):
        repository, sources = Repository(), Sources()
        memory = CampaignMemory(repository, sources)
        claim = entry()
        repository.admitted = dict(kind="remember", request_id="remember-avatar", entry_type="claim", entry=claim)
        memory.apply(deepcopy(repository.admitted), now=1.0)
        packet = memory.context(claim["scope"], "avatar", now_monotonic=1, now_timestamp_ms=1000, max_bytes=32768)
        self.assertEqual(packet["claims"][0]["value"]["state"], "Nia")
        self.assertFalse(packet["grants_authority"])
        packet["claims"][0]["value"]["state"] = "changed copy"
        self.assertEqual(repository.rows[0]["entry"]["value"]["state"], "Nia")
        sources.retained = False
        disputed = memory.context(claim["scope"], "avatar", now_monotonic=2, now_timestamp_ms=2000, max_bytes=32768)
        self.assertFalse(disputed["grants_authority"])
        self.assertTrue(disputed["reobservations"])

    def test_cdda_binding_keeps_its_existing_visible_identity_constraint(self):
        self.assertEqual(validate_memory_entry(entry(), "claim"), entry())
        with self.assertRaises(ContractError):
            validate_cdda_entry(entry(), "claim")

    def test_shared_schema_preserves_unique_source_and_support_constraints(self):
        for field in ("sources", "support_sources", "support_claims", "supersedes"):
            candidate = entry()
            if field.startswith("support_"):
                key = field.removeprefix("support_")
                candidate["supports"][0][key] = ["premise", "premise"]
                if key == "sources":
                    candidate["sources"] = ["premise"]
            else:
                candidate[field] = ["duplicate", "duplicate"]
            with self.subTest(field=field), self.assertRaises(ContractError):
                validate_memory_entry(candidate, "claim")
