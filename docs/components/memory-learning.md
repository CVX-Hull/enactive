---
owner: harness maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
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

A supported `player-journal/1` (SQLite `user_version=1`) can reopen across native
sessions. Unsupported active stores refuse before launch. Capacity or source
registration failure is reported; healthy basic control remains available. Digest
mismatch refuses source consumption. Unknown or partial physical delivery stops
further input and is never replayed. Handoff carries a labelled summary hint,
not a knowledge graph, and does not renew authority.

Journal tests (`tests/test_player_journal.py`) and [application tests](../../tests/test_player_application.py)
cover the supported formats and composition. They do not establish learning
benefit. Sealed historical evidence retains its original scope; there is no live
curator scheduler in the current route.
