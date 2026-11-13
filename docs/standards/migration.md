---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# S-MIGRATION One current contract, coordinated migration

Backward compatibility is not supported anywhere in project-controlled code,
configuration, storage, tooling or documentation contracts. Each boundary has one
current format and behavior. Remove old readers/writers, fallback paths, deprecated
aliases, compatibility shims and downgrade negotiation in the same change that
replaces them. Do not keep an old path behind a flag or as an optional adapter.

At architecture level, identify every affected producer, consumer, dependency and
persisted format before changing a contract. At implementation level, migrate all
callers, tests, fixtures, tools and current guidance together; reject unsupported
versions rather than guessing a format. At delivery level, stop affected writers,
preserve evidence, perform an explicit offline migration or justified recreation,
then deploy the coordinated set. Unresolved actions remain unresolved; migration
must never replay an input, fabricate missing authority or discard saves.

A one-time offline conversion is a migration operation, never a runtime reader or
ongoing supported API. Record inputs, outputs, validation and removal of temporary
conversion tooling. If conversion cannot preserve meaning, archive the old artifact
and create current state only after resolving its retention and uncertainty duties.
Going back means checking out the earlier source and starting from fresh stores
([procedure](../operations/migration.md)); it never enables mixed versions. Historical reports and archived source remain
immutable evidence, not supported execution paths; their content is never edited, but a
link whose target moved or was removed may be repointed to its new home or to a commit
permalink of the old file ([ADR 010](../decisions/010-streamlined-delivery.md)). Upstream-owned game saves and
upstream internals remain CDDA's responsibility: pin the chosen engine and follow
its supported save procedures; do not edit saves or remove authentic engine behavior.

**Closed archive reads and additive evidence events (owner decision on #403).** The
owner scoped this requirement to allow two narrow cases. Because the owner
set them, the closing rule below still holds: no repository exception can add to them.
First, the evaluator reads, read-only, old record versions only for the sealed sessions
in one closed index, `data/evaluation/archive-sessions.json`, and for each session only
the versions the index records for it. The index is closed and never grows. Adding a
session is a new owner decision, a row in the
[owner decision log](../decisions/owner-decisions.md). The index holds 54 sessions: 30
older development-loop sessions, 22 whose run-ending record is
`campaign-watch-terminal/3`, and the two of the supervised launch check. All 54
predate the dollar limit, so each is read in the versions the index records for it.
Every other old version is an error naming the file and version. The evaluator never admits
or plays from the archive and never modifies it; it only derives evaluation records.
Second, an evidence-only event (one that no admission, control or player-visible path
reads) may be added inside an unchanged telemetry version when it changes no existing
field and every reader that uses it marks its absence in older traces as not recorded,
never as a failure or as a value presented as recorded. No event has been added inside
the current `player-host` telemetry version 4, where `context-manifest` and the reported
cost belong to the contract. The case still governs the archived telemetry version 3
traces: `context-manifest` was added inside that version, so the evaluator records its
absence from an older trace as `manifest: absent` and the context view rebuilds as
`exact: false`. Anything else, including another
archive or a changed existing field, needs a new version and a migration as above.

Every affected PR identifies the old and new contracts, the migrated callers and
data, the removed paths and the rejection tests, or explains why no migration
applies. Existing version guards, schemas and negative tests enforce known
boundaries. Review checks for unlisted compatibility paths; no static control proves
their absence across all code. This user requirement cannot be waived through a
repository exception.

[Standards index](../engineering.md).
