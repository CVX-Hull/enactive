---
owner: lead
status: historical
kind: change
date: '2026-11-12'
scope: 'The evaluator''s two archive lists replaced by one closed index of 54 sealed sessions on the owner''s decision of 12 November 2026 (#555), with the evidence that what the evaluator reads is unchanged'
---

# One closed archive index, 12 November 2026

The evaluator read old record versions through two separate lists. On 12 November 2026
the owner decided
([#555](https://github.com/CVX-Hull/enactive/issues/555)) to replace them with one
closed index of exactly the sealed sessions the evaluator reads, each with the record
versions it carries. This record holds what replaced what, how the index was derived and
the evidence that the evaluator's reads did not change. The current rule is in
[S-MIGRATION](../standards/migration.md) and the reader's contract in
[the evaluation contract](../contracts/evaluation.md).

## What replaced what

| Before | After |
| --- | --- |
| `data/evaluation/archive-labels.json`: 30 sessions with `campaign-run/4` manifests, and their operator labels | `data/evaluation/archive-sessions.json` (`archive-sessions/1`): 54 sessions keyed by session ID, each with its sealed study, run directory and record versions; the 30 older entries hold the same operator labels |
| `data/evaluation/archive-sessions-terminal-3.json`: 22 sessions with `campaign-watch-terminal/3` terminals | The same index |
| Two list readers in `harness/evaluation/core/sources.py`, one branch each | One reader, and one table of the accepted version combinations with the fields used from each record that is not current |

The index holds three combinations of versions, and the reader refuses an index entry
with any other:

| Sessions | Manifest | Receipt | Driver | Host trace | Run-ending record |
| --- | --- | --- | --- | --- | --- |
| 30 | `campaign-run/4` | `campaign-receipt/3` | `player-driver/3` | `player-host/3`, telemetry 3 | `campaign-watch-terminal/2` |
| 22 | `campaign-run/5` | `campaign-receipt/3` | `player-driver/3` | `player-host/3`, telemetry 3 | `campaign-watch-terminal/3` |
| 2 | `campaign-run/5` | `campaign-receipt/3` | `player-driver/3` | `player-host/3`, telemetry 3 | `campaign-watch-terminal/4` |

By study: 37 in `372-382-dev-loop`, 8 in `522-held-out`, 7 in `397-seven-day` and 2 in
`supervised-launch-check-558`.

The two sessions of the third row carry only current versions, so the evaluator reads
them as current and takes nothing from the index for them. They are listed because the
index describes every sealed session the evaluator reads. An entry does not by itself
make an old version readable: the reader accepts an old version only where the index
lists that exact version for that session.

## How the index was derived

A one-off script, not committed, read the sealed evidence store read-only. For every
`<study>/computer-sessions/<run>/manifest.json` it took the manifest's `schema` and
`session`, the `schema` of `receipt.json` and of its `driver` record, the `schema` and
`telemetry_version` of the first event of each `actors/*/host.jsonl`, and the `schema`
of `watch-terminal.json`. That gave 54 sessions with 54 distinct session IDs. Every
session has all five records, and every host trace of a session starts with the same
host version.

The result was checked against the two lists before they were deleted:

- the sessions with a `campaign-run/4` manifest are exactly the 30 of the labels list,
  all in `372-382-dev-loop`, and each listed `run` is the run directory's name;
- the sessions with a `campaign-watch-terminal/3` terminal are exactly the 22 of the
  other list, with the same study and run;
- the remaining two are the sessions of `supervised-launch-check-558`.

The operator labels (`arm`, `start`, `scenario`, `lineage`, `admission`) were copied
unchanged. The old `run` label became the entry's `run`.

## Sessions left out

The store holds 73 directories with a campaign manifest: 13 `campaign-run/3`, 34
`campaign-run/4` and 26 `campaign-run/5`. The index holds 54. The evaluator refused the
other 19 before this change and refuses them after it.

Six have a `campaign-run/4` or `campaign-run/5` manifest:

| Session directory | Why the evaluator cannot read it |
| --- | --- |
| `164-terra/development/computer-sessions/terra164-development` | `campaign-run/4` manifest outside the 30, with a `campaign-watch-terminal/1` terminal |
| `359-ongoing-alex/production-ongoing/computer-sessions/alex164-ongoing` | The same |
| `359-ongoing-alex/production-replacement/computer-sessions/alex164-replacement` | The same |
| `164-terra/next-preparation/computer-sessions/terra164-next` | `campaign-run/4` manifest outside the 30; no receipt, host trace or session database |
| `372-382-dev-loop-operator/lh/dry/lh0a2` | A `campaign-run/5` manifest and nothing else: no session database |
| `372-382-dev-loop-operator/lh/retired/lh1a1-build1` | The same |

The other 13 are the `campaign-run/3` sessions under `2026-11-03-iteration164-runs` and
`2026-11-05-candidate-research`, with `campaign-receipt/2` receipts and `player-host/2`
traces. Their manifest version is refused.

One indexed session does not evaluate from the sealed copy, before or after this change.
`522-held-out/computer-sessions/lh4a1` was in the list of 22. Its manifest, receipt and
terminal are read, but its `session.sqlite3` is in write-ahead-log mode with no
write-ahead-log files beside it, and SQLite cannot open that read-only inside the
store's read-only directory: `cannot read computer-session/1 (attempt to write a
readonly database)`. So 53 of the 54 indexed sessions evaluate from the store as sealed.

## Evidence that behaviour is unchanged

Three comparisons, each run on `origin/main` (`748ebb6`) and on this change, against the
same sealed store.

- **What the reader returns.** `sources.read_run` on all 73 campaign directories, with
  input digests, plus `read_manifest` and `read_end_facts` on their own and the labels
  the pipeline takes for the session. The whole returned value was serialized and
  hashed. 69 of 73 results are identical: all 53 successful reads, the `lh4a1` error and
  15 refusals. The other four are the refused `campaign-run/4` manifests outside the
  index, which differ only in the message's wording, because it names the index file:
  `…is read only for the sealed sessions that archive-sessions.json lists with that
  version; session '…' is not listed`.
- **What the evaluator writes.** `pipeline.evaluate` with the CDDA binding and a fixed
  creation time on all 54 indexed sessions, hashing every row of every table of the
  evaluation record. 53 records are identical, with the same labels in `run_facts`;
  `lh4a1` fails with the same error.
- **The manifest fields.** For the 30 `campaign-run/4` manifests, `run_facts` computed
  from the listed fields alone equals `run_facts` computed from the whole manifest, and
  every listed field is present.

The store was not written: it held 54,491 files before and after.

Tests, in `tests/test_evaluation_core.py`:

- every earlier assertion about `/4` manifests and `/2` and `/3` terminals passes
  unchanged, with only the fixture that supplies the list rewritten to write an index;
- `test_the_shipped_archive_index_is_exactly_the_54_sealed_sessions_in_three_version_combinations`
  pins the index: 54 entries, counts 30, 22 and 2, session IDs of 32 lowercase hex
  digits, unique study and run, labels on exactly the 30 older sessions;
- `test_the_archive_index_matches_the_sealed_store` ran against the store and passed:
  every indexed session's files carry exactly the indexed versions, no other campaign
  session in the store is listed or read in an old version, and the six sessions above
  are refused;
- `test_an_index_entry_with_an_unlisted_version_combination_is_refused_at_load`.

The focused evaluation, viewer, host-analysis, trace-projection and probe tests passed
with no test skipped: 253 passed, with `ENACTIVE_EVIDENCE_ROOT` naming the main
checkout's store for the trace-projection tests. The whole suite passed in the change's
worktree: 1017 passed and 20 skipped, with the main checkout's installed player-host
modules linked in for the run. The fast checkpoint check passed.

One difference outside any session read: a missing index, an index in another version
or an entry with an unaccepted combination is now an error naming the index. The two
old lists were read as empty when missing or malformed.
