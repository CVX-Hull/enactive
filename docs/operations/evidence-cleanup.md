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

Retain curated acceptance artifacts and failure evidence until superseded by
reviewed equivalent evidence or explicitly selected for removal; if removed,
record availability as removed in the evidence index. Keep unresolved-incident
journals until resolved. Routine unreferenced journals/frames can be pruned after
30 days, only with sessions stopped and after checking references/ownership.
This initial policy is manual; no scheduled deletion is installed. Native frame
rotation within a live process remains the game's existing bounded behavior.

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
For a lost temporary build, re-extract using setup. For an unreadable archive,
remove only the named corrupt cache entry after preserving diagnostics.

Fresh source checkouts contain acceptance metadata but not local demo media.
Maintainers must distinguish unavailable evidence from a newly failed probe.

[Operations index](../runbook.md).
