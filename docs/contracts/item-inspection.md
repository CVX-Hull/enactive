---
owner: maintainer
review_trigger: Changes to this interface, its callers, persisted formats or authority boundary
status: active
---

# Selected item, inspection and activity composition

A returned navigation input may open an ordinary in-game menu in the same session.
Mission/10 records a `navigate` PhaseReceipt (`operation=navigate`) and terminal
partial result, retaining the verified prefix and last verified route position.
The menu has no scene; the opening input receives no displacement credit or retry.
Inspection uses the existing menu outcome `inspected`, with no input; standalone
inspection skills still require normal play. Only exact current retained feedback with unchanged attribution/authority can open
this phase. Unknown delivery and activity/debug/unsupported boundaries do not.
Explicit menu/editor children share the original root, Work, deadlines
and cumulative primitive ceiling. An interrupted recovered suffix transfers to
that original root and game anchor before its continuation closes. No interaction,
item or activity root is borrowed. A normal return closes the prompt; a subsequent
navigation plan is a new explicit player choice, not automatic route continuation.
Ledger10 validates the selected child links and closed receipt variants on write
and reopen; historical records restore no private phase or input authority. The
[repair brief](../changes/055-navigation-menu-interruption.md) records rationale and
qualification limits.

Mission/10 retains explicit item units (`items` or `charges`) and root/select/commit
steps. The pure [item policy](../../harness/gameplay/interactions.py) checks exact
represented target, native row contradictions, known availability and chosen
count. A focus batch sends at most eight observed arrows and never confirms.
Multi-selection opens the native count field with one `MARK_WITH_COUNT`; only its
exact returned transition gives that private item phase quantity-editor ownership.
The pinned engine uses the same string-popup implementation for count and filter,
so interpreting the field as a count is insufficient. Its edit must use the
immutable root quantity; filter relabeling and ordinary menu confirmation cannot
bypass this path. Literal editing and fresh whole-value commit are separate.
Returning to the selector still requires fresh interpreted count/unit and complete
selection coverage before a distinct commit. Known extra selected rows contradict
a summary omitting them and stop confirmation. Single-selection consume supports
one native unit. Actual acquisition, consumption or storage is not inferred.

Inspection requests one registered inventory/consume/needs/look/messages/map/identity
action and owns its returned controls. Consume inspection uses the default-bound
`eat` action and its all-items selector, also used by item-consume roots; the
separate by-type `open_consume` menu has no default key binding. This is one chosen
engine action, with no automatic alias/fallback or consumption credit. CDDA may
return another outcome (both consume entry points first try `eat_here`); interpret
the actual result before further input. Item, activity, inspection and interaction
children retain the original root Work association, deadlines and cumulative input
ceiling. Phase receipts name their actual kind/operation and restore no authority.
A refused later proposal cannot erase an earlier delivered edit; partial effects
still need interpretation.

Long-running work continues through [activity polling, interruption and resumption](#activity-polling-interruption-and-resumption).

## Activity polling, interruption and resumption

An activity root opens ordinary wait/sleep/craft controls. Item, inspection or
interaction roots may also enter an ordinary native activity after their own
attributed input, such as consuming an item. At a retained owned activity poll,
Observe performs one deadline-bounded observation without input or Resume;
typed activity polls remain restricted to their original activity root and goal.
Session, actor, epoch, operator, takeover and control generations
must remain unchanged. Fresh progress, a native output menu or normal return may
advance its checkpoint; ordinary input is still unavailable at a poll. A returned
menu retains the original root kind, Work, game anchor and limits and requires
fresh player interpretation through that root's existing explicit controls. It
does not permit another root, arbitrary menu adoption or automatic answers.
Normal
return closes the phase but proves neither sleep duration nor completed Work.
Retain observed root/child/mission budget overshoot and actual effects. No polling
call renews original deadlines or claims unseen elapsed game time.
Healthy local game-time overshoot has the same partial `macro_exhausted` meaning
through typed polling and plain Observe as through ordinary control. Check
global game/input/mapping/wall/reserve limits, clock, custody, retained evidence
and unsettled delivery before this classification. Normal return closes the
root; an actual menu retains its original scope for explicit Observe closure.
No key, activity interruption, replay, refund or authority reacquisition follows
automatically. Activity-only sources do not manufacture a new normal game-clock
endpoint. For an ordinary owned activity, plain Observe uses its own immutable
observation deadline capped by the original mission/ending reserve, including
when the root expired before admission or during capture/lock wait. After a
validated capture and fatal checks, expired root wall time reports local
`macro_exhausted: "wall_seconds"`. The original root, deadline, anchor and charges
remain unchanged. An ongoing activity retains observation-only lineage; inputs,
typed polls and paused registered activity/recovery retain their original root
ceilings. Normal return closes the root; a returned menu retains exhausted scope
for another explicit Observe's durable `macro_closure` before a genuinely new
root. Actual observation timeout, global exhaustion, clock regression, custody/
Pause change, unsettled delivery and integrity/storage failure remain fatal.
No observation renews execution or manufactures an unseen game-clock endpoint.
These existing PhaseReceipt stages now settle and reopen coherently for the
supported owned roots; no field, enum, persisted shape or native/tool version
changes. Navigation activity support remains outside this contract. Historical
failed observations remain failures; no private phase is restored on reopen.

Trusted Python `recover_mission` supplies exact six-field transport receipts for
paused activity interruption and its owned answer, without operator-Pause renewal,
a lease or Resume. Native fixed expiry is checked immediately before publication;
pure correlation captures a terminal ACK/time before acceptance or retention I/O.
A later persistence failure stops authority without rewriting that ACK as unknown.
Genuinely unknown delivery retains its identity and cannot be replayed. The ordinary
operator recovery API remains separate. The registered activity adapter now composes
this transport through the existing writer and ledger; public JSON has no raw
recovery executor. A permitted interrupt child first stops ordinary dispatch,
preserving the original operator mark, actor/epoch, root Work and all ceilings.
One bounded fresh paused observation can find natural completion before any
interrupt is sent. Otherwise each interrupt and exact YES/NO answer is charged
as an ordinary primitive mapping. Terminal request/result/clock remain immutable
delivery evidence even without an after-frame or after a failed publication
bookkeeping transaction; a writable settlement atomically binds the native UUID.
No semantic effect or Work completion follows from an ACK.

The private paused phase requires unchanged session/takeover/control generations,
original host consent and nonregressing evidence. Observe is read-only under the
original root/child/mission deadlines. A known frameless ACK requires a fresh
observation, while persistence faults or unknown delivery stop continuation. NO
may leave native activity running while the harness is paused; after a fresh poll
closes its answered confirmation, another interruption uses a new UUID and the
same cumulative root budget. An answered confirmation cannot be answered twice.

Resume is a separate charged activity child, eligible only at a fresh paused
normal/menu boundary under the original operator mark. It grants no lease until
its verified return; root/child/mission time and actor fences still apply before
publishing a new prompt or normal source. A newer user Pause wins throughout.
Ledger12 rejects earlier formats before mutation; there is no compatibility reader.
Reopening restores neither the private phase nor authority. Source tests do not
qualify native gameplay. Already-returned but uninterpretable semantic outcomes
remain unsupported by delivery reconciliation.

[Contract index](../protocol.md).
