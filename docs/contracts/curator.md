---
owner: lead
review_trigger: A change to the knowledge repository layout, the fact, article or submission shapes, the gate checks or result, session inputs, validation, the draft lifecycle, close-out, restore or the grooming summary
status: active
---

# Curator contract

This contract states the formats and rules for curator sessions, validation, drafts,
publication, restore and grooming. The [curator component](../components/curator.md)
explains the responsibilities and shows the pipeline from trace to delivered knowledge.
[Curator hosts](../operations/curator-hosts.md) owns host configuration and procedures.
Terms are in the [glossary](../glossary.md).

| Format | Where | Written by |
| --- | --- | --- |
| [`curator-knowledge/5`](#knowledge-repository-curator-knowledge5) | `knowledge.json` | Repository initialization |
| [`curator-fact/6`](#facts-curator-fact6) | `facts.jsonl`: [facts](#facts-curator-fact6) and [articles](#articles) | Gate, from submissions |
| [`curator-submission/3`](#submissions-curator-submission3) | `submissions/<id>/submission.json` | Curator |
| [`curator-coverage/2`](#coverage-stamp-curator-coverage2) | `coverage.json` | Gate, from the session runner's stamp |
| [`curator-gate/2`](#gate-result-curator-gate2) | `gate.jsonl` | Gate |
| `container-manifest/1` | [Session](#session-close-out) and [draft](#drafts) manifests | Session runner |
| [`curator-boundary-grooming/2`](#boundary-grooming-summary-curator-boundary-grooming2) | `grooming-summary.json` | Boundary grooming command |

## Who decides what

The model decides what to record, how to word it, what to merge, narrow or retire, and
which tags and articles exist. Software writes provenance, sighting order, scopes bound to
the cited world, lifecycle flags and versions, and checks structure. No format or check
names a kind of thing in a game, under the [charter's](../charter.md) portability
constraint.

The gate reads references, scopes and shapes. It never judges whether a claim is true,
whether an unbound fact holds in every world, or whether article prose repeats one
world's detail. Facts are hypotheses that an actor is told to check cheaply before
relying on them.

## Knowledge repository (`curator-knowledge/5`)

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
| `knowledge.json` | Exactly `schema` (`curator-knowledge/5`) and `game` |
| `facts.jsonl` | Fact and article revision records, current and historical |
| `provenance.json` | [Frame positions, sparse `frame_clocks`, session labels, lineage edges and the last admission](#provenance) |
| `coverage.json` | The [coverage stamp](#coverage-stamp-curator-coverage2); present from the first publication of a submission |
| `programs/.keep`, `tests/.keep` | Empty placeholders; the gate refuses any other content there |

- **Versions.** Each publication is one commit on `main` and one tag `v<N>`. Tagging
  establishes publication, and the highest tag is the published version. Initialization
  writes `v0` with no records. Version tags `v0` through `v<N>` must be consecutive
  lightweight tags forming a single parent chain rooted at `v0` with no
  `refs/replace/*` overrides and valid Git object hashes; the gate verifies this
  commit and object chain on every history read.
- **Other formats.** Readers and writers refuse another repository or record schema with
  a message to start a new repository. There is no layout migration and no import;
  `curator-knowledge/4`, `ontology/types.json` and `curator-type/2` are retired.

### Provenance

`provenance.json` holds `frames`, `frame_clocks`, `sessions`, `branches`, `restores` and, after an
admission publishes, `last_admission`.

- **`frames`** maps a frame source ID to its position: `session`, `actor`, `step` and
  `order`. `order` is the triple of admission ordinal, actor directory and step. It
  compares sightings and says nothing about elapsed time. A frame keeps its recorded
  position; a new frame takes its earliest occurrence in the window.
- **`frame_clocks`** is a sparse map from a frame source ID to a verbatim non-blank HUD
  clock or brief visual phase label (1 to 64 printable UTF-8 characters). Uninterpreted
  by software, omitted when no clock or cue is visible, and immutable once recorded.
- **`sessions`** maps a sealed session ID (32 hexadecimal digits) to its directory
  `name`, `world`, `lineage`, `admission` and `context` (a map of declared run-wide
  axes, `{}` when none are declared). A frame source ID begins with its sealed session
  ID, so a citation identifies its own session.
- **`branches` and `restores`** record lineage fork edges and restore cuts when a world
  has multiple lineages or restored runs, so export computes inherited and unknown
  timeline states without exposing raw labels.
- **`last_admission`** holds the `coverage` stamp of the last admission publication and
  the `citations` accumulated across the published windows of that admission.

### Worlds, lineages and context axes

The operator chooses an opaque `world` label of 1 to 40 printable ASCII characters,
unique among the worlds of one game's repository, and freezes it in the run package
([decision on a separate world label](../decisions/owner-decisions.md#a-separate-world-label)).
A package that names a lineage must name a world, a world may stand without a lineage,
and several lineages may share a world. The package also declares a required top-level
`context` map (`{}` by default) of 0 to 8 run-wide invariant axes (`[a-z][a-z0-9_]{0,31}`,
never `game`, `world` or `lineage`, values 1 to 64 printable ASCII characters). Nothing compares
labels or axes with the game, so a consistent wrong declaration goes undetected.

The [trace projection](measurement-tools.md#trace-projection) verifies a session's
labels and `context`. A session without verified labels has no world and supports only
unbound facts.

The gate refuses a publication when any compatible tagged version, including one a
restore has since replaced, conflicts with the session labels:

- a sealed session ID recorded with a different name, world, lineage, admission or
  `context`;
- one directory name with two sealed IDs;
- one lineage and admission with two sealed IDs;
- one lineage with two worlds.

A session recorded with no world stays so.

## Facts (`curator-fact/6`)

A fact is one durable claim. The JSON Schema in
[`schemas/curator-fact.schema.json`](../../schemas/curator-fact.schema.json) closes its
stored shape. [World memory first](../decisions/owner-decisions.md#world-memory-first),
[free-text facts](../decisions/owner-decisions.md#free-text-facts-with-optional-subject),
the [knowledge graph and scoping decision](../decisions/owner-decisions.md#knowledge-graph-scoping-rfc-approved)
and the [frozen store-migration contract](../design/store-migration-contract.md)
govern the fields.

| Field | Written by | Rule |
| --- | --- | --- |
| `schema`, `record` | curator | `curator-fact/6` and `fact` |
| `id` | curator | Matches `[a-z0-9][a-z0-9-]{0,63}`; unused across compatible tagged history and disjoint from all `state_key`s |
| `statement_kind` | curator | Fixed kind: `observation`, `state`, `outcome`, `inference` or `synthesis` (Kinds 1–5; `synthesis` requires at least one `depends_on` link) |
| `state_key` | curator | Optional opaque kebab identifier matching `id`; required on `state`, optional on world-bound `synthesis`, forbidden elsewhere; shares the global namespace with IDs and slugs |
| `anchor` | curator | Optional same-world `state_key` on world-bound facts forming an acyclic parent forest |
| `depiction_source_id` | curator | Optional frame source ID that must belong to `citations` |
| `tags` | curator | 0 to 8 distinct hyphenated tags (`[a-z0-9]+(?:-[a-z0-9]+)*`, max 32 chars) |
| `text` | curator | Non-blank claim in the curator's words |
| `subject` | curator | Optional non-blank short name |
| `scope` | curator + software | Open axis map (1 to 8 keys). Software sets `game` and, when `binds: ["world"]`, `world` |
| `when` | curator | Optional non-blank UTF-8 condition string (omitted when unconditional) |
| `links` | curator | Distinct `{rel, target}` edges: `depends_on` (fact ID or `state_key`), `contradicts`, `part_of`, `see_also` |
| `citations` | curator | Non-empty distinct frame source IDs |
| `seen`, `valid_from`, `valid_to` | software | Sighting and end positions (`valid_to` is null until an `ended` retirement or single-timeline `changed` supersession sets it) |
| `lineages` | software | Lineages observed on cited frames (world-bound facts only) |
| `lifecycle_state` | software | `active`, `contested`, `superseded`, `retracted` or `ended` |
| `stale_citations`, `needs_review` | software | Fixed-point review flags propagated over two-strength `depends_on` and citations (stored `stale_citations` may record a lapsed `state_key`; delivered `stale_citations` names history record IDs only while `needs_review` still propagates) |
| `published_in`, `session` | software | Version and curator session that published it |
| `retagged` | software | Optional list of `{from, to, version}` tag reassignments |
| `superseded_by` + `superseded_reason` or `retired` | software | Replacement ID list and `superseded_reason` (`restated`, `narrowed`, `corrected`, `changed`; lifecycle is `superseded`, `retracted`, or `ended` for `changed`), or retirement record (`wrong` or `ended` events); mutually exclusive except per-lineage `ended` forks combining `changed` and `retired.events` with `valid_to: null` |

- **Submitted and stored scope differ.** A submitted `scope` names only curator-declared
  axes (never `game` or `world`); the curator binds a fact to the cited world with
  `binds: ["world"]`. Every `state` fact must bind `world` and carry `state_key`. Software fills
  `scope.game` from the repository and `scope.world` from the one world of every cited
  frame's session, refusing mixed worlds or unlabelled sessions. Declared non-`game`,
  non-`world` axes must match the cited sessions' `context`.
- **Keyed inertial fluents.** At most one active uncontested reading may hold per
  `(world, surviving timeline, state_key)`; simultaneous readings for one key require
  `contradicts` links (`contested`). `supersede_fact` with `reason_kind: "changed"` records
  a temporal transition on the same `state_key`, sets the prior reading to `lifecycle_state: "ended"`
  with `superseded_reason: "changed"`, and requires atomic repair of any citing current world
  article in the same submission.
- **Current records.** A record is current while its `lifecycle_state` is `active` or
  `contested`. `superseded`, `retracted` and `ended` records stay in `facts.jsonl` as
  evidence; `superseded` records always hold a non-empty `superseded_by` and `superseded_reason`.
- **Two-strength `depends_on` and acyclicity.** A `depends_on` reading pin (fact ID) follows
  verified 1-to-1 `restated` chains silently and invalidates on `changed`, `corrected`, `ended`,
  `retracted`, `narrowed`, N→1 merge, or `contested`; a `state_key` entity-existence pin stays
  quiet across `restated`, `changed`, and `contested` and invalidates only when no active or
  contested reading exists for that key on the surviving timeline. The effective `depends_on`
  graph on every surviving timeline must be acyclic.
- **Scope lattice and replacement.** Scope `A` is at least as general as `B` when every
  key-value pair of `A` is present in `B`. `supersede_fact` preserves the superseded
  facts' scope (and world); `narrow_fact` replaces one fact with two or more strictly
  narrower facts whose scopes refine the original. `retire_fact` with `reason_kind: "ended"`
  records observed `transition` or `absence` events with `end_citations` on a surviving
  segment of the fact's world.
- **Conflicts and shadowing.** A `contradicts` edge between comparable scopes at equal
  scope marks both `contested`; between strictly ordered scopes it is local shadowing,
  not a conflict.
- **No belief value.** A fact carries no probability, confidence or weight
  ([decision](../decisions/owner-decisions.md#no-belief-value-in-the-fact-store)).

## Articles

Facts are the unit of evidence and articles the unit of reading
([decision](../decisions/owner-decisions.md#curator-writes-articles-over-facts)).
Articles share `facts.jsonl` and `curator-fact/6`. Each article has a stable `slug`
across revisions; software assigns each revision ID `<slug>@v<N>`.

| Field | Written by | Rule |
| --- | --- | --- |
| `schema`, `record` | curator | `curator-fact/6` and `article` |
| `slug` | curator | Stable identifier (`[a-z0-9][a-z0-9-]{0,63}`); unique among current articles and disjoint from fact IDs and `state_key`s |
| `id` | software | `<slug>@v<N>` assigned on publication; facts, slugs and `state_key`s share one namespace |
| `title` | curator | Non-blank; unique among current articles |
| `lead` | curator | Non-blank summary an actor can act on |
| `body` | curator | Non-empty list of `{text, facts}` claims citing current facts compatible with `scope` |
| `tags` | curator | 0 to 8 distinct tags, counted alongside facts |
| `scope` | curator + software | Open axis map combining cited facts' scopes plus declared axes; unbound articles cite unbound facts, world-bound articles bind one world |
| `links` | curator | Distinct `{rel, target}` edges to facts, article slugs or `state_key`s (for `depends_on`) |
| `last_confirmed` | software | Latest `seen` among cited facts |
| `lifecycle_state`, `stale_citations`, `needs_review` | software | Fixed-point state and flags |
| `published_in`, `session`, `retagged`, `superseded_by`, `superseded_reason`, `retired` | software | Revision provenance; article `retired` carries `reason` and `reason_kind` (`wrong` or `editorial`) |

An article's stored scope combines the scopes of its cited facts with any declared
non-world axes: an unbound article cites unbound facts, and a world-bound article cites
facts of that one world or unbound facts. Every claim traces through a fact to a frame.

## Submissions (`curator-submission/3`)

A submission is a directory `submissions/<id>/` with one `submission.json` of at most
200 changes and 256 KiB, closed by
[`schemas/curator-submission.schema.json`](../../schemas/curator-submission.schema.json).

```json
{"schema": "curator-submission/3", "base_version": "v3", "summary": "…",
 "changes": [{"op": "add_fact", "fact": {"schema": "curator-fact/6", "record": "fact",
              "id": "f12", "statement_kind": "observation",
              "tags": ["doors"], "text": "…", "scope": {}, "links": [],
              "citations": ["00000000000000000000000000000001-1"]}}]}
```

The top level has exactly `schema`, `base_version`, `summary` (text) and `changes`
(non-empty), with optional `from_drafts` (draft IDs) and optional `frame_clocks`
(sparse map of in-window `frame_source_id` to verbatim clock/phase label). Software-owned fields and
unexpected keys are refused.

| Operation | Exact fields beyond `op` |
| --- | --- |
| `add_fact` | `fact` |
| `supersede_fact` | `ids` (distinct current fact IDs), `reason_kind` (`restated`, `corrected`, or `changed`), replacement `fact` |
| `narrow_fact` | current fact `id`, `facts` (two or more strictly narrower facts) |
| `retire_fact` | current `id`, `reason`, `reason_kind` (`wrong` with `citations`, or `ended` with `end`, `end_citations`, optional `citations`) |
| `add_article` | `article` (with `slug`) |
| `revise_article` | `slug` and one or more replacement fields (`title`, `lead`, `tags`, `links`, `scope`, `body`) |
| `edit_article` | `slug` and targeted patches (`set_title`, `set_lead`, `set_scope`, `add_claims`, `replace_claims`, `remove_claims`, `add_links`, `remove_links`, `add_tags`, `remove_tags`) |
| `remap_citations` | `from` (non-empty list of distinct fact IDs), `to` fact ID, `in` list of article slugs |
| `retire_article` | `slug`, `reason`, `reason_kind` (`wrong` or `editorial`) |
| `retag` | `assignments` (map of current fact ID or article slug to new tag list); grooming/hygiene only, at most once per submission |

- **Targets and one revision per slug.** Each fact target is changed at most once per
  submission. Article edits, revisions and `remap_citations` targeting the same `slug`
  compose within one submission and publish **at most one revision per slug per
  submission** (replacing the former one-change-per-target rule for articles); a tag-only
  `retag` updates the current revision in place without creating a new revision. Mixing
  `retire_article` with an edit or revision of the same `slug` is refused.
- **Minimal edits.** `replace_claims` and `remove_claims` require exact `index`,
  `old_text` and `old_facts` guards so stale patches fail cleanly.
- **Citations and carry-over.** A `restated` supersession may carry forward citations
  from the superseded facts (`citations` may be empty when unchanged); `corrected`
  requires non-empty new or trace citations. An `ended` retirement requires novel
  `end_citations` in the session trace (on a surviving segment for world-bound facts).

## Gate and pre-validation

The gate (`harness/curator/gate.py`) is the only writer of versions after
initialization. Pure structural and cross-record checks live in
[`harness/curator/check.py`](../../harness/curator/check.py), invoked both by the gate
and by the curator host's `validate_submission` tool via
[`harness/curator/validate.py`](../../harness/curator/validate.py). The gate executes
nothing a submission or repository contains and calls no model. Its controls address
[R-GAME-COUPLING and R-REGRESSION](../risks.md).

### Checks

Stages run in this order, and the first stage with a problem rejects the submission and
lists that stage's diagnostics:

1. **Well formed.** JSON Schema validation (`curator-submission/3`), exact fields and
   size limits.
2. **Base version.** `base_version` is the published version; otherwise the submission is
   stale.
3. **Candidate.** Operations apply together to a copy: targets are current, IDs and slugs
   are unused across compatible tagged history (including post-restore reservations),
   declared axes and world bindings match cited sessions, scope lattice and carry-over
   rules hold, `old_text`/`old_facts` guards match, and `retag` appears only in grooming.
4. **References, fixed point and filing.** Claims cite compatible current facts, links
   resolve to current records, titles and slugs are unique, and the lifecycle fixed point
   converges cleanly. Grooming files every current unbound fact in at least one current
   article (except facts narrowed out); an admission may leave facts unfiled.

`validate_submission` runs the same four stages inside the sandbox against the staged
workspace and `validation-context.json`, returning identical diagnostics and recording
each passing prefix's exact file paths and SHA-256 digests (`submission-validated` host
event).

The gate also validates the stored shape of every tagged version before applying a
submission, and the candidate tree before publishing. An incompatible history rejects
the submission.

### Publication

An accepted submission publishes in one commit and one tag, after discarding any
unpublished work in the tree. A publication writes `facts.jsonl`, `provenance.json` and
`coverage.json` together. If a failure leaves it unclear whether the tag exists, the
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
  `published_in`, session and citations. Record IDs, article slugs and session labels
  stay reserved across all compatible tags, including those absent from the restored tree.
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
| `knowledge/` | Published version without `.git`, `current-facts.jsonl` (current records only) and `validation-context.json` | No |
| `brief.md` | Software-written: window, declared axes, drafts, worklist, recent gate results and tag list | No |
| `grooming.md` | The grooming instructions, in grooming sessions | No |
| `workbench/` | Staged validator copy (`harness/curator`, `harness/trace`, `schemas` and `jsonschema` runtime) | No |
| `submissions/`, `drafts/`, `scratch/` | Proposals, open and stale drafts, temporary files | Yes |

Submission names, gate diagnostics and tags are `repr`-escaped in the brief, so they
cannot start a line.

### The tag list in the brief

[`type_usage.py`](../../harness/curator/type_usage.py) lists every tag used by at least
one current fact or article with its usage count, `df/N`, majority flag (`df > N/2`), and
tag-vs-scope overlap. Unused tags leave the list automatically; `statement_kind` is fixed
and needs no list. [`hygiene.py`](../../harness/curator/hygiene.py) supplies the per-world
`state_key` index in admission briefs and the deterministic advisory worklist (article-size
cutoff `8,192` UTF-8 bytes, bibliographic coupling, near-duplicate candidates, potential
contradictions, and key-alias candidates) in grooming and `hygiene` briefs.

- **Nearest tags.** A tag's words are its lower-cased alphanumeric tokens. Two tags are
  near when their shared words are at least 1/3 of all words of the two. At most 10 pairs
  are shown, closest first, then lexicographically.
- **Size.** Tag rows stop at 32,768 bytes, at a whole row, with a count of the rest.
  Pair rows stop when the list would pass 65,536 bytes. The host refuses a brief over
  262,144 bytes.

### Windows of decisions

A session reads whole admissions or a **window**: one actor of one sealed or staged
session, and a range of its steps (`seq` in `steps.jsonl`, first and last inclusive,
integers satisfying `1 ≤ first ≤ last` when restricted). A step is one computer
operation, and one model request can produce zero or more steps. Session and actor names
match `[A-Za-z0-9_-]+`. [`window.py`](../../harness/curator/window.py) narrows a whole
projection in place; the full window changes nothing.

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
| Trace | The supplied sessions or one window | Last admission's cited frames, steps, tool calls and actor boundary operations |
| Store | Current records in `current-facts.jsonl` and published tree | Current records in `current-facts.jsonl` and published tree |
| Instructions | Brief and [shared instructions](../../tools/curator_host/prompt.md) | Also [`grooming.md`](../../tools/curator_host/grooming.md) |
| Window | Full or restricted | Full only |
| `retag` | Refused | Allowed (at most once per submission) |
| Filing | May leave unbound facts unfiled | Files every current unbound fact |
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

### Boundary grooming summary (`curator-boundary-grooming/2`)

[Boundary grooming](../operations/curator-hosts.md#post-admission-boundary-grooming)
runs one grooming session on a live runner's repository against the sealed run of its
last published admission, and writes `grooming-summary.json`.

| Field | Value |
| --- | --- |
| `schema`, `run`, `knowledge_root` | `curator-boundary-grooming/2`, run directory name and repository root |
| `status` | `completed`, `failed` or `skipped` |
| `reason` | Null when completed; otherwise first failure found, or `no-published-admission` when skipped |
| `published_before`, `published_after` | Versions; `published_after` is null when unreadable |
| `stale_records` | Count of current records with non-empty `stale_citations` at `published_after`; null when unreadable |
| `cap_usd`, `cost_usd` | Session cap and cost. A skip reports cost `0` and no cap |
| `session_state`, `verdicts`, `proxy`, `sandbox` | From the session summary; absent from a skip |
| `summary` | Relative path of the session summary, or null |

A failure reason is the session error, `unresolved-result`, `proxy-unsettled`,
`proxy-revoked-or-breached`, `cap-reached`, `session-not-sealed`, `provider-error`,
`cleanup-unconfirmed`, `stale-citations-unreadable` or `stale-citations-remain`.
When a session stops on a local spend refusal or a provider error after earlier
validated submissions already published, `status` is `failed` while `published_after`
reflects the published version. A clean rejection that leaves no stale citations
completes.

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
not already aborted), then gates submissions in directory-name order, seals the record
and deletes the workspace.

- **Clean exit (`exit_code == 0`).** Gates all collected submissions in directory-name
  order and seals the session `sealed`.
- **Provider-error exit (`exit_code == 75`).** When the curator host stops on a provider
  or transport failure (`stop_reason: "provider-error"`), close-out reads the
  `submission-validated` events in `host-output.log` and gates **only** the longest
  contiguous prefix of collected submissions whose exact paths and SHA-256 digests match
  a passing `validate_submission` call (`all_passed: true`). Unvalidated or modified
  submissions are skipped. Drafts are kept without aging, and when no other close-out
  error occurs the session seals as `sealed` with `lifecycle.stopped: "provider-error"`.
- **Live runner rule for `provider-error`.** A single `provider-error` session that
  publishes at least one validated submission advances the cursor normally; one that
  publishes nothing retries the same window once without halving its width; an unexpected
  rejection does not advance the cursor; two consecutive `provider-error` sessions trip
  the runner's `SESSION_FAILURES = 2` stop limit.
- **Draft aging and gating order.** Because draft aging runs before gating on clean
  exits, a draft archived as `abandoned` on its sixth untouched session is no longer
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

- **Abort.** A crash, a breached limit or a handled failure (other than a clean
  `provider-error` exit `75`, which gates its validated prefix and seals with
  `lifecycle.stopped: "provider-error"`) seals the record as `aborted` where writable.
  An error before gating gates nothing. A later error cannot undo a publication already
  made.
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

The exporter selects every current record whose `scope` is satisfied by the package's
`world`, `lineage` and `context` (with no `world`-bound records when no world is named),
plus derived timeline history, sparse cited-frame `frame_clocks`, `anchor_display`, and aliases. The delivered `delivered-knowledge/4` file
contains no raw `world` or `lineage` label anywhere in its bytes, including coverage
stamps and aliased session identifiers.
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
| `harness/curator/gate.py`, `knowledge.py`, `check.py`, `validate.py` | Every repository format, JSON Schemas, pure validation, publication, history validation and restore |
| `harness/curator/session.py`, `type_usage.py`, `hygiene.py`, `containers.py` | Record schemas, tag usage, deterministic hygiene worklist, provenance, gate results, staged workbench, session and draft manifests |
| `harness/curator/window.py`, `harness/trace/projection.py` | Session labels, `context`, frame positions and coverage stamps, from `trace-projection/3` |
| `harness/curator/runner.py`, `tools/curator_host/live_runner.py` | Version tags, `last_admission` stamp, `provider-error` outcomes and gate results |
| `tools/curator_host/host.mjs`, `run.mjs`, `workspace-tools.mjs` | Curator host tool set (`validate_submission`), atomic writes and `provider-error` exit `75` |
| `tools/curator_host/shadow.py`, `groom.py` | Gate results, `curator-boundary-grooming/2` summaries and `last_admission` |
| `tools/curator_host/prompt.md`, `grooming.md` | Restate the `curator-submission/3` and `curator-fact/6` shapes to the curator |
| `tools/knowledge_export.py`, `tools/campaign_package.py` | Scoped selection, timeline history, blinding aliases, `delivered-knowledge/4` and `campaign-run/13` |
| `harness/player/`, `tools/player_host/` | Delivered `delivered-knowledge/4` validation, `player-knowledge/4` reads and compact query hits, ranking and projections |
| `tools/memory_screen_checks.py` | Fact and article records of every version |
| `harness/viewer/`, `tools/campaign_watch.py` | Gate results, close-out receipts, coverage stamps, `curator-boundary-grooming/2` and delivered snapshots |
