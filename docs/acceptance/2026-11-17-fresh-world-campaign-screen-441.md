---
owner: lead
status: historical
kind: run
date: '2026-11-17'
scope: 'Approved first-stage fresh-world CDDA screen with two supervised initial admissions stopped at unverified scenario selection'
---

# Fresh-world campaign screen (#441)

## At a glance

- The actor created two fresh worlds in separate options-only userdirs, with
  independent player journals and one native child at a time. Both admissions
  entered play without visible confirmation of the required Evacuee scenario.
- The lead issued a verified Pause in each session. Both continuations were
  ineligible. Neither lineage supplied an eligible Save-to-title checkpoint or
  normal native exit. The first stage ended after those two initial admissions.
- The [run ledger](../../data/evaluation/runs.jsonl) holds both provider-reported
  subtotals, and records one unpriced player attempt per admission at its frozen
  bound. Both receipts had complete accounting in the protocol's sense. The two
  unpriced attempts leave the full provider charge unavailable.

## Frozen scope and identities

The owner approved up to $30 for [#441](https://github.com/CVX-Hull/enactive/issues/441),
with two fresh worlds and at most one eligible continuation per world. Both initial
admissions used source `e9b851448ef2e81f155fc2d2f0b3fb6dd431892e`, the same prepared
windowed native app and bridge, current guide, prompt, v18 knowledge, and medium
Terra through OpenRouter pinned to OpenAI on the default tier. Each package carried
the approved 45-minute wall limit, 240 aggregate attempts, declared $4.50 run limit
and $1 ending reserve. The actor owned menu and gameplay inputs.

| Admission | Session | Manifest SHA-256 |
| --- | --- | --- |
| Lineage A initial | `0ee9f831f013422fb357f6da94946a17` | `b7b5d903520cb8190f7bbcc7bedd2e05fc560cdcf5b5db14381753e96e0310df` |
| Lineage B initial | `6063ace03a77497497353307bed45f68` | `d32c4927d3e3932a5a6502efcec61288c585a1c14524328058a5f8bf53047878` |

The lead archived the first userdir under the game lock and verified its file
hashes before preparing the second with the same initial options bytes. The
second package copied the first's exact frozen driver inputs and private knowledge.
It supplied an unused session and journal, a separate loopback port and the second
lineage label. Both packages passed the maintained offline validator. The ledger's
actual-spend admission check passed before both launches.

## Setup observations and stop decisions

Frame suffixes below use the session prefixes in the table above. The world labels
and survivor names come from displayed screens. The intended `S1` assignment in
the ledger records the package's Evacuee target.

| Admission | Visible world and survivor | Setup sequence and observed progress | Eligibility |
| --- | --- | --- | --- |
| A initial | Del Monte Forest, seen as an empty new world in frame 77. Launa “Slayer” Villa, Scoundrel, in frame 380. | Frame 81 had random “Play Now!” highlighted when the actor asked to click Custom Character. Frame 150 already showed game loading. The actor reached a refugee-center scene at 08:00:00 in frame 380 and moved into the center by 08:00:43 in frame 859. The retained setup frames do not resolve an Evacuee selection. | Operator Pause ended the attempt. A continuation was skipped because the scenario and the required Save-to-title and normal exit were unverified. |
| B initial | Carnot, seen as an empty new world in frame 36. Rachell Madrigal, Tourist, in frame 449. | Frame 40 again had random “Play Now!” highlighted. The actor sent Home and Enter intending Custom Character. Frame 116 already showed loading, and frame 430 showed a refugee-center scene at 08:00:00. The final inventory view in frame 451 obscured the clock. The retained setup frames do not resolve an Evacuee selection. | Operator Pause ended the attempt. B continuation was skipped for the same eligibility reasons. |

The matched boundary in both runs was a highlighted random-start option,
an input intended to reach custom setup, and a returned loading view. The A
click and B keyboard sequence do not isolate the cause. Transport completion
shows that the computer operation settled. Setup correctness requires visible
confirmation. Neither run qualified for evaluating the approved Evacuee
progress or continuity endpoints. Neither was classified as a death.
The lead supplied only the two Pause requests and left the frozen assignments
in place. The unused continuation slots and remaining
envelope closed with this stage. The seven-day outcome in
[#145](https://github.com/CVX-Hull/enactive/issues/145) remains open.

<!-- evaluate-table study=441 core=2 binding=cdda:2 -->
| Run | Arm | Start | End | Game h | Decisions | Setup | Routine pace | Long activities | Out of play | Longest stall | $ / decision | Large rewrites |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh-world-screen-441-0ee9f831f013422fb357f6da94946a17 | fresh-world-screen | S1 | owner_pause | 0.01 | 26 | 10 | 2.7 | 0 · 0.00 h | 59% | 7 | 0.0031 | 0% |
| fresh-world-screen-441-6063ace03a77497497353307bed45f68 | fresh-world-screen | S1 | owner_pause | 0.00 | 12 | 10 | — | 0 · 0.00 h | 67% | 2 | 0.0030 | 0% |
<!-- /evaluate-table -->

These generated evaluator metrics describe the attempts. The `owner_pause`
label records the lead's operator Pause in both cases. Evacuee setup, eligible
save, reload and sustained useful play remain unverified.

## Accounting and cleanup

Use `.venv/bin/python -m tools.run_ledger totals --study 441 --envelope 30`
for counted spend. The ledger's `provider_usd` entries are the response costs
returned by OpenRouter. Each cut-off player request had no usable cost field,
so the maintained accounting bounded it. The owner manages OpenRouter billing.

Both session-bound Pause replies were forwarded. Each watcher recorded
`operator_pause` and verified owned cleanup. The custodian dispositions were
`incomplete`, and native cleanup needed a signal in both. The terminal-coverage
flags for ordinary completion remained false. Input authority was revoked and
host/MCP quiescence and native absence verified independently of game outcomes.
The lead checked all twelve exact owned process groups, all six loopback
listeners, and availability of the shared lock.

The [private evidence seal](../../data/evidence/index.json) retains both
packages, original captures and traces, journals, evaluator stores, Pause
replies and terminal receipts, and the two archived userdirs and logs. The
lead verified every sealed hash and matched both working packages, both
evaluator directories and the userdir archive to their sealed copies before
retiring those working directories.
