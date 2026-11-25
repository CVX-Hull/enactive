---
owner: lead
status: proposed
review_trigger: "The owner decides whether to take up the programs line, the curator contract's fact or gate rules change, or a program producer is built."
---

# Programs and monitor

## At a glance

**Question.** Should curator-written programs act in the playing model's place under a stop-only monitor, and what interfaces do they need?

**Answer.** The [bounded program interface brief](bounded-program-interface.md) specifies the interface boundary ([25 November disposition](../decisions/owner-decisions-archive.md#wave3-wave4-live-validation-accepted-963), following the [20 November brief decision](../decisions/owner-decisions.md#register-the-bounded-program-interface-brief)). A program build remains deferred; this proposal authorizes no build.

**Unknown.** Does delegation help at a matched failure rate? Can the monitor detect anomalies?

**Decision needed.** The owner decides whether to take up the line under the [bounded program interface brief](bounded-program-interface.md). Adoption depends on the integrated study.

The reasons are in the retired [curated-player decision record](../decisions/009-curated-player.md).

## What a program is

A program can replace the playing model on its interface. Like that model, called the actor, it receives the full-resolution frame, objective and delivered knowledge. It returns basic inputs with emissions, a slot request, or a yield with a reason. It sends only basic controls through the actor's port under the [computer-control boundary](../decisions/006-computer-control-boundary.md). Each run pins the program version.

A passive policy runs in isolation with no I/O, bounded memory and a per-step time limit. Only the curator's or gate's sandbox would execute curator-written code and tests. The custodian and publisher would execute no program code. The [gate](../contracts/curator.md#gate-and-pre-validation) publishes data only and refuses program or test content in its repository.

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

Offline replay filters candidates for supervised play by checking preconditions, success predicates and agreement with recorded inputs. Replay establishes agreement only for observed inputs. A stored program enters as `stored_ineligible`, becomes `probationary` only after passing gate-owned offline qualification, and stays probationary until scored on traces that arrive after publication ([pre-qualification storage and eligibility](bounded-program-interface.md#pre-qualification-storage-and-eligibility)).

The library tracks invocations, successes, yields, aborts and regressions. Revisions cite their parents, and programs retire below a performance threshold.

## Emissions the proposal adds

Each field joins existing tool calls with the work that first reads it, under the
[decision on tool intent and citations](../decisions/owner-decisions.md#tool-intent-required-and-cites-optional).

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
- A program pin never changes silently on a base change or restore. Delivered knowledge changes during a run only as an [announced newer version](../contracts/player-host.md#a-newer-version-during-play), never through a restore.
- Partial or unknown delivery ends input permanently.
- Views show missing data as absent or unknown.

The [bounded program interface brief](bounded-program-interface.md) freezes artifact identity and layout, base and version pins, pre-qualification storage and selection eligibility, revocation semantics for pinned runs, the passive envelope, refused versions, and fact-store dependencies.

## Pages that change on adoption

Adoption updates the [charter](../charter.md), [player tooling standard](../standards/player-tooling.md), [architecture](../architecture.md), [computer-control contract](../contracts/computer-control.md), [run custody](../operations/run-custody.md), [curator contract](../contracts/curator.md), and [spectator view contract](../contracts/spectator-view.md) with the [spectator component](../components/spectator.md). The computer-control boundary, one-input-sender rule, P-TRUTH, no-lead-hint rule and S-MIGRATION continue to govern the design.

## How it would be judged

The integrated study measures the share of decisions programs handle at a matched failure rate and the monitor's detection rate on recorded program anomalies.
