---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# S-WORK Reviewable and proportionate changes

Keep one integration queue and a bounded number of active outcomes in GitHub.
Shape [outcome-focused iterations](../workflows/work-items.md#outcome-focused-iterations)
with a required core, optional scope, effort appetite and explicit completion or
stop/rescope conditions. Include relevant research/reuse, design, integration,
verification/validation, review, current docs and cleanup in the scope and forecast.
Use small integrated changes and inexpensive feedback within the larger outcome;
neither a task nor a runtime attempt automatically defines an iteration. Required
quality/evidence cannot become optional scope; a successful investigation is not
delivery of a capability it found unsuccessful. C-REVIEW checks selection and fit.
For gameplay, authentic useful development play is the primary behavioral feedback
loop. Use focused offline checks to isolate observed failures and protect changed
boundaries; follow the [gameplay feedback policy](../workflows/development.md#gameplay-as-the-primary-feedback-loop)
instead of adding publication/readiness gates before each ordinary attempt.
At the existing boundary/outcome review, revisit applicable earlier violations
and trace the constraint to its maintained mechanism, regression or explicit
owned evidence gap. Retired gates need a new justified decision before returning;
do not quietly inherit them from old run scripts or chat summaries.
Before assigning implementation, record the outcome and highest changed boundary,
then affected components, interfaces/state/callers, code/tests and operating docs.
Review from that boundary down, using the [risk-based assurance policy](../workflows/review.md#risk-based-assurance).
The existing Issue/PR is sufficient for a contained change; a consequential change
links its brief. This impact record is not a second plan or clause-by-clause matrix.
Issues own scope, acceptance, accountable owner, blockers and exceptions; Project
Status owns execution stage: Backlog, Ready, In progress, Review, Validation, Done.
Blocked work retains its stage and records the condition, owner and next action.
Deferred work needs a reason and revisit trigger. Cancelled or duplicate issues
are closed as not planned and excluded from accepted delivery counts.
At meaningful discussion, research, review and delivery checkpoints, reconcile
actionable findings into the existing Issues/Project. Record an accountable owner,
next action, acceptance and dependencies; disposition duplicates or deferrals.
Update affected principles, standards, controls and authoritative guidance when
the finding changes their meaning or implementation. A chat promise or proposal
is not a delivered control. C-REVIEW checks this reconciliation; no separate action
tracker or automatic semantic-completeness claim is added.
Prospective campaign forecasts include automatic record expansion and storage/
context limits as well as visible input/frame/time allowances. Check rates and
units against real retained counts; packet output bounds do not bound retrieval
work. A contradicted capacity lane needs an owned repair or an explicit incomplete
outcome before admission, rather than a hidden limit increase during play.
Before publishing commits, verify the intended public author/committer identity
and full messages, including co-author trailers. Use explicit repository-local Git
configuration as described in [setup](../setup.md#choose-an-explicit-git-identity);
never substitute an inferred OS account name or local email for the maintainer's
public identity. Review all new commits, not only the eventual squash commit.
Before merging where issue completion awaits merged-main validation, inspect
GitHub’s `closingIssuesReferences` and require none under the
[project workflow](../project-management.md). Negating a closing phrase in prose does
not prevent automatic closure. Update Issue/Project only after actual validation.
Before a significant change, write a short [review brief](../changes/001-engineering-system.md)
covering problem, visible behavior, alternatives, maintenance/reversibility,
evidence/uncertainty and decision needed. Routine fixes need only a cohesive diff
and relevant checks. New boundary/guarantee/dependency changes need design review;
changes to user constraints or substantial new commitments require user input.
Do not invent approval gates for routine authorized work.

A milestone finishes when its stated outcomes and relevant validation are met,
known limitations are explicit and the lead verifies evidence. Fast development
checkpoints improve reviewability and expose actual integration failures before
full qualification; preserve unsuccessful attempts. Use the development-first
checkpoint table rather than treating every attempt as formal acceptance. Review
the stopping policy as well as the success criteria: finite development must allow
useful investigation without granting deployment acceptance or erasing limits.
Review should improve overall code health without indefinite polish or stylistic vetoes.

[Standards index](../engineering.md).
