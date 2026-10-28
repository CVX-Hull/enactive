---
owner: maintainer
review_trigger: Changes to this operating task, supported setup or recovery behavior
status: active
---

# Coordinated migration

Follow [S-MIGRATION](../standards/migration.md#s-migration-one-current-contract-coordinated-migration)
for every contract change. Stop the controller and affected writers, save/quit CDDA
normally if running, and confirm the owned processes stopped. Record the affected
formats and exact code versions; preserve original files and hashes before conversion.
Migrate the entire producer/consumer/tool/configuration set and its current docs.

Validate converted data against the new contract before replacing active files.
Unsupported bridge records block startup; do not delete admissions or infer a
successful action to make startup pass. Reconcile incident evidence offline while
keeping unknown outcomes unknown. If meaningful conversion is impossible, retain
an incident archive and document the explicit transition to a fresh bridge with
unresolved work still tracked. No replay or save editing is permitted. Historical
reports and journals stay immutable; they need no runtime reader.

Build manifests require `schema_version: 1`; current evidence stores require store version 6.
Never just relabel an unknown file. A reviewed one-time build-manifest migration
must first verify workspace ownership, pinned source/headers and binary hashes,
then record before/after hashes. Alternatively preserve the old manifest/workspace
and use a fresh extraction. Permanent setup/startup paths only read current formats.
Remove temporary converters after recording their operation. Roll back only as a
coordinated system with a validated data transition, never by enabling a fallback.

The historical wire-v4 cutover archived the stopped bridge with original hashes under
`.runtime/incidents/` and start a fresh bridge. Do not relabel old requests. Carry
unresolved identities as verified `incident/1` references in
`historical-incidents.json`; startup validates referenced bytes without parsing
old protocol records. These remain visible historical unknowns and grant no
execution permission. Its evidence format3 accepted native4 observations.
The current `incident/1` reference list admits at most256 individual identities
and128KiB of ASCII-escaped JSON, preserving room in the existing status/client
envelope. Larger histories require explicit reshaping; do not bundle or drop IDs
to make a migration appear resolved.
For the current native7/mission11/ledger13/archive6/memory6 cutover, apply the same
stopped, hash-inventoried incident archive procedure. Preserve prior mission
ledgers/archives as historical evidence; do not relabel them as eligible procedure
libraries or restore their execution authority. Current stores accept native7/store6
only. A separate explicit offline export can preserve the selected native6/store5
baseline as typed advisory data; it never rewrites those archives or restores input.
Canonical Procedure/3 remains native7 and reflection/3 rejects prior records.
Historical learning004/006 retain their original unsupported contracts.

Archive the entire quiescent old bridge and preserve its unresolved identities as
verified historical incident references before starting a fresh native7 bridge;
never relabel old requests or restore execution authority. Use a fresh store for
the new admission. Upstream engine saves are not edited or converted by this
migration; an ordinary Load still requires fresh identity/adoption.

Before pinning new current donors, freeze clean source and run the current-only
engineering export from the project root:

```sh
.venv/bin/python tools/export_procedure_library.py --pins .runtime/export-pins.json --max-bytes 33554432
```

The bounded JSON pin file has exactly `sources` and `dependencies` arrays of
`{mission_id, ledger_sha256, index_sha256}`. Sources are new closed current missions;
dependencies are their complete already-exported ancestry. The output appetite
includes every original PNG, original ledger/index and manifest. Existing exports
are never overwritten. Fresh artifacts are reserved exclusively and their manifest
is published last; failed partial output is ineligible. Live readers use only
`.runtime/procedure-library/<mission>/<ledger-sha>-<index-sha>/`, with shared locks
and independently checked original-byte derivation. Stored original paths are
provenance; image reads derive managed paths from capture IDs.

Legacy conversion is a finite engineering migration using exact original validator
source in an owned temporary extraction. It is not an option of this maintained
current-only CLI or a live reader. Retain original hashes and unknown effects,
validate all source and episode joins, qualify actual current retrieval/revision,
then retire the temporary converter. Never relabel an old packet native7 or add
missing marker fields. An exported HistoricalProcedure cannot run; it may be the
explicit parent of a new current revision. Full acceptance remains separate.

For current-contract donors, the procedure library accepts completed, failed,
stopped and paused archives only after physical and internal closure: both shared
locks exclude runtime writers; exact ledger/index/dependency pins, settled
requests/primitives/effects and closed reflective work must validate. Preserve the
original phase and bytes. A failed or closed paused donor can supply historical
fallible procedures, but cannot restore authority or satisfy the separate
normally completed learning requirement for campaign acceptance. Complete and
normally close that learning outcome before the subsequent fresh campaign.
GitHub and the current delivery evidence own exact prospective identifiers.

[Operations index](../runbook.md).
