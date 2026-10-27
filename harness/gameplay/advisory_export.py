"""One immutable advisory export format, built only by offline engineering work.

Original ledgers, indices and PNGs remain byte-identical. The current projection
is reproducible from those blobs, not a certificate supplied by validator prose.
The live library accepts this format only; current raw archive validation is an
export prerequisite. One-time historical conversion lives outside current tools.
"""
from __future__ import annotations

from collections.abc import Sequence
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3

from .advisory_capture import capture_projection, request_projection
from .contracts import _pairs, _reject_constant, validate_json
from .evidence import _canonical
from .mission_ledger import DB_VERSION
from .procedure_archive import (
    MAX_DATABASE_BYTES, MAX_PRIMITIVES, MAX_REQUESTS, ProcedureLibraryError,
    SealedProcedureArchive, _id, _object, _pins, captured_database, validate_record_closure,
)
from .procedures import MAX_PROCEDURE_RECORDS, import_procedure, procedure_schema, validate_procedure

VERSION = "advisory-export/1"
MAX_MANIFEST_BYTES = 128 * 1024 * 1024
DEFAULT_EXPORT_BYTES = 32 * 1024 * 1024
HISTORICAL_VALIDATOR = "9a57c57cdd60943edd6029ce8676361041314d4e"
HISTORICAL_VALIDATOR_SHA256 = "cacaa69ac442ab767f8c57147dd17402f0fd7a24dc09b847dcc0abc9dc2e8e35"


def artifact_parts(mission: str, pin: dict) -> tuple[str, ...]:
    """Only trusted root and strictly checked original pins determine storage."""
    return (".runtime", "procedure-library", mission, pin["ledger_sha256"] + "-" + pin["index_sha256"])



def original_root(mission: str, reference: dict) -> Path:
    """Recorded path provenance only; never use this path for filesystem access."""
    path = Path(reference["frame_path"])
    suffix = (".runtime", "missions", mission, "evidence", "frames", reference["observation_id"] + ".png")
    if (not path.is_absolute() or ".." in path.parts or str(path) != reference["frame_path"]
            or tuple(path.parts[-6:]) != suffix or len(path.parts) <= 6):
        raise ProcedureLibraryError("Original frame path contradicts its qualified captured identity")
    return path.parents[5]


def derive_data(database: sqlite3.Connection, index: dict, pin: dict) -> dict:
    """Derive current bounded data from independently read pinned originals.

    Full old wire grammar belongs to offline validation, not this current data
    reader. Admission identity, environment and dependency fields are nevertheless
    bound to originals and all existing semantic closure guards still apply.
    """
    rows = SealedProcedureArchive._rows
    metadata_rows = rows(database, "SELECT key,value FROM metadata ORDER BY key", 64)
    if len({key for key, _ in metadata_rows}) != len(metadata_rows):
        raise ProcedureLibraryError("Duplicate captured metadata identity")
    metadata = dict(metadata_rows)
    admission, state = _object(metadata["admission"]), _object(metadata["state"])
    if admission.get("mission_id") != pin["mission_id"] or admission.get("schema") != "mission/11":
        raise ProcedureLibraryError("Captured admission differs from its original mission/schema")
    if "learning" not in admission:
        raise ProcedureLibraryError("Captured admission lost its original learning policy")
    learning = admission["learning"]
    if learning is not None and type(learning) is not dict:
        raise ProcedureLibraryError("Captured learning policy must be an object or null")
    environment = None if learning is None else learning["environment"]
    dependencies = [] if learning is None else learning["library_sources"]
    _pins(dependencies, pin["mission_id"])
    version = database.execute("PRAGMA user_version").fetchone()[0]
    # These explicit tuples describe original provenance in the current format;
    # they never select a legacy runtime/module or a native input receiver.
    if version == 12 and index["store_version"] == 5:
        protocol, view = 6, "program-view/1"
    elif version == DB_VERSION and index["store_version"] == 6:
        protocol, view = 7, "program-view/2"
    else:
        raise ProcedureLibraryError("Unsupported original export baseline")
    if environment is not None and (type(environment) is not dict or environment.get("native_protocol") != protocol):
        raise ProcedureLibraryError("Original admission and captured native contract differ")
    if environment is not None:
        environment_shape = procedure_schema()["properties"]["environment"]
        environment_shape["properties"]["native_protocol"] = {"type": "integer", "const": protocol}
        validate_json(environment, environment_shape)
    events, records = set(), []
    for event, record_id, body in rows(database,
            "SELECT event_id,record_id,body FROM memory WHERE entry_type='procedure' ORDER BY sequence",
            MAX_PROCEDURE_RECORDS):
        _id(event)
        _id(record_id)
        if event in events:
            raise ProcedureLibraryError("Duplicate captured procedure event")
        events.add(event)
        record = (import_procedure(body, ledger_sha256=pin["ledger_sha256"], index_sha256=pin["index_sha256"])
                  if protocol == 6 else validate_procedure(_object(body, 32_768)))
        if (record["id"] != record_id or record["mission_id"] != pin["mission_id"]
                or record["environment"] != environment):
            raise ProcedureLibraryError("Captured procedure differs from its original owner/environment")
        records.append({"event_id": event, "record": record})
    captures = []
    source_root = None
    for entry in index["entries"]:
        captured = capture_projection(entry["observation"])
        recorded_root = str(original_root(pin["mission_id"], entry["reference"]))
        if source_root is not None and source_root != recorded_root:
            raise ProcedureLibraryError("Original sources cross recorded archive roots")
        source_root = recorded_root
        if captured["original_protocol"] != protocol:
            raise ProcedureLibraryError("Original captured protocol differs from its source contract")
        captures.append({"reference": entry["reference"], "capture": captured,
                         "initial_lag_seconds": entry["initial_lag_seconds"], "retention": entry["retention"]})
    requests = rows(database, "SELECT id,payload,digest,state,result FROM requests ORDER BY rowid", MAX_REQUESTS)
    primitives = rows(database,
        "SELECT id,request_id,intent,native_id,state,result,effect FROM primitives ORDER BY rowid", MAX_PRIMITIVES)
    # Validate individual string bounds before serializing the large aggregate.
    headers = []
    for identity, payload, digest, disposition, result in requests:
        headers.append(request_projection(_object(payload)))
        _object(result)
    for identity, parent, intent, native, disposition, result, effect in primitives:
        _object(intent)
        if result is not None:
            _object(result)
        if effect is not None:
            _object(effect, 32_768)
    return {"schema": "advisory-data/1", "source": pin, "original_root": source_root,
            "original_contract": {"ledger_version": version, "native_protocol": protocol,
                "store_version": index["store_version"], "program_view": view},
            "admission": {"mission_id": admission["mission_id"], "schema": admission["schema"],
                "phase": state["phase"], "environment": environment, "library_sources": dependencies},
            "captures": captures, "procedures": records,
            "requests": [list(row) for row in requests], "request_headers": headers,
            "primitives": [list(row) for row in primitives],
            "reflection_states": [row[0] for row in rows(database, "SELECT state FROM reflection_jobs ORDER BY rowid", 64)]}


def read_manifest(encoded: bytes) -> dict:
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ProcedureLibraryError("Advisory manifest exceeds its byte bound")
    result = json.loads(encoded, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    if (type(result) is not dict or set(result) != {"schema", "source", "validator", "data"}
            or result["schema"] != VERSION or type(result["data"]) is not dict
            or type(result["validator"]) is not dict
            or set(result["validator"]) != {"git_revision", "source_sha256"}):
        raise ProcedureLibraryError("Unsupported current advisory export format")
    from .procedure_archive import _sha
    revision = result["validator"]["git_revision"]
    if type(revision) is not str or len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ProcedureLibraryError("Malformed offline validator provenance")
    _sha(result["validator"]["source_sha256"])
    return result


def _mkdir(parent: int, name: str) -> int:
    try:
        os.mkdir(name, 0o700, dir_fd=parent)
    except FileExistsError:
        pass
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)


def write_exports(archive: SealedProcedureArchive, validator: dict, *, max_bytes: int = DEFAULT_EXPORT_BYTES) -> tuple[Path, ...]:
    """Publish fresh exports from a fully offline-validated, still locked closure.

    A historical one-time conversion may call this builder with its pinned old
    read-only validator. This does not itself certify that validation took place.
    Live readers independently bind and validate all current captured data.
    """
    if type(max_bytes) is not int or not 1 <= max_bytes <= 4 * 1024**3:
        raise ProcedureLibraryError("Export requires a positive bounded output appetite")
    archive._open()
    pins = archive._pins
    prepared, used = [], 0
    # Complete source reading/derivation before publishing any artifact.
    for mission, pin in pins.items():
        index_bytes = archive._read(mission, "evidence/evidence.json",
                                    min(34 * 1024 * 1024, max_bytes - used), pin["index_sha256"])
        used += len(index_bytes)
        ledger = archive._read(mission, "mission.sqlite3", min(MAX_DATABASE_BYTES, max_bytes - used), pin["ledger_sha256"])
        used += len(ledger)
        index = json.loads(index_bytes, object_pairs_hook=_pairs, parse_constant=_reject_constant)
        with captured_database(ledger) as database:
            data = derive_data(database, index, pin)
        files = {"mission.sqlite3": ledger, "evidence/evidence.json": index_bytes}
        for capture in data["captures"]:
            ref = capture["reference"]
            image = archive._read(mission, "evidence/frames/" + ref["observation_id"] + ".png",
                                  min(32 * 1024 * 1024, max_bytes - used), ref["frame_sha256"])
            used += len(image)
            files["evidence/frames/" + ref["observation_id"] + ".png"] = image
        manifest = _canonical({"schema": VERSION, "source": pin, "validator": validator, "data": data})
        read_manifest(manifest)
        used += len(manifest)
        if used > max_bytes:
            raise ProcedureLibraryError("Complete advisory export exceeds the original output appetite")
        prepared.append((mission, pin, manifest, files))
    published = []
    for mission, pin, manifest, files in prepared:
        parent = os.dup(archive._root_fd)
        directory = None
        try:
            parts = artifact_parts(mission, pin)
            for part in parts[:-1]:
                child = _mkdir(parent, part)
                os.close(parent)
                parent = child
            # Exclusive mkdir reserves this fresh artifact; no prior output can
            # be overwritten. A reader needs the manifest committed last.
            os.mkdir(parts[-1], 0o700, dir_fd=parent)
            directory = archive.root.joinpath(*parts)
            destination = os.open(parts[-1], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            lock = os.open("mission.lock", os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=destination)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                evidence = _mkdir(destination, "evidence")
                try:
                    evidence_lock = os.open("evidence.lock", os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                            0o600, dir_fd=evidence)
                    os.close(evidence_lock)
                finally:
                    os.close(evidence)
                for relative, content in [*files.items(), (".manifest.tmp", manifest)]:
                    target = os.dup(destination)
                    try:
                        path_parts = relative.split("/")
                        for part in path_parts[:-1]:
                            child = _mkdir(target, part)
                            os.close(target)
                            target = child
                        descriptor = os.open(path_parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                             0o600, dir_fd=target)
                        with os.fdopen(descriptor, "wb") as stream:
                            stream.write(content)
                            stream.flush()
                            os.fsync(stream.fileno())
                    finally:
                        os.close(target)
                os.link(".manifest.tmp", "manifest.json", src_dir_fd=destination, dst_dir_fd=destination, follow_symlinks=False)
                os.unlink(".manifest.tmp", dir_fd=destination)
                os.fsync(destination)
                published.append(directory)
            finally:
                os.close(lock)
                os.close(destination)
        except BaseException:
            if directory is not None:
                shutil.rmtree(parts[-1], dir_fd=parent)
            # Previously completed immutable exports remain evidence, not rolled
            # back by deleting public artifacts after a later source failure.
            raise
        finally:
            os.close(parent)
    return tuple(published)



class _CurrentExportArchive(SealedProcedureArchive):
    """Validate new current raw donors against already exported dependencies."""

    def __init__(self, root: Path, sources: Sequence[dict], library: SealedProcedureArchive | None):
        self._library = library
        current = "offline-export"
        while any(pin["mission_id"] == current for pin in sources):
            current += "-x"
        super().__init__(root, sources, current_mission_id=current)

    def validate_episode(self, episode: dict) -> tuple[tuple[str, str], ...]:
        if episode["mission_id"] not in self._pins and self._library is not None:
            return self._library.validate_episode(episode)
        return super().validate_episode(episode)

    def _validate_closure(self) -> None:
        if self._library is None:
            return super()._validate_closure()
        overlap = self._pins.keys() & self._library._pins.keys()
        if overlap:
            raise ProcedureLibraryError("New raw donors and exported dependencies must be disjoint")
        pins = {**self._pins, **self._library._pins}
        _pins(list(pins.values()), "offline-combined-closure")
        validate_record_closure([*self._library.records(), *self._records], pins,
            {**self._library._dependencies, **self._dependencies}, self.validate_episode)


def export_current(root: Path, sources: list[dict], *, validator_revision: str,
                   dependencies: Sequence[dict] = (), max_bytes: int = DEFAULT_EXPORT_BYTES) -> tuple[Path, ...]:
    """Export new current raw donors; dependencies are explicitly current exports.

    There is no raw historical fallback. A current mission with an imported parent
    keeps its complete original pins and validates that ancestry from exports.
    """
    from contextlib import ExitStack
    from .procedure_library import ProcedureLibrary
    source_sha = hashlib.sha256(Path(__file__).with_name("procedure_archive.py").read_bytes()).hexdigest()
    with ExitStack() as stack:
        library = (stack.enter_context(ProcedureLibrary(root, dependencies, current_mission_id="offline-dependencies"))
                   if dependencies else None)
        archive = stack.enter_context(_CurrentExportArchive(root, sources, library))
        return write_exports(archive, {"git_revision": validator_revision, "source_sha256": source_sha}, max_bytes=max_bytes)
