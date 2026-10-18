"""Frozen suite C: visible retrieval, irreversible projection and loss controls.

Counters are logical work, not CPU/index visits. ``retrieval_records_scanned`` counts
every retained row inspected by Python retrieval (archive or summary),
``eligible_match_candidates_ranked``
counts eligible FTS MATCH results before LIMIT, and ``projection_records_visited``
counts every input row to every compaction pass (including eligibility rejects).
Storage is canonical JSON bytes, except the separately reported SQLite serialized
database size. Context bytes count the returned records per query, not tokens.
FTS construction counters count one document row and one metadata row prepared
and inserted per archive record, excluding SQLite's internal operations.
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, replace
from itertools import product

from tools.memory_study.common import json_bytes, rng

OPERATIONS = ("close", "open")
KEYS = tuple(product((f"room{i}" for i in range(4)), OPERATIONS,
                     (f"door{i}" for i in range(4))))
DEPTHS = (1, 2, 4, 8)
STRATA = ("rare", "updated", "missing", "ordinary")
FTS_SCHEMA = ("CREATE VIRTUAL TABLE search USING fts5(record_id UNINDEXED, body, "
              "tokenize='unicode61 remove_diacritics 2')")


@dataclass(frozen=True)
class Record:
    id: str
    receipt_index: int
    session: str
    context: str
    operation: str
    target: str
    outcome: str
    available: bool = True
    source_ids: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, str, str]:
        return self.context, self.operation, self.target

    @property
    def body(self) -> str:
        return (f"session {self.session} context {self.context} "
                f"operation {self.operation} target {self.target} outcome {self.outcome}")


@dataclass(frozen=True)
class Query:
    context: str
    operation: str | None
    target: str
    session: str = "s1"


@dataclass(frozen=True)
class Assessor:
    rare_key: tuple[str, str, str]
    updated_key: tuple[str, str, str]


@dataclass(frozen=True)
class Retrieved:
    records: tuple[Record, ...]
    retrieval_records_scanned: int = 0
    eligible_match_candidates_ranked: int = 0


def payload(record: Record, *, lineage: bool = True) -> dict:
    """Canonical stored/returned fields; no assessor labels are serialized."""
    value = asdict(record)
    if not lineage or not record.source_ids:
        del value["source_ids"]
    value["body"] = record.body
    return value


def generate(seed: int, *, all_allow: bool = False, rare_unavailable: bool = False,
             distractor_sessions: bool = False) -> tuple[tuple[Record, ...], Assessor]:
    random = rng(seed, "C")
    rare_key = random.choice(KEYS)
    other_keys = tuple(key for key in KEYS if key != rare_key)
    draws = [random.choice(other_keys) for _ in range(62)]
    updated_key = random.choice(sorted(set(draws)))
    records = []
    for index, key in enumerate([rare_key, *draws, updated_key]):
        available = index in (0, 63) or index % 11 != 0
        if index == 0 and rare_unavailable:
            available = False
        session = "s2" if distractor_sessions and index != 0 and index % 5 == 0 else "s1"
        outcome = "block" if not all_allow and index in (0, 63) else "allow"
        records.append(Record(f"r{index:02d}", index, session, *key, outcome, available))
    return tuple(records), Assessor(rare_key, updated_key)


def eligible(record: Record, session: str) -> bool:
    return record.available and record.session == session


def compatible(record: Record, query: Query) -> bool:
    return (eligible(record, query.session) and record.context == query.context
            and record.target == query.target
            and (query.operation is None or record.operation == query.operation))


def exact(records: tuple[Record, ...], query: Query) -> Retrieved:
    latest = {}
    for record in records:
        if compatible(record, query):
            previous = latest.get(record.key)
            if previous is None or (-record.receipt_index, record.id) < (
                    -previous.receipt_index, previous.id):
                latest[record.key] = record
    return Retrieved(tuple(latest[key] for key in sorted(latest)), len(records))


def answer(records: tuple[Record, ...], query: Query) -> str | None:
    """One answerer for every method, using only its returned visible records."""
    latest = exact(records, query).records
    required = 2 if query.operation is None else 1
    if len(latest) != required or len({record.outcome for record in latest}) != 1:
        return None
    return latest[0].outcome


def match_expression(query: Query) -> str:
    terms = [query.context]
    if query.operation is not None:
        terms.append(query.operation)
    terms.append(query.target)
    return " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)


class FTSArchive:
    """Whole-corpus BM25, with hard eligibility before top-k selection."""

    def __init__(self, records: tuple[Record, ...]):
        self.records = {record.id: record for record in records}
        self.connection = sqlite3.connect(":memory:")
        try:
            self.connection.execute(FTS_SCHEMA)
        except sqlite3.OperationalError as error:
            self.connection.close()
            raise RuntimeError("Suite C requires SQLite FTS5; backend creation failed") from error
        self.connection.execute("CREATE TABLE metadata (record_id TEXT PRIMARY KEY, "
                                "receipt_index INTEGER, session TEXT, available INTEGER)")
        self.connection.executemany("INSERT INTO search(record_id, body) VALUES (?, ?)",
                                    [(r.id, r.body) for r in records])
        self.connection.executemany("INSERT INTO metadata VALUES (?, ?, ?, ?)",
                                    [(r.id, r.receipt_index, r.session, r.available) for r in records])
        self.connection.commit()
        self.database_bytes = len(self.connection.serialize())

    def close(self) -> None:
        self.connection.close()

    def retrieve(self, query: Query, k: int) -> Retrieved:
        clause = (" FROM search JOIN metadata USING (record_id) "
                  "WHERE search MATCH ? AND session = ? AND available = 1")
        parameters = (match_expression(query), query.session)
        candidates = self.connection.execute("SELECT count(*)" + clause, parameters).fetchone()[0]
        rows = self.connection.execute(
            "SELECT record_id" + clause
            + " ORDER BY bm25(search) ASC, receipt_index DESC, record_id ASC LIMIT ?",
            (*parameters, k)).fetchall()
        return Retrieved(tuple(self.records[row[0]] for row in rows),
                         eligible_match_candidates_ranked=candidates)


def recent(records: tuple[Record, ...], query: Query, k: int) -> Retrieved:
    candidates = sorted((r for r in records if eligible(r, query.session)),
                        key=lambda r: (-r.receipt_index, r.id))
    return Retrieved(tuple(candidates[:k]), len(records))


def reservoir(records: tuple[Record, ...], query: Query, k: int, random) -> Retrieved:
    selected = []
    seen = 0
    for record in records:
        if not eligible(record, query.session):
            continue
        seen += 1
        if len(selected) < k:
            selected.append(record)
        else:
            position = random.randrange(seen)
            if position < k:
                selected[position] = record
    return Retrieved(tuple(selected), len(records))


def majority(records: tuple[Record, ...], session: str = "s1") -> tuple[Record, ...]:
    groups = {}
    for record in records:
        if eligible(record, session):
            groups.setdefault(record.key, []).append(record)
    summaries = []
    for key, group in sorted(groups.items()):
        latest = min(group, key=lambda r: (-r.receipt_index, r.id))
        allows = sum(r.outcome == "allow" for r in group)
        blocks = len(group) - allows
        outcome = latest.outcome if allows == blocks else "allow" if allows > blocks else "block"
        sources = tuple(sorted({source for r in group for source in (r.source_ids or (r.id,))}))
        summaries.append(replace(latest, id="summary:" + ":".join(key),
                                 outcome=outcome, source_ids=sources))
    return tuple(summaries)


def compact(records: tuple[Record, ...], depth: int, method: str) -> tuple[tuple[Record, ...], int]:
    retained = records
    visited = 0
    for _ in range(depth):
        visited += len(retained)
        if method == "majority":
            previous = retained
            retained = majority(retained)
            if previous and previous[0].source_ids and retained != previous:
                raise AssertionError("Majority projection must be idempotent")
        elif method == "truncation":
            retained = tuple(sorted(retained, key=lambda r: (r.receipt_index, r.id)))[
                max(1, len(retained) // 2):]
        else:
            raise ValueError(f"Unknown compaction method: {method}")
    return retained, visited


def _storage(records: tuple[Record, ...], *, archive: bool, index_bytes: int = 0,
             index_entries: int = 0, projection_work: int = 0) -> dict[str, int]:
    record_bytes = json_bytes([payload(r, lineage=False) for r in records])
    lineage = {r.id: r.source_ids for r in records if r.source_ids}
    return {"retained_records": len(records), "archive_records": len(records) if archive else 0,
            "retained_record_bytes": record_bytes,
            "archive_record_bytes": record_bytes if archive else 0,
            "lineage_entries": sum(len(ids) for ids in lineage.values()),
            "lineage_bytes": json_bytes(lineage) if lineage else 0,
            "sqlite_database_bytes": index_bytes, "index_entries": index_entries,
            "fts_document_rows_constructed": index_entries,
            "metadata_rows_constructed": index_entries,
            "projection_records_visited": projection_work}


def _score(metrics: dict, result: Retrieved, query: Query, truth: str | None,
           required: tuple[Record, ...], stratum: str) -> None:
    predicted = answer(result.records, query)
    sources = {source for r in result.records for source in (r.source_ids or (r.id,))}
    direct = sum(any(r.key == wanted.key and r.receipt_index == wanted.receipt_index
                     and r.outcome == wanted.outcome for r in result.records) for wanted in required)
    counts = {
        "queries": 1, "decision_correct": int(predicted == truth),
        "answer_correct": int(predicted is not None and predicted == truth),
        "known_answers": int(truth is not None),
        "necessary_abstentions": int(predicted is None and truth is None),
        "avoidable_abstentions": int(predicted is None and truth is not None),
        "unsupported_answers": int(predicted is not None and truth is None),
        "wrong_answers": int(predicted is not None and truth is not None and predicted != truth),
        "required_latest_sources": len(required), "latest_records_recalled": direct,
        "latest_source_lineage_recalled": sum(r.id in sources for r in required),
        "records_returned": len(result.records),
        "context_record_bytes": json_bytes([payload(r) for r in result.records]),
        "wrong_operation_candidates": sum(query.operation is not None
                                          and r.operation != query.operation for r in result.records),
        "retrieval_records_scanned": result.retrieval_records_scanned,
        "eligible_match_candidates_ranked": result.eligible_match_candidates_ranked,
        "answerer_records_visited": len(result.records),
    }
    for name, count in counts.items():
        metrics[name] = metrics.get(name, 0) + count
        scoped = f"{stratum}_{name}"
        metrics[scoped] = metrics.get(scoped, 0) + count


def run(seeds: tuple[int, ...]) -> list[dict]:
    rows = []
    for seed in seeds:
        for all_allow, missing_source, other_sessions in product((False, True), repeat=3):
            records, assessor = generate(seed, all_allow=all_allow, rare_unavailable=missing_source,
                                         distractor_sessions=other_sessions)
            index = FTSArchive(records)
            try:
                for masked, k in product((False, True), (4, 8, 16)):
                    condition = (f"outcomes={'all-allow' if all_allow else 'rare-update'};"
                                 f"source={'rare-unavailable' if missing_source else 'normal'};"
                                 f"session={'distractors' if other_sessions else 'normal'};"
                                 f"visibility={'masked' if masked else 'full'};k={k}")
                    configurations = [(name, records, 0) for name in
                                      ("exact", "fts5", "recent", "reservoir")]
                    for operator, depth in product(("majority", "truncation"), DEPTHS):
                        retained, work = compact(records, depth, operator)
                        configurations.append((f"{operator}-depth{depth}", retained, work))
                    for method, retained, work in configurations:
                        is_archive = method in ("exact", "fts5", "recent", "reservoir")
                        metrics = _storage(retained, archive=is_archive,
                                           index_bytes=index.database_bytes if method == "fts5" else 0,
                                           index_entries=len(records) if method == "fts5" else 0,
                                           projection_work=work)
                        # Initialize even absent strata so per-seed rows have the
                        # same metric schema without inventing zero-denominator rates.
                        empty = {}
                        _score(empty, Retrieved(()), Query("room0", "open", "door0"),
                               None, (), "rare")
                        names = [name for name in empty if not name.startswith("rare_")]
                        metrics.update({name: 0 for name in names})
                        metrics.update({f"{stratum}_{name}": 0
                                        for stratum in STRATA for name in names})
                        random = rng(seed, f"C-reservoir:{condition}")
                        for key in KEYS:
                            query = Query(key[0], None if masked else key[1], key[2])
                            required = exact(records, query).records
                            truth = answer(required, query)
                            full_query = Query(*key)
                            stratum = ("rare" if key == assessor.rare_key else "updated"
                                       if key == assessor.updated_key else "missing"
                                       if not exact(records, full_query).records else "ordinary")
                            if method == "fts5":
                                result = index.retrieve(query, k)
                            elif method == "recent":
                                result = recent(retained, query, k)
                            elif method == "reservoir":
                                result = reservoir(retained, query, k, random)
                            else:
                                result = exact(retained, query)
                            if len(result.records) > k:
                                raise AssertionError("Suite C context budget exceeded")
                            _score(metrics, result, query, truth, required, stratum)
                        rows.append({"suite": "C", "seed": seed, "condition": condition,
                                     "method": method, "metrics": metrics})
            finally:
                index.close()
        bit = rng(seed, "C").getrandbits(1)
        for labels in (2, 16, 256):
            # Arbitrary query names all request the same retained bit. Labels do
            # not require one retained answer each; no query identity is stored.
            query_labels = tuple(f"label{i}" for i in range(labels))
            predictions = [same_bit_answer(bit, label) for label in query_labels]
            rows.append({"suite": "C", "seed": seed, "condition": f"same-bit;labels={labels}",
                         "method": "same-bit", "metrics": {
                             "queries": labels, "answer_correct": sum(p == bit for p in predictions),
                             "retained_bits": 1, "retained_records": 1,
                             "retained_record_bytes": json_bytes(bit)}})
    return rows


def same_bit_answer(retained_bit: int, query_label: str) -> int:
    """Every distinct label requests the same bit; label identity adds no state."""
    return retained_bit
