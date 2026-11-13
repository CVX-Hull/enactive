---
owner: lead
status: historical
date: '2026-11-12'
scope: 'Review of every control against the charter''s scope of use on 12 November 2026: the controls removed or simplified and why, the controls kept after challenge, the owner decisions taken and left open, the workspace cleanup, and the mapping from retired ordinal labels to descriptive names (#553)'
---

# Control review against the scope of use, and descriptive names, 12 November 2026

The owner asked that every control be tied to a realistic risk in what Enactive is: a
local gameplay player on a personal computer, for someone who supplies the game and
OpenRouter access. The owner also asked for descriptive names in place of labels such
as "P1". This record holds what was decided and done on 12 November 2026. The current
rules are in the [charter](../charter.md#scope-of-use-and-what-is-guaranteed), the
[risk register](../risks.md), the [controls page](../controls.md), the
[control rule](../standards/authority.md#control-review) and the
[naming standard](../standards/documentation.md#names).

## Method

Three read-only inventories covered the executable controls, the written rules and
procedures, and every ordinal label. The lead drafted the register, the control map and
a list of verdicts. An independent clean-context reviewer then challenged each row and
verdict against the source and the dated records. Its findings changed the result:

- Ten evidence citations in the draft register were wrong or unsupported and were
  corrected.
- Two risks were missing: private files reaching a model provider, and a merged tree
  that differs from the reviewed one.
- One planned simplification was dropped: re-hashing the evidence store takes 8.6
  seconds, so it stays in every full local check.
- One planned check was narrowed: requiring a control for every risk would have invited
  invented controls.
- Seven failed pull-request checks from 9 to 12 November 2026 were read from GitHub's
  run logs (an eighth was not read). Four were the host-name text scan, two were
  macOS-only calls on the Linux runner and one was a study test. One of the scan
  failures also showed a failing player-host subtest whose cause was not established.

A second independent review read the finished change. It found the control rule too
easy to satisfy for a new test, one manual step written only in the controls table,
and three ratings that broke the register's own rule; all were corrected before merge.

## Owner decisions

The owner answered four questions on 12 November 2026
([#553](https://github.com/CVX-Hull/enactive/issues/553#issuecomment-6839216814)).

| Question | Decision |
| --- | --- |
| The finished curator-memory study's tooling and tests | "Retire it" |
| Diagram accessibility metadata and recorded visual review | "Guidance only" |
| The `required` attention policy | "Remove it" |
| How the 22 sealed runs whose run-ending record has the earlier shape stay readable once that policy is removed | "Extend the closed archive" |

## Removed or simplified

| Control | Why it went | What covers the risk now | Change |
| --- | --- | --- | --- |
| Tooling and tests of the curator-memory study (#178), with the probe-validation, probe-timeline and shadow-report tools only it used | The study closed with a permanent no-go, so the tests protected nothing. They were 439 of 1,530 collected tests, and one failed whenever a file was added to live curator or trace code | Nothing is needed; the code is recoverable from commit `08c8f7a`, and its tracked data sits beside its records under `assets/` | [#554](https://github.com/CVX-Hull/enactive/pull/554) |
| Host-neutrality text scan over `docs/design/` | Four pull-request checks from 9 to 12 November failed on a host name in a study design page; none prevented a defect | The scan still covers code and current guidance (R-GAME-COUPLING) | [#554](https://github.com/CVX-Hull/enactive/pull/554) |
| The `required` attention policy: operator confirmation every 15 seconds, with its gateway checks and tests | Requiring a person to watch a run is outside the scope of use. Development runs already used `best-effort` by owner decision | Per-run limits and the operator's Pause (C-RUN-LIMITS, C-RUNTIME) | [#558](https://github.com/CVX-Hull/enactive/pull/558) |
| The standards-to-principles-to-controls identifier matrix in `engineering.md`, and `check_identifiers` | It checked that three lists agreed with each other, not that any control served a risk | Each control row names its risks; a small check fails an unknown risk ID or a control row without one (R-STALE-DOCS) | The register change under #553 |
| `check_diagrams`, control C-VISUAL, and the recorded independent visual review of each changed diagram | Accessibility conformance is out of scope; no failure is recorded | One paragraph of guidance; a diagram of a changed boundary is reviewed with that change | The register change under #553 |
| Control C-MAINTENANCE | It bundled an evidence check with a review habit and named no single risk | C-EVIDENCE for the store; the control rule's pruning triggers for the habit | The register change under #553 |
| Calendar reviews: 90-day drift review, "recorded due date" | ADR 010 had already replaced them with event triggers; three pages still carried them | Each page's own review trigger; the control rule | The register change under #553 |
| Five repeated passages asking for review effort, escaped defects and false alarms to be recorded at checkpoints | No measurement was ever recorded under them | One pruning rule with named triggers | The register change under #553 |
| The eight-column finding table at each campaign segment boundary | No recorded use that changed a decision | Each finding listed with what was observed, where, and its disposition | The register change under #553 |
| Deployment order and rollback in every migration statement, and the rollback procedure | There is one local install; "deployment" is a checkout | The migration statement keeps contracts, callers, removed paths and rejection tests | The register change under #553 |
| Repeated statements in the review workflow page that agent review is not human approval, with its list of unavailable human approvals | One maintainer; separate approvers are out of scope | One sentence in that page; contributing, operator permissions and the pull-request template each keep theirs | The register change under #553 |

## Kept after challenge

Each of these was proposed for removal by an inventory and kept, with its risk now
stated in the controls page.

| Control | Why it stays |
| --- | --- |
| Full re-hash of the evidence store in a full local check | It costs 8.6 seconds; the store is the only copy (R-EVIDENCE-LOSS) |
| Read-only evidence files and the missing-store error | They stop accidental change by cleanup scripts and agents, not the owner |
| Fail-to-full profile selection in `tools/ci.py` and its tests | Already written and cheap; it stops a code change passing under the documents-only profile (R-WRONG-MERGE) |
| Import contracts with negative fixtures; the scan of shared code for host, provider and model names | Agents write most code; the fixtures prove the contracts bite (R-ARCHITECTURE-DRIFT, R-GAME-COUPLING) |
| Run admission from a clean tree, an exact commit and frozen input hashes | A result must be attributable to what produced it (R-FALSE-CLAIM) |
| The curator's sandbox and proxy | The curator runs model-written commands; the sandbox is what keeps unrelated files and the key away from it (R-PRIVATE-DATA, R-KEY-LEAK) |
| Main's ruleset with no bypass | It stops an agent holding the owner's token from pushing an untested tree (R-WRONG-MERGE) |
| Writing a deciding study down before it runs, with a power check | It stopped one study before any spend (R-STUDY-OVERRUN) |

One control was added: before a study spends its budget, run one unit end to end and
read its trace. A study's question sessions had run without their screenshots, and
format checks did not notice.

## Evidence and limits

- The study retirement's pull-request check passed 969 tests in 241 seconds; the check
  on the commit before it took about 450 seconds.
- The attention-policy removal was reviewed independently before merge. The review
  confirmed that Pause, the custody deadline and cleanup are unchanged, and it ran the
  real gateway under real supervision with stand-in children. No run with a real game
  and provider was made after the change; the first such launch is its real-use check.
- That change touches supervision, the gateway, the evaluator and the spectator page,
  not the native adapter, so no native acceptance was required.
- During that review the reviewer's probe script started the real run command twice
  with a placeholder credential. Both were refused at package validation; no game
  started and no provider was called.

## Left for the owner

- How spend is capped, and the current cumulative figure:
  [#555](https://github.com/CVX-Hull/enactive/issues/555).
- Seven smaller candidates, among them three records per run, the acceptance-manifest
  check, the closing-reference check and the sandbox's free-space floor:
  [#556](https://github.com/CVX-Hull/enactive/issues/556).
- The cost of the pull-request check and where the sandbox tests run:
  [#557](https://github.com/CVX-Hull/enactive/issues/557).

## Workspace cleanup

Removed from the local checkout, after checking each against merged pull requests and
the sealed evidence manifests:

- Five finished worktrees (3.0 GB). The lineage worktree's 2,444 run files all matched
  the sealed `522-held-out` manifest by hash.
- 24 local branches whose pull requests had merged, and one stash.
- Empty lock stubs and one merged pull-request draft under `.runtime/`.

Archived under `.runtime/archive/` before removal, because they were neither merged
nor sealed:

- `529-answer-key-runtime-2026-11-12.tar.gz`: diagnostics and check logs from one
  worktree (11 MB).
- `unmerged-branches-2026-11-12.bundle`: two branches that never had a pull request
  (`codex/p1-visual-inputs`, `p1-178-study-3-approved-history`).
- `stash-p1-verified-prefix-2026-11-12.patch`: the dropped stash.
- `522-operator-2026-11-12.tar.gz`: operator working files, also present in the sealed
  manifest.

## Names

Historical records keep the labels of their time. This table translates them.

| Retired label | Where it appears | Current name |
| --- | --- | --- |
| P0 (ADR 009) | Curated-player phases | Baseline and workbench phase |
| P1 (ADR 009) | Curated-player phases | Curator and memory phase |
| P1.0 | A stage before that phase | Context-stability readiness stage |
| P2 (ADR 009) | Curated-player phases | Programs and monitor phase |
| P3 (ADR 009) | Curated-player phases | Practice instance phase |
| "P1 study", "the P1 offline study", `p1-*` files and branches | Issue #178 and its records | Curator memory study |
| `p1-study/1` | Study protocol | Curator memory study, power-gate protocol |
| `p1-study/2` | Study protocol | Curator memory study, added-lineage protocol |
| `p1-study/3` | Study protocol | Curator memory study, answer-key protocol |
| Arm A, arm B | The study's two systems | No-curator arm, curator arm |
| `lh1` to `lh4` | The study's held-out runs | Held-out lineages one to four |
| P0, P1, P2 (Project Priority) | Issues and the Project | Urgent, Important, Follow-up |
| P1 to P8 (ADR 007) | Design principles numbered inside that historical decision record | No current name; they are not used outside it |
| `"label": "P1"` in the run ledger | One pilot run's operator label | The pilot run `ceil01` |

Identifiers stored in sealed data (`p1-study/3`, `p1-arms-frozen/1`, `lh4`, evidence
store names such as `p1-grounded-completion-178`) are not renamed, because sealed
evidence is not edited.
