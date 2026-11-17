---
owner: lead
status: historical
kind: review
date: '2026-11-16'
scope: 'Ready delivery reconciliation and retirement of owned temporary checkouts and duplicate outputs after evidence preservation; no saves or sealed evidence removed'
---

# Ready delivery retirement

## At a glance

The selected Ready items **#463, #680 and #668** are implemented on main, closed and
Done in the Project. Their pull requests passed protected full CI, independent review
and merged-main structural validation; each squash tree matched its exact tested
head. Fourteen dependent issue descriptions now reflect those delivered contracts
and their remaining decisions. No additional issue was promoted to Ready, and no
new phase, campaign, model trial or research spending was authorized.

| Delivered item | Merge | Its evidence |
| --- | --- | --- |
| #463, journal/public intent/hints | [#685](https://github.com/CVX-Hull/enactive/pull/685), `7c6c2469` | [Adoption checks](2026-11-16-curated-memory-adoption.md) |
| #680, prospective structural scoreability | [#686](https://github.com/CVX-Hull/enactive/pull/686), `26a8ddea` | [Offline diagnostic](2026-11-16-withholding-scoreability-repair.md) |
| #668, no-model CDDA preparation | [#687](https://github.com/CVX-Hull/enactive/pull/687), `6f2da2c8` | [Preparation and CI repair](2026-11-16-cdda-recurrence-preparation.md) |

## Preservation and retirement

The `ready-delivery-retirement` entry in the
[evidence index](../../data/evidence/index.json) retains 202 files (7,824,545 bytes):
worker binary patches, the documentation worker's commit patch, development outputs,
projection metadata, process inspection, and original delivery/failure/CI logs.
The full verifier reported **“Evidence store and manifests: consistent.”** after
checking every hash, including the new preservation and CI-repair entries.

Five worktrees under `.runtime/worktrees/` were created by this task through Git.
The app inventory contained PR attachments and no managed worktree. No other agent
was running. Each dirty worker diff matched its retained binary patch, with no
untracked source. After preserving those changes, the lead restored its intermediate
tree to its base, verified clean Git status, then removed the checkout:

- `curated-memory-service`, `curated-memory-docs`, `curated-memory-projection`;
- `withholding-scoreability`, `recurrence-preparation`.

The recurrence checkout's six development-output directories and all projection
metadata matched retained copies. Its **272 projected PNGs** matched the existing
sealed `397-seven-day/computer-sessions/sd1a2/sources/` bytes, checked independently
by the lead and reviewer. The projection was a disposable derived copy, never a
second source lineage.

Ten original output directories had **320 files / 10,795,343 bytes** matched by path
and hash to their sealed copies before removal:

| Original under `.runtime/` | Retained location under `.runtime/evidence/` |
| --- | --- |
| `computer-sessions/curated-memory-model-check` | `curated-memory-adoption-463/computer-sessions/curated-memory-model-check` |
| `native-checks/curated-memory-adoption` | `curated-memory-adoption-463/native-pipeline` |
| `curated-memory-adoption-check-logs` | `curated-memory-adoption-463/checks` |
| `withholding-scoreability-680` | `withholding-scoreability-680/diagnostic` |
| `recurrence-preparation-668-sealed-input` | `cdda-recurrence-preparation-668/preparation` |
| `recurrence-preparation-668-ci-repair` | `cdda-recurrence-preparation-668-ci-repair/preparation` |
| `ready-delivery-retirement` | `ready-delivery-retirement/retirement` |
| `recurrence-preparation-668`, `recurrence-preparation-668-final`, `recurrence-preparation-668-reviewed` | `ready-delivery-retirement/retirement/recurrence-attempts/primary-<original-name>` |

Known sealing exclusions were a derived Python bytecode cache, an empty released
fixture lock, and the temporary `requirements-before-retirement.lock`. The last
matched `6f6c548e:requirements-dev.lock` byte for byte, so Git retains it. No credential,
save or unique source file was discarded. Routine checker logs and spectator-suite
screenshots were pruned after local checks stopped; cited acceptance logs/images
had already been sealed.

Eight owned local branches were removed: the five `work/<worktree-name>` branches
and `feat/curated-memory-adoption`, `fix/withholding-scoreability`,
`research/cdda-recurrence-preparation`. The three remote feature refs were already
absent after merge; an explicit deletion reported “remote ref does not exist,” and
remote-tracking refs were pruned. Main history was not rewritten.

## Process and tracker reconciliation

The scoped process inspection found no project runtime/test command matches, and
the shared game lock was available. Earlier native/model receipts separately
verified their process/group absence and input revocation. No unrelated process
was stopped. No native build was removed. All sealed evidence, saves/checkpoints,
credentials, application files and shared dependency caches remain available.

The replacement bodies for #25, #42, #177, #384, #387, #441, #445, #457, #464, #465,
#664, #666, #677 and #681 were independently reviewed and published after #668's
merge/main validation. They preserve the open belief decision, deferred cut,
separate campaign/model-trial approvals, and source/outcome/integration/price gaps
before future research. The work remains scoped to CDDA with Terra current.

This retirement uses the existing evidence/cleanup workflow and introduces no new
standing gate or framework. Its record and hashes receive their own protected
delivery; the implementation results remain in the three linked records.
