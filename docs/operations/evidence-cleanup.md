---
owner: maintainer
review_trigger: Changes to this operating task, supported setup or recovery behavior
status: active
---

# Evidence retention and cleanup

Track small reports/manifests, source pins and checks in Git. Keep user saves,
large media, journals, credentials and downloads out of Git. Use Git commit/tree,
diff and PR for source identity. A manifest records external artifacts' relative
paths, byte counts, hashes, source/candidate and limitations. Snapshot
journals before indexing them: a live journal can append even during normal shutdown.
Keep the full live journal, label the snapshot/cutoff, and verify its bytes/hash; do
not truncate a journal or overwrite a historical hash to hide later events. A hash
identifies bytes; it does not prove the depicted behavior without inspection.

**Sealed evidence store (owner decision, 7 November 2026).** Raw run evidence that a
dated record cites (packages, frames, traces, evaluator records, memory stores,
userdirs) is sealed read-only under `.runtime/evidence/<study>/` before the worktree or
directory that holds it is removed. `python -m tools.evidence seal STUDY --from
SUBDIR=PATH@ORIGIN --cited-by RECORD --note TEXT` copies it in once and checks every copy
by hash. It then writes the tracked manifest `data/evidence/<study>.sha256` (one
`shasum -a 256` line per file, so stock tools verify it) and the study's
`evidence-index/1` entry in `data/evidence/index.json`: citing records, each part's
origin (repository-relative path and commit), file count, total bytes, manifest hash,
visibility, availability and a note on what stayed elsewhere. It skips and reports the
names `Cataclysm.app`, `credentials.json`, `.env`, `.venv`, `__pycache__`, `node_modules`,
`.DS_Store` and any `*.lock`; refuses links and names a manifest line cannot hold; leaves
nothing behind if it fails; and only removes write permission. A sealed study is never
rewritten; removing one is an owner decision, recorded by setting its `availability` to
`removed` with the reason. `tools/evidence.py verify` runs in the fast checks (file set,
total bytes, no write permission) and the full profile (every hash). A sealed study
missing from a present store is an error; a fresh clone without the store reports each
study as not present. The store is the only copy: there is no off-machine backup, and
raw evidence is not published (owner decisions, 7 November 2026; restic to object
storage is the researched option if a backup is chosen). Older items directly under
`.runtime/evidence/` and the operator files each study's note names stay outside the
seal until [#420](https://github.com/CVX-Hull/enactive/issues/420).

Retain curated acceptance artifacts and failure evidence until superseded by
reviewed equivalent evidence or explicitly selected for removal; if removed,
record availability as removed in the evidence index. Keep unresolved-incident
journals until resolved. Routine unreferenced journals/frames can be pruned after
30 days, only with sessions stopped and after checking references/ownership.
This initial policy is manual; no scheduled deletion is installed. Current captured
PNGs are immutable custodian-owned sources charged to the original frame/byte
capacities. Do not rotate or delete them during a live session.

Never delete saves as routine cleanup. For user-directed stale-world cleanup,
stop the owned game/controller first, identify closed test/failed worlds and
preserve accepted campaign saves and current reusable checkpoints. Prefer an
ordinary project-local archive outside `.runtime/user/save/`; verify its contents
before removing the selected active directories and record the archive location
and retained worlds in the environment ledger. Keep campaign evidence separately;
retiring a save does not renew a failed mission or establish a normal ending.
Preserve manifests before removing owned build directories/downloads. Identify
the exact path from the build manifest and verify its checkout ownership marker;
never use broad /tmp or global-cache cleanup.

Use the app's artifact inventory and archive operation for managed worktrees.
A Git bundle preserves source; it does not establish checkout ownership or preserve
ignored dependencies and runtime evidence. If the app is unavailable, or reports
a checkout as primary or owned by another task, retain it rather than forcing a
Git/filesystem removal. Resume cleanup when ownership can be verified. Keep the
canonical runtime owner and needed local evidence available throughout cleanup.

For a lost temporary build, re-extract using setup. For an unreadable archive,
remove only the named corrupt cache entry after preserving diagnostics.

Fresh source checkouts contain selected public evidence, not complete private run media.
Maintainers must distinguish unavailable evidence from a newly failed probe.

[Operations index](../runbook.md).
