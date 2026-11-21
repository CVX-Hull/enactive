---
owner: lead
status: historical
date: '2026-10-24'
scope: Design and development record preserved on this date; current architecture/protocol
  and GitHub own behavior and remaining work
---

# Input authority and gameplay evidence — implementation brief

The owner needs reliable input authority before a planner can act on retained
observations. This round implements [#29](https://github.com/CVX-Hull/enactive/issues/29)
and [#32](https://github.com/CVX-Hull/enactive/issues/32) from base
`abb58670f15d9c23daec43a32beda9a3d148d085`. GitHub owns live status and estimates.
The [native design](../design/native-control.md) and
[gameplay design](../design/gameplay.md) own the accepted larger behavior.
This brief fixes the increment's implementation interfaces. The dated
[acceptance](../acceptance/2026-10-17-foundation-implementation.md) records what was
tested and observed; GitHub owns publication and completion state.

## Before and after

At the base revision, an activity's DEFAULTMODE could look like ordinary play, and
reloading a world reset relative coordinates without replacing the process session. The increment
positively marks input boundaries, revokes stale requests and replaces world
authority across reloads. A new evidence adapter retains bounded original frames
and validates typed gameplay records. It does not start a planner or spend API funds.

Full interruption/confirmation/debug-dismissal controls remain #30/#31/#8. Real
observation acceptance for the later gameplay pipeline remains #33. #29 still
requires its own real normal/activity/menu/debug/reload probes before closure.

## Agreed wire interface

Native protocol becomes integer `2`, with existing observation keys retained.
Add required `boundary` object with exactly these fields:

| Field | Type and meaning |
| --- | --- |
| `kind` | `normal_play`, `activity_poll`, `interrupt_confirmation`, `debug_prompt`, `menu`, or `unsupported` |
| `id` | Nonempty opaque string; input-boundary identity, not a frame counter |
| `control_generation` | Nonnegative integer; native operator-control generation |
| `recovery_operations` | Array of supported recovery operation names; empty in this increment |
| `interrupt_request_id` | Null in this increment; future owning interruption request string |

Only positively marked `normal_play` exports `scene`. Existing scene names/types
remain: provenance, relative three-integer position, integer turn, visible creatures
and eight adjacent cells. No new hidden-state exports. Generic DEFAULTMODE is never
sufficient authority; raw/nested debug and activity scopes override ordinary play.
Unknown callers are unsupported. Explicit menu input remains distinct from gameplay;
the implementation must document its supported hook coverage. No generic menu
classification may make an unknown DEFAULTMODE caller ordinary play.
Observe may report any instrumented boundary without injecting input. `key`,
`action` and `resume` require either positive normal play or an explicitly supported
menu, with matching successful frame and authority checks. All three reject at
activity, interrupt-confirmation, debug and unsupported boundaries. Recovery later
gets its separate narrow operations; there is no arbitrary-key escape hatch.

Every input-authorizing envelope (`key`, `action`, `resume`) requires
`authority: {controller_boot_id: <nonempty string>, counter: <nonnegative integer>}`.
The controller atomically publishes the identical object in `authority.json` under
the bridge. Read-only observe does not require an admission token. Native verifies
the token at its final input commit gate, including requests already claimed.
Pause, shutdown, startup retirement and observed takeover revoke before subsequent
admission; later run leases will reuse this mechanism. No v1 fallback. Native
control generation and host authority counter are independent.

Session changes on each world entry/exit; frame names include session. A failed
capture has `frame_ok: false` and cannot become evidence by reusing an old path.
Host records preserve unknown old-session outcomes without treating new-world
observations as success. Context scope uses RAII restoration; boundary identity
must be stable across repaint and change across actual context transitions/takeover.

## Evidence and record interface

Use frozen standard-library dataclasses and existing JSON Schema validation in
`harness/gameplay/contracts.py`. Serialized records use `schema: "gameplay/1"`
and `record_type` equal to the class name. Reject extra fields, bool-as-integer,
nonfinite numbers, unknown versions/enums and JSON input over 1 MiB. Define
`to_dict()` and class `from_dict()` round trips; validation failures use a domain
`ContractError`. Nested budgets and vectors use shared definitions, not arbitrary
unvalidated dictionaries. All eight records in the gameplay design are in scope.
Public types and field names are the module's single source of truth after review.

`EvidenceRef` uses `observation_id`, `session`, `revision`, `timestamp_ms` (native
Unix milliseconds), `received_monotonic` (host seconds), `turn`, `frame_path`,
`frame_sha256`, `boundary_kind`, and `visibility_version: "cdda-visible/1"`.
The visibility version is an adapter allowlist constant, not a new native export.
Observation identity is SHA-256 of the session and immutable frame basename with
an unambiguous encoding. The native top-level `id` correlates a request and may be
empty; it is not observation identity. Conflicting metadata for the same frame
identity invalidates authority instead of minting a new observation.
Coordinates/displacements serialize as three integer arrays. Task target must
equal origin plus cardinal distance. Plan candidates bind task/plan versions,
execution epoch, evidence authority and skill version; they never carry code.
Primitive dispositions retain the design vocabulary, independently of displacement.

The evidence adapter consumes native-v2 dictionaries and an explicit local receipt
time supplied at actual ingestion. Re-reading/copying the same observation never
refreshes it. It validates frame identity/path containment and source availability,
then copies and hashes immutable originals to a caller-supplied project session
directory. Current evidence requires successful frame, normal play, coherent scene,
matching session/revision and age at most three seconds. Capture failure, stale or
contradictory values and changed session invalidate current authority. Historical
references stay historical; interpretations are explicitly tagged and bounded.
Evidence does not itself dispatch input or grant a controller lease.
At first ingestion also require native timestamp age between -1000 and 3000 ms
against the host wall clock: a newly read old file cannot acquire fresh authority.
The one-second future tolerance accommodates clock adjustment, not remote clocks;
larger discontinuities fail closed and require re-observation. Effective age is
`max(0, wall_age_at_ingest) + now_monotonic - original_received_monotonic`, in
seconds; the initial native lag is not discarded. Duplicate/copy/reopen never
renews that receipt or initial age. Import Linter keeps the gameplay package independent
of controller/HTTP/CLI/build tooling and process/network launch APIs.

Enforce 32 distinct frames and 64 MiB per task/run, including reopening an existing
store; no automatic deletion to make room. Missing/corrupt/evicted source is an
error, not a synthetic replacement. Expose capacity failure before dispatch and
test preservation through bridge-cache eviction. Each PNG is at most 32 MiB,
matching the existing server cap. After retaining the before-frame, pre-dispatch
reservation must hold one further distinct slot and 32 MiB for the after/failure
frame; explicit consumption/release prevents another operation from spending it.
A post-action image exceeding that supported bound is missing evidence, stops the
run and cannot produce a successful reference. Tests may use smaller configured
limits but cannot raise the production ceilings. Model/provider work is excluded.

## Allocation, checks and maintenance

Two clean-context workers start at the base above in separate project-local
worktrees: `.runtime/worktrees/native-boundaries` on `work/native-boundaries` and
`.runtime/worktrees/gameplay-evidence` on `work/gameplay-evidence`.

Native worker owns `native/cdda_harness.{h,cpp}`, `native/upstream.json`,
`tools/patch_game.py`, `harness/controller.py`, `harness/server.py`,
`tools/governance.py`, and existing controller/governance/setup/server tests.
Lead integration additionally owns CLI discovery, viewer boundary admission, Import
Linter controls/fixtures, acceptance schema and all repaired cross-boundary defects.
Evidence worker owns only `harness/gameplay/{__init__,contracts,evidence}.py` and
`tests/test_gameplay_{contracts,evidence}.py`. Lead owns all other files, current
docs/control registry, integration, dependency environments, builds, saves and
runtime. Workers use isolated test outputs; source isolation does not authorize
shared runtime writes. Escalation follows S-AGENT, including the two-repair limit.

The lead inspects changes and integrates once per coherent handoff. Independent
review checks authority races, nested scope, record invariants and retention limits.
Run focused tests and the common lane; native hash/anchor checks and a fresh pinned
build are separate from real windowed probes. Retain failed attempts. Update current
architecture/protocol/overview/control map only to the capabilities actually shipped.
Accepted larger design portions remain explicitly future behavior.

Publish through protected PR/CI, verify the exact candidate and only close accepted
issues. Keep source rollback in Git; reject mixed native/host versions rather than
maintaining an untested dual protocol. Revisit retention/schema limits when the
skills/planner consumers expose concrete needs, with coordinated version changes.
No new dependency or global environment change is selected.

## Coordinated-migration scope addition

The user's no-backward-compatibility requirement applies across the project, not
only native wire v2. S-MIGRATION makes coordinated producer/consumer/data/tool/doc
cutover mandatory and removes legacy readers, aliases and runtime fallbacks.
The lead owns this addition: validate stored controller requests/responses on
startup, remove synthetic orphan-input recovery, version active build metadata,
and extend existing protocol drift/negative-test controls. Offline migration keeps
original evidence and unresolved outcomes; historical reports are not runtime formats.
No native binary or gameplay record format change is needed for this addition.
Acceptance includes unsupported-format preservation/rejection, current durable
admission restoration, a verified local build-manifest conversion, independent
review and common CI. Full native gameplay evidence remains tied to its original
source checkpoint; later host-only validation is reported separately.
