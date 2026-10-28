"""Passive, rebuildable campaign views over the mission ledger and canonical sources.

The ledger owns immutable assertions and request/effect history. This module owns
only their bounded semantic projection; it cannot admit work or execute inputs.
The small reducer is specific to the closed campaign-memory contract, rather than
another history store, general provenance engine or learned retrieval service.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Callable

from .contracts import ContractError, json_object
from .source_contracts import CapacityError, EvidenceError, SourceReference
from .contracts import canonical
from .memory_contracts import MAX_CONTEXT_BYTES, MAX_HANDOFF_CONTEXT_BYTES, MAX_HANDOFF_SOURCES, MEMORY_VERSION, MemoryRequestRefusal, validate_memory_entry, validate_work_view, validate_scope, validate_context_query
from .memory_ports import MemoryRepository, MemorySources, MemoryRecordNotFound, ProcedureEpisodeRefusal
from .procedures import MAX_PROCEDURE_RECORDS, project_procedures

MAX_CLAIMS = 32
MAX_WORK = 16
MAX_SOURCES = 16


def _copy(value: dict) -> dict:
    return json_object(value)


def _clock(now: float) -> None:
    if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
        raise ContractError("Memory requires finite nonnegative time")


def _wall_clock(value: int) -> None:
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ContractError("Memory requires integer host wall-clock milliseconds")


def _identity(prefix: str, value: dict) -> str:
    return prefix + hashlib.sha256(canonical(value).encode()).hexdigest()


def _group(entry: dict) -> str:
    return canonical({"scope": entry["scope"], "key": entry["key"]})


def _later(left: dict, right: dict) -> bool:
    """Strict supported partial order: missing clocks cannot invent alignment."""
    a, b = left["observed_time"], right["observed_time"]
    pairs = [(a[k], b[k]) for k in ("revision", "turn") if a[k] is not None and b[k] is not None]
    # A clock present on just one side makes the orders incomparable.
    if any((a[k] is None) != (b[k] is None) for k in ("revision", "turn")):
        return False
    return bool(pairs) and all(x >= y for x, y in pairs) and any(x > y for x, y in pairs)


class CampaignMemory:
    """No authority, worker, replay, controller or process references.

    `apply` consumes an already-admitted exact request. Contexts are advisory
    decoded copies. A decision must refer to a packet issued by this instance;
    after restart callers retrieve again. The durable Decision's frozen fields
    retain its exact version/query and selected IDs, without a second packet log.
    """
    def __init__(self, ledger: MemoryRepository, store: MemorySources, library=None):
        self.ledger = ledger
        self.store = store
        self.library = library
        self._packets: list[dict] = []
        self._procedure_heads()

    def _procedure_records(self) -> tuple[dict, ...]:
        return (() if self.library is None else self.library.records()) + tuple(
            row["entry"] for row in self.ledger.memory_records("procedure"))

    def _procedure_heads(self) -> dict[str, dict]:
        records = self._procedure_records()
        policy = self.ledger.learning
        if (records and policy is None or policy is not None and policy.library_sources and self.library is None):
            raise ContractError("Procedure retrieval requires its admitted library and environment")
        if policy is not None and any(record["schema"] == "procedure/3"
                                      and record["environment"] != dict(policy.environment) for record in records):
            raise ContractError("Procedure history crosses its admitted environment")
        return project_procedures(records)

    @staticmethod
    def _procedure_ref(entry: dict) -> dict:
        return {"mission_id": entry["mission_id"], "revision_id": entry["id"]}

    def procedure_source(self, mission_id: str, source_id: str) -> tuple[dict, bytes]:
        if mission_id == self.ledger.mission_id:
            return self.store.export_source(source_id)
        if self.library is None:
            raise ContractError("Historical procedure evidence is not admitted")
        return self.library.source(mission_id, source_id)

    def _procedure_dependencies(self, entry: dict, *, candidate=False) -> dict[tuple[str, str], type[ContractError]]:
        """Collect qualified ancestry sources and validate joins without image I/O."""
        records = self._procedure_records()
        by_id = {(record["mission_id"], record["id"]): record for record in records}
        chain = [entry]
        current = entry
        while current["parent"] is not None:
            parent = current["parent"]
            current = by_id[(parent["mission_id"], parent["revision_id"])]
            chain.append(current)
        sources: dict[tuple[str, str], type[ContractError]] = {}
        primitives = self.ledger.primitive_records()
        # Retained ancestry stays strict even while validating a new revision.
        for record in reversed(chain):
            new = candidate and record is entry
            refusal = MemoryRequestRefusal if new else ContractError
            for episode in record["support"] + record["counterexamples"]:
                mission = episode["mission_id"]
                if mission == self.ledger.mission_id:
                    linked = set()
                    for identity in episode["request_ids"]:
                        try:
                            request = self.ledger.request(identity)
                        except MemoryRecordNotFound as exc:
                            if not new:
                                raise
                            raise MemoryRequestRefusal("Procedure episode request is not retained") from exc
                        if request["state"] in ("accepted", "running"):
                            raise refusal("Procedure evidence requires a settled original request")
                        linked.update(request["request"].get("sources", ()))
                        linked.update((request["result"] or {}).get("source_ids", ()))
                        for primitive in primitives:
                            if primitive["request_id"] != identity:
                                continue
                            if (primitive["state"] in ("prepared", "published")
                                    or primitive["state"] == "unknown" and primitive["effect"] is None):
                                raise refusal("Procedure episode has unresolved original input effects")
                            linked.update(primitive["intent"][key] for key in ("source_before", "preflight_source"))
                            receipt = primitive["result"] or {}
                            linked.update(receipt[key] for key in ("source_before", "preflight_source", "source_after")
                                          if receipt.get(key) is not None)
                    if not set(episode["source_ids"]) <= linked:
                        raise refusal("Procedure evidence is unrelated to its cited requests")
                else:
                    if self.library is None:
                        raise refusal("Procedure episode mission is not admitted")
                    try:
                        self.library.validate_episode(episode)
                    except ProcedureEpisodeRefusal as exc:
                        if not new:
                            raise
                        raise MemoryRequestRefusal(str(exc)) from exc
                for source in episode["source_ids"]:
                    qualified = (mission, source)
                    if qualified in sources:
                        continue
                    sources[qualified] = refusal
        return sources

    def _procedure_support(self, entry: dict, *, candidate=False) -> set[tuple[str, str]]:
        """Validate complete ancestry, episode joins and images; never semantic truth."""
        sources = self._procedure_dependencies(entry, candidate=candidate)
        for qualified, refusal in sources.items():
            metadata, _ = self.procedure_source(*qualified)
            if metadata["disposition"] != "retained":
                raise refusal("Disputed procedure evidence is ineligible")
        return set(sources)

    def select_procedure(self, selection: dict) -> dict:
        heads = self._procedure_heads()
        chosen = next((entry for entry in heads.values() if self._procedure_ref(entry) == {
            key: selection[key] for key in ("mission_id", "revision_id")}), None)
        if (chosen is None or chosen["schema"] != "procedure/3"
                or chosen["status"] not in ("candidate", "active")):
            raise MemoryRequestRefusal("Select an eligible current procedure revision, with scoped applicability")
        self._procedure_support(chosen)
        return _copy(chosen)

    def _scope(self, scope: dict) -> dict:
        return validate_scope(scope, mission_id=self.ledger.mission_id)

    def _references(self) -> dict[str, SourceReference]:
        return {ref.observation_id: ref for ref in self.store.historical_references}

    def _sources(self, entry: dict) -> list[SourceReference]:
        refs = self._references()
        result = []
        for identity in entry["sources"]:
            ref = refs.get(identity)
            if ref is None:
                raise MemoryRequestRefusal("Source identity/session differs from memory scope")
            if ref.session != entry["scope"]["session"]:
                raise MemoryRequestRefusal("Source identity/session differs from memory scope: every cited source "
                    "must share the entry's grounding session. Cross-session sources need separately grounded entries.")
            if self.store.source_status(ref) != "retained":
                raise MemoryRequestRefusal("Disputed source cannot establish memory")
            result.append(ref)
        return result

    def _validate_claim(self, entry: dict, claims: dict[str, dict], *, retired: set[str]) -> None:
        refs = self._sources(entry)
        dependencies = {identity for group in entry["supports"] for identity in group["claims"]}
        pending = list(dependencies)
        visited = set()
        while pending:
            identity = pending.pop()
            if identity == entry["id"] or identity not in claims:
                raise MemoryRequestRefusal("Self, forward, missing or cyclic claim support")
            if identity in retired:
                raise MemoryRequestRefusal("A correction cannot derive from its retired premise")
            if identity in visited:
                continue
            visited.add(identity)
            premise = claims[identity]
            if premise["scope"] != entry["scope"]:
                raise MemoryRequestRefusal("Claim supports cannot align another coordinate/session scope")
            pending.extend(c for group in premise["supports"] for c in group["claims"])
        # The observed order must name an actual source boundary, including its
        # absent native turn. Older premises may accompany that anchor.
        order = entry["observed_time"]
        if refs and not any(order == {"revision": ref.revision, "turn": ref.turn} for ref in refs):
            raise MemoryRequestRefusal("Observed order must match an actual retained source")
        if not refs and any(v is not None for v in order.values()):
            raise MemoryRequestRefusal("Source-free interpretation has no observed native order")
        if any(_later({"observed_time": {"revision": ref.revision, "turn": ref.turn}}, entry) for ref in refs):
            raise MemoryRequestRefusal("Claim order predates its source")
        if not entry["supports"] and entry["status"] not in ("unknown", "disputed", "retired"):
            raise MemoryRequestRefusal("A supported value requires explicit support groups")

    def apply(self, request: dict, *, now: float) -> dict:
        """Append admitted memory; `now` is the ledger's real wall time in seconds."""
        _clock(now)
        data = self.ledger.validate_application(request)
        entry, kind = data["entry"], data["entry_type"]
        if kind == "decision":
            return self.record_decision(entry, now=now, event_id=data["request_id"])
        if kind == "procedure":
            if self.ledger.learning is None:
                raise MemoryRequestRefusal("Procedure adaptation is not admitted")
            if entry["environment"] != dict(self.ledger.learning.environment):
                raise MemoryRequestRefusal("Procedure environment differs from frozen admission")
            existing = self._procedure_records()
            self._procedure_heads()  # Existing history is never a candidate refusal.
            if len(existing) >= MAX_PROCEDURE_RECORDS:
                raise CapacityError("Procedure projection exceeds 256 records")
            try:
                project_procedures((*existing, entry))
            except ContractError as exc:
                # Pure projection of a validated addition to a valid closure.
                raise MemoryRequestRefusal(str(exc)) from exc
            self._procedure_support(entry, candidate=True)
            sequence = self.ledger.append_memory(data["request_id"], kind, entry, now=now, candidate=True)
            return _copy({"memory_version": sequence, "entry": entry, "grants_authority": False})
        if kind == "claim":
            claims = {row["entry"]["id"]: row["entry"] for row in self.ledger.memory_records("claim")}
            self._validate_claim_history(claims)
            retired = set(data.get("retired_ids", []))
            if data["kind"] == "correct":
                if set(entry["supersedes"]) != retired:
                    raise MemoryRequestRefusal("Correction supersedes must exactly match durable retired_ids")
                if any(identity not in claims or claims[identity]["scope"] != entry["scope"] for identity in retired):
                    raise MemoryRequestRefusal("Correction requires existing claims in its exact scope")
            elif entry["supersedes"]:
                raise MemoryRequestRefusal("Retirement requires an explicit durable correct request/reason")
            self._validate_claim(entry, claims, retired=retired)
            if entry["received_time"] > int(now * 1000):
                raise MemoryRequestRefusal("Claim receipt time is in the future")
        else:
            self._sources(entry)
            old = [r["entry"] for r in self.ledger.memory_records("work") if r["entry"]["id"] == entry["id"]]
            if old and any(entry[k] != old[-1][k] for k in ("scope", "intent", "predecessor_work_id")):
                raise MemoryRequestRefusal("A work identity retains its scope, intent and predecessor")
            if not entry["sources"] and (entry["available"] or entry["observed_output"] or entry["progress"] is not None or entry["status"] == "completed"):
                raise MemoryRequestRefusal("Observed work/available output requires retained evidence")
            primitives = {p["logical_id"]: p for p in self.ledger.primitive_records()}
            if any(identity not in primitives or primitives[identity]["intent"]["expected_session"] != entry["scope"]["session"]
                   for identity in entry["unresolved_effects"]):
                raise MemoryRequestRefusal("Work references an unknown or differently scoped primitive effect")
        sequence = self.ledger.append_memory(data["request_id"], kind, entry, now=now, candidate=True)
        return _copy({"memory_version": sequence, "entry": entry, "grants_authority": False})

    @staticmethod
    def _validate_claim_history(claims: dict[str, dict]) -> None:
        """Check retained dependency order without computing pairwise frontiers."""
        seen = set()
        for identity, claim in claims.items():
            parents = set(claim["supersedes"]) | {c for group in claim["supports"] for c in group["claims"]}
            if not parents <= seen:
                raise ContractError("Durable claims contain missing/forward/cyclic dependencies")
            if any(claims[parent]["scope"] != claim["scope"] for parent in parents):
                raise ContractError("Durable claim dependencies cross their exact scope")
            seen.add(identity)

    @staticmethod
    def _frontier(claims: dict[str, dict], *, selected_ids: set[str] | None = None) -> tuple[list[list[str]], set[str]]:
        """Validate the full graph, then reduce complete groups containing selected IDs."""
        CampaignMemory._validate_claim_history(claims)
        retired = {identity for claim in claims.values() for identity in claim["supersedes"]}
        ancestors: dict[str, set[str]] = {}
        for identity, claim in claims.items():
            ancestors[identity] = set(claim["supersedes"])
            for predecessor in claim["supersedes"]:
                ancestors[identity].update(ancestors.get(predecessor, ()))
        selected_groups = None if selected_ids is None else {_group(claims[identity]) for identity in selected_ids}
        groups: dict[str, list[str]] = {}
        for identity, claim in claims.items():
            group = _group(claim)
            if selected_groups is None or group in selected_groups:
                groups.setdefault(group, []).append(identity)
        frontiers = []
        for ids in groups.values():
            if not any(claims[identity]["supersedes"] for identity in ids):
                # Missing clocks cannot align different masks. Within each
                # mask, maxima preserve all equal-order claims and conflicts.
                masks: dict[tuple[bool, bool], list[str]] = {}
                for identity in ids:
                    order = claims[identity]["observed_time"]
                    mask = (order["revision"] is not None, order["turn"] is not None)
                    masks.setdefault(mask, []).append(identity)
                surviving: set[str] = set()
                for mask, members in masks.items():
                    if not any(mask):
                        surviving.update(members)
                    elif all(mask):
                        pairs = {(claims[identity]["observed_time"]["revision"],
                                  claims[identity]["observed_time"]["turn"]) for identity in members}
                        maxima = set()
                        max_turn = None
                        # Descending pairs visit the highest turn first at
                        # each revision; lower revisions must exceed it.
                        for revision, turn in sorted(pairs, reverse=True):
                            if max_turn is None or turn > max_turn:
                                maxima.add((revision, turn))
                                max_turn = turn
                        surviving.update(identity for identity in members if
                            (claims[identity]["observed_time"]["revision"],
                             claims[identity]["observed_time"]["turn"]) in maxima)
                    else:
                        clock = "revision" if mask[0] else "turn"
                        maximum = max(claims[identity]["observed_time"][clock] for identity in members)
                        surviving.update(identity for identity in members
                            if claims[identity]["observed_time"][clock] == maximum)
                frontiers.append([identity for identity in ids if identity in surviving])
                continue
            frontiers.append([identity for identity in ids if not any(
                identity in ancestors[other] or (other not in ancestors[identity] and _later(claims[other], claims[identity]))
                for other in ids if other != identity)])
        return frontiers, retired

    @staticmethod
    def _closure(ids: list[str], claims: dict[str, dict]) -> set[str]:
        result = set(ids)
        pending = list(ids)
        while pending:
            for support in claims[pending.pop()]["supports"]:
                for identity in support["claims"]:
                    if identity not in claims:
                        raise ContractError("Durable claim support is missing")
                    if identity not in result:
                        result.add(identity)
                        pending.append(identity)
        return result

    @staticmethod
    def _effects(entry: dict, refs: dict[str, SourceReference], primitives: tuple[dict, ...]) -> list[str]:
        sources = [refs[s] for s in entry["sources"] if s in refs]
        affected = []
        for primitive in primitives:
            intent = primitive["intent"]
            if (intent["expected_session"] != entry["scope"]["session"]
                    or primitive["state"] in ("rejected", "not_dispatched")):
                continue
            if not sources or any(ref.revision <= intent["expected_revision"] for ref in sources):
                affected.append(primitive["logical_id"])
        return affected

    @staticmethod
    def _work_views(rows: tuple[dict, ...], refs: dict[str, SourceReference]) -> tuple[dict, dict]:
        """Latest planning fields plus a coherent observed-state source frontier.

        Work has no independent native clock field. Its retained source boundary
        supplies one only when that association is provable. A later receipt does
        not replace newer observed progress/output/status/stage with an older image
        reading. Commitments, predictions and next verification remain planning
        fields; they never establish observed completion.
        """
        events: dict[str, list[dict]] = {}
        for row in rows:
            events.setdefault(row["entry"]["id"], []).append(row["entry"])
        views, reasons = {}, {}
        measured = ("progress", "available", "observed_output", "status", "stage")
        for identity, entries in events.items():
            latest = _copy(entries[-1])
            observed = [entry for entry in entries if entry["sources"]]
            ordered = []
            for entry in observed:
                sources = [refs[s] for s in entry["sources"] if s in refs]
                orders = [{"observed_time": {"revision": ref.revision, "turn": ref.turn}} for ref in sources]
                maxima = [order for order in orders if not any(_later(other, order) for other in orders)]
                distinct = {canonical(order) for order in maxima}
                order = maxima[0] if len(distinct) == 1 and len(sources) == len(entry["sources"]) else None
                ordered.append((entry, order))
            frontier = [(entry, order) for entry, order in ordered if order is None or not any(
                other is not None and _later(other, order) for _, other in ordered)]
            if frontier:
                values = {canonical({k: entry[k] for k in measured}) for entry, _ in frontier}
                orders = {canonical(order) for _, order in frontier if order is not None}
                ambiguous = len(values) != 1 or len(orders) != 1 or any(order is None for _, order in frontier)
                sources = set(latest["sources"]) | {s for entry, _ in frontier for s in entry["sources"]}
                latest["sources"] = sorted(sources)
                if ambiguous:
                    latest.update(progress=None, available=[], observed_output=[], status="unknown", stage="unknown")
                    reasons[identity] = ["conflicting/incomparable work state frontier; reobserve progress, output and stage"]
                else:
                    for key in measured:
                        latest[key] = frontier[-1][0][key]
            views[identity] = latest
        return views, reasons

    def context(self, scope: dict, query: str, *, max_bytes: int, now_monotonic: float,
                now_timestamp_ms: int, required_work_ids: frozenset[str] | None = None,
                support_source_ids: tuple[str, ...] = (),
                source_status: Callable[[str], str] | None = None, cache: bool = True) -> dict:
        """Selective32KiB/16sources, or complete handoff128KiB/128sources.

        Source-check work is bounded separately from retained archive size. Broken
        frontier sources remain unknown across reopen; no fallback selects an older
        matching sentence. Historical scope hints remain explicitly last_seen.
        """
        complete = required_work_ids is not None
        if complete and type(required_work_ids) is not frozenset:
            raise ContractError("Complete context requires an explicit frozen Work set")
        maximum = MAX_HANDOFF_CONTEXT_BYTES if complete else MAX_CONTEXT_BYTES
        source_limit = MAX_HANDOFF_SOURCES if complete else MAX_SOURCES
        if type(max_bytes) is not int or not 512 <= max_bytes <= maximum:
            raise ContractError("Context byte allowance is outside its current mode")
        if not complete and (support_source_ids or source_status is not None):
            raise ContractError("Additional source checks require complete handoff context")
        scope = self._scope(scope)
        validate_context_query(scope, query, min(max_bytes, MAX_CONTEXT_BYTES))
        _clock(now_monotonic)
        _wall_clock(now_timestamp_ms)
        rows = {kind: self.ledger.memory_records(kind) for kind in ("claim", "work", "decision", "procedure")}
        version = max((row["sequence"] for records in rows.values() for row in records), default=0)
        claims = {r["entry"]["id"]: r["entry"] for r in rows["claim"]}
        refs = self._references()
        work, work_reasons = self._work_views(rows["work"], refs)
        if complete and (len(required_work_ids) > MAX_WORK or not required_work_ids <= work.keys()):
            raise CapacityError("Complete handoff context requires every bounded Work identity")
        frontiers, retired = CampaignMemory._frontier(claims)
        primitives = self.ledger.primitive_records()
        frontier_ids = {identity for ids in frontiers for identity in ids}
        disputed = set()
        for ids in frontiers:
            different_values = len({canonical(claims[i]["value"]) for i in ids}) > 1
            different_orders = len({canonical(claims[i]["observed_time"]) for i in ids}) > 1
            if different_values or different_orders:
                disputed.update(ids)
        mission_id = self.ledger.mission_id
        checks: dict[tuple[str, str], str] = {}

        def qualified_current(identities: set[str]) -> set[tuple[str, str]]:
            return {(mission_id, identity) for identity in identities}

        current = None
        try:
            current, fresh = (None, False) if complete else self.store.inspect_current(
                now_monotonic=now_monotonic, now_timestamp_ms=now_timestamp_ms)
            if current is not None:
                checks[(mission_id, current.observation_id)] = "retained"
            if not fresh:
                current = None
        except CapacityError:
            raise
        except EvidenceError:
            # Selected closures below retain the exact source loss diagnostic.
            current = None
        # inspect_current may have verified an opaque menu source before returning
        # None. Reserve its one check even when its identity was not returned.
        reserved_check = 0 if complete or checks else 1

        def check(identity: str, mission: str = mission_id) -> str:
            qualified = (mission, identity)
            if qualified not in checks:
                if len(checks) + reserved_check >= source_limit:
                    raise CapacityError("Packet source-check budget exhausted")
                ref = refs.get(identity)
                if mission != mission_id:
                    try:
                        metadata, _ = self.procedure_source(mission, identity)
                        checks[qualified] = metadata["disposition"]
                    except CapacityError:
                        raise
                    except (ContractError, OSError) as exc:
                        checks[qualified] = "unavailable: " + str(exc)
                elif source_status is not None:
                    checks[qualified] = source_status(identity)
                elif ref is None:
                    checks[qualified] = "unavailable"
                else:
                    try:
                        checks[qualified] = self.store.source_status(ref)
                    except CapacityError:
                        raise
                    except EvidenceError as exc:
                        checks[qualified] = "unavailable: " + str(exc)
            return checks[qualified]

        valid: dict[str, bool] = {}
        def supported(identity: str, visiting: frozenset[str] = frozenset()) -> bool:
            if identity in valid:
                return valid[identity]
            if identity in visiting:
                raise ContractError("Cyclic durable supports")
            entry = claims[identity]
            groups = entry["supports"]
            result = False
            for group in groups:
                # Evaluate every declared premise, retaining concrete source loss
                # even when another conjunct already failed.
                good_sources = [check(s) == "retained" for s in group["sources"]]
                good_claims = [supported(c, visiting | {identity})
                               and not self._effects(claims[c], refs, primitives)
                               for c in group["claims"]]
                result |= all(good_sources + good_claims)
            valid[identity] = (result and identity not in retired and identity not in disputed
                               and identity in frontier_ids
                               and entry["status"] not in ("unknown", "disputed", "retired"))
            return valid[identity]

        terms = set(re.findall(r"[\w-]+", query.lower()))
        def rank(entries: list[dict]) -> tuple:
            exact = any(e["scope"] == scope for e in entries)
            text = " ".join(canonical(e.get("key", {})) + " " + e.get("text", e.get("intent", "")) for e in entries).lower()
            score = sum(term in text for term in terms)
            usable = [e for e in entries if e["id"] not in retired | disputed
                      and e["status"] not in ("unknown", "disputed", "retired", "failed")]
            fresh = current is not None and any(current.observation_id in e["sources"]
                and not self._effects(e, refs, primitives) for e in usable)
            eligibility = 0 if fresh else (1 if usable else 2)
            return (0 if exact else 1, eligibility, -score, entries[0]["id"])

        groups = [] if complete else [ids for ids in frontiers if not terms or rank([claims[i] for i in ids])[2] < 0]
        groups.sort(key=lambda ids: rank([claims[i] for i in ids]))
        ordered_work = ([work[identity] for identity in sorted(required_work_ids)] if complete else
            [entry for entry in work.values() if not terms or rank([entry])[2] < 0])
        ordered_work.sort(key=lambda entry: rank([entry]))
        packet: dict[str, Any] = {"schema": MEMORY_VERSION, "record_type": "Context", "packet_id": "",
            "scope": scope, "query": query, "memory_version": version,
            "as_of": {"timestamp_ms": now_timestamp_ms, "monotonic": now_monotonic},
            "claims": [], "work": [], "sources": [], "procedures": [], "procedure_refs": [], "procedure_sources": [], "dispositions": {},
            "omitted": {"claims": len(claims), "work": len(work), "procedures": len(self._procedure_heads()), "bounds": 0, "reasons": {}},
            "reobservations": [], "grants_authority": False}
        selected: set[str] = set()
        selected_sources: set[str] = set(support_source_ids)
        if len(selected_sources) > source_limit:
            raise CapacityError("Complete handoff support source bound exhausted")

        def finish(value: dict) -> dict:
            result = _copy(value)
            result["packet_id"] = _identity("packet-", {k: v for k, v in result.items() if k != "packet_id"})
            return result

        def fits(value: dict) -> bool:
            return len(canonical(finish(value)).encode()) <= max_bytes

        def sources_for(ids: set[str]) -> set[str]:
            return {s for identity in ids for s in claims[identity]["sources"]}

        def add_sources(candidate: dict, identities: set[str]) -> None:
            candidate["sources"] = [{"id": identity, "status": check(identity),
                "reference": None if identity not in refs else refs[identity].to_dict()} for identity in sorted(identities)]

        if complete:
            add_sources(packet, selected_sources)

        def reobserve(candidate: dict, entry: dict, reason: str) -> None:
            candidate["reobservations"].append({"id": entry["id"], "scope": entry["scope"],
                "reason": reason, "instruction": "Reobserve " + entry.get("coverage", entry.get("next_verification", "visible state"))})

        def omit(reason: str, count: int) -> None:
            packet["omitted"]["bounds"] += count
            reasons = packet["omitted"]["reasons"]
            reasons[reason] = reasons.get(reason, 0) + count

        for ids in groups:
            closure = self._closure(ids, claims)
            new_ids = closure - selected
            source_ids = selected_sources | sources_for(closure)
            if (len(selected | closure) > MAX_CLAIMS or len(source_ids) > MAX_SOURCES
                    or len(set(checks) | qualified_current(source_ids)) + reserved_check > MAX_SOURCES):
                reason = "claim/dependency limit" if len(selected | closure) > MAX_CLAIMS else "distinct source/check limit"
                omit(reason, len(new_ids))
                continue
            candidate = _copy(packet)
            for identity in sorted(new_ids):
                original = claims[identity]
                entry = _copy(original)
                reasons = []
                is_supported = supported(identity)
                effects = self._effects(entry, refs, primitives)
                if identity in retired:
                    entry["status"] = "retired"; reasons.append("explicit correction retired premise")
                elif identity in disputed:
                    entry["status"] = "disputed"; reasons.append("conflicting or incomparable frontier")
                elif not is_supported:
                    entry["status"] = "unknown"; reasons.append("source/support unavailable, disputed or retired")
                elif effects:
                    entry["status"] = "last_seen"; reasons.append("potentially changed by primitives: " + ",".join(effects))
                elif entry["scope"] != scope:
                    entry["status"] = "last_seen"; reasons.append("historical session/coordinate scope; alignment unproved")
                elif current is not None and current.observation_id in entry["sources"]:
                    entry["status"] = "inferred" if original["status"] == "inferred" else "current"
                else:
                    entry["status"] = "last_seen"; reasons.append("retained observation is not a fresh current boundary")
                if entry["status"] in ("unknown", "disputed", "retired"):
                    entry["value"] = {"quantity": None, "state": None}
                candidate["claims"].append(entry)
                if reasons:
                    candidate["dispositions"][identity] = reasons
                    if identity in ids:
                        reobserve(candidate, original, "; ".join(reasons))
            add_sources(candidate, source_ids)
            candidate["omitted"]["claims"] = len(claims) - len(selected | closure)
            if fits(candidate):
                packet, selected, selected_sources = candidate, selected | closure, source_ids
            else:
                omit("packet byte limit", len(new_ids))

        for original in ordered_work:
            source_ids = selected_sources | set(original["sources"])
            if (len(original["sources"]) > MAX_HANDOFF_SOURCES or len(packet["work"]) >= MAX_WORK
                    or len(source_ids) > source_limit
                    or len(set(checks) | qualified_current(source_ids)) + reserved_check > source_limit):
                if complete:
                    raise CapacityError("Complete handoff Work/source bound exhausted; no omission")
                omit("work/source limit", 1)
                continue
            candidate = _copy(packet)
            entry = validate_work_view({**original, "record_type": "WorkView"})
            bad = [s for s in entry["sources"] if check(s) != "retained"]
            effects = self._effects(entry, refs, primitives)
            unresolved = [p["logical_id"] for p in primitives if p["logical_id"] in set(effects) | set(entry["unresolved_effects"])
                          and (p["state"] in ("prepared", "published") or (p["state"] == "unknown" and p["effect"] is None))]
            reasons = list(work_reasons.get(entry["id"], ()))
            fresh_scoped_source = (entry["scope"] == scope and current is not None
                                   and current.observation_id in entry["sources"])
            needs_observation = bool(entry["sources"]) or entry["status"] != "planned"
            if bad or effects or (needs_observation and not fresh_scoped_source):
                entry["status"] = "unknown"
                entry["available"] = []
                if bad:
                    entry.update(progress=None, observed_output=[])
                    reasons.append("work source unavailable; reobserve progress, output and status")
                else:
                    reasons.append("retained progress/output/stage are historical; current availability/status needs fresh scoped observation")
            if unresolved:
                entry["status"] = "unknown"
                # The closed schema bounds this list; do not silently discard a
                # premise when an old work item has too many unresolved effects.
                if len(unresolved) > 16:
                    if complete:
                        raise CapacityError("Complete handoff unresolved-effect bound exhausted")
                    omit("work unresolved-effect limit", 1)
                    continue
                reasons.append("unknown delivery/effect remains unresolved")
            entry["unresolved_effects"] = unresolved
            candidate["work"].append(entry)
            if reasons:
                candidate["dispositions"][entry["id"]] = reasons
                reobserve(candidate, original, "; ".join(reasons))
            add_sources(candidate, source_ids)
            candidate["omitted"]["work"] = len(work) - len(candidate["work"])
            if fits(candidate):
                packet, selected_sources = candidate, source_ids
            else:
                if complete:
                    raise CapacityError("Complete handoff packet byte limit; no omission")
                omit("packet byte limit", 1)
        heads = list(self._procedure_heads().values())
        heads.sort(key=lambda entry: (-sum(term in canonical(entry).lower() for term in terms), entry["procedure_id"]))
        for entry in heads:
            if not complete and terms and not any(term in canonical(entry).lower() for term in terms):
                continue
            try:
                support = set(self._procedure_dependencies(entry))
            except (ContractError, OSError) as exc:
                if complete:
                    raise CapacityError("Complete procedure context has unavailable support: " + str(exc)) from exc
                omit("procedure support unavailable: " + str(exc)[:256], 1)
                continue
            qualified = {(source["mission_id"], source["source_id"]) for source in packet["procedure_sources"]} | support
            if (len(packet["procedures"]) >= 16
                    or len(qualified | qualified_current(selected_sources)) > source_limit
                    or len(set(checks) | support) + reserved_check > source_limit):
                if complete:
                    raise CapacityError("Complete handoff procedure/source bound exhausted; no omission")
                omit("procedure/source limit", 1)
                continue
            bad = [check(source, mission) for mission, source in sorted(support)]
            if any(status != "retained" for status in bad):
                reason = "procedure support unavailable: " + next(status for status in bad if status != "retained")[:256]
                if complete:
                    raise CapacityError("Complete procedure context has unavailable support: " + reason)
                omit(reason, 1)
                continue
            candidate = _copy(packet)
            candidate["procedures"].append(entry)
            candidate["procedure_refs"].append(self._procedure_ref(entry))
            candidate["procedure_sources"] = [{"mission_id": mission, "source_id": source} for mission, source in sorted(qualified)]
            candidate["omitted"]["procedures"] = len(heads) - len(candidate["procedures"])
            if fits(candidate):
                packet = candidate
            elif complete:
                raise CapacityError("Complete handoff procedure packet byte limit; no omission")
            else:
                omit("procedure packet byte limit", 1)
        if not packet["claims"] and not packet["work"] and not packet["procedures"]:
            packet["reobservations"] = [{"scope": scope, "reason": "No supported matching memory fits this packet",
                "instruction": "Inspect current visible coverage for: " + query}]
        packet = finish(packet)
        if len(canonical(packet).encode()) > max_bytes:
            raise CapacityError("Packet cap cannot retain its envelope and explicit omissions")
        if cache:
            self._packets.append(_copy(packet))
            self._packets = self._packets[-32:]
        return _copy(packet)

    def record_decision(self, entry: dict, *, now: float, event_id: str | None = None) -> dict:
        """Retain actual selected references and qualified procedure support."""
        _clock(now)
        refusal = MemoryRequestRefusal if event_id is not None else ContractError
        entry = validate_memory_entry(entry, "decision", player=True)
        matches = [p for p in self._packets if all(entry[k] == p[k] for k in ("packet_id", "scope", "query", "memory_version"))
                   and entry["omitted"] == p["omitted"]["claims"] + p["omitted"]["work"] + p["omitted"]["procedures"]]
        for packet in matches:
            if (set(entry["claim_ids"]) <= {c["id"] for c in packet["claims"]}
                    and set(entry["work_ids"]) <= {w["id"] for w in packet["work"]}
                    and set(entry["source_ids"]) <= {s["id"] for s in packet["sources"]}
                    and all(ref in packet["procedure_refs"] for ref in entry["procedure_refs"])
                    and all(source in packet["procedure_sources"] for source in entry["procedure_sources"])):
                procedure_sources = set()
                for procedure in packet["procedures"]:
                    if self._procedure_ref(procedure) in entry["procedure_refs"]:
                        procedure_sources.update(self._procedure_support(procedure))
                if not procedure_sources <= {(source["mission_id"], source["source_id"]) for source in entry["procedure_sources"]}:
                    raise refusal("Decision must retain its selected procedure dependency closure")
                chosen = [c for c in packet["claims"] if c["id"] in entry["claim_ids"]]
                chosen += [w for w in packet["work"] if w["id"] in entry["work_ids"]]
                needed = {source for item in chosen for source in item["sources"]}
                needed_claims = {c for item in chosen for g in item.get("supports", []) for c in g["claims"]}
                if not needed <= set(entry["source_ids"]) or not needed_claims <= set(entry["claim_ids"]):
                    raise refusal("Decision must retain its selected dependency closure")
                sequence = self.ledger.append_memory(event_id if event_id is not None else _identity("decision-", {"id": entry["id"]}), "decision", entry, now=now, candidate=event_id is not None)
                return _copy({"memory_version": sequence, "entry": entry, "packet_id": packet["packet_id"], "grants_authority": False})
        raise refusal("Decision requires an exact issued packet/version and selected IDs")
