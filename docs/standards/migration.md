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
Rollback deploys a coherent earlier system with its corresponding data migration;
it never enables mixed versions. Historical reports and archived source remain
immutable evidence, not supported execution paths. Upstream-owned game saves and
upstream internals remain CDDA's responsibility: pin the chosen engine and follow
its supported save procedures; do not edit saves or remove authentic engine behavior.

Every affected PR identifies the old and new contracts, migrated callers/data,
removed paths, rejection tests, deployment order and rollback/retention decision,
or explains why no migration applies. Existing version guards, schemas and negative
tests enforce known boundaries. Review checks for unlisted compatibility paths;
no static control proves their absence across all code. Review this coverage when
formats, dependencies or controls change and at the normal maintenance checkpoint.
This user requirement cannot be waived through a repository exception.

[Standards index](../engineering.md).
