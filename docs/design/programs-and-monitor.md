---
owner: lead
status: proposed
review_trigger: "The fact store's field table merges (the owner's revisit condition for the programs line), the bounded program interface brief (#839) lands, or a program producer is built."
---

# Programs and monitor

## At a glance

**Question.** Should curator-written programs act in the playing model's place under a stop-only monitor, and what interfaces do they need?

**Answer.** The [owner's 20 November 2026 decision](../decisions/owner-decisions.md#in-force) keeps this unbuilt proposal parked until the fact store's field table merges.

**Unknown.** Does delegation help at a matched failure rate? Can the monitor detect anomalies?

**Decision needed.** The [bounded program interface brief (#839)](https://github.com/CVX-Hull/enactive/issues/839) must settle artifact and eligibility choices. Adoption depends on the integrated study.

The reasons are in the retired [curated-player decision record](../decisions/009-curated-player.md).

## What a program is

A program can replace the playing model on its interface. Like that model, called the actor, it receives the full-resolution frame, objective and delivered knowledge. It returns basic inputs with emissions, a slot request, or a yield with a reason. It sends only basic controls through the actor's port under the [computer-control boundary](../decisions/006-computer-control-boundary.md). Each run pins the program version.

A passive policy runs in isolation with no I/O, bounded memory and a per-step time limit. Only the curator's or gate's sandbox executes curator-written code and tests. The custodian and publisher execute no program code.

Budgets cap steps, wall time and model spend. A failed precondition or unrecognized screen makes the program yield.

## Model calls through capability slots

A program requests model calls through named, swappable slots. The runner executes them within budget and returns results as data.

## Supervised asynchronous runs

Only one sender holds input access at a time. Actor input preempts between batches, waiting up to a stated bound for the current batch's receipt. Under the computer-control contract, input stops permanently if the bound expires without a receipt or delivery is partial or unknown. Actor input based on a frame older than the program's last delivered input is refused.

A handoff seals only with no program running. The user's permanent Pause fence operates independently of this resumable transfer.

## Risk classes and the stop-only monitor

An action counts as high-risk unless the gate verifies its class on recorded cases. A high-risk step needs prior approval or pauses for the actor.

The first program phase includes a low-cost model slot that watches program progress and frames and can only stop a program or make it yield. It flags observations of the actor to the curator alone and uses only the player's knowledge. Its detection rate comes from recorded program anomalies.

## Fitting and the library

Offline replay filters candidates for supervised play by checking preconditions, success predicates and agreement with recorded inputs. Replay establishes agreement only for observed inputs. A new program is probationary until scored on traces that arrive after publication.

The library tracks invocations, successes, yields, aborts and regressions. Revisions cite their parents, and programs retire below a performance threshold.

## Emissions the proposal adds

Under the [owner's decision of 13 November 2026, "Intent now, rest later"](../decisions/owner-decisions.md#in-force), each field joins existing tool calls with the work that first reads it.

- `expectation` predicts visible effects. Prediction errors guide curator attention, program success checks and source reliability.
- `goal` marks the start, finish or abandonment of a subgoal for program induction.
- `confidence` states the actor's certainty for calibration against outcomes.
- `flags` mark anomalies or recurring situations to surface ontology gaps and program candidates.

## Which issue owns which interface

| Interface | Owner issue | What must be proved |
| --- | --- | --- |
| Knowledge, facts and program eligibility | [#457](https://github.com/CVX-Hull/enactive/issues/457) | Verify schema agreement, gate eligibility and revocation independently. |
| Artifact, submission envelope and passive interface | [#465](https://github.com/CVX-Hull/enactive/issues/465) | Show full observations, pinned versions, isolated execution and refusal of unsupported versions after coordinated migration. |
| Capability slots | [#466](https://github.com/CVX-Hull/enactive/issues/466) | Prove that the runner mediates calls within budget. |
| Run supervision and active stop | [Supervision (#467)](https://github.com/CVX-Hull/enactive/issues/467), [monitor (#468)](https://github.com/CVX-Hull/enactive/issues/468) | Prove one sender, bounded preemption, frame freshness, handoff and active stop with receipts. |
| Fitting and library | [#469](https://github.com/CVX-Hull/enactive/issues/469) | Use later traces and finite supervised play to support probation, revision, retirement and utility claims. |
| Program views | [#471](https://github.com/CVX-Hull/enactive/issues/471) | Show recorded program identities, state, receipts and explicit unknowns. |
| Integrated programs and monitor study | [#470](https://github.com/CVX-Hull/enactive/issues/470) | Measure delegation and detection to inform adoption. |

- Eligibility revocation, active input stop and knowledge restore have distinct effects.
- Program and delivered-knowledge pins never change silently on a base change or restore.
- Partial or unknown delivery ends input permanently.
- Views show missing data as absent or unknown.

The bounded interface brief freezes artifact identity and layout, base and version pins, selection eligibility and revocation, and the passive envelope. It decides whether artifacts can be stored before they qualify and how revocation affects pinned selections.

## Pages that change on adoption

Adoption updates the [charter](../charter.md), [player tooling standard](../standards/player-tooling.md), [architecture](../architecture.md), [computer-control contract](../contracts/computer-control.md), [mission ownership](../operations/mission-ownership.md), and [evaluation contract](../contracts/evaluation.md) with [observer operations](../components/observer-operations.md). The computer-control boundary, one-input-sender rule, P-TRUTH, no-lead-hint rule and S-MIGRATION continue to govern the design.

## How it would be judged

The integrated study measures the share of decisions programs handle at a matched failure rate and the monitor's detection rate on recorded program anomalies.
