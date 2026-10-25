## Problem and result

<!-- Explain the user-visible problem and resulting behavior. Keep one reviewable outcome. -->

<!-- Link the owning iteration's required core and optional scope. A PR is an integration
batch, not necessarily the whole iteration. Note material scope/forecast changes and
remaining review/validation/docs/cleanup; do not close the outcome on code alone.
No new iteration document, full-suite rerun or report per task is required. -->

<!-- Scope from the highest changed responsibility down to components, contracts/state/callers,
implementation and procedures. Link the parent/component design; explain unchanged boundaries.
Select applicable risk-based assurance from docs/project-management.md; no duplicate plan needed. -->

<!-- S-CODE reuse review: for new/expanded custom tools, processes, docs generators or
controls, link the existing brief/ADR or briefly name the existing option, unmet gap,
smallest custom scope, maintenance owner/cost and replacement/retirement trigger.
Prefer mature-tool configuration; do not create a separate inventory for this PR. -->

## Issue references

Refs #

<!-- Link the issue and dependencies. Use Refs while validation is pending; add a closing
reference only after acceptance is verified. A duplicate/cancelled issue is not delivered work. -->

## Verification

<!-- Record candidate/environment, exact commands actually run and results, including failures.
Separate portable checks, native builds and observed gameplay. State checks not run and why.
Fast checkpoint: .venv/bin/python tools/check.py --fast plus applicable focused tests.
Full portable command: .venv/bin/python tools/check.py (or --profile full).
Record the actual protected CI profile and linked run under
docs/project-management.md#protected-ci-profiles. Broad source changes need full
regression before merge. Editorial omits runtime/viewer tests; movement/viewer run explicit component and boundary tests; main-smoke runs selected
regressions and viewer tests and links qualifying PR coverage, never a full-main claim.
Reuse existing valid exact-candidate evidence without a duplicate local full run.
Label development evidence versus formal acceptance; link consolidated run findings.
Do not require another full suite/reviewer for every development attempt.
Native bridge/input/renderer/compiler/source-pin/protocol changes need relevant native acceptance.
Redact secrets, private paths and data; do not attach saves by default. -->

## Migration and removal evidence

<!-- S-MIGRATION: identify old/new contracts; migrated producers, consumers, fixtures,
configuration and data; removed old paths; unsupported-version rejection tests;
coordinated deployment order and rollback/retention decision. No runtime compatibility
path, alias, fallback or downgrade. If unaffected, explain why migration is not needed. -->

## Documentation and limitations

<!-- Link contracts/guidance updated in this change. Describe remaining uncertainty,
scope exclusions, migration limits and follow-up issues. Say why no docs change is needed if applicable. -->

## Independent review evidence

<!-- For consequential changes, identify reviewer (human or agent), candidate reviewed,
findings and disposition. Challenge custom infrastructure/reuse rationale and reject
unjustified duplication. If pending, say so. Do not present agent review as human approval. -->

<!-- Review changed architecture/design before commitment, code against the adopted design,
then outcome evidence. Select product/security/research/operations lenses only as relevant.
Consolidate expensive assurance around a coherent outcome; record material gaps and cost. -->
