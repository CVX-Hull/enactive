---
owner: lead
review_trigger: Historical migration record; supersede with new evidence rather than rewriting outcomes
status: historical
date: 2026-10-18
scope: Main-history sanitization, native Issue and Project preservation, canonical references and replacement publication
---

# Migration to Enactive

The canonical repository is [CVX-Hull/enactive](https://github.com/CVX-Hull/enactive).
The [existing public Project](https://github.com/users/CVX-Hull/projects/2) keeps its
identity and planning history. The user selected this name and explicitly approved
the real migration. The [brief](../changes/015-enactive-migration.md) explains the
alternatives and controls; this record separates preservation from publication.

## Preserved work and source

| Boundary | Verified result |
| --- | --- |
| Original main history | All 28 commits retained; every source tree and parent relationship identical. Exact message replacements with pinned git-filter-repo 2.47.0 changed 21 commit hashes. |
| Sanitized baseline | `6e51da53d80b2274f5c3c9e19ecf34e8177285e2`; 719 Git objects, including unreachable objects, scanned with no checked personal-name/email matches. This is a scoped scan, not a universal privacy guarantee. |
| Real Issues | 63 natively transferred at their original numbers; 26 open. Titles, states/reasons, creators, assignees, labels, milestones, created/closed times and conversation authors/times/content preserved, allowing only observed native reference qualification. |
| Closure provenance | All 37 closed Issues retain the original `closed_by` and closure-event actor/time. Original API `closed_at` and timeline times sometimes differ by one second; each was compared to its own original value. |
| Planning | Same 63 Project item IDs, archived flags and all manual field values; same Project identity, views and filters. No priority, estimate, delivery status or start/finish date was promoted by migration. |
| Relationships | All 69 dependency and 47 parent-child edges verified using new Issue IDs. Five milestones retain names, descriptions, states and due dates; 16 original labels retained. |
| Historical PR context | 21 closed `historical-change` records occupy the original PR numbers. They preserve safe descriptions, dated conversation, actual merge attribution/time and tree-equivalent sanitized main links. The source API returned no native reviews, inline comments or review threads for these PRs. |

Historical records are **not native PRs, new tasks or accepted deliveries**. They
are closed as not planned for administrative exclusion, carry only the archive
label and are absent from the Project. That closure does not mean the original
merged change was cancelled. Native Issues and comments receive new GitHub IDs;
Issue numbers and Project item IDs stay stable. This is not a promise that outside
links to old IDs, anchors or source branches continue to resolve.

Canonical Issue, documentation and Project references move to Enactive together.
Links to old PRs lead to explicitly labeled historical records. Historical CI runs
and rule URLs remain references to the original server events, and original bare
revision values/JSON receipts remain historical provenance. Old source-branch
objects and PR refs are not imported. Rewritten commit signatures are not original
signatures. Earlier native acceptance is not relabeled as a new game run.

## Verification and publication

The sanitized baseline's [new hosted run](https://github.com/CVX-Hull/enactive/actions/runs/39138157433)
passed. Replacement [ruleset 25346774](https://github.com/CVX-Hull/enactive/rules/25346774)
matches the original: main requires a PR, strict Actions-bound `controller`
(integration 15368), resolved conversations, squash merge, and no deletion,
non-fast-forward or configured bypass. Required human approvals remain zero;
independent agent review is manually recorded evidence. Initial clean-main bootstrap
preceded rule activation. Administrators can change rules later.

Common checks passed: 438 Python tests, viewer regressions, import boundaries,
document/diagram/governance and whitespace checks. Clean-context review independently
verified source-tree/topology preservation, closure provenance and Project values;
no confirmed defect remained in the reviewed documentation candidate.
CI-passing direct-push rejection, exact final candidate CI and protected
PR/merged-main publication are required before migration completion.
The native PR and Actions records supply exact candidate and merge identities;
passing portable CI does not establish gameplay acceptance.

## Failures, boundaries and maintenance

The first author-field-only audit missed co-author trailers. Raw Git-object
inspection corrected it before replacement publication. The transfer first
appeared to omit an assignee; later readback showed asynchronous settlement. Work
stopped on unexpected reference transformations, accepted only narrowly verified
GitHub qualification/Issue-URL changes, and resumed by destination identity. A TLS
timeout interrupted read-only verification; bounded read retries completed it.
No native Issue was transferred twice and no closed Issue was reopened for migration.
The first common run could not launch the local headless Chromium renderer inside
the sandbox. The authorized rerun passed the full lane; both outputs are retained.
Replacement security settings, including private vulnerability reporting and secret
scanning/push protection, require readback after public visibility before retiring
the source repository.

Original snapshots, the native Git bundle/commit map, canary results, raw-object
scan and migration verification receipts stay in ignored, private project-local
storage. They contain original metadata and must not be published. The old
repository is retained rather than deleted; after full replacement verification,
it is made a private archive. No Support/privacy requests are submitted. Private
archival and clean replacement cannot erase outside clones, caches or previously
downloaded objects, and historical CI links may require maintainer access.

Native implementation, saves and runtime evidence are unchanged. No graphical
session or build is claimed. All tooling, copies and backups remain project-local;
global installations and Git profiles are untouched. Disposable canary resources
are separate from the real repositories and Project and are removed after evidence
retention. Future publication follows [explicit local identity setup](../setup.md#choose-an-explicit-git-identity)
and full-message/trailer inspection under C-REVIEW; this manual control does not
prove arbitrary-file privacy. #75 retains the next maintenance trigger and due date.
