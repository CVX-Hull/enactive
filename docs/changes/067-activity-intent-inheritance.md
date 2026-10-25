---
owner: lead
review_trigger: Activity intent composition or original-root collection changes
status: historical
date: 2026-10-25
scope: Current SDK/MCP activity intent; mission wire and native contracts unchanged
---

# Let software preserve activity intent

Parent: [player interface](../components/player-interface.md).
[#215](https://github.com/CVX-Hull/enactive/issues/215) owns this bounded repair.
The [technical cases](../acceptance/2026-10-25-activity-continuation.md) exposed an
interrupt child refused before admission because its descriptive target differed
from the original wait. Repeating immutable prose is mechanical work, not a new
player decision. The existing receiver correctly rejected the mismatch.

## Design and reuse

Keep the current player → SDK → single writer architecture. Before staging an
activity child, reuse the existing read-only original-result collection to obtain
the exact root selected by the current phase. Pass that validated request to the
pure composer; copy semantic activity operation, target, duration and consent
exactly. Ordinary direct/program roots instead supply the original expected
outcome and consent, with duration bounded by both explicit game ceilings and the
activity wire maximum. Explicit limits and original cumulative accounting remain
unchanged. The selected checkpoint still supplies the exact unanswered interrupt
owner. Missing/mismatched roots refuse locally before a new child is staged.

The player supplies only the child step and explicit YES/NO answer, while still
choosing evidence, outer scope and limits. Activity start supplies operation,
target, duration and consent. Do not add another store, endpoint, scheduler,
model turn, canonical-goal cache or duplicated receiver guards. The existing
result API and schema validator fill this concrete gap. A new diagram would add
no responsibility or flow; the component view describes the added read within
the existing composition block.

## Migration and evidence

MCP 6.0.0 is the only current model-input contract. Migrate all SDK/MCP callers and
focused tests together; reject copied child fields and root answer/owner fields.
Canonical mission/11 requests, persisted ledgers, player-view/4 and native6 remain
unchanged. Frozen historical attempts remain evidence, never current examples.
Retire already loaded 5.4 producer actors; fresh hosts export/load current cards
and schemas. Do not ask a sleeping user to restart the app merely to refresh an
obsolete actor, and do not retain an old-shape input path.

Check exact semantic copying; direct/program duration bounds and consent; explicit
limits; selected mission/origin/root shape; missing/unavailable originals;
wrong/answered interrupt owners; and no new child staging/submission on failure.
Independent review and applicable protected source CI qualify the implementation.
Actual fresh-host usability and registered native interruption/answer/continuation
remain separate evidence lanes. Neither these fixtures nor a naturally completed
wait prove that capability or useful-play cadence. The authoritative protocol,
guide, setup and component view own the resulting current behavior.
