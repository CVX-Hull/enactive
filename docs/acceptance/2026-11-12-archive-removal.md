---
owner: lead
status: historical
kind: change
date: '2026-11-12'
scope: 'Removal of the local archive directory and its five items on the owner''s decision of 12 November 2026, after the workspace cleanup of the same day (#553)'
---

# Local archive removed, 12 November 2026

The [workspace cleanup](2026-11-12-control-review-and-names.md#workspace-cleanup) of
12 November 2026 moved material that was neither merged nor sealed into
`.runtime/archive/` instead of deleting it, and listed it for the owner. Asked what
should happen to the five items, the owner answered "Delete all five". The directory
was removed the same day.

| Removed | What it held | Still available elsewhere |
| --- | --- | --- |
| `529-answer-key-runtime-2026-11-12.tar.gz` | Diagnostics and check logs from one removed worktree, 10 MB | No |
| `unmerged-branches-2026-11-12.bundle` | Two branches that never had a pull request: `codex/p1-visual-inputs` (2 commits) and `p1-178-study-3-approved-history` (5 commits) | No. Their subjects were superseded by merged work: the study's handout executor and its approved protocol text |
| `stash-p1-verified-prefix-2026-11-12.patch` | One stash touching the study's frozen arms file and protocol page | No |
| `522-operator-2026-11-12.tar.gz` | Operator working files for the fourth held-out lineage | Yes: all 58 files match the sealed `522-held-out` manifest by hash |
| `worktree-drafts-2026-11-08.tar.gz` | Drafts archived by the [8 November retirement](2026-11-08-retirement.md) | No |

No sealed evidence, tracked file or game save was touched. The checkout keeps no
archive directory; material that must outlive a removed worktree is sealed into the
[evidence store](../operations/evidence-cleanup.md) or committed.
