---
owner: maintainer
status: superseded
scope: Earlier native7/mission11 semantic gameplay contract; retained historical bookmarks only
replacement: docs/contracts/computer-control.md
---

# Player transport and original result collection

This contract is historical. The sole current replacement is
[Computer control and player ports](computer-control.md). The current harness
provides pixels, basic key/text/pointer/wait, mechanical custody/resources,
independent permanent Pause and exact original collection. All game semantics,
save/load, identity, memory assertions and outcome judgments belong to the player.
Actor handoff has no game-phase or identity predicate.

[Read the original contract at the accepted checkpoint](https://github.com/CVX-Hull/enactive/blob/433ed973afe312d03f777d8b102a0cba528af746/docs/contracts/player-transport.md).
Its old native/mission commands, schemas, recovery paths and executable imports
are unsupported and must not be replayed against current stores. Preserve old
artifacts as inert history; [migration](../operations/migration.md) explains
fresh current stores and coherent rollback.

## Certified request admission refusal

Historical bookmark: use the [current replacement](computer-control.md) for
mechanical authority and player-service behavior. The original section remains
readable in the accepted-checkpoint link above.
