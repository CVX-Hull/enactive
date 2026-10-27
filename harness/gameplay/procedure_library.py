"""Read current immutable advisory exports, never raw mission donor directories.

Original bytes remain pinned provenance. Their current projections and all shared
settlement/source/lineage predicates are checked before any data is exposed.
No historical validator, subprocess, Git lookup or runtime writer is invoked.
"""
from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
import json
import os
from pathlib import Path
from typing import Any

from .advisory_capture import capture_projection, request_projection, source_envelope, validate_captured_mapping
from .advisory_export import (
    HISTORICAL_VALIDATOR, HISTORICAL_VALIDATOR_SHA256, MAX_MANIFEST_BYTES,
    artifact_parts, derive_data, original_root, read_manifest,
)
from .contracts import EvidenceRef, _pairs, _reject_constant, validate_json
from .evidence import MAX_METADATA_BYTES, _canonical, _identity
from .native_receipts import _ACK_FIELDS
from .procedure_archive import (
    MAX_DATABASE_BYTES, ProcedureEpisodeRefusal, ProcedureLibraryError, SealedProcedureArchive,
    _ELIGIBLE_ARCHIVE_PHASES, _id, _object, _pins, captured_database,
)
from .procedures import MAX_PROCEDURE_RECORDS

# Preserve the public refusal types used by memory callers. They describe data
# selection/integrity, never a compatibility path to raw donor archives.
__all__ = ["ProcedureLibrary", "ProcedureLibraryError", "ProcedureEpisodeRefusal"]


class ProcedureLibrary(SealedProcedureArchive):
    """A single current export reader with exact original ledger/index pins."""

    def __init__(self, root: Path, sources: Sequence[dict], *, current_mission_id: str):
        self._manifests: dict[str, dict] = {}
        self._origins: dict[str, dict] = {}
        super().__init__(root, sources, current_mission_id=current_mission_id)

    def _parts(self, mission: str) -> tuple[str, ...]:
        return artifact_parts(mission, self._pins[mission])

    def _index_version(self, mission: str) -> int:
        return self._origins[mission]["store_version"]

    def _expected_frame_path(self, mission: str, identity: str, reference: EvidenceRef) -> Path:
        # A current export may move. Original absolute paths stay provenance;
        # all actual reads use the managed artifact directory and capture ID.
        return original_root(mission, reference.to_dict()) / ".runtime" / "missions" / mission / "evidence" / "frames" / (identity + ".png")

    def _observation_data(self, mission: str, value: dict) -> dict:
        captured = capture_projection(value)
        if captured["original_protocol"] != self._origins[mission]["native_protocol"]:
            raise ProcedureLibraryError("Captured source differs from its original provenance")
        return deepcopy(value)

    def _load_index(self, mission: str, pin: dict) -> None:
        manifest = read_manifest(self._read(mission, "manifest.json", MAX_MANIFEST_BYTES))
        if manifest["source"] != pin:
            raise ProcedureLibraryError("Advisory export does not match its admitted original pins")
        contract = manifest["data"]["original_contract"]
        validate_json(contract, {"type": "object", "properties": {
            "ledger_version": {"type": "integer", "enum": [12, 13]},
            "native_protocol": {"type": "integer", "enum": [6, 7]},
            "store_version": {"type": "integer", "enum": [5, 6]},
            "program_view": {"enum": ["program-view/1", "program-view/2"]}},
            "required": ["ledger_version", "native_protocol", "store_version", "program_view"],
            "additionalProperties": False})
        self._manifests[mission] = manifest
        self._origins[mission] = {key: contract[key] for key in ("native_protocol", "store_version", "program_view")}
        super()._load_index(mission, pin)

    def _load_ledger(self, mission: str, pin: dict) -> None:
        for suffix in ("-wal", "-shm", "-journal"):
            try:
                descriptor = self._file(mission, "mission.sqlite3" + suffix)
            except FileNotFoundError:
                continue
            os.close(descriptor)
            raise ProcedureLibraryError("Sealed advisory originals cannot have SQLite sidecars")
        encoded = self._read(mission, "mission.sqlite3", MAX_DATABASE_BYTES, pin["ledger_sha256"])
        index_bytes = self._read(mission, "evidence/evidence.json", MAX_METADATA_BYTES, pin["index_sha256"])
        index = json.loads(index_bytes, object_pairs_hook=_pairs, parse_constant=_reject_constant)
        with captured_database(encoded) as database:
            data = derive_data(database, index, pin)
            # Canonical equality preserves type distinctions (e.g.1 vs1.0), unlike
            # Python dictionary equality. Used records always come from originals.
            if _canonical(data) != _canonical(self._manifests[mission]["data"]):
                raise ProcedureLibraryError("Export projection differs from independently read original bytes")
            if data["original_contract"]["native_protocol"] == 6 and self._manifests[mission]["validator"] != {
                    "git_revision": HISTORICAL_VALIDATOR, "source_sha256": HISTORICAL_VALIDATOR_SHA256}:
                raise ProcedureLibraryError("Historical export names an unsupported offline validation baseline")
            admission = data["admission"]
            if admission["phase"] not in _ELIGIBLE_ARCHIVE_PHASES:
                raise ProcedureLibraryError("Advisory export requires an eligible internally closed archive")
            if any(state not in ("completed", "expired", "unknown", "unreviewed") for state in data["reflection_states"]):
                raise ProcedureLibraryError("Advisory reflection admission remains open")
            self._dependencies[mission] = _pins(admission["library_sources"], mission)
            self._environments[mission] = admission["environment"]
            self._load_requests(database, mission)
            self._load_primitives(database, mission)
            for item in data["procedures"]:
                _id(item["event_id"])
                self._records.append(item["record"])
                if len(self._records) > MAX_PROCEDURE_RECORDS:
                    raise ProcedureLibraryError("Advisory library exceeds procedure record bound")

    def _request_data(self, mission: str, value: str) -> dict:
        # Original request grammar is verified offline. These current captured
        # identity/source fields and shared primitive predicates are checked live.
        request = _object(value)
        request_projection(request)
        return request

    def _mapping(self, mission: str, intent: dict, receipt: dict, **scope: Any) -> None:
        validate_captured_mapping(intent, receipt, protocol=self._origins[mission]["native_protocol"], **scope)

    def _ordinary_captures(self, mission: str, intent: dict, receipt: dict) -> None:
        entries = self._entries[mission]
        preflight = entries.get(intent["preflight_source"])
        if preflight is None:
            raise ProcedureLibraryError("Captured ordinary delivery lost its original preflight")
        published = _object(receipt["native_request_json"], 4096)
        observed = preflight["observation"]
        if (any(published[key] != observed[key] for key in ("session", "revision", "frame", "takeover_generation"))
                or published["boundary_id"] != observed["boundary"]["id"]):
            raise ProcedureLibraryError("Captured native admission contradicts its actual original preflight")
        if receipt.get("source_after") is None:
            return
        after = entries.get(receipt["source_after"])
        if after is None:
            raise ProcedureLibraryError("Captured delivery names unavailable original after evidence")
        projected = {key: after["observation"][key] for key in _ACK_FIELDS}
        ack = receipt["native_ack"]
        if (any(ack[key] != item for key, item in projected.items() if key not in {"id", "status", "error"})
                or receipt["source_after"] != _identity(ack)):
            raise ProcedureLibraryError("Captured ACK contradicts original after evidence")

    def source(self, mission_id: str, source_id: str) -> tuple[dict, bytes]:
        metadata, image = super().source(mission_id, source_id)
        pin = self._pins[mission_id]
        origin = {**self._origins[mission_id], "ledger_sha256": pin["ledger_sha256"], "index_sha256": pin["index_sha256"]}
        # The envelope has no current observation member, even for native7 donors.
        result = source_envelope(mission_id, origin, metadata["reference"], metadata["observation"])
        return result, image
