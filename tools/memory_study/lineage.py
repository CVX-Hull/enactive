"""Suite L: bounded visible-event replay versus an incremental dependency view.

All counters are logical operations, not CPU instructions. Event inspections count
one received/archive row visited; source/claim inspections count one eligibility
node evaluated (including rejected nodes), plus each observation visited while
finding a property's frontier. Index operations count logical entries written by
construction or a direct query lookup. Dependency traversals count reverse edges
visited during invalidation; cache inspections count entries checked, and cache
invalidations count entries removed. Validation inspections count existing identity
entries checked for bounds/claims and premise nodes visited to reject cycles. Rebuild
work has separate counters and is included in total_work. JSON sizes are canonical
UTF-8 bytes, not heap usage. Persistent state and peak temporary query state are
reported separately. Diagnostic methods are intentionally incomplete toy ablations,
not descriptions of current TaskMemory.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
from typing import Any

from tools.memory_study.common import json_bytes, rng


@dataclass(frozen=True)
class Event:
    event_id: str
    kind: str
    receipt_index: int
    session: str = "s1"
    frame: str = "f1"
    entity: str = "door"
    event_turn: int | None = None
    payload: tuple[tuple[str, Any], ...] = ()

    def get(self, key: str) -> Any:
        return dict(self.payload)[key]

    @property
    def scope(self) -> tuple[str, str, str]:
        return self.session, self.frame, self.entity

    @property
    def property(self) -> tuple[str, str, str, str]:
        return (*self.scope, self.get("key"))


def semantic(event: Event) -> dict:
    value = asdict(event)
    del value["receipt_index"]
    value["payload"] = dict(event.payload)
    return value


def validate_event(event: Event) -> None:
    if not isinstance(event, Event):
        raise ValueError("candidate input must be an Event")
    if any(not isinstance(value, str) or not value for value in
           (event.event_id, event.kind, event.session, event.frame, event.entity)):
        raise ValueError("event identity and scope must be nonempty strings")
    if type(event.receipt_index) is not int or event.receipt_index < 0:
        raise ValueError("receipt index must be a nonnegative integer")
    if event.event_turn is not None and type(event.event_turn) is not int:
        raise ValueError("event turn must be an integer or unknown")
    if (not isinstance(event.payload, tuple)
            or any(not isinstance(item, tuple) or len(item) != 2 or not isinstance(item[0], str)
                   for item in event.payload)):
        raise ValueError("typed payload must be immutable key/value pairs")
    payload = dict(event.payload)
    required = {"observe": {"key", "value"}, "derive": {"claim", "proofs"},
                "dispute_source": {"source"}, "retire_claim": {"claim"},
                "new_session": set(), "effect": {"command", "outcome"}}
    if event.kind not in required or set(payload) != required[event.kind]:
        raise ValueError("unsupported event kind or typed payload")
    if len(payload) != len(event.payload):
        raise ValueError("duplicate payload keys")
    for key in set(payload) - {"value", "proofs"}:
        if not isinstance(payload[key], str) or not payload[key]:
            raise ValueError("payload identity must be a nonempty string")
    if event.kind == "observe" and type(payload["value"]) is not bool:
        raise ValueError("observation value must be Boolean")
    if event.kind == "effect" and payload["outcome"] not in ("confirmed", "unknown"):
        raise ValueError("effect outcome must be explicit confirmed or unknown")
    if event.kind == "derive":
        if payload["claim"] != event.event_id:
            raise ValueError("derive event ID must be its new claim ID")
        proofs = payload["proofs"]
        if not isinstance(proofs, tuple) or len(proofs) > 4:
            raise ValueError("at most four immutable alternative proofs")
        for proof in proofs:
            if not isinstance(proof, tuple) or len(proof) > 4:
                raise ValueError("at most four immutable premises per proof")
            if any(not isinstance(p, str) or not p for p in proof):
                raise ValueError("premise IDs must be nonempty strings")


@dataclass(frozen=True)
class Query:
    kind: str
    id: str = ""
    key: str = ""
    command: str = ""
    session: str = "s1"
    frame: str = "f1"
    entity: str = "door"
    turn: int = 10

    @property
    def context(self) -> tuple[str, str, str, int]:
        return self.session, self.frame, self.entity, self.turn


@dataclass(frozen=True)
class AssessedQuery:
    after: int
    query: Query
    expected: bool | int | str | None
    rebuild: bool = False


@dataclass(frozen=True)
class Case:
    name: str
    events: tuple[Event, ...]
    assessments: tuple[AssessedQuery, ...]


def load_cases() -> tuple[Case, ...]:
    """Expand literal shorthand; expectations stay outside candidate objects."""
    fixture = json.loads((Path(__file__).resolve().parents[2] /
                          "docs/design/memory-study-cases.json").read_text())
    if fixture["protocol"] != "memory-study-v1.1":
        raise ValueError("unsupported lineage fixture protocol")
    cases = []
    for raw in fixture["cases"]:
        events = []
        for index, item in enumerate(raw["events"]):
            kind = item["kind"]
            if kind == "observe":
                payload = (("key", item.get("key", item["id"])),
                           ("value", item.get("value", True)))
            elif kind == "derive":
                payload = (("claim", item.get("claim", item["id"])),
                           ("proofs", tuple(tuple(p) for p in item["proofs"])))
            else:
                payload = tuple((k, item[k]) for k in
                                ("source", "claim", "command", "outcome") if k in item)
            events.append(Event(item["id"], kind, index,
                                item.get("session", "s1"), item.get("frame", "f1"),
                                item.get("entity", "door"),
                                item.get("turn", 1 if kind == "observe" else None), payload))
        assessments = []
        for item in raw["queries"]:
            active = ("s1", "f1")
            for event in events[:item["after"] + 1]:
                if event.kind == "new_session":
                    active = event.session, event.frame
            query = Query(item["kind"], item.get("id", ""), item.get("key", ""),
                          item.get("command", ""), item.get("session", active[0]),
                          item.get("frame", active[1]), item.get("entity", "door"),
                          item.get("turn", 10))
            assessments.append(AssessedQuery(item["after"], query, item["expected"],
                                            item.get("rebuild", False)))
        cases.append(Case(raw["name"], tuple(events), tuple(assessments)))
    return tuple(cases)


def permute(case: Case, seed: int) -> Case:
    """Shuffle only observation blocks, insert one replay, keep final queries."""
    random = rng(seed, "L")
    events = []
    index = 0
    while index < len(case.events):
        if case.events[index].kind != "observe":
            events.append(case.events[index])
            index += 1
            continue
        end = index
        while end < len(case.events) and case.events[end].kind == "observe":
            end += 1
        block = list(case.events[index:end])
        first = block[0]
        random.shuffle(block)
        position = block.index(first)
        block.insert(random.randrange(position + 1, len(block) + 1), first)
        events.extend(block)
        index = end
    events = tuple(replace(event, receipt_index=i) for i, event in enumerate(events))
    final = len(case.events) - 1
    assessments = tuple(replace(a, after=len(events) - 1)
                        for a in case.assessments if a.after == final)
    return Case(case.name, events, assessments)


COUNTERS = tuple(f"{phase}_{unit}" for phase, units in (
    ("query", ("archive_inspections", "source_inspections", "claim_inspections",
               "index_operations")),
    ("update", ("event_inspections", "index_operations", "dependency_traversals",
                "cache_inspections", "cache_invalidations", "validation_inspections")),
    ("rebuild", ("event_inspections", "index_operations")),
) for unit in units)


class State:
    """Ordinary dictionaries shared for state representation, not answer caching."""

    def __init__(self, count: dict[str, int], phase: str, ablation: str = "",
                 skip_retirement: bool = False, maintain_reverse: bool = False):
        self.count, self.phase = count, phase
        self.ablation, self.skip_retirement = ablation, skip_retirement
        self.maintain_reverse = maintain_reverse
        self.sources: dict[str, Event] = {}
        self.claims: dict[str, Event] = {}
        self.properties: dict[tuple, list[str]] = {}
        self.reverse: dict[str, set[str]] = {}
        self.disputed: set[str] = set()
        self.retired: set[str] = set()
        self.effects: dict[str, str] = {}
        self.active = ("s1", "f1")

    def write(self, n: int = 1) -> None:
        self.count[f"{self.phase}_index_operations"] += n

    def add(self, event: Event) -> set[str]:
        affected = set()
        if event.kind == "observe":
            self.sources[event.event_id] = event
            self.properties.setdefault(event.property, []).append(event.event_id)
            self.write(2)
            affected.update(self.properties[event.property])
        elif event.kind == "derive":
            claim = event.get("claim")
            if claim in self.claims:
                raise ValueError("multiple derive events for one claim are unspecified")
            self.claims[claim] = event
            self.write()
            if self.maintain_reverse:
                for proof in event.get("proofs"):
                    for premise in proof:
                        if claim not in self.reverse.setdefault(premise, set()):
                            self.reverse[premise].add(claim)
                            self.write()
            affected.add(claim)
        elif event.kind == "dispute_source":
            self.disputed.add(event.get("source"))
            affected.add(event.get("source"))
            self.write()
        elif event.kind == "retire_claim":
            if not self.skip_retirement:
                self.retired.add(event.get("claim"))
                affected.add(event.get("claim"))
                self.write()
        elif event.kind == "new_session":
            self.active = event.session, event.frame
            affected.update(self.sources)
            affected.update(self.claims)
            self.write()
        elif event.kind == "effect":
            self.effects[event.get("command")] = event.get("outcome")
            self.write()
        else:
            raise ValueError("unsupported event kind")
        return affected

    def scope_ok(self, scope: tuple, context: tuple) -> bool:
        return self.ablation == "no_scope" or (
            scope == context[:3] and context[:2] == self.active)

    def frontier(self, prop: tuple, turn: int) -> tuple[str, ...]:
        candidates = [self.sources[s] for s in self.properties.get(prop, ())]
        self.count["query_source_inspections"] += len(candidates)
        if not candidates or any(e.event_turn is None for e in candidates):
            return ()
        candidates = [e for e in candidates if e.event_turn <= turn]
        if not candidates:
            return ()
        if self.ablation == "no_valid_time":
            candidates = [max(candidates, key=lambda e: e.receipt_index)]
        else:
            latest = max(e.event_turn for e in candidates)
            candidates = [e for e in candidates if e.event_turn == latest]
        if len({e.get("value") for e in candidates}) != 1:
            return ()
        return tuple(e.event_id for e in candidates if e.event_id not in self.disputed)

    def evaluate(self, node: str, context: tuple, cache: dict | None = None,
                 frontiers: dict | None = None) -> bool:
        if cache is not None:
            self.count["query_index_operations"] += 1
        if cache is not None and node in cache:
            return cache[node]
        if node in self.sources:
            self.count["query_source_inspections"] += 1
            source = self.sources[node]
            prop = source.property
            if frontiers is not None:
                self.count["query_index_operations"] += 1
            if frontiers is not None and prop in frontiers:
                current = frontiers[prop]
            else:
                current = self.frontier(prop, context[3])
                if frontiers is not None:
                    frontiers[prop] = current
                    self.count["query_index_operations"] += 1
            answer = self.scope_ok(source.scope, context) and node in current
        else:
            self.count["query_claim_inspections"] += 1
            event = self.claims.get(node)
            answer = False
            if event is not None and node not in self.retired and self.scope_ok(event.scope, context):
                proofs = event.get("proofs")
                if self.ablation == "no_alternate_proofs":
                    proofs = proofs[:1]
                answer = any(all(self.evaluate(p, context, cache, frontiers) for p in proof)
                             for proof in proofs)
        if cache is not None:
            cache[node] = answer
            self.count["query_index_operations"] += 1
        return answer

    def answer(self, query: Query, cache: dict | None = None,
               frontiers: dict | None = None) -> bool | int | str | None:
        self.count["query_index_operations"] += 1
        if query.kind in ("supported", "source_eligible"):
            if query.kind == "source_eligible" and query.id not in self.sources:
                return False
            if query.kind == "supported" and query.id not in self.claims:
                return False
            return self.evaluate(query.id, query.context, cache, frontiers)
        if query.kind == "current_value":
            prop = (*query.context[:3], query.key)
            if self.ablation == "no_scope":
                # The diagnostic deliberately aliases a property across scopes.
                prop = next((p for p in self.properties if p[3] == query.key), prop)
            if not self.scope_ok(prop[:3], query.context):
                return None
            if frontiers is not None:
                self.count["query_index_operations"] += 1
            if frontiers is not None and prop in frontiers:
                current = frontiers[prop]
            else:
                current = self.frontier(prop, query.turn)
                if frontiers is not None:
                    frontiers[prop] = current
                    self.count["query_index_operations"] += 1
            return self.sources[current[0]].get("value") if current else None
        if query.kind == "effect":
            return self.effects.get(query.command, "unknown")
        raise ValueError("unsupported query kind")

    def serialized(self) -> dict:
        return {"sources": sorted(self.sources), "claims": sorted(self.claims),
                "properties": [[list(p), ids] for p, ids in sorted(self.properties.items())],
                "reverse": [[p, sorted(ids)] for p, ids in sorted(self.reverse.items())],
                "disputed": sorted(self.disputed), "retired": sorted(self.retired),
                "effects": self.effects, "active": self.active}

    def index_entries(self) -> int:
        return (len(self.sources) + len(self.claims) + sum(map(len, self.properties.values()))
                + sum(map(len, self.reverse.values())) + len(self.disputed)
                + len(self.retired) + len(self.effects) + 1)


class ArchiveReplay:
    """Strong simple comparator: reconstruct from the complete archive per query."""

    def __init__(self, ablation: str = ""):
        self.ablation = ablation
        self.archive: list[Event] = []
        self.identities: dict[str, Event] = {}
        self.count = dict.fromkeys(COUNTERS, 0)
        self.skip_retirement = False
        self.peak_query_state_bytes = 0
        self.last_receipt = -1
        self.maintain_reverse = False

    def validate_derivation(self, event: Event) -> None:
        if event.kind != "derive":
            return
        self.count["update_validation_inspections"] += len(self.identities)
        claims = {e.get("claim"): e for e in self.identities.values() if e.kind == "derive"}
        claims[event.event_id] = event
        visiting, finished = set(), set()

        def visit(node: str) -> None:
            self.count["update_validation_inspections"] += 1
            if node in visiting:
                raise ValueError("cyclic derivation")
            if node in finished or node not in claims:
                return
            visiting.add(node)
            for proof in claims[node].get("proofs"):
                for premise in proof:
                    visit(premise)
            visiting.remove(node)
            finished.add(node)

        visit(event.event_id)

    def ingest(self, event: Event) -> None:
        self.count["update_event_inspections"] += 1
        validate_event(event)
        if event.receipt_index <= self.last_receipt:
            raise ValueError("receipt index must increase")
        value = semantic(event)
        if event.event_id in self.identities:
            if semantic(self.identities[event.event_id]) != value:
                raise ValueError("event ID reused with different semantic payload")
            if self.ablation != "no_deduplication":
                self.last_receipt = event.receipt_index
                return
        else:
            self.validate_derivation(event)
            for kind, limit in (("observe", 16), ("derive", 16)):
                if event.kind == kind:
                    self.count["update_validation_inspections"] += len(self.identities)
                    if sum(e.kind == kind for e in self.identities.values()) >= limit:
                        raise ValueError("source/claim budget exceeded")
        if len(self.archive) >= 64:
            raise ValueError("archive budget exceeded")
        if event.event_id not in self.identities:
            self.identities[event.event_id] = event
            self.count["update_index_operations"] += 1
        self.archive.append(event)
        self.last_receipt = event.receipt_index
        self.count["update_index_operations"] += 1

    def reconstruct(self, phase: str) -> State:
        state = State(self.count, phase, self.ablation, self.skip_retirement,
                      self.maintain_reverse)
        for event in self.archive:
            counter = "archive_inspections" if phase == "query" else "event_inspections"
            self.count[f"{phase}_{counter}"] += 1
            state.add(event)
        self.peak_query_state_bytes = max(self.peak_query_state_bytes,
                                         json_bytes(state.serialized()))
        return state

    def rebuild(self) -> None:
        if self.ablation == "no_retirement_on_rebuild":
            self.skip_retirement = True
        self.reconstruct("rebuild")

    def query(self, query: Query) -> bool | int | str | None:
        if query.kind == "archive_count":
            self.count["query_index_operations"] += 1
            return len(self.archive)
        if query.kind == "historical":
            self.count["query_index_operations"] += 1
            return query.id in self.identities
        state = self.reconstruct("query")
        return state.answer(query)

    def storage(self) -> dict[str, int]:
        archive = [asdict(event) for event in self.archive]
        # Identity lookup references archive entries; semantic payload is not copied.
        extra = self.identity_state()
        return {"archive_records": len(archive), "archive_bytes": json_bytes(archive),
                "index_entries": len(self.identities), "extra_state_bytes": json_bytes(extra),
                "source_records": sum(e.kind == "observe" for e in self.identities.values()),
                "claim_records": sum(e.kind == "derive" for e in self.identities.values()),
                "dependency_edges": 0, "eligibility_cache_entries": 0,
                "frontier_cache_entries": 0,
                "peak_query_state_bytes": self.peak_query_state_bytes}

    def identity_state(self) -> dict:
        offsets = {id(event): i for i, event in enumerate(self.archive)}
        return {"identities": [[key, offsets[id(event)]]
                               for key, event in self.identities.items()],
                "last_receipt": self.last_receipt, "skip_retirement": self.skip_retirement}


class IncrementalView(ArchiveReplay):
    """Maintain reverse dependencies; lazily refresh invalidated eligibility."""

    def __init__(self):
        super().__init__()
        self.maintain_reverse = True
        self.state = State(self.count, "update", maintain_reverse=True)
        self.caches: dict[tuple, dict[str, bool]] = {}
        self.frontiers: dict[tuple, dict[tuple, tuple[str, ...]]] = {}

    def ingest(self, event: Event) -> None:
        before = len(self.archive)
        super().ingest(event)
        if len(self.archive) == before:
            return
        affected = self.state.add(event)
        pending = list(affected)
        while pending:
            node = pending.pop()
            for child in self.state.reverse.get(node, ()):
                self.count["update_dependency_traversals"] += 1
                if child not in affected:
                    affected.add(child)
                    pending.append(child)
        for cache in self.caches.values():
            for node in affected:
                self.count["update_cache_inspections"] += 1
                if node in cache:
                    del cache[node]
                    self.count["update_cache_invalidations"] += 1
        if event.kind == "observe":
            for cache in self.frontiers.values():
                self.count["update_cache_inspections"] += 1
                if event.property in cache:
                    del cache[event.property]
                    self.count["update_cache_invalidations"] += 1
        elif event.kind == "dispute_source":
            source = self.state.sources.get(event.get("source"))
            if source is not None:
                for cache in self.frontiers.values():
                    self.count["update_cache_inspections"] += 1
                    if source.property in cache:
                        del cache[source.property]
                        self.count["update_cache_invalidations"] += 1

    def rebuild(self) -> None:
        self.count["update_cache_invalidations"] += sum(map(len, self.caches.values()))
        self.count["update_cache_invalidations"] += sum(map(len, self.frontiers.values()))
        self.caches.clear()
        self.frontiers.clear()
        self.state = self.reconstruct("rebuild")
        self.state.phase = "update"

    def query(self, query: Query) -> bool | int | str | None:
        if query.kind == "archive_count":
            self.count["query_index_operations"] += 1
            return len(self.archive)
        if query.kind == "historical":
            self.count["query_index_operations"] += 1
            return query.id in self.identities
        if query.kind == "effect":
            return self.state.answer(query)
        self.count["query_index_operations"] += 2
        if query.context not in self.caches:
            self.caches[query.context] = {}
            self.frontiers[query.context] = {}
            self.count["query_index_operations"] += 2
        cache = self.caches[query.context]
        frontier = self.frontiers[query.context]
        return self.state.answer(query, cache, frontier)

    def storage(self) -> dict[str, int]:
        result = super().storage()
        extra = {**self.identity_state(), "state": self.state.serialized(),
                 "caches": [[list(k), v] for k, v in sorted(self.caches.items())],
                 "frontiers": [[list(k), [[list(p), ids] for p, ids in sorted(v.items())]]
                               for k, v in sorted(self.frontiers.items())]}
        cache_entries = (sum(map(len, self.caches.values())) + sum(map(len, self.frontiers.values()))
                         + len(self.caches) + len(self.frontiers))
        result.update(extra_state_bytes=json_bytes(extra),
                      index_entries=len(self.identities) + self.state.index_entries() + cache_entries,
                      dependency_edges=sum(map(len, self.state.reverse.values())),
                      eligibility_cache_entries=sum(map(len, self.caches.values())),
                      frontier_cache_entries=sum(map(len, self.frontiers.values())))
        return result


METHODS = ("archive_replay", "incremental_view", "diagnostic_no_deduplication",
           "diagnostic_no_valid_time", "diagnostic_no_alternate_proofs",
           "diagnostic_no_scope", "diagnostic_no_retirement_on_rebuild")


def evaluate(case: Case, method: str, passes: int) -> tuple[dict[str, int], tuple]:
    candidate = IncrementalView() if method == "incremental_view" else ArchiveReplay(
        method.removeprefix("diagnostic_") if method.startswith("diagnostic_") else "")
    metrics = dict.fromkeys(("queries", "mismatches", "false_current", "unsupported",
                             "lost_supported", "history_loss", "resurrection", "scope_leaks",
                             "false_confirmed_effects", "rebuilds"), 0)
    answers = []
    for index, event in enumerate(case.events):
        candidate.ingest(event)
        assessments = [a for a in case.assessments if a.after == index]
        for _ in range(passes):
            for assessment in assessments:
                if assessment.rebuild:
                    candidate.rebuild()
                    metrics["rebuilds"] += 1
                query = assessment.query
                actual = candidate.query(query)
                expected = assessment.expected
                answers.append(actual)
                metrics["queries"] += 1
                if type(actual) is type(expected) and actual == expected:
                    continue
                metrics["mismatches"] += 1
                if query.kind == "current_value" and actual is not None:
                    metrics["false_current"] += 1
                if query.kind in ("supported", "source_eligible") and actual is True:
                    metrics["unsupported"] += 1
                if ((query.kind in ("supported", "source_eligible") and expected is True)
                        or (query.kind == "current_value" and expected is not None and actual is None)):
                    metrics["lost_supported"] += 1
                if query.kind == "historical" and expected is True:
                    metrics["history_loss"] += 1
                if case.name == "retirement_rebuild" and query.kind == "supported" and actual is True:
                    metrics["resurrection"] += 1
                if (case.name in ("session_alias", "frame_alias")
                        and ((query.kind == "current_value" and actual is not None)
                             or (query.kind in ("supported", "source_eligible") and actual is True))):
                    metrics["scope_leaks"] += 1
                if query.kind == "effect" and actual == "confirmed":
                    metrics["false_confirmed_effects"] += 1
    metrics.update(candidate.count)
    metrics.update(candidate.storage())
    metrics["correct"] = metrics["queries"] - metrics["mismatches"]
    metrics["total_work"] = sum(candidate.count.values())
    metrics["received_events"] = len(case.events)
    return metrics, tuple(answers)


def run(seeds: tuple[int, ...]) -> list[dict]:
    """Return deterministic seed aggregates; final seed execution belongs to lead."""
    rows = []
    for seed in seeds:
        for template in load_cases():
            for regime, case in (("literal", template), ("permuted_final", permute(template, seed))):
                for passes in (1, 4, 16):
                    reference = None
                    for method in METHODS:
                        metrics, answers = evaluate(case, method, passes)
                        if method == "archive_replay":
                            reference = answers
                        if method in ("archive_replay", "incremental_view"):
                            if metrics["mismatches"] or answers != reference:
                                raise AssertionError(f"complete L method failed: {case.name}/{regime}/{method}")
                        rows.append({"suite": "L", "seed": seed,
                                     "condition": f"{regime}/{case.name}/passes={passes}",
                                     "method": method, "metrics": metrics})
        fixture = json.loads((Path(__file__).resolve().parents[2] /
                              "docs/design/memory-study-cases.json").read_text())
        ambiguity = fixture["identity_ambiguity"]
        worlds = ambiguity["assessor_worlds"]
        visible_inputs = [json.dumps(ambiguity["visible"], sort_keys=True) for _ in worlds]
        if len(set(visible_inputs)) != 1 or worlds[0] == worlds[1]:
            raise AssertionError("identity ambiguity construction broken")
        rows.append({"suite": "L", "seed": seed, "condition": "identity_ambiguity",
                     "method": "identification_control", "metrics": {
                         "identical_visible_inputs": 1, "assessor_worlds": len(worlds),
                         "unique_identity_available": 0,
                         "visible_input_bytes": json_bytes(ambiguity["visible"])}})
    return rows
