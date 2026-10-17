---
owner: lead
status: historical
date: '2026-10-17'
scope: Public source, project management, hosted portable checks and branch-rule verification
---

# Public workflow acceptance

## Delivered surfaces and authority

[Repository](https://github.com/CVX-Hull/cdda-player) and [Project](https://github.com/users/CVX-Hull/projects/2)
are public. Issues own scope, acceptance, dependencies and blockers; Project fields
own stage and sequencing. Durable contracts remain in Git. The owner-facing
[Direction view](https://github.com/users/CVX-Hull/projects/2/views/4) groups five
outcomes by Now/Next/Later and sorts by priority. Execution uses six delivery stages;
Needs attention filters blocked, decision-needed and risk labels. The three views
and public visibility were inspected without signing in. Thirteen issues were seeded
with accountable ownership, provisional size/confidence, acceptance, exclusions and
explicit dependencies; bounded research is sized separately from unknown implementation.
All six initial Project transition workflows were removed so closure or merge cannot
silently establish acceptance. Fields do not mechanically enforce semantic readiness,
WIP or Done. The lead owns that review; issue #13 records the next maintenance boundary.

## Source publication and delegation

Bootstrap source: `739340985f3bc99b78857cb7272a77e128b2abd9`. MIT applies to original
project work, by the user's decision. NOTICE retains CDDA-derived CC BY-SA code and
artwork/font attribution. Downloaded software, game saves, environments and runtime
logs remain ignored. Gitleaks 8.30.1 scanned all seven bootstrap commits (~1.82 MB)
with no findings; source/history inspection complemented it. This is detection
evidence, not proof that all possible secrets or licensing issues are absent.

Two bounded workers ran from `c04af99` in separate project-local worktrees: one owned
the workflow/research guidance, the other contributor/security guides and templates.
The lead inspected and integrated their disjoint results, extended existing metadata
and link checks to the new root guides, and retained design and verification.
Fresh-context independent review found no outstanding material findings. The completed
worker trees were archived under ignored local publication evidence before removal.
No global package/profile change or game/runtime mutation was needed.

## Checks, failures and repairs

The complete local lane passed 84 Python tests, four viewer scenarios, Ruff, import
contracts, local document links, metadata, lifecycle/due-date controls and actual
Mermaid rendering. The commit hook first rejected a trailing blank line in LICENSE;
it was repaired and the gate rerun. No failed gate was bypassed.

The [first hosted run](https://github.com/CVX-Hull/cdda-player/actions/runs/39069852062)
failed because Ubuntu denied the downloaded Chrome's sandbox namespaces. The
[initial repair run](https://github.com/CVX-Hull/cdda-player/actions/runs/39069952613)
then exposed an asynchronous Puppeteer executablePath API mismatch missed by
syntax-only review. The command now awaits the pinned API and was executed locally.
The repair uses an exact-path AppArmor profile on the disposable Ubuntu 24.04 runner;
Chrome sandboxing stays enabled. No host-wide user-namespace sysctl was disabled.
Independent review checked the corrected command against the installed declarations.
A [subsequent run](https://github.com/CVX-Hull/cdda-player/actions/runs/39070035684)
passed rendering but timed out during a functional fixture's 250 ms resume setup.
Normal file/thread exchanges now allow two seconds; production deadlines and the
explicit short timeout/freeze regressions are unchanged. Shared-runner scheduling
sensitivity is the working explanation, not a measured latency diagnosis.
[PR #14](https://github.com/CVX-Hull/cdda-player/pull/14) preserves the failures and repairs.

The repaired candidate `c53527501771590443096b27eb9f588439952f38` passed the
[push run](https://github.com/CVX-Hull/cdda-player/actions/runs/39070139456) and
[PR run](https://github.com/CVX-Hull/cdda-player/actions/runs/39070144468), including
all 84 Python tests and four viewer cases. PR #14 then merged normally as
`e20a8677d215aeb6a59bace6c99db175c03e9ad9`; no bypass was used.
This exercises the successful protected-PR path on the actual repository.

## Enforced branch rules

[Ruleset 25319489](https://github.com/CVX-Hull/cdda-player/rules/25319489) targets main
in active mode: require a PR, strict up-to-date `controller` check bound to the observed
GitHub Actions app (15368), resolved review conversations, squash merges, no force
push and no deletion. Bypass actors are empty; the operating account reports bypass
`never`. Required human approvals are zero because one account cannot approve its
own PR. Independent agent review remains manual evidence, not a second human identity.

GitHub rejected PR #14 merge attempts both while the real check was in progress and
when it failed (HTTP 405 naming `controller`). These probes exercised the actual
repository rules; no bypass or rule relaxation was used.

The unchanged-tree probe `11dafcf94271b2f7e8e8766643dac4343c58ea08`, parented directly
on main `e20a8677d215aeb6a59bace6c99db175c03e9ad9`, passed its genuine
[Actions run](https://github.com/CVX-Hull/cdda-player/actions/runs/39070229641).
A normal fast-forward push of that SHA to main then failed with GH013:
“Changes must be made through a pull request.” Main was identical before and after.
This isolates the PR requirement from missing checks or a non-fast-forward rejection.
The integrated [main run](https://github.com/CVX-Hull/cdda-player/actions/runs/39070226855)
also passed. Force-push/deletion prevention was inspected in the active API rules;
no destructive main-history or deletion experiment was performed.

## Maintenance and limits

Keep issue stages, estimates and blocker labels current at checkpoints. Review
control effectiveness by 2027-01-15 or an earlier event; do not just renew dates.
The actual failures show that syntax review cannot establish current library API
behavior or Linux browser compatibility. Execute boundary calls and retain real
hosted probes. Full CI has installation/rendering cost; start with two implementation
workers and one integration slice, and tune only from observed queues and rework.
No calibrated throughput, elapsed-time forecast or financial-cost estimate exists yet.

This increment changes project workflow and portable CI, not native gameplay.
Runtime paths remain identical to `88dd803681a6d464692b1176a4becc67e62af5a2`.
Earlier [MVP acceptance](2026-10-17-mvp.md) owns native evidence and its media limits.
Local raw receipts and archived worker files are under ignored
`.runtime/evidence/publication/`; a fresh clone has public run/PR/rules links and
this report, not those local files. Administrators can change rules later: this
report is a dated verification, not a permanent guarantee.
