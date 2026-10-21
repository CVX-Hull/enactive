---
owner: lead
review_trigger: Development checkpoints, verification timing, campaign evidence or CI policy changes
status: active
---

# Reach meaningful real play before comprehensive qualification

Repeated short attempts exposed harness/API and operator problems before normal
play. Around the entry-refresh repair, two full suites took 394.183 and 396.567
seconds, followed by hosted checks; independent008 stopped after about 121 seconds
of setup. Those are scoped observations, not a calibrated efficiency experiment.
The user asked us to get reasonably far before paying for the full ceremony.

[#169](https://github.com/CVX-Hull/enactive/issues/169) owns activation and upkeep;
[#170](https://github.com/CVX-Hull/enactive/issues/170) owns the next observed API fix.

The authoritative [workflow checkpoint table](../project-management.md#development-first-delivery)
separates development from formal acceptance. Fast checks plus relevant focused
behavioral/negative tests support a reproducible development commit and finite
real run. Full review, portable checks and native outcome evidence qualify the
coherent result. Original full mission criteria and protected main remain intact.
A complete unassisted development run can support functional acceptance after
its unchanged exact source passes the remaining checks; it is not relabeled a
held-out experiment or repeated merely to change its label. Failed attempts stay
failed. Source repairs require quiescence/closure and a new finite run.

Reuse the existing check runner, Ruff, Import Linter, document/governance checks,
Git hooks and GitHub Actions. Add an explicit `--fast` checkpoint option to the
existing runner; the default retains the entire portable suite. The hook uses
fast mode; CI uses full mode. Run CI for PRs and pushes to main rather than duplicate
feature-branch push/PR jobs. GitHub concurrency cancels superseded PR runs only.
Keep the required `controller` job and ruleset unchanged; no path filters skip it.
[GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
documents the branch/event/concurrency behavior and the pending-check risk of
skipping a required workflow. No bespoke test selector, tracker, permission bypass,
new dependency or second gameplay executor is needed.

Development notes reference existing admission/ledger/archive and retain concise
closure, costs/unknowns, cleanup and owned findings. Consolidate public reports at
integration/acceptance. Current contracts still change with behavior. Record the
run purpose in its existing issue/note/admission objective; this is an engineering
evidence classification, not a runtime mode or protocol/format migration.

Lead owns the check runner, configuration, current docs and control registry.
C-REVIEW checks default-full behavior, fast failure propagation, relevant-test
selection, required CI triggers and evidence reuse without retrospective success.
C-PORTABLE/C-RELEASE enforce fast/full mechanical boundaries and protected merge;
C-MAINTENANCE reviews useful gameplay reached versus verification/waiting burden
at integration/closeout and existing event/date triggers. Revisit if escapes rise
or checking again dominates learning; strengthen targeted checks or simplify the
workflow from actual evidence. No dates or prior allowances are renewed.
