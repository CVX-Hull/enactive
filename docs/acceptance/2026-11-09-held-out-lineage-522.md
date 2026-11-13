---
owner: lead
status: historical
kind: run
date: '2026-11-09'
scope: 'P1 held-out lineage lh4 (#522) under p1-study/2: the frozen package, one admission lost to infrastructure, seven admissions ending by the 12-boundary size rule, spend, and the held-out handling; aggregates only'
---

# P1 held-out lineage lh4 (#522)

[p1-study/2](https://github.com/CVX-Hull/enactive/blob/329810b/docs/design/p1-study-2.md#running-lh4) adds one held-out lineage, `lh4`, to #382's three.
#522 ran it on 9 November 2026 (local time; the last admissions ended on 10 November UTC). It
ended by its frozen size rule after seven admissions with **13 boundaries**, above the 12 the rule
needs. The survivor was alive at the end.

**This record holds aggregates only.** `lh4` is held out until scoring: the lead read no frame,
memory record, handoff summary, report or prompt from it, and this record names no game content.
The decisions and the frozen package are on [#522](https://github.com/CVX-Hull/enactive/issues/522).

## Owner decisions

| When (2026) | Decision |
| --- | --- |
| 9 November | p1-study/2 approved, with an $80 actual-spend envelope for `lh4`; source "Current main" |
| 9 November | "Approve launch" of the frozen package; credential map: "You may copy it unread" |
| 9 November | After `lh4a1` was lost: "Diagnose first, $0", then "Approve restart plan" |
| 9 November | After `lh4b5` ended by a host stop: "Continue, record deviation" |

## Frozen inputs

Carried over from [#397](2026-11-07-seven-day-397.md#frozen-inputs) except where this table says
otherwise.

| Setting | Value |
| --- | --- |
| Source | `97199464291122b53d2e1568beec7b3fcede3be4` (main after #523), in a clean run worktree |
| Adapter | `computer-build/1`, built fresh from that source and clean; `bridge.dylib` `aa266613…`; its native check passed |
| Game | The project's patched Tiles app, cloned into the run worktree and prepared windowed with its own userdir, log and game lock; installed binary `84690db6…`, the bytes #397 ran |
| Player | S1 Evacuee, no aid; main's player guide (`f282326e…`) as context; #382's prompts, byte for byte |
| Route | OpenRouter, `openai/gpt-6.1-terra`, pinned `openai`, no fallback, medium effort |
| Per admission | At most 400 charged attempts across at most 2 hosts; 7,200 host seconds; 7,800 custodian seconds; `--attention best-effort` |
| Lineage | `L4`, arm `p1-held-out`, ledger study 522; one userdir and one store, `player-memory-lh4.sqlite3` |
| Accounting base | 20,584 attempts and $415.809017929 (after #397) |

**Operator tooling** is outside git, as in #382 and #397, adapted from #397's scripts and reviewed
independently in three rounds: two before the first launch and one for the `lh4b` restart change.
The digests are those of the files as sealed, after that change; the first launch's are in the
addendum on #522.

| File | SHA-256 | Role |
| --- | --- | --- |
| `lh4_package.py` | `5a680db0…` | Builds and preflights one package; prints counts and digests only |
| `lh4_admit.py` | `a02407aa…` | Runs one admission behind the gates below and reconciles its spend |
| `lh4_monitor.py` | `6e6e3ab8…` | Builds the run monitor's frame list and strictly checks its one-line answer |
| `lh4_report.py` | `3fd47cb7…` | Prints an allowlist of the frozen evaluator's numbers and outcome codes |
| `assets/options.json` | `831a0486…` | The pristine windowed options (#397's) |

**Gates before each admission:** every started admission reconciled; order; at most ten admissions;
the previous admission's run-monitor answer passing; the lead's D4 review from aggregates; fewer
than 12 boundaries; the $80 envelope under the actual-spend rule.

## Stop rules

The lineage ends at the first of: **12 boundaries**; death; ten admissions; the envelope; two
consecutive custody stops with one cause. A boundary is a handoff inside an admission or an
admission boundary, counted as actors that observed at least one frame, summed over admissions,
minus one.

## Admissions

| Admission | Status | Attempts | Decisions | Game h | Chunks | Longest stall | $ actual | Wall s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `lh4a1` | Lost to infrastructure: provider errors at stream start; no input sent | 4 | — | 0 | 1, not counted | — | 1.23 | 9 |
| `lh4b1` | Player stop after one handoff | 208 | 200 | 0.57 | 2 | 14 | 2.49 | 1,944 |
| `lh4b2` | Player stop after one handoff | 315 | 306 | 1.13 | 2 | 13 | 5.66 | 2,987 |
| `lh4b3` | Player stop after one handoff | 189 | 179 | 0.26 | 2 | 17 | 2.94 | 1,840 |
| `lh4b4` | Player stop after one handoff | 248 | 240 | 2.77 | 2 | 12 | 3.43 | 2,404 |
| `lh4b5` | Host stop at context capacity after one handoff; game closed by the custodian | 301 | 294 | 5.72 | 2 | 23 | 5.59 | 2,831 |
| `lh4b6` | Player stop after one handoff | 228 | 218 | 14.77 | 2 | 11 | 3.00 | 1,802 |
| `lh4b7` | Player stop after one handoff | 324 | 316 | 2.53 | 2 | 15 | 5.77 | 2,802 |

Attempts, dollars and wall seconds are the [run ledger](../../data/evaluation/runs.jsonl)'s
(study 522); decisions, game hours and stalls are the frozen evaluator's.

## Result

**Ended by the size rule.** After `lh4b7` the lineage had 14 chunks and **13 boundaries**: seven
handoffs and six admission boundaries. The operator tool then refused an eighth admission.

- **Size:** seven admissions (`lh4b1`–`lh4b7`), 1,813 attempts, 1,753 decisions, **27.76 game hours**.
- **Survival:** no death. Every run-monitor answer had `dead` false, and the evaluator recorded
  no death event.
- **Continuity:** the run monitor answered `continues` true for `lh4b2`–`lh4b7`. `lh4b1` began with
  a setup restart, which #382's D7 allows for a first admission.
- **Custody:** no custody stop and no fault.
- **Spend:** **$30.11** of the $80 envelope: $28.88 for `lh4b1`–`lh4b7` and $1.23 for the lost
  `lh4a1`. Cumulative actual spend is about $445.92 of the standing $1,000.
- **Held-out cap for replay:** p1-study/2 sets each held-out B repeat's cap at 1.0× the actor's
  spend on lh1–lh4. With `lh4b1`–`lh4b7` at $28.88, that is $30.46 + $28.88 = **$59.34**.

**The run monitor.** One fresh development agent per admission (seven), a general-purpose
subagent of Claude Code on Sonnet 5.5, given p1-study/2's frozen brief. Each wrote its answer to
a file and replied only "done"; the operator script printed the parsed fields. They used 527,371
tokens in all.

## Deviations and events

1. **`lh4a1` was lost to infrastructure.** It ended after 9 seconds with `provider-error`: two of
   its four requests returned HTTP 200 with a provider error in the first stream event, and the
   second one's retry failed too. No input was sent and no world was saved. Stream-start errors
   had appeared once in 7,621 earlier requests on this route (#372's development runs and #397).
   OpenAI's status page reported "Elevated Errors On API" minutes later. The owner approved a
   restart as `lh4b` on the same frozen source once that incident was resolved.
   - Its used userdir and empty store were moved, not deleted, to the run worktree's
     `archive-lh4a1/`.
   - Its $1.23 counts in the envelope and the accounting base. It does not count in the sequence,
     the admission cap or the boundary count. It was not a custody stop.
   - `lh4a1` and `lh4b1` both carry the labels `L4`, admission 1. Only `lh4b1`–`lh4b7` are the
     held-out lineage.
2. **`lh4b5` ended by a host stop.** Its second actor reached the context limit after 199
   requests, and the host stopped it. The player had not quit, so the custodian closed the game
   with SIGTERM. The newest save was 3 min 49 s older than the stop, so `lh4b6` resumed from a
   slightly earlier world state. p1-study/2 does not cover this case. The owner chose to continue
   and record it. It affects both arms equally, because both replay the same trace.
3. **Envelope floor.** After `lh4a1`, the operator tool took the largest admission as at least
   the frozen $7.06 forecast until an `lh4b` admission had a spend row. That is stricter than the
   ledger rule alone.
4. **Run-monitor delivery.** Each monitor received the frozen brief word for word, followed by a
   marked operator note naming the tools to use and which listed frames belong to the previous
   segment.
5. **`lh4b4`'s spend row** was provisional for a few minutes, while one provider cost record was
   still missing. A later reconciliation made it final at $3.43.
6. **Waived until scoring,** as p1-study/2 says: #397's day checks, the lead's per-admission
   frame reviews and campaign-admission's finding tables.

## Held-out handling

- **What the lead read:** attempts, decisions, dollars, wall seconds, outcome and settlement
  codes, chunk counts, the evaluator's allowlisted numbers, the run monitor's parsed answers, and
  for the two events above host event types, status codes, receipt codes and file timestamps.
- **What the lead did not read:** frames, memory records, handoff summaries, final reports,
  prompts, the supervisor's output (it holds the final reports), the evaluator's records, and the
  supervisor's spectator pages.
- **The owner** asked whether the spectator was on during `lh4b2` and was given its local address.
  Whether the owner watched is not known to the lead.
- **Sealed evidence:** study `522-held-out` in the evidence store holds the run worktree's
  `.runtime` (packages, evaluation records, the lineage userdir and store, the adapter build and
  `archive-lh4a1/`) and the operator directory. It stays unread until scoring.

## Next

#178 names `lh4b1`–`lh4b7` in the lineage map, writes `lh4`'s probes with blinded agents, freezes
them and re-runs the power gate on lh1–lh4. No replay stage starts before that gate passes.
