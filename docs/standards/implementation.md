---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# S-CODE Maintainable implementation

Use cohesive responsibilities, descriptive names, explicit types at Python
boundaries and upstream conventions in C++ patches. Validate inputs at trust
boundaries; bound sizes, waits and action counts. Use atomic publication and
explicit expected-error handling; service-boundary catches must retain diagnostics.
Use library-owned mutation APIs to preserve their buffer/state invariants instead
of manually changing shadow lengths or flags. Qualify real boundary behavior when
native callbacks change; patch-anchor tests alone do not exercise the widget.
Comments explain otherwise unavailable intent. Select dependencies for concrete
capability and lifetime cost; pin locally and record provenance. Evaluate mature
tools before writing generic controls, parsers or infrastructure. Use maintained
implementations that fit the requirement; custom code needs a documented gap and
a bounded scope. Review adoption, compatibility, licenses and upgrade burden. Current stack
preferences are [decisions](../decisions/002-local-contract.md), not permanent bans.

This reuse requirement applies to architecture, implementation, documentation,
workflow and controls. Before adding or substantially expanding a custom tool or
process, record the existing capability considered, the concrete unmet requirement,
the smallest necessary custom scope, its owner/maintenance cost and a replacement
or retirement trigger in the existing brief, ADR or PR. Small changes need only a
short rationale; no separate catalog or template is required. Prefer configuration
and thin integration of maintained tools. Do not build another version-control,
tracker, parser, validator, renderer or generic lint framework where an existing
capability fits. Dependencies also have costs; reuse is a reasoned decision, not a
requirement to add a package for every small project-specific rule.
Judge the choice against the overall objective and the available ecosystem, not
only the current implementation's convenience. Consider engine/platform features,
standard libraries, maintained tools/frameworks and services we can reasonably
adopt or acquire. Prefer an existing capability or thin integration when it
accelerates useful delivery at lower total complexity, latency, operating and
maintenance cost. Custom code remains appropriate for a demonstrated domain gap
or when it is simpler than adopting a dependency. A feature, abstraction, control
or procedure without a concrete contribution should be simplified, deferred or
removed. Routine choices need no new evaluation report or approval ceremony.
Assess this value over the relevant project horizon. Reusable tooling, better
observability, evaluation fixtures, checkpoint reuse or architectural seams may
justify upfront investment through future delivery, learning or cost reduction.
For consequential investments, record the expected uses/benefit, uncertainty,
initial and recurring cost, and a reassessment/replacement trigger in the existing
issue/brief/ADR. A bounded experiment can resolve uncertainty; neither immediate
payback nor a precise ROI estimate is mandatory. Avoid speculative generality,
but do not equate all enabling work with overengineering.

Read [Behavioral testing and timing evidence](testing.md) for this part of the standard.

## Platform contracts and proportional validation

Rely on documented platform contracts with their required configuration and scope.
Use SQLite transactions and declared constraints for database consistency; enable
foreign keys on the relevant connections. Use ordinary OS process/file APIs and
same-filesystem atomic replacement for publication. Do not recreate these guarantees
with application journals, shadow state, repeated readbacks or generic recovery
layers. SQLite does not commit game inputs or external files atomically with its
rows; successful atomic replacement alone is not a power-loss durability claim.
Keep application-specific intent/ACK correlation, source applicability, custody
and unknown-delivery handling at their real boundaries.

Validate external/untrusted data at ingress, changed authority at dispatch, and
stored evidence when it is consumed, reopened or audited. Do not repeatedly
revalidate already validated internal values or rehash unchanged archived files
merely to confirm an ACK. Additional checks need a concrete failure/risk, an unmet
platform guarantee and a benefit proportionate to their latency and maintenance
cost. Handle documented I/O/DB errors; do not assume arbitrary OS/SQLite contract
violations or turn this single-host game into a distributed storage system.
Tests exercise our integration, required configuration and domain invariants;
they do not re-prove SQLite/POSIX or inject impossible platform behavior to justify
extra production machinery. At integration, remove redundant checks and needless
fallbacks as well as fixing missing ones. No blanket hardening campaign or new
checker is required. Primary references: [SQLite transactions](https://www.sqlite.org/lang_transaction.html),
[foreign-key configuration](https://www.sqlite.org/foreignkeys.html#fk_enable),
and [Python's OS replacement contract](https://docs.python.org/3/library/os.html#os.replace).

C-REVIEW requires the reviewer to challenge unsupported custom infrastructure and
hold acceptance until its gap is justified or the duplication removed.
Review the platform guarantee/configuration and the residual project requirement;
challenge duplicated checks, hypothetical failure models and disproportionate
recovery complexity. Record the consequential decision in the existing brief/PR.
Semantic fit cannot be proved by a keyword check or test for the presence of a rationale.
Use mature tools to enforce their supported properties; keep project checks bounded
to the remaining project rules. [ADR003](../decisions/003-development-controls.md) and
[ADR004](../decisions/004-documentation-controls.md) record the existing choices.

[Standards index](../engineering.md).
