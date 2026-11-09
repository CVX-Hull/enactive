---
owner: maintainer
review_trigger: Behavior, control failures, release or constraints change
status: active
---

# Engineering standards and workflow

The lead adjudicates design and verification.
Principles are in the [charter](charter.md); what each control stops, where it is
enforced and its gap are in [controls](controls.md). Each standard below is mandatory
in its scope and names its principles and controls here, the one place that maps them.
An exception needs scope, reason, owner and revisit/expiry in a GitHub issue linked
to the affected standard; [work](work.md) links the work tracker.
Exceptions cannot override user instructions or hide failed acceptance.

## Authority and reading order

- [Authority and reading order](standards/authority.md).

## S-UX Understandable and controllable experience

Principles: P-AUTHORITY, P-TRUTH, P-REVIEW, P-UNCERTAINTY.

- [S-UX Understandable and controllable experience](standards/experience.md).

Controls: C-PORTABLE, C-RUNTIME, C-NATIVE, C-USABILITY.

## S-ARCH Explicit architectural boundaries

Principles: P-CHANGE, P-ISOLATION, P-REVIEW, P-GENERALITY.

- [S-ARCH Explicit architectural boundaries](standards/architecture.md).

Controls: C-BOUNDARY, C-REVIEW, C-DOCUMENTS.

## S-PROTOCOL Command and observation authority

Principles: P-AUTHORITY, P-TRUTH, P-UNCERTAINTY.

- [S-PROTOCOL Command and observation authority](standards/protocol.md).

Controls: C-RUNTIME, C-PORTABLE, C-NATIVE.

## S-CODE Maintainable implementation

Principles: P-CHANGE, P-UNCERTAINTY, P-KNOWLEDGE, P-GENERALITY.

- [S-CODE Maintainable implementation](standards/implementation.md).

Controls: C-PORTABLE, C-REVIEW, C-BOUNDARY.

## S-DELIVERY Reproducible and isolated delivery

Principles: P-ISOLATION, P-CHANGE, P-KNOWLEDGE.

- [S-DELIVERY Reproducible and isolated delivery](standards/delivery.md).

Controls: C-SETUP, C-RELEASE, C-NATIVE, C-REVIEW.

## S-OPS Observable operation and recovery

Principles: P-AUTHORITY, P-UNCERTAINTY, P-ISOLATION.

- [S-OPS Observable operation and recovery](standards/operations.md).

Controls: C-RUNTIME, C-PORTABLE, C-NATIVE, C-MAINTENANCE.

## S-AGENT Accountable agent-assisted work

Principles: P-TRUTH, P-KNOWLEDGE, P-REVIEW.

- [S-AGENT Accountable agent-assisted work](standards/agents.md).

Controls: C-REVIEW, C-PORTABLE, C-NATIVE, C-MAINTENANCE.

## S-DOCS Useful maintained documentation

Principles: P-KNOWLEDGE, P-REVIEW, P-CHANGE.

- [S-DOCS Useful maintained documentation](standards/documentation.md).

Controls: C-DOCUMENTS, C-USABILITY, C-REVIEW, C-MAINTENANCE, C-VISUAL.

### Visual explanations

Read [Visual explanations](standards/documentation.md#visual-explanations).

## S-WORK Reviewable and proportionate changes

Principles: P-REVIEW, P-CHANGE, P-KNOWLEDGE.

- [S-WORK Reviewable and proportionate changes](standards/work.md).

Controls: C-REVIEW, C-RELEASE, C-USABILITY.

## S-MIGRATION One current contract, coordinated migration

Principles: P-CHANGE, P-KNOWLEDGE, P-UNCERTAINTY.

- [S-MIGRATION One current contract, coordinated migration](standards/migration.md).

Controls: C-PORTABLE, C-DOCUMENTS, C-REVIEW, C-RELEASE, C-MAINTENANCE.

## S-EVIDENCE Claims with scoped evidence

Principles: P-TRUTH, P-KNOWLEDGE, P-UNCERTAINTY.

- [S-EVIDENCE Claims with scoped evidence](standards/evidence.md).

Controls: C-DOCUMENTS, C-PORTABLE, C-NATIVE, C-RELEASE, C-MAINTENANCE, C-REVIEW.

## Workflow and maintenance

- [Control review](standards/authority.md#control-review).
- [Change and review cadence](standards/authority.md#change-and-review-cadence).
