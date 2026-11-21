---
owner: lead
review_trigger: Player journal, hints, handoff context or delivery changes
status: active
---

# Evidence, memory and learning

The player journal (`harness/player/journal.py`) retains public calls,
fallible hints and referenced source images. It is not a player-authored knowledge
store. The curator writes knowledge through its gate; the player receives a frozen
briefing, reminders and read tools. A hint can inform later curation but cannot
publish a fact or grant input authority. Source references show availability, not
attention. [Computer control](../contracts/computer-control.md#player-knowledge-and-executable-proposals)
owns the exact journal, hint and handoff contracts.

The [computer-control contract](../contracts/computer-control.md#responsibilities-and-current-data)
governs reopening the journal across native sessions. Capacity or source
registration failure is reported; healthy basic control remains available. Digest
mismatch refuses source consumption. Unknown or partial physical delivery stops
further input and is never replayed. Handoff carries a labelled summary hint,
not a knowledge graph, and does not renew authority.

Journal and application tests cover the supported formats and composition. They do
not establish learning benefit. Sealed historical evidence retains its original scope.
See the [curator runner and delivery boundary](curator.md#curator-and-trace-workbench)
for how publication during an admission relates to the frozen briefing.
