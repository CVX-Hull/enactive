---
owner: lead
review_trigger: A change to the knowledge repository layout, the fact, article, type or submission shapes, the gate checks or result, session inputs, the draft lifecycle, close-out, restore or the grooming summary
status: active
---

# Curator contract

This contract states the formats and rules for curator sessions, drafts, publication,
restore and grooming. The [curator component](../components/curator.md) explains the
responsibilities and shows the pipeline from trace to delivered knowledge.
[Curator hosts](../operations/curator-hosts.md) owns host configuration and procedures.
Terms are in the [glossary](../glossary.md).

| Format | Where | Written by |
| --- | --- | --- |
| [`curator-knowledge/3`](#knowledge-repository-curator-knowledge3) | `knowledge.json` | Repository initialization |
| [`curator-fact/4`](#facts-curator-fact4) | `facts.jsonl`: [facts](#facts-curator-fact4) and [articles](#articles) | Gate, from submissions |
| [`curator-type/2`](#types-curator-type2) | `ontology/types.json` | Gate, from submissions |
| [`curator-submission/1`](#submissions-curator-submission1) | `submissions/<id>/submission.json` | Curator |
| [`curator-coverage/2`](#coverage-stamp-curator-coverage2) | `coverage.json` | Gate, from the session runner's stamp |
| [`curator-gate/2`](#gate-result-curator-gate2) | `gate.jsonl` | Gate |
| `container-manifest/1` | [Session](#session-close-out) and [draft](#drafts) manifests | Session runner |
| [`curator-boundary-grooming/1`](#boundary-grooming-summary-curator-boundary-grooming1) | `grooming-summary.json` | Boundary grooming command |

## Who decides what

The model decides what to record, how to word it, what to merge or retire, and which
types and articles exist. Software writes provenance, sighting order and versions, and
checks structure. No format or check names a kind of thing in a game, under the
[charter's](../charter.md) portability constraint.

The gate reads references and shapes. It never judges whether a claim is true, whether
a `game` fact holds in every world, or whether article prose repeats one world's detail.
Facts are hypotheses that an actor is told to check cheaply before relying on them.

## Knowledge repository (`curator-knowledge/3`)

One Git repository per game lives under a project-local root, by default
`.runtime/knowledge/`
([decision](../decisions/owner-decisions.md#knowledge-repository-local-and-sealed-per-study)).

| Path | Holds |
| --- | --- |
| `<game>/` | The repository. Only the gate commits after initialization. |
| `<game>.state/sessions/<id>/` | One session's record: `manifest.json`, `brief.md`, host output, submissions and `close-out.json`. Kept after close. |
| `<game>.state/drafts/<id>/` | One draft: `manifest.json` and its files. |
| `<game>.state/drafts-archive/<id>/` | Promoted and abandoned drafts. |
| `<game>.state/workspaces/<id>/` | The session's workspace, deleted at close. |
| `<game>.state/gate.jsonl` | Gate results, in order. |
| `<game>.state/lock` | The exclusive lock a session or a restore holds. |

A published tree holds exactly these files:

| File | Content |
| --- | --- |
| `knowledge.json` | Exactly `schema` (`curator-knowledge/3`) and `game` |
| `facts.jsonl` | Fact and article records, current and historical |
| `ontology/types.json` | The current types |
| `provenance.json` | [Frame positions, session labels and the last admission](#provenance) |
| `coverage.json` | The [coverage stamp](#coverage-stamp-curator-coverage2); present from the first publication of a submission |
| `programs/.keep`, `tests/.keep` | Empty placeholders; the gate refuses any other content there |

- **Versions.** Each publication is one commit on `main` and one tag `v<N>`. Tagging
  establishes publication, and the highest tag is the published version. Initialization
  writes `v0` with no records or types.
- **Other formats.** Readers and writers refuse another repository or record schema with
  a message to start a new repository. There is no layout migration and no import.

### Provenance

`provenance.json` holds `frames`, `sessions` and, after an admission publishes,
`last_admission`.

- **`frames`** maps a frame source ID to its position: `session`, `actor`, `step` and
  `order`. `order` is the triple of admission ordinal, actor directory and step. It
  compares sightings and says nothing about elapsed time. A frame keeps its recorded
  position; a new frame takes its earliest occurrence in the window.
- **`sessions`** maps a sealed session ID (32 hexadecimal digits) to its directory
  `name`, `world`, `lineage` and `admission`. A frame source ID begins with its sealed
  session ID, so a citation identifies its own session.
- **`last_admission`** holds the `coverage` stamp of the last admission publication and
  the `citations` accumulated across the published windows of that admission.

### Worlds and lineages

The operator chooses an opaque `world` label of 1 to 40 printable ASCII characters,
unique among the worlds of one game's repository, and freezes it in the run package
([decision on a separate world label](../decisions/owner-decisions.md#a-separate-world-label)).
The operator assigns a distinct label to each world and reuses a label across lineages
only when they share that world; the exporter selects `world` facts by label equality.
A package that names a lineage must name a world, a world may stand without a lineage,
and several lineages may share a world. Nothing compares the label with the game, so a
consistent wrong label goes undetected.

The [trace projection](measurement-tools.md#trace-projection) verifies a session's
labels. A session without verified labels has no world and supports only `game` facts.

The gate refuses a publication when any compatible tagged version, including one a
restore has since replaced, conflicts with the session labels:

- a sealed session ID recorded with a different name, world, lineage or admission;
- one directory name with two sealed IDs;
- one lineage and admission with two sealed IDs;
- one lineage with two worlds.

A session recorded with no world stays so.

## Facts (`curator-fact/4`)

A fact is one durable claim.
[World memory first](../decisions/owner-decisions.md#world-memory-first) and
[free-text facts](../decisions/owner-decisions.md#free-text-facts-with-optional-subject)
govern the shape.

| Field | Written by | Rule |
| --- | --- | --- |
| `schema`, `record` | curator | `curator-fact/4` and `fact` |
| `id` | curator | Non-empty; unused by any record in the compatible tagged history |
| `type` | curator | A type that exists once the submission is applied |
| `text` | curator | Non-empty; the claim in the curator's words |
| `known` | curator | `observed` (the cited frames show it), `inferred` (concluded from them) or `hinted` (rests on a player hint visible in the cited steps). The gate checks the value only |
| `scope.game` | curator | The repository's game |
| `scope.level` | curator | `world` (true of the world it was seen in) or `game` (true in any world) |
| `scope.world` | software | On a `world` fact only: the one world of every cited frame's session |
| `citations` | curator | Non-empty, distinct frame source IDs |
| `subject` | curator | Optional non-empty short name |
| `seen` | software | Position of the latest cited frame by `order` |
| `published_in`, `session` | software | Version and curator session that published it |
| `retyped` | software | List of `{from, to, version}` type assignments |
| `superseded_by` or `retired` | software | Replacement ID, or `{reason, citations, published_in, session}`; never both |

- **Submitted and stored scope differ.** A submitted `scope` holds exactly `game` and
  `level`. A stored `world` fact also holds `world`. The gate refuses a `world` fact
  whose citations name two worlds or a session with no world.
- **Current records.** A record is current until it has `superseded_by` or `retired`.
  Historical records stay in `facts.jsonl` as evidence.
- **Replacing across scopes.** A replacement has the same level, and for a `world` fact
  the same world, as every fact it supersedes. A `world` fact is retired only with
  citations from its own world. No operation promotes a `world` fact to a `game` fact.
- **Game scope rests on the curator's word.** The gate asks for no evidence from a
  second world.
- **Time.** `seen` is the one stored time. No game clock or wall time is kept, so a
  fact's age in game time cannot be computed. Where time matters, `text` states it as
  the screen showed it.
- **No belief value.** A fact carries no belief, confidence or weight
  ([decision](../decisions/owner-decisions.md#no-belief-value-in-the-fact-store)).
- **Asserter.** Only a curator session submits facts, and `session` names it.

## Articles

Facts are the unit of evidence and articles the unit of reading
([decision](../decisions/owner-decisions.md#curator-writes-articles-over-facts)).
Articles share `facts.jsonl` and the `curator-fact/4` schema.

| Field | Written by | Rule |
| --- | --- | --- |
| `schema`, `record` | curator | `curator-fact/4` and `article` |
| `id` | curator | As for a fact; facts and articles share one set of IDs |
| `title` | curator | Non-empty; unique among current articles |
| `lead` | curator | Non-empty. The instructions ask for one or two sentences an actor can act on; the gate does not parse them |
| `body` | curator | Non-empty list of exactly `{text, facts}` claims; each `text` is a nonblank string and `facts` is a non-empty list of distinct current `game` fact IDs |
| `links` | curator | Distinct titles of other current articles; may be empty |
| `last_confirmed` | software | Latest `seen` among the cited facts |
| `published_in`, `session`, `superseded_by`, `retired` | software | As for a fact; an article's `retired` has empty `citations` |

An article that cites a `world` fact is refused at publication and at restore. `world`
facts stand alone. Every claim traces through a fact to a frame.

## Types (`curator-type/2`)

| Field | Written by | Rule |
| --- | --- | --- |
| `schema` | curator | `curator-type/2` |
| `name` | curator | Non-empty; unique in the ontology |
| `description` | curator | Text |
| `fields` | curator | List of strings; adds no keys to facts |
| `identity` | curator | Distinct names from `fields`, possibly empty, that say when two facts are about the same thing |
| `reason` | curator | Non-blank: why the type is needed and how it relates to existing types |
| `published_in` | software | Version that added the type or last wrote it by a revision |

- **Identity is guidance.** A fact has no typed values, so the gate cannot compare facts
  by identity.
- **Reason is stated, not judged.** The gate checks that it is not blank. A
  specialization is stated there; the format has no parent field.
- **Definitions stay recoverable.** Every fact a submission adds names a type that
  exists once the submission is applied, so the version in `published_in` holds the
  definition the fact was written under.

## Submissions (`curator-submission/1`)

A submission is a directory `submissions/<id>/` with one `submission.json` of at most
200 changes and 256 KiB.

```json
{"schema": "curator-submission/1", "base_version": "v3", "summary": "…",
 "changes": [{"op": "add_fact", "fact": {"schema": "curator-fact/4", "record": "fact", "id": "f12",
              "type": "relation", "text": "…", "known": "observed",
              "scope": {"game": "example", "level": "game"}, "citations": ["frame-id"]}}]}
```

The top level has exactly `schema`, `base_version`, `summary` (text) and `changes`
(non-empty), with optional `from_drafts` (draft IDs). The fields marked “software” in
the tables above are refused in a submission, as is any other unexpected field.

| Operation | Exact fields beyond `op` |
| --- | --- |
| `add_fact` | `fact` |
| `supersede_fact` | `ids` (one or more distinct current fact IDs), replacement `fact` |
| `retire_fact` | current `id`, non-empty `reason`, non-empty distinct `citations` |
| `add_type` | `type` |
| `add_article` | `article` |
| `revise_article` | current `id`, replacement `article` with a new ID |
| `retire_article` | current `id`, non-empty `reason` |
| `revise_types` | `action`, `names`, `types`, `assignments` (fact ID to new type name) |

- **Targets.** Each target is current and changed at most once per submission.
- **Citations.** A citation names a frame in the session's trace. In grooming, a
  replacement may also cite frames of the facts it supersedes. Retirement of a world
  fact may also cite that fact's own recorded frames.
- **Articles.** To split or merge articles, add the resulting articles and retire or
  revise their predecessors in one submission, repairing links and fact references.

### Type revisions

`revise_types` is accepted only in a grooming session, at most once per submission.

| Action | Existing `names` | New `types` |
| --- | --- | --- |
| `merge` | two or more | one |
| `split` | one | two or more |
| `rename` | one | one |
| `deprecate` | one | none |

- An assigned fact is current, has a type in `names` at the base version, and is neither
  retired nor superseded by the same submission.
- A submission that replaces a definition under a name the base version already had
  assigns every surviving fact of that name, even when the name does not change. This
  includes deprecating a type and adding one of the same name.
- Software appends `{from, to, version}` to the `retyped` list of each assigned fact.
- Every current fact ends with a type that exists.

## Gate v0

The gate is the only writer of versions after initialization. It executes nothing a
submission or the repository contains, and calls no model. Its structural controls
address [R-GAME-COUPLING and R-REGRESSION](../risks.md).

### Checks

Stages run in this order, and the first stage with a problem rejects the submission and
lists that stage's problems:

1. **Well formed.** Known schema and operations, exact fields, and the size limits.
2. **Base version.** `base_version` is the published version. Otherwise the submission
   is stale.
3. **Candidate.** The operations apply together to a copy. Types and targets exist, IDs
   are new, scopes match, and citations resolve.
4. **References and filing.** Claims cite current `game` facts, links name current
   articles, and current titles are unique. Grooming files every current `game` fact in
   at least one current article. An admission may leave facts unfiled.

The gate also validates the stored shape of every tagged version before it applies a
submission, and the candidate tree before it publishes. An incompatible history rejects
the submission.

### Publication

An accepted submission publishes in one commit and one tag, after discarding any
unpublished work in the tree. A publication writes the records, types, provenance and
coverage stamp together. If a failure leaves it unclear whether the tag exists, the
result is `unknown`; resolve it against tagged history before retrying.

### Gate result (`curator-gate/2`)

| Field | Value |
| --- | --- |
| `schema` | `curator-gate/2` |
| `operation` | `submission` or `restore` |
| `operation_id` | Software-generated; also in the publication commit's message |
| `status` | `published`, `rejected`, `unchanged` (restore only) or `unknown` |
| `base_version` | The submission's base or the restore's expected base; null when a submission names no valid one |
| `restored_from` | Restore target; null for a submission |
| `version` | Result version. Null when rejected; set when unknown only if the tag is established |
| `submission`, `session` | Submission directory and curator session; null for a restore |
| `from_drafts` | Draft IDs the submission names; empty for a restore |
| `diagnostics` | List of strings |

Only a published submission promotes drafts. The last ten results appear in the next
session's brief. An unsupported row in an active `gate.jsonl` blocks submissions,
restores and session starts. Continue from a fresh state directory with the same
compatible Git history and all its tags, and keep the old journal and sessions as
evidence.

## Operator restore

An operator publishes a previously published, compatible snapshot as a new version:

```sh
python -m harness.curator.gate restore ROOT --game GAME --expected-base VERSION --target VERSION
```

- **Checks.** The gate takes the session lock, validates the tagged history, and
  requires the expected base to be current and the target to be a tag.
- **Effect.** It publishes the exact target tree as a new, higher version and removes
  files absent at the target, such as `coverage.json` at `v0`. A target identical to the
  current tree returns `unchanged` and creates no tag.
- **What is kept.** Restored records keep their original `seen`, `last_confirmed`,
  `published_in`, session and citations. Record IDs and session labels stay reserved
  across all compatible tags, including those absent from the restored tree.
- **Reporting.** The commit names the operation, base and target. A reporting failure
  after tagging leaves the restore published, even when the result is `unknown`.

Frozen packages keep their version and digest. A running actor receives no restored
version, and a restore [invalidates the covered prefix](../components/curator.md#delivery-to-a-running-actor).

## Sessions

One session runs at a time per repository, under an exclusive lock. The host runs in the
[curator sandbox](../research-curator-sandbox.md). A session is an `admission` session,
which extracts knowledge from a trace, or a `grooming` session, which reorganizes the
store.

### Workspace

| Path | Holds | Writable |
| --- | --- | --- |
| `trace/` | The [trace projection](measurement-tools.md#trace-projection), narrowed to the session's window | No |
| `knowledge/` | The published version without `.git`, plus `current-facts.jsonl` with only current facts and articles | No |
| `brief.md` | Software-written: the window, drafts, recent gate results and type list | No |
| `grooming.md` | The grooming instructions, in grooming sessions | No |
| `workbench/` | A copy of `harness/trace` | No |
| `submissions/`, `drafts/`, `scratch/` | Proposals, open and stale drafts, temporary files | Yes |

Submission names, gate diagnostics, and type names and fields are `repr`-escaped in the
brief, so they cannot start a line.

### The type list in the brief

[`type_usage.py`](../../harness/curator/type_usage.py) lists each published type with its
fields and its count of current facts, and flags a type with none as unused. The brief
asks the curator to check the list before any `add_type`. The list is advice: the gate
does not check the choice of type.

- **Nearest types.** A type's words are the distinct lower-cased runs of letters and
  digits in its name and field names. Two types are near when their shared words are at
  least 1/3 of all the words of the two. At most 10 pairs are shown, closest first, then
  by first and second name.
- **Size.** Type rows stop at 32,768 bytes, at a whole row, with a count of the rest.
  Pair rows stop when the list would pass 65,536 bytes. The host refuses a brief over
  262,144 bytes.

### Windows of decisions

A session reads whole admissions or a **window**: one actor of one sealed or staged
session, and a range of its steps (`seq` in `steps.jsonl`, first and last inclusive,
integers satisfying `1 ≤ first ≤ last` when restricted). A
step is one computer operation, and one model request can produce zero or more steps.
Session and actor names match `[A-Za-z0-9_-]+`.
[`window.py`](../../harness/curator/window.py) narrows a whole projection in place; the
full window changes nothing.

- **Kept.** The steps in range, their frames and tool calls, and the actor's received
  prompt and guide. A call belongs to the step its result names; a call that names none
  belongs to the step of the next call that does, or to the last step.
- **Dropped.** Other actors, handoff packets, the memory and journal stores and the
  actor's final report, because each reports beyond the range.
- **Recorded.** `trace/manifest.json` gains `window` (session, actor, first, last as
  clamped, `steps_available`) and what was dropped, and its hashes are of the narrowed
  trace.
- **Refused.** A window that starts after the actor's last step aborts the session
  before the host runs. The gate refuses a citation of a frame outside the range.

### Coverage stamp (`curator-coverage/2`)

The session runner derives the stamp from the window, and the gate writes it with each
version. It has exactly `schema`, `session`, `actor` and `last_step`. A whole-admission
session stamps its comma-joined session names with null `actor` and `last_step`. A
submission that carries `coverage` is refused.

A stamp describes one window. The [component](../components/curator.md#publication-and-coverage)
defines the covered prefix that joins them. During a live run, the curator runner writes
that unbroken covered prefix (and `restored: true` when a restore replaces the tip) to
`covered-prefix.json` (`curator-covered-prefix/1`), and the campaign driver converts each
verified prefix or restore invalidation into a `coverage-update-entry/1` record on the
player host's `--knowledge-updates` list, where `restored: true` withholds further
coverage-gated cuts for the run ([player-host coverage updates](player-host.md#a-newer-version-during-play)).

### Admission and grooming

| Rule | Admission session | Grooming session |
| --- | --- | --- |
| Trace | The supplied sessions or one window | The last admission's cited frames, their steps and tool calls, and the first and last framed operations of each actor |
| Store | Current records in `current-facts.jsonl` and the published export | Current records in `current-facts.jsonl` and the published export |
| Instructions | Brief and [shared instructions](../../tools/curator_host/prompt.md) | Also its own [`grooming.md`](../../tools/curator_host/grooming.md) |
| Window | Full or restricted | Full only |
| `revise_types` | Refused | Allowed |
| Filing | May leave `game` facts unfiled | Files every current `game` fact |
| Coverage stamp | From its own window | The last admission's stamp, retained |

- **Grooming inputs.** The host passes `SessionConfig.grooming_brief`; the session
  copies it into the workspace and records its contents and SHA-256. A missing path, a
  restricted window, a trace other than the last published admission, or a retained
  citation absent from that trace stops the session before the host starts.
- **Inherited citations.** A grooming replacement may cite the union of the superseded
  facts' citations and the session's frames. A world fact retirement may cite that
  fact's recorded citations and session frames from its own world. Citations of unrelated
  facts do not qualify. Software takes inherited positions from recorded provenance.
- **Growth.** Grooming addresses the store's growth, and the store has no hard cap
  ([decision](../decisions/owner-decisions.md#groom-the-store-between-admissions)).
  Submission and host resource limits still apply.

### Boundary grooming summary (`curator-boundary-grooming/1`)

[Boundary grooming](../operations/curator-hosts.md#post-admission-boundary-grooming)
runs one grooming session on a live runner's repository against the sealed run of its
last published admission, and writes `grooming-summary.json`.

| Field | Value |
| --- | --- |
| `schema`, `run`, `knowledge_root` | Format, run directory name and repository root |
| `status` | `completed`, `failed` or `skipped` |
| `reason` | Null when completed; otherwise the first failure found, or `no-published-admission` when skipped |
| `published_before`, `published_after` | Versions; `published_after` is null when it cannot be read |
| `cap_usd`, `cost_usd` | Session cap and cost. A skip reports cost `0` and no cap |
| `session_state`, `verdicts`, `proxy`, `sandbox` | From the session summary; absent from a skip |
| `summary` | Relative path of the session summary, or null |

A failure reason is the session error, `unresolved-result`, `proxy-unsettled`,
`proxy-revoked-or-breached`, `cap-reached`, `session-not-sealed` or
`cleanup-unconfirmed`. When a session stops on a local spend refusal after earlier
submissions already sealed and published, `status` is `failed` with reason
`cap-reached` while `published_after` still reflects the published version. A clean
rejection that leaves the version unchanged completes.

## Drafts

A draft is a container (`container-manifest/1`, kind `draft`) the curator carries
between sessions.

| State | Entered when |
| --- | --- |
| `open` | A session creates it or writes to it |
| `stale` | Three sessions have passed without a write |
| `abandoned` | Three more untouched sessions have passed; the draft is archived |
| `promoted` | A submission that names an active draft in `from_drafts` publishes; the draft is archived |

A draft ID matches `[a-z0-9][a-z0-9-]{0,63}`, and an archived ID is not reused. A session
already aborted before draft collection keeps its drafts and ages none.

## Session close-out

When a sandbox result is available and reports no surviving process, the session runner
collects `submissions/`, then collects `drafts/` and ages untouched active drafts (when
not already aborted), then gates submissions in directory-name order after a clean exit
(promoting each `from_drafts` ID still present in the active store when a `submission`
publishes), seals the record and deletes the workspace. Because draft aging runs before
gating, a draft archived as `abandoned` on its sixth untouched session is no longer
active for promotion, and a gating or later close-out error that marks the session
`aborted` does not undo draft aging already recorded. Gating stops at an `unknown`
result or a close-out error. Without a result it collects nothing, and exit and
survivors are recorded as null.

### Collection follows no link

The host could replace a directory with a link, and a process that escaped the stop
could still be writing. Every collected tree is therefore opened component by component
relative to its parent's descriptor with `O_NOFOLLOW` and checked with `fstat`.

- A writable directory that is no longer a plain directory is not collected.
- A draft that is, or holds, a link or a special file is refused.
- A link, special file or limit breach under `submissions/` stops all gating for the
  session.
- A tree over its limit is refused whole: 4 MiB for a draft, 16 MiB for all submissions
  together, and 10,000 entries for any tree. Each refusal is listed in the record.

### Abort and interruption

- **Abort.** A crash, a breached limit or a handled failure seals the record as
  `aborted` where it is writable. An error before gating gates nothing. A later error
  cannot undo a publication already made.
- **Drafts.** After an observed unclean exit, collectable drafts are kept without aging.
- **Cleanup.** Removing the workspace clears file flags and permissions first. A removal
  failure is written to `cleanup-failed.json`, and the lock is released.
- **Interruption.** An interruption during preparation or execution attempts an aborted
  close-out, gates nothing without a clean result, and re-raises. Sandbox cleanup failures
  are kept in the record's errors. If that close-out fails, `close-out-failed.json`
  retains the error category where writable.
- **Limits.** A second interruption, a hard kill or an unwritable record can prevent a
  terminal record. Interruption during later gating is outside this guarantee.

Proxy shutdown and unsettled accounting are separate
[host guards](../operations/curator-hosts.md).

## Delivery boundary

The exporter selects every current `game` fact and article and the current `world` facts
of one world, or no `world` facts when no world is named. The delivered
`delivered-knowledge/2` file does not name the world.
[Delivered knowledge and recall](player-host.md#delivered-knowledge-and-recall) owns the
delivered format and its preflight checks,
[freezing delivered knowledge](../operations/campaign-run.md#freeze-delivered-knowledge)
owns the procedure, and the
[withholding study contract](withholding-study.md) owns study draws. How judges measure
use is in [measurement tools](measurement-tools.md#adjudication-and-the-standing-use-measures).

## Readers that change together

A change to a format here migrates its readers and writers in the same change
([S-MIGRATION](../standards/migration.md)).

| Code | Reads or writes |
| --- | --- |
| `harness/curator/gate.py`, `knowledge.py` | Every repository format, at publication, history validation and restore |
| `harness/curator/session.py`, `type_usage.py`, `containers.py` | Record and type schemas, provenance, gate results, session and draft manifests |
| `harness/curator/window.py`, `harness/trace/projection.py` | Session labels, frame positions and coverage stamps, from `trace-projection/3` |
| `harness/curator/runner.py`, `tools/curator_host/live_runner.py` | Version tags, the stamp in each version's `last_admission`, and gate results |
| `tools/curator_host/shadow.py`, `groom.py` | Gate results and, for grooming, `last_admission` |
| `tools/curator_host/prompt.md`, `grooming.md` | Restate the submission shapes to the curator |
| `tools/knowledge_export.py` | Current facts and articles, with their scope |
| `tools/memory_screen_checks.py` | Fact and article records of every version |
| `harness/viewer/curator.py` | Gate results, close-out receipts and coverage stamps |

The player, player host and knowledge view read only the delivered file.
