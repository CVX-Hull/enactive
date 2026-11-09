---
owner: lead
status: historical
date: '2026-11-08'
scope: 'Accepted simplification of delivery, controls, CI, documentation, evidence storage and local resources after the 8 November 2026 audit (#498); delivered in #506-#512'
---

# ADR 010 — Streamlined delivery: one home per fact, controls that earn their keep

**Status: adopted, 8 November 2026.** The owner asked for a plan to streamline the
process and make the project pristine, and for no second copies kept without a reason.
The owner accepted this direction and settled its four questions the same day
([owner decisions](#owner-decisions-8-november-2026)). All seven leaves landed; the
current standards, workflows and controls page now carry its rules, and the
[outcome record](../acceptance/2026-11-08-streamlined-delivery-010.md) holds the measured
results and deviations. This page is the decision's rationale.

## Context: what the audit found

Six independent read-only reviews on 8 November 2026 covered code, documentation,
controls and gates, data storage, delivery history and setup, at main `4c8809a`. A
seventh reviewed this proposal. The lead checked the figures below against the files,
Git history and GitHub's run records; the method is given where a figure is derived.

**What is sound and stays.** Code follows [S-MIGRATION](../standards/migration.md): no
reader accepts an old version. `harness/computer`, `player`, `trace` and `curator` carry
no game semantics ([ADR006](006-computer-control-boundary.md)). Git identity,
credentials and project-local installs follow AGENTS.md. The full regression lane has
caught defects that focused selection missed. Import Linter is cheap and its negative
fixtures test our configuration. The evidence store's design (tracked manifests,
read-only payloads) is right. Main's ruleset (strict up-to-date status checks, squash
only, a required `controller` check from the Actions app, no bypass actors) is sound.

**Where effort goes without return.**

| Area | Finding |
| --- | --- |
| Controls | The control registry (`docs/control-registry.json`, 885 lines), its schema (253 lines), the generated [controls map](../controls.md) (350 lines), lifecycle code in `tools/governance.py` and `tests/test_governance.py` (412 lines) mainly check each other. No commit shows the registry lifecycle, map freshness, the evidence-id list or the diagram render catching a defect. The standard→control mapping is kept three times ([engineering](../engineering.md), registry, generated map), and the map has drifted: it says eight Import Linter contracts; `pyproject.toml` has eleven. All 11 controls fall due on 2027-01-15; strict profiles then fail every run (`tools/governance.py:96-98`) until dates are bumped. |
| CI | Full run 42545820618 took 501 s: the power-simulation test 267 s, the adapter suite 190 s, three browser suites 150 s run after pytest, and a diagram render whose output is discarded 32 s. Of the last 20 main pushes, 12 changed code and 10 of those reran the full suite, because every path under `tools/` counts as validation context (`tools/ci.py:92`). About 60 lines of `tools/ci.py` prove when the reduced main profile may run. |
| Delivery | Of the last 60 squash merges on main, 24 changed only documentation and 36 touched an ADR, a dated acceptance record or the work map (`git diff-tree` per commit, 6–8 November). A leaf needs about 10–15 Project edits: six statuses, four planning fields, two hand-kept dates and reconciliation sweeps, for one maintainer. |
| Documentation | `docs/` holds 747 tracked files. [Work](../work.md) and the [overview](../overview.md) restate results that dated records own, and [ADR 009](009-curated-player.md) is accumulating a status log. One authority rule is written three times (documentation.md, standards/authority.md, workflows/authority.md). 24 superseded contracts are kept so that old links resolve, but only 4 pages, all historical, link to them. 112 historical records still carry a `review_trigger`. Design and research pages have no row in the [documentation map](../documentation.md). |
| Evidence and data | The store is the only copy of 2.35 GB that 31 records rest on (owner decision, 7 November 2026), and `tools.evidence verify` reports a missing store as "not present", the same as on a fresh clone (`tools/evidence.py:209-211`). The #454 curator-shadow evidence is unsealed. The closed evidence-id list forced a 45-line schema file that nothing validates against, while five data files declare no schema although [S-EVIDENCE](../standards/evidence.md) says they must. |
| Local resources | 17 worktrees (5.4 GB) and 86 local branches had accumulated, almost all merged. The documents name three worktree roots and give no cleanup step. `.gitignore`'s `node_modules/` misses the symlinks worktrees use. |
| Code | Small strict-JSON, canonical-dump and file-hash helpers are copied three to five times. Two finished study scripts remain in `tools/`. Hard-coded game vitals in `harness/viewer/views.py` and `web/app/supervise.js` are missing from the coupling table in [architecture](../architecture.md). Provider tables live in `harness/curator/proxy.py`, including one provider no host uses; the host-neutrality rule (`tests/test_host_neutrality.py`) covers player hosts and coding agents but not providers or models. |

The stale worktrees, merged branches and duplicate copies were removed with the
owner's approval before this proposal; L3's dated record lists them.

## Principles of the change

1. **One home per fact.** Git owns source history, GitHub owns live status and
   timestamps, dated records own results, ADRs own decisions, standards own rules.
   Any other place links; it does not restate. A generated or retained copy needs a
   named reader that cannot use the original.
2. **A control exists to stop a named failure more cheaply than the failure costs.**
   Each control states that failure and where it is enforced. A control that only
   checks another control, or a document's bookkeeping, is removed.
3. **Process fits one maintainer and at most two workers.** States, fields and records
   are kept only where a decision reads them.
4. **Current pages describe the current system; they are not changelogs.** A current
   page says what is true and how to use it, not what changed, when, or what it
   replaced. Change history lives in Git and PRs, results in dated records, decisions
   in ADRs. A page records history only when that is its declared purpose, as a dated
   record, an ADR or the acceptance index is.
5. **The boundaries that matter do not weaken.** S-MIGRATION's one-current-contract
   rule, the ADR006 and [ADR008](008-evaluation-and-spectator.md) boundaries, evidence
   sealing, independent review of boundary and outcome changes, full regression before
   merging code, identity checks and project-local installs are unchanged. Where a
   leaf amends a standard's text, the leaf names the passage.

## Decisions by area

### Delivery and work tracking

- **Statuses:** Backlog, Ready, In progress, Done. Review and validation state lives on
  the PR (draft, checks, review comments). [S-WORK](../standards/work.md)'s status list
  and the WIP rules in [work items](../workflows/work-items.md) are rewritten to match;
  no tool reads the Project values, so this is a documentation and Project change only.
- **Fields:** Priority on every leaf; Horizon only on `outcome` issues. Size and
  Confidence are dropped; an estimate goes in the Ready brief when it helps a decision.
- **Dates and cycle time:** no hand-kept dates. Cycle time is measured from GitHub's
  own timestamps, PR opened to merged and issue opened to closed; the In progress start
  is no longer recorded.
- **Ready brief:** five lines: problem, acceptance, owner and owned paths, stop
  condition, owner decisions needed. Reconcile the Project when selecting work, not at
  every checkpoint.
- **Records travel with their change.** The record, ADR line and work-map line a
  change causes land in its PR. Outcome records produced after merge (native,
  gameplay or study results) remain their own change. A docs-only PR is for
  documentation work itself, not a status note.
- **Unchanged:** [review by decision and risk](../workflows/review.md); `Refs #N` and
  the empty `closingIssuesReferences` check before merge (it guards #75); the lead
  merges under the [standing delegation](../operator-permissions.md#engineering-decision-and-merge-delegation).

### Controls

- Replace the registry, its schema, the generator and the lifecycle and calendar checks
  in `tools/governance.py` with a hand-written [controls page](../controls.md): one row
  per control giving the failure it stops, where it is enforced, and its known gap,
  naming main's ruleset for the merge guarantee. Standards link to it; engineering.md
  no longer mirrors the mapping.
- **Kept:** the full regression suite; Import Linter with its negative fixtures; Ruff;
  document front matter and link checks; the acceptance-manifest checks and the
  charter/standard identifier checks now in `tools/governance.py`; `tools.evidence
  verify`; the host-neutrality scan; the closing-reference check.
- **Removed:** the registry lifecycle and 90-day dates; the generated-map freshness
  check; the closed evidence-id list and the schema it forced; the separate compile
  step (Ruff `E9` covers it); the duplicate link-check and argv-mirroring tests; the
  unused `assurance_governance` marker.
- A control is reviewed when it fails, is bypassed or costs more than expected, in the
  issue that changes it, not on a calendar.

### CI

- **PR runs:** the full suite on any code change, as now. The browser suites, the
  adapter suite and the power-simulation test each run in their own parallel lane, so
  the slowest lane, not the sum, sets the wall time. The power test keeps reproducing
  the frozen pre-registered output on every run; speeding up the simulation itself is
  in scope. Expected full run: about 300 s, to be measured.
- **Main pushes:** the fast checks only, without npm or browser installs. Strict
  up-to-date protection makes the PR head contain main's tip and serializes merges, so
  a squash leaves main with exactly the tree the PR's full run tested. The main-smoke
  eligibility proof in `tools/ci.py` and its tests are removed. "Merged-main validation"
  in [development](../workflows/development.md), work items, S-WORK and campaign
  admission is redefined as that PR run plus main's fast checks.
- **Timing tests:** the 50 ms policy-step budget becomes injectable, so tests that do
  not test timing do not depend on runner speed.

### Documentation

- Work is navigation: the selected outcome, links to its issues and the generated
  acceptance index. No result tables or dated narrative. The overview states current
  capability and links records; ADRs state decisions and link records for outcomes.
- Current pages lose their change narration ("now", "no longer", "replaced", "since",
  dated "on … we" paragraphs): the dated narrative in environment.md and the removal
  history in evidence cleanup move to dated records, and a page keeps only the rule
  and a link. The documentation standard states the rule (principle 4); review checks
  it, since no lexical scan can tell narration from a dated record's purpose.
- One authority statement, in the documentation map; standards/authority.md and
  workflows/authority.md shrink to links or go.
- The 24 superseded contracts and the anchor stubs in protocol.md and architecture.md
  are deleted. S-MIGRATION's "historical reports remain immutable evidence" and the
  documentation map's lifecycle section are amended to allow link-only maintenance of
  historical records, content unchanged; the 4 linking records then point to commit
  permalinks.
- Historical records need no `review_trigger`; the metadata check stops requiring it
  and new records omit it. Existing records are not edited for this.
- The map gains rows for `design/` and the research pages; superseded research is
  marked historical. `docs/changes/` is frozen with an index note.
- Diagrams render natively on GitHub ([owner decision 1](#owner-decisions-8-november-2026)).
  Orphan diagrams with no host page are removed.

### Evidence and data

- `tools.evidence verify` fails when the store is expected but absent. The first seal on
  a machine records that expectation in the repository's local Git configuration,
  which survives the loss of `.runtime` and is absent on a fresh clone or CI.
- Seal the #454 curator-shadow runs and knowledge repository now, citing their records.
- A tracked file under `data/` is either validated against a schema under `schemas/`
  by a test, or named, by path or directory, by code or a test that reads it; the
  document check fails on any other. Dated record assets are defined by their record.
  This replaces the closed evidence-id list, and S-EVIDENCE's schema sentence is
  amended to match.
- `docs/environment.md` lists every `.runtime` entry with its owner and lifecycle.
- One dated retirement record lists the 8 November removals (worktrees, branches, the
  #397 originals after their hash match against the sealed study, duplicates and unused
  downloads) and the archive kept. [Evidence cleanup](../operations/evidence-cleanup.md)
  keeps the procedure, not a history of removals.
- The store stays the only copy ([owner decision 2](#owner-decisions-8-november-2026)).

### Local resources

- One worktree root, `.runtime/worktrees/<leaf>`. A worktree installs its own
  dependencies with `npm ci`; it may link the main `.venv` only if the leaf leaves the
  Python lockfile unchanged. Removing the worktree and local branch is part of Done,
  after `git status` shows nothing uncommitted.
- `.gitignore` uses `node_modules` and `.venv` without the trailing slash, so links are
  ignored too. `fetch.prune` is set in the local configuration (done).

### Code

- One small neutral module for strict JSON decoding, canonical dumps and file hashing,
  used by computer, player, evaluation and tools, within the Import Linter contracts.
- Remove the finished study scripts `tools/diff_cost.py` and `tools/phash_measure.py`;
  their records keep the commit. `tools/probe_validation.py` and `probe_timeline.py`
  stay while P1 uses them.
- Add the viewer's and spectator page's game vitals to the coupling table, or have the
  binding supply them.
- The sandbox profile is written under the session's state directory, not the system
  temporary directory. Fix the stale `harness/__init__.py` docstring.
- Extend the host-neutrality rule to provider and model names in `harness/` and in
  `tools/` outside the adapter directories, keeping its current allowlist. Research
  pages, ADRs, dated records and `data/` are exempt, because S-EVIDENCE requires
  provider facts to be cited from dated sources. The provider tables move from
  `harness/curator/proxy.py` into the curator host, the provider no host uses is
  removed, and the shadow-session tool moves under the curator host.

## Leaves

Each leaf is one PR. At most two run at once in separate worktrees; the lead integrates.

| Leaf | Scope | Done when |
| --- | --- | --- |
| L1 CI and safety | Calendar failure removed; missing-store error; parallel lanes; fast checks on main; redefined merged-main validation; injectable step budget; the tautological assertion in `tests/test_p1_analysis.py` | Full CI measured; main push under 2 minutes; a removed store fails verify locally and a fresh clone does not |
| L2 Controls | Registry, schema, generator and lifecycle code replaced by the hand-written page; evidence-id list and unused schema removed; all readers updated: `tools/documents.py`, `tools/ci.py`, `tests/test_host_neutrality.py`, `tests/test_record_indexes.py`, `tests/test_ci.py`, `.gitattributes`, the CI profile page, the documentation map, engineering.md | Full regression passes; each control row states a failure and an enforcement point |
| L3 Evidence and data | #454 sealed; data rule and S-EVIDENCE amendment; environment.md complete; the 8 November retirement record | `verify --full` passes; the data rule holds for every tracked `data/` file |
| L4 Documentation | One home per fact; change narration removed from current pages; authority merge; superseded contracts and stubs removed with the S-MIGRATION and lifecycle amendment; metadata rule; map rows; diagrams per decision | Document checks pass; no current page restates a dated result or narrates its own changes |
| L5 Delivery | Work items, S-WORK, review, development and project management rewritten to the rules above; Project statuses and fields changed | The next leaf runs end to end under the new flow |
| L6 Code hygiene | Shared JSON/hash module; study scripts; coupling table; sandbox temporary path; docstring; duplicate tests | Full regression passes |
| L7 Provider names | Extended host-neutrality rule; provider tables and the shadow-session tool moved; unused provider removed | Host-neutrality scan passes with the new scope |

**Order.** L1, then L2: both edit `tools/governance.py` and the controls page, so they
run one after the other. After L2, L3, L6 and L7 touch disjoint files and can run two at
a time. L4 follows L2, because it rewrites pages that link the registry. L5 can land any
time after L1. P1 work (#178) is not blocked by any leaf.

**Expected result (estimates, to be measured).** About 3,000 lines of governance code,
schema, tests and documentation removed; full CI about 300 s instead of 500 s; most
main pushes in about a minute; a few Project edits per leaf instead of 10–15.

## Owner decisions, 8 November 2026

Asked through the host's question tool; each answer chose the first option.

1. **Diagrams: GitHub-native Mermaid.** Each diagram is one fenced `mermaid` block in
   its host page, with `accTitle` and `accDescr`, which GitHub renders; that block is
   the only copy. L4 deletes the `.mmd` sources, the 18 rendered SVGs (6.7 MB), the
   receipt, `tools/diagrams.py` and the renderer dependencies, and
   supersedes the diagram part of [ADR 004](004-documentation-controls.md). Accepted
   cost: GitHub's Mermaid version is outside our control, and a source that no longer
   renders shows up only on GitHub. The pinned browser stays for the viewer suites.
   The rejected option kept the SVGs and the render check.
2. **Evidence backup: keep the single copy.** The 7 November decision stands. L1's
   missing-store failure makes a loss visible; it cannot undo one. The rejected option
   was an encrypted off-machine backup.
3. **Controls registry: replace it with the hand-written page (L2).** The rejected
   option kept the registry and removed only the calendar failure.
4. **Project: simplify (L5)** to four statuses, Priority on leaves, Horizon on outcomes
   and no hand-kept dates. The rejected option kept the current Project.

## Alternatives considered

- **Fix only the defects** (the January failure, the drifted count, the missing-store
  check). Cheapest now, but the duplication that produced the drift remains, and
  every later change pays for it.
- **Remove controls without replacement.** Rejected: the full regression lane, Import
  Linter and the evidence checks prevent real failures.
- **Move history into an archive directory.** Rejected: it rewrites hundreds of links
  for no reader's benefit. Historical records stay where they are and stop being
  restated.
- **Path-conditional CI for the power test.** Rejected: [CI profiles](../workflows/ci-profiles.md)
  forbid path-conditional selection, and its inputs reach into the evaluation core and
  the lockfile. A parallel lane keeps it on every run.

## Consequences

Fewer, clearer rules, and checks that fail only for real defects. The cost is a
deliberate migration over seven PRs and less recorded process detail: no review and
validation columns, no hand-kept dates and no calendar re-review. Where that detail
matters, it is on the PR and in GitHub's own timestamps. The merge guarantee moves
from an in-repository proof to main's ruleset, which the controls page names.
