---
owner: lead
review_trigger: Changes to this delivery decision, ownership or review policy
status: active
---

# Evidence and documentation cadence

Use the existing issue, immutable admission, ledger and archive. The
[tracked run ledger](../contracts/evaluation.md#tracked-run-ledger-and-metrics-snapshot)
(`data/evaluation/runs.jsonl`) is the one numeric record of a development run, which
gets exactly one row there. The study's dated record presents the run's numbers
through the generated run tables or by citing the ledger, and keeps no second
hand-typed copy of attempts, spend or duration (method in
[development runs](../development-runs.md#recording-a-run)). Its notes give what the
ledger does not hold: artifacts, outcome on the frozen metric, known unknowns,
cleanup disposition and the next owned action. A short comment on the owning issue
may announce the run and link its ledger row. Acceptance records and independent review
are for adoption decisions, contract changes and merges.
Do not copy the entire contract, write a standalone acceptance report, launch
another review swarm or publish an amendment for every menu error. Retain the raw
evidence immediately; consolidate reports, selected images/provenance and finding
dispositions at the integration/acceptance checkpoint. Public notes need the usual
identity/privacy inspection. Historical failures remain accessible and never turn
into passing tests after a repair.

Update authoritative contracts when behavior changes; mark incomplete support and
unrun checks plainly. Keep chat updates brief and the overview understandable.
An issue/PR brief is enough for a routine fix. A consequential workflow/boundary
change may need one short design rationale, not parallel plan/status systems.
Apply S-CODE's platform-contract rule during that review: state which configured
DB/OS/library behavior already supplies the guarantee and what project requirement
remains. Simplification and removal of duplicate validation/recovery are valid work
outcomes. Track evidence-backed gaps in existing issues; speculative hardening is
not a new campaign gate or a reason to add another approval layer.

Development episodes used to select repairs remain development data. Freeze source,
objective, conditions and limits before every run. Formal acceptance is a decision
on the resulting evidence, not a requirement to repeat an unchanged run. A complete
unassisted development run may establish the prospective functional mission outcome
after its unchanged exact source passes full checks and independent evidence review.
The run must actually meet every original criterion, including independence, memory
succession and normal ending; missing evidence or prohibited assistance cannot be
repaired afterward. Keep its development label. Held-out comparisons and generalized
learning/performance claims require their separately frozen assessment conditions
and source-episode separation; development data is not relabeled held-out data. A comprehensive acceptance suite
is paid once per coherent candidate and repeated when new changes, failures or uncovered risk
justify it. Do not rerun it for unchanged procedural admissions or duplicate a
passed hosted suite locally solely to complete a checklist.

### Enforcement and upkeep

The optional local commit hook runs the fast command. Development play need not wait for
CI, but formal acceptance/merge requires the actual successful exact-candidate
check under the [CI profile policy](ci-profiles.md#protected-ci-profiles). It may complete after an unchanged development
run, before acceptance is granted. C-PORTABLE/C-RELEASE own the mechanical
boundaries; C-REVIEW checks selected tests, outcome scope and evidence rather than
approving ordinary gameplay actions.

## Efficient discovery

Optimize for useful uncertainty resolved and capability progress per unit of work.
Use the cheapest relevant check first: producer source/configuration, a focused
real-component reproduction, then finite native exploration and the integrated
outcome. For example, registered action names do not prove default key bindings;
inspect the engine's existing bindings before spending another creation cycle.
Batch related unknown capabilities into a coherent development admission where
possible. A traceable failure can guide the next experiment without a fresh full
suite or report package. The player uses supported replanning/recovery while its
scope remains eligible; unknown delivery or lost authority never permits replay.

Retain the starting basis, source/configuration, intent, observations, delivery and
semantic outcome, costs, interventions and finding disposition in the existing
admission/ledger/archive/Git/Issues. Show the maintainer a small coverage/findings
summary with links to those records; do not build a second history or tracker.
Continuing across admissions is an ordinary player Load of a game save, as in
#382's chained lineages. It restores no old authority and rolls back no run.
Source repairs still require closure and a new finite admission; exploratory
evidence keeps its declared conditions and does not become a fresh assessment.

## Upkeep

A step in this cadence is a control. Simplify or remove one whose cost is not
justified by the defects it catches, and strengthen a targeted check when evidence
warrants it, under the [control rule](../standards/authority.md#control-review).
Repair or simplify a navigation map that hides the invariant, assertion or gap a
reader is looking for.

[Workflow index](../project-management.md).
