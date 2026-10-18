---
owner: lead
status: historical
date: 2026-10-18
scope: Reviewed repository identity migration; GitHub owns live work and current controls own future publication
---

# Enactive repository migration

The user requested removal of historical personal metadata, prohibited Support
requests, selected **Enactive**, and explicitly approved the real migration.
Inspecting author/committer fields alone missed personal co-author trailers in
commit messages. The replacement must preserve useful history and project work
without importing the old PR branches that contain the same metadata.

Use an independent repository, not a fork or mirror. Pinned git-filter-repo in an
owned project-local environment sanitizes main's messages from a native Git bundle.
Verify every source tree and parent relationship against the original. Retain the
original bundle and commit map privately. Rewritten hashes and signatures are not
the original commit identities. Do not force-push or delete the source repository.

Use native Issue transfer and keep the existing Project rather than inventing a
tracker or recreating planning history. Transfer real Issues in original numbered
order. Each old PR slot becomes a closed, labeled historical change record with its
original description, dated conversation and actual merge outcome. These archives
are neither native PRs nor new deliveries and stay outside the Project. Full import
would bring back unwanted PR objects; dropping all PR context would lose useful
review evidence. The archive choice retains original Issue numbers and readable
references while explicitly disclosing the loss of native PR semantics.

Verify every Issue, conversation, milestone, dependency and parent-child link,
and all original Project item identities and manual values against snapshots.
GitHub transfer changes Issue/comment identities, rewrites some references and
settles associated metadata asynchronously. Resume uncertain operations by reading
actual server identities; never repeat a transfer merely because a response timed
out. Restore missing hierarchy edges using new native IDs. Preserve closed state
and attribution without reopening/reclosing work to simulate history.

Migrate current documentation, Issues, comments and Project navigation together.
Original CI URLs, source-branch-only revisions and historical receipt values remain
explicitly historical. Add full-message identity inspection to the existing manual
review control and repository-local setup, without a new privacy framework.

The lead owns this coupled migration and all writes. Read-only source/API sweeps
and clean-context plan/final review provide independent evidence; implementation
workers would share the same stateful critical path. Verify common checks, new
hosted CI, a CI-passing direct push rejection, and an actual protected PR merge.
Only then cut over local Git and make the old repository a private archive. Keep
native dependencies, saves and runtime evidence in place. No game rebuild or play
is needed because product implementation is unchanged.

The [acceptance record](../acceptance/2026-10-18-enactive-migration.md) records the
evidence and remaining limits. Cleanup covers only named disposable canary
repositories/Project and owned duplicate tooling. No global settings change.
Maintenance uses C-REVIEW/C-RELEASE and existing #75 on publication failures,
identity changes or the scheduled control review; unrelated due dates are not renewed.
