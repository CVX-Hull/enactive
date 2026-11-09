---
owner: lead
status: historical
date: '2026-11-08'
scope: 'Removal of stale worktrees, merged branches, second copies of sealed evidence and unused downloads on 8 November 2026, with what was archived first (ADR 010, #501)'
---

# Retirement of stale resources and second copies, 8 November 2026

The owner approved removing stale resources that would not lose data, and asked that no
second copy be kept without a reason ([ADR 010](../decisions/010-streamlined-delivery.md)).
Everything below was either already held elsewhere, verified by path and hash, or
archived first. Nothing that exists in only one place was deleted.

## Worktrees and branches

- **17 worktrees** under `.runtime/worktrees/` (about 5.4 GB), all for merged branches:
  `cache-fix`, `p0-446`, `p0-448`, `p0-449`, `p0-450`, `p0-452`, `p0-452-images`,
  `p0-453`, `p0-453-gate`, `p0-454`, `p0-455`, `p0-456`, `p1-489`, `p1-490`, `p1-491`,
  `p1-go`, and the #397 run worktree `397` (below). Their uncommitted content was
  ignored installs except three items, archived first (below).
- **82 local branches** whose tip is in main or in a GitHub pull request head
  (`refs/pull/N/head`), and the remote branch `adr7-candidate` of closed #332, whose
  commits that pull request keeps. Kept: `aid-zoom-view`, `backup/p0-453-wip` and
  `p0-453-gate`, whose commits exist nowhere else.
- Stale remote-tracking references were pruned; the clone now prunes on fetch.

## Second copies of sealed evidence

- **`.runtime/worktrees/397`** (969 MB): all 2,401 files of its `source/.runtime` and
  `operator/` matched the sealed `397-seven-day` study by path and hash; the rest was the
  checkout at `db38b30`, environments and caches, the app copy, the credential reference
  and locks, which the seal skips by rule.
- **`.runtime/archive/397-lineage-1-user`** and its manifest: all 165 files matched the
  same study's `user/` entries by path and hash.
- **`.runtime/curator-shadow/`** and **`.runtime/knowledge/shadow-454/`**: sealed as the
  `curator-shadow-454` study (612 files) citing the #454, #489 and P0 records; every
  original matched the manifest before removal.

A full `verify --full` of the store passed before and after each removal.

## Downloads, tools and routine output

- `downloads/pkgconf-3.0.8.*`: no longer fetched by setup.
- `toolchain/gitleaks`: no current check or document uses it.
- `check-logs/`: runs older than the five newest (routine output).
- Empty `.worktrees/` and `.claude/worktrees/`; bytecode-only folders `harness/gameplay/`,
  `experiments/` and `tools/memory_study/` left from removed modules.

## Archived first

`.runtime/archive/worktree-drafts-2026-11-08.tar.gz` (checksum beside it) holds the only
content that existed nowhere else:

- untracked early drafts from the `p0-452-images` and `p0-453-gate` worktrees (main later
  merged different versions);
- the uncommitted diagnostic test from the #489 caching investigation in `p1-go`;
- the ADR 009 P0 goal prompt that was `.runtime/goal-p0.txt`.

## Left in place

- `dist/seven-day-video/`: the 19 October recap video export. No record cites it and the
  store does not hold it, so it is an original; keeping or removing it is the owner's call.
- `.runtime/logs/`: the 17–18 October setup and check logs, kept by the
  [7 November retirement](2026-11-07-runtime-retirement.md).
