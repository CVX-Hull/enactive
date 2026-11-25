---
owner: lead
status: proposed
review_trigger: "The owner decides whether to take up the programs line, a program implementation leaf (#465-#470) begins, or the active curator, player-host, player-ports, or spectator-view contracts change."
---

# Bounded program interface brief

## At a glance

- **Question.** Before any program implementation leaf ([#465](https://github.com/CVX-Hull/enactive/issues/465)–[#470](https://github.com/CVX-Hull/enactive/issues/470)) begins, what exact artifact identity, multi-file layout, pre-qualification storage rule, revocation semantics, passive execution envelope, refused versions, and fact-store dependencies must be frozen?
- **Answer.** This brief freezes those boundaries for [ADR 009](../decisions/009-curated-player.md#interface-milestones-and-acceptance-ownership) and [programs and monitor](programs-and-monitor.md) with zero code or schema changes. Curator-submitted programs are immutable multi-file artifacts introduced via coordinated successor contracts (`curator-knowledge/5`, `curator-submission/3`, `delivered-knowledge/4`), separated cleanly from retired `player-memory/2` hooks. Structural gate validation may store an artifact only as `stored_ineligible` (never exported or runnable in play); revocation is a monotonic gate record checked before every invocation that blocks new pins and new invocations without silently mutating a pinned run or touching live custody.
- **Evidence standing.** Evidence that induced programs improve screenshot-only play is weak to absent, and external coding/web benchmarks show self-generated skills harming performance or incurring large regression taxes. **This brief claims no need to build programs** and authorizes no implementation, migration, or spend.
- **Unknown.** Whether routine-recurrence delegation beats direct actor play at a matched failure rate; which language/interpreter, semantic oracle, or belief representation (if any) would earn adoption.
- **Decision needed.** None for this brief ([25 November disposition](../decisions/owner-decisions-archive.md#wave3-wave4-live-validation-accepted-963), following the [20 November brief decision](../decisions/owner-decisions.md#register-the-bounded-program-interface-brief)). Opening any program implementation leaf (`#465`–`#470`), the integrated study, a practice instance, or any spend requires separate owner decisions.

## Scope, terms, and active-contract baseline

Terms follow the [glossary](../glossary.md). This brief refines the interface handoff named in [ADR 009](../decisions/009-curated-player.md#interface-milestones-and-acceptance-ownership) and [programs and monitor](programs-and-monitor.md) against the active contracts:

- [Computer-control contract](../contracts/computer-control.md) (`computer-request/3`, `computer-receipt/2`, one input sender, permanent Pause, and permanent input stop on partial or unknown delivery).
- [Player ports contract](../contracts/player-ports.md) (`player-journal/1`, `player-computer-result/2`, `player-knowledge/3`, required `intent`, optional `cites`, no hidden countdown exposure).
- [Player host contract](../contracts/player-host.md) (`player-host/12`, `delivered-knowledge/3`, pinned immutable run packages).
- [Curator contract](../contracts/curator.md) (`curator-knowledge/4`, `curator-fact/5`, `curator-submission/2`, `curator-gate/2`, `curator-coverage/2`).

Nothing in `curator-knowledge/4` accepts program or test files today: `harness/curator/gate.py` enforces that `programs/.keep` and `tests/.keep` are empty and refuses any other entry under `programs/` or `tests/`. Adopting this interface requires a coordinated `S-MIGRATION` across three closed formats—the repository (`curator-knowledge/5`), submissions (`curator-submission/3`), and delivered exports (`delivered-knowledge/4`)—migrating every producer, gate check, exporter, reader, and rejection test together.

## Program artifact identity, multi-file layout, manifest, and tests

### Identity and version pinning

Every curator-submitted program carries both a stable lineage slug and an immutable revision identity:

- **`slug`**: matches `[a-z0-9][a-z0-9-]{0,63}` (same character grammar as fact IDs and article slugs in `schemas/curator-fact.schema.json`). Program slugs share one reserved namespace across compatible tagged history, including tags superseded by an operator restore, so a retired or restored slug is never silently recycled.
- **`revision`**: software-assigned `<slug>@v<N>` on gate publication, where `v<N>` is the monotonic repository tag that published it (`published_in`).
- **`parent_revision`**: `null` for an initial program, or the current active lineage head `<slug>@v<K>` (`K < N`) for a revision. Revising a non-head ancestor is rejected, enforcing a strictly linear revision chain per slug and preventing hidden sibling branches.
- **`artifact_sha256`**: software-computed lowercase 64-hex SHA-256 digest over the single canonical UTF-8 JSON encoding (`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`) of the exact submitted manifest object (`schema`, `slug`, `parent_revision`, `summary`, `scope`, `entrypoint`, `files`, `tests`, `declared_slots`, `declared_budgets`, `declared_risk_class`, `evidence_facts`), where `files` and `tests` are sorted lexicographically by POSIX `path` and `manifest.json` is reserved outside both tables. All software-assigned fields (`revision`, `published_in`, `session`, `artifact_sha256`, `eligibility_state`, and revocation metadata) are excluded from the hash input, so the gate at submission time and any downstream verifier reading the published `manifest.json` reproduce the identical digest.
- **Package pin**: any run package that enables a program pins the closed tuple `(repository_id, knowledge_version, commit, program_revision, artifact_sha256)`. A run's program pin never changes silently on a base change, live knowledge update, or operator restore.

### Multi-file repository layout

Under the proposed successor repository schema (`curator-knowledge/5`), each published program revision lives in two fixed subtrees alongside `knowledge.json`, `facts.jsonl`, `provenance.json`, and `coverage.json`:

| Path | Content and gate rules |
| --- | --- |
| `programs/<slug>/manifest.json` | Closed manifest (`curator-program/1` proposed). Submitted fields: `schema`, `slug`, `parent_revision`, `summary`, `scope`, `entrypoint`, `files`, `tests`, `declared_slots`, `declared_budgets`, `declared_risk_class`, `evidence_facts`. Software-assigned fields: `revision`, `published_in`, `session`, `artifact_sha256`, `eligibility_state`. Reserved outside `files` and `tests`. |
| `programs/<slug>/<relative-path>` | Multi-file program sources and static assets listed in `manifest.json` (`files`). Regular Git blobs (`100644`) only; safe relative POSIX paths; `manifest.json` forbidden here; no symlinks, submodules, `..`, or unlisted files. |
| `tests/<slug>/<relative-path>` | Curator-authored tests and recorded-frame fixtures listed in `manifest.json` (`tests`). Regular blobs (`100644`) only; safe relative POSIX paths; no unlisted files. |

- **Integrity and size bounds.** Every entry in `files` and `tests` carries `{path, sha256, bytes}` sorted lexicographically by `path`. The gate verifies exact file-set equality (excluding `programs/<slug>/manifest.json` from `files`), regular-blob mode, per-file and total byte limits, and exact SHA-256 digests before publication.
- **Scope.** Programs are game-level (`scope.game` matches the repository, plus optional declared run-wide axes that match the cited sessions' `context`). A world-bound program is refused unless a later design decision explicitly justifies world-scoped code.
- **Submission contract and test deletion rule.** Program mutations enter through the proposed `curator-submission/3` contract (extending `changes` with `add_program`, `revise_program`, and `revoke_program` operations). Curator-authored tests execute only inside the curator's sandbox or the gate's own sandbox—never in the custodian, publisher, or live player harness. In a `revise_program` change, deleting any test file present in `parent_revision` requires an explicit non-blank `deleted_tests` map (`path -> reason`) on that change object and is reported in gate diagnostics. Curator tests are self-checks, not an independent semantic oracle.
- **Base version.** Every submission carries `base_version` (`v<N>`); a stale base is rejected without mutation.

## Pre-qualification storage and eligibility

[ADR 009](../decisions/009-curated-player.md#interface-milestones-and-acceptance-ownership) left open whether an artifact may be stored in the repository before it passes semantic qualification. This brief freezes a strict separation between **storage eligibility** and **use eligibility** through a software-owned `eligibility_state` field (never curator-submitted):

| `eligibility_state` | Meaning | Exported in `delivered-knowledge/4`? | May a run package pin or start it? |
| --- | --- | --- | --- |
| `stored_ineligible` | Passed deterministic structural, manifest, sandbox-isolation, and curator self-test checks at the gate, but has not passed gate-owned qualification. | No (absent from delivered `programs` catalog). | No; refused at package preflight and runner start. |
| `probationary` | Passed gate-owned offline qualification checks on unexposed post-freeze traces (prerequisite under `#457`) and awaits post-publication trace scoring (`#469`). | Yes, in `programs` marked `probationary`. | Only in explicitly supervised runs with matching package pin. |
| `eligible` | Met post-publication probation scoring and non-regression criteria (`#469`). | Yes, in `programs` marked `eligible`. | Yes, with matching package pin. |
| `revoked` | Permanently disabled by a gate revocation record (operator or retirement rule). | No from `programs`; recorded in `revoked_programs` history. | No; refused for new pins and new invocations. |

- **Drafts vs. stored artifacts.** Unfinished work stays outside the repository in managed `drafts/<id>/` containers (`harness/curator/containers.py`). An artifact enters the repository as `stored_ineligible` only after deterministic structural validation, sandboxed self-test execution, and non-regression of repository invariants pass.
- **Qualification prerequisite.** Independent semantic qualification and post-freeze later-trace gating remain prerequisites under `#457` ([prospective curator gate](prospective-curator-gate.md)). Deterministic storage checks in `#465` alone establish `stored_ineligible` storage and isolated fixture execution—never `probationary` or `eligible` live qualification.

## Revocation semantics and effect on pinned runs

[ADR 009](../decisions/009-curated-player.md#interface-milestones-and-acceptance-ownership) left open what revoking a program does to a run that has already pinned it. Revocation, active input stop, and knowledge restore are three distinct mechanisms with non-overlapping effects:

1. **Eligibility revocation (`#457` gate operation).** Revocation targets an immutable `(program_revision, artifact_sha256)` pair and publishes a new monotonic repository tag `v<N+1>` recording the revocation reason and software provenance. Like reserved record IDs and session labels in `harness/curator/gate.py`, revocation is **monotonic across tagged history**: once a revision is revoked, no later tag or operator restore can un-revoke it.
2. **Effect on runs that already pinned the revoked revision.**
   - **No silent pin mutation.** A frozen package's `(program_revision, artifact_sha256)` pin never switches silently to another version.
   - **New runs / future admissions.** Package preflight refuses to freeze or launch a package pinning a revoked revision (`rejected: program_revoked`).
   - **Running admission, between invocations (authoritative pre-start check).** Enforcing revocation must not depend on optional live knowledge updates (`live_knowledge_updates` may be off, and under the [host contract](../contracts/player-host.md#a-newer-version-during-play) an actor may keep playing on an older adopted version). Before every `program_start`, the runner therefore checks the authoritative revocation state from the configured repository revocation source (or the frozen package's revocation snapshot in a disconnected run with no configured repository) independently of whether the actor adopted a newer knowledge update. If the target `program_revision` is revoked, the runner refuses `program_start` with `status: "rejected", reason: "program_revoked"`. If the configured revocation source is unreadable or its state cannot be established, the runner fails closed and refuses `program_start` with `status: "rejected", reason: "revocation_state_unknown"`.
   - **Running admission, in-flight invocation.** Revocation is a knowledge-repository data event and holds no computer custody. Stopping an already executing program invocation requires the active supervision stop/preemption path (`#467`/`#468`), which waits up to the declared batch-receipt bound and permanently stops automated input if the bound expires or delivery is partial or unknown under the [computer-control contract](../contracts/computer-control.md#native-channel).
3. **Operator knowledge restore (`harness/curator/gate.py` `restore`).** When the target snapshot differs from the current tip, restoring an earlier tag republishes that snapshot as a new version and invalidates `covered-prefix.json` (`restored: true`); when the target snapshot is byte-identical to the current tip, the gate returns `status: "unchanged"` with the current version and publishes no tag (`harness/curator/gate.py:221-228`). In either case, a restore is never delivered to a running actor, never stops in-flight input, and never clears any revocation recorded in compatible tagged history.

## Passive execution envelope

A program is a passive, single-step policy executed in an isolated sandbox with no filesystem I/O, no network access, bounded memory, and a per-step wall-time limit. It never runs inside the custodian, the gate publisher, or the live player host process. Every step exchanges closed JSON data (plus full-resolution frame bytes) across the runner boundary:

### Step input envelope (proposed `program-step-input/1`)

| Field | Rule |
| --- | --- |
| `schema` | Exact literal `"program-step-input/1"`. |
| `program_pin` | Closed `{slug, revision, artifact_sha256}` of the running artifact. |
| `step_index` | Nonnegative integer step counter (`0` on invocation start). |
| `frame` | Full-resolution player-visible frame (`source_id`, `width`, `height`, original PNG/pixel bytes). Never a resampled thumbnail crop like the retired `program-view/4`. |
| `objective` | Frozen run objective text matching what the actor receives. |
| `delivered_knowledge` | Read-only view of the run's pinned or adopted delivered knowledge (`version`, `commit`, `repository_id`, blinded `articles`, `facts`, `history`). Contains no raw world/lineage labels and no evaluator data. |
| `last_result` | `null` on step `0`, or the prior step's projected result (`player-computer-result/2` or bounded `slot_result` data). |
| `budget_remaining` | Invocation-local remaining steps and wall-time ceiling only. Never exposes experiment-wide countdowns, remaining run dollars, or final-actor policy ([player ports](../contracts/player-ports.md#mcp-projection-and-envelopes)). |
| `state` | Bounded opaque JSON-serializable state returned by the previous step (`null` on step `0`), reset per invocation. |

### Step output envelope (proposed `program-step-output/1`)

Each step returns a closed tagged union with `schema: "program-step-output/1"` and exactly one `kind`:

- **`kind: "actions"` (basic computer input + emissions).**
  - `actions`: `1..32` basic actions matching `action_schema()` in `harness/computer/protocol.py` and `harness/player_tools.py` (key, text, click, wait only; clicks cite `source_id` and original full-image coordinates; zero game-specific verbs).
  - `source_id`: frame `source_id` or `null` (required when `actions` includes a click).
  - `declared_risks`: list of exact length `len(actions)` giving `"low"` or `"high"` for each action `actions[i]` (advisory only; the runner treats any action as `"high"` unless the gate verified its risk class on recorded cases). Before dispatching any batch to computer control, the **runner** checks every action in the batch and **withholds dispatch** whenever any action is high-risk without prior approval—pausing for actor approval or yielding `high_risk_approval_needed` rather than relying on the program to yield voluntarily.
  - `emissions`: closed object requiring `intent` (non-blank single line, at most 512 characters) and optional `cites` (at most 16 unique IDs), matching `harness/player_tools.py`. Additional proposal fields (`expectation`, `goal`, `confidence`, `flags`) join only with the consumer work that reads them ([intent decision](../decisions/owner-decisions.md#tool-intent-required-and-cites-optional)).
  - `state`: updated bounded opaque JSON state.
- **`kind: "slot_request"` (runner-mediated model call; `#466` consumer).**
  - `slot`: slot name listed in `manifest.json` (`declared_slots`) and bound in the run package.
  - `request`: closed structured payload (frame or region reference plus bounded prompt/options; exact slot schema is owned by `#466`).
  - `emissions`: required `intent` and optional `cites`.
  - `state`: updated bounded opaque JSON state.
  - In `#465` passive-only execution before `#466` exists, any `slot_request` fails cleanly with `reason_code: "slot_unavailable"`.
- **`kind: "yield"` (explicit return of control to the actor).**
  - `reason_code`: closed enum of `"completed"`, `"precondition_failed"`, `"unrecognized_screen"`, `"high_risk_approval_needed"`, `"budget_exhausted"`, `"slot_unavailable"`, or `"error"`.
  - `detail`: bounded non-blank explanation (fallible data, never authority).
  - `emissions`: required `intent` and optional `cites` (and optional future fields when adopted).
  - `summary`: optional bounded progress summary handed to the actor.

### Runner-enforced failure and custody rules

- **Sandbox or schema violation.** Per-step timeout, memory breach, illegal I/O attempt, extra/missing envelope keys, mismatched `declared_risks` length, or an unsupported schema version aborts the invocation immediately (`status: "aborted"`) and returns control to the actor without silent retry.
- **Computer delivery uncertainty.** A partial or unknown delivery receipt during a program's action batch permanently stops automated input under the [computer-control contract](../contracts/computer-control.md#native-channel). The runner never downgrades partial or unknown delivery into a resumable `yield` or retries the batch.

## Refused versions and separation from dormant legacy `player-memory/2` hooks

Under [S-MIGRATION](../standards/migration.md), every reader and writer accepts an **exact allowlist of the one current schema version per format family** and refuses everything else—no compatibility shims, fallback loaders, or silent format upgrades. When `#465` migrates to `curator-knowledge/5`, `curator-submission/3`, `delivered-knowledge/4`, `curator-program/1`, `program-step-input/1`, and `program-step-output/1`:

- **Retired program and view families (all versions refused):** `player-program/*` (including `player-program/1` and `player-program/2`), `player-program-run/*`, and `program-view/*` (including `program-view/3` and `program-view/4`). `tests/test_player_view.py` already asserts that `actor_result` refuses `player-program/1` and `player-program-run/99` as `UnsupportedResult`.
- **Retired store and knowledge families (all non-current versions refused):** `player-memory/*` (`player-memory/2`), `player-record/*` (`player-record/1`), `curator-type/*` (`curator-type/2`), `curator-knowledge/1` through `curator-knowledge/4`, `curator-fact/1` through `curator-fact/4`, `curator-submission/1` through `curator-submission/2`, `delivered-knowledge/1` through `delivered-knowledge/3`, and `player-knowledge/1` through `player-knowledge/2`.
- **Active `curator-knowledge/4` guard (unchanged today):** Until that migration happens, `curator-knowledge/4` continues to reject any file under `programs/` or `tests/` beyond empty `.keep` placeholders (`harness/curator/gate.py:79-88`).

### Dormant legacy `player-memory/2` hooks in the current tree

Three read-only evidence/viewer paths still carry the word `programs` solely to read closed-archive `player-memory/2` runs:

| Location | Current role | Frozen boundary rule |
| --- | --- | --- |
| `harness/trace/memory_reader.py` | Read-only sealed-store reader for historical `player-memory/2` SQLite files (including their legacy `programs` table). | Sealed-evidence reader only; confers no authoring, storage, or execution capability. |
| `harness/evaluation/core/sources.py:188` | `MemoryFacts.programs: dict[str, dict]` (`schema = 'player-memory/2'`) for closed-archive evaluation reads. | Never reused, overloaded, or extended to carry ADR 009 curator-submitted programs. |
| `harness/viewer/views.py:416-441` and `/api/view/run/<run>/programs` (`harness/viewer/app.py:271`) | Projects legacy `player-memory/2` programs, `player_program_run` calls, and `program_save` events; returns `capability: "retired"` on current `player-journal/1` runs. | Must not be overloaded with ADR 009 program records. `#471` migrates program views cleanly under `S-MIGRATION` once real `#465`/`#467`/`#469` producers exist, showing missing data as absent or unknown. |

## Active fact-store dependencies and the asserter-field rule

A future program artifact relies on these exact fields of the active [curator contract](../contracts/curator.md) (`curator-knowledge/4`, `curator-fact/5`, `schemas/curator-fact.schema.json`) and its blinded delivery projection (`delivered-knowledge/3`, `harness/player/knowledge.py`, carried forward into `delivered-knowledge/4`):

- **Repository and provenance fields (`curator-knowledge/4`):** `knowledge.json` (`schema`, `game`), tag `v<N>`, 40-hex tag `commit`, `repository_id` (`v0` commit), `provenance.json` (`frames`, `sessions`, `branches`, `restores`, `last_admission`), and `coverage.json` (`curator-coverage/2`).
- **Fact and article fields (`curator-fact/5`):**
  - Identity and revision: `id`, article `slug` and revision `<slug>@v<N>`, `published_in`, `session`.
  - Epistemic indexing: `claim_kind` (`interface`, `mechanic`, `entity_property`, `instance_state`, `strategy`), `evidence_basis` (`observed`, `inferred`, `hinted`), `tags`, `text`, optional `subject`, optional `when` (`note`, `requires`).
  - Scope and citations: `scope` (open axis map with software-owned `game` and optional `world`), `lineages` (world-bound), `citations` (frame source IDs), `seen`, `valid_from`, `valid_to`.
  - Lifecycle and graph flags: `lifecycle_state` (`active`, `contested`, `superseded`, `retracted`, `ended`), `stale_citations`, `needs_review`, `links` (`depends_on`, `contradicts`, `part_of`, `see_also`), `superseded_by`, `retired`.
- **Delivered projection (`delivered-knowledge/3` -> `delivered-knowledge/4`):** Programs read delivered knowledge through the same blinded projection as the actor (`world: null`, `branch_relation`, `unverified_branch`, `condition_unverified`, `shadowed_by`, `contradicted_by`, and `history` maps), never receiving raw world or lineage labels.

**Asserter-field rule.** The active `curator-fact/5` table carries **no `asserter` field** because only one kind of asserter exists today: the curator (identified by `session`). That rule stays unchanged until a second kind of producer actually submits facts to the store under a distinct identity. Passive programs defined in this brief emit only actions, slot requests, and yields—never fact submissions—and a stop-only monitor need never assert a fact. Executing a program therefore does not by itself add an `asserter` field; if a later phase introduces a program or model-slot producer that asserts facts into the store alongside the curator, adding `asserter` belongs strictly to that coordinated migration, never speculatively ahead of it.

## Evidence standing: weak routine-recurrence evidence and no claim of need

Evidence for building induced programs remains weak across both external literature and local play records:

- **External benchmarks ([curated-programs research](../research-curated-programs.md)).** Self-generated skills scored below the no-skill baseline on all three configurations tested in SkillsBench (`-8.1` to `-11.5` percentage points); regressions cancelled `59%` of gross gains in The Regression Tax; only `15.6%` of induction turns passed execution verification in ASI, where a verified-text ablation outscored programs in memory. No read primary source tests induced program libraries on a real-time screenshot-only game.
- **Local play records.** In the sealed-trace sample recorded at ADR 009's evidence checkpoint, only one program existed (walking up 25 times, twice; [ADR 009](../decisions/009-curated-player.md#problem)). In subsequent live runs—including the [seven-day campaign (#896)](../acceptance/2026-11-22-seven-day-campaign-896.md) and the [bounded standard-build live validation (#963)](../acceptance/2026-11-25-wave3-wave4-live-validation-963.md) (`690` decisions, `$0.0051`/decision, `94.04%` prompt cache read share, `35 / 691` = `5.1%` of input batches containing any wait action)—direct actor play with curated articles and facts operated without programs, and no local measurement yet shows high-frequency, low-variance routine recurrence where program delegation would beat direct actor play at a matched failure rate.

**No claim of need.** This brief specifies the interface boundary only and authorizes no build, schema migration, or spend. It does not claim that the project needs programs now; it ensures that any future decision to test programs starts from a coherent, non-overlapping specification.

## Explicitly open choices (not decided here)

Following `#839`'s stop condition, these choices remain open and require their own design notes and owner decisions if the programs line is later opened:

- **Program language and sandboxed interpreter/runtime.** Whether passive policies run as a restricted Python subset, WebAssembly, or a declarative state-machine grammar is left open for `#465`.
- **Semantic oracle, post-freeze admission cohort, and counterfactual utility policy.** How the gate qualifies a program beyond deterministic structural checks and replay filtering remains open under `#457` ([prospective curator gate](prospective-curator-gate.md)) and `#469`.
- **Belief or uncertainty calculus.** Facts carry no belief value ([belief decision](../decisions/owner-decisions.md#no-belief-value-in-the-fact-store)); numerical belief comparison remains separate under `#677` ([belief-method comparison](belief-method-comparison.md)).
- **Capability slot taxonomy and binding calibration.** Exact slot signatures, caching keys, and two-binding escalation calibration belong to `#466`.
- **Asynchronous supervision preemption bounds and stop-only monitor anomaly rules.** Batch-boundary preemption latency bounds, frame-freshness cursors, and monitor anomaly calibration belong to `#467` and `#468`.
- **Practice-instance determinism and fork mechanics.** Remains deferred under the [practice decision](../decisions/owner-decisions.md#revisit-practice-for-program-trials-or-determinism) (`#472`).
