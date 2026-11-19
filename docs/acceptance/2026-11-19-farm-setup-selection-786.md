---
owner: lead
status: historical
date: '2026-11-19'
kind: review
scope: 'Retained negative and positive setup cases checked for the next Farm package; no game launch or provider dispatch'
---

# Farm setup selection checked against retained frames (#786)

## At a glance

The retained cases support adding an observed Custom Character selection to
the next Farm brief. The positive editor and Farm cases cover separate steps.
The exact Handy Man or Handy Woman Farm assignment still needs live verification.
This audit used the original sealed recordings and cost $0.

## Failed path and positive references

Frame numbers below are source-ID suffixes within each listed admission. The
[private evidence index](../../data/evidence/index.json) locates the seals.
Use the host trace to pair requests with returned sources, then compare the
original PNGs and, for #785, the operation receipts. The tracked SHA-256
manifests identified the selected source PNGs, host traces and #785 session
database and write-ahead log. The audited bytes matched those manifests.

| Case and seal path | Actual inputs and rendered evidence |
| --- | --- |
| [#785 Thedford](2026-11-19-farm-setup-stop-785.md), `farm-setup-stop-785/admission-1` | Frame 43 lists the new Thedford world in the World menu. Request 7 clicked New Game at (215, 520) and sent Up and Enter in the same operation, `6399f8a8a1004fd6bb84f9aeccbe38d2`. Frame 47 shows **Play Now!** highlighted at the bottom and Custom Character visible at the top. Request 8 clicked the visible Custom Character row at (229, 407), using frame 47, in operation `73e35c0875b544f3b0170a33f92b9535`. Frame 92 shows native loading. Requests 9–11 observed without input. Frame 179 shows the cabin introduction with the world-build modal. The actor ended with `cannot_continue`. |
| [#741 Regent](2026-11-17-evacuee-editor-check-741.md), `evacuee-editor-check-741/package` | Request 6 navigated to New Game and returned frame 64 with **Custom Character highlighted**. Request 7 sent Enter separately. Frame 65 still shows the highlighted submenu. Subsequent observations followed the transition without input. Frame 195 is the first returned editor view, on Points. Frame 197 shows the Scenario tab, and frame 204 shows the accepted **Evacuee** scenario on Description. The actor ended in the editor. |
| [#772 Malvern](2026-11-18-two-wake-memory-772.md), `two-wake-memory-772/admission-1` | The actor entered the editor with a compound command in request 6. The retained frames establish later editor and entry states. Frame 178 shows Safe Place in the Scenario tab and frame 179 shows Survivor in the Profession tab. Frame 185 lists Farm in the location picker while Random is highlighted. Request 17 chose Farm with its visible shortcut. Frame 225 shows **Safe Place, Farm and Survivor** together on Description. Frame 229 shows the distinct final confirmation prompt. Frame 325 shows **Elias Reed**, the farm house and 08:00 on spring day 61 after entry. |

Both #785 input operations completed mechanically. The three action receipts
for request 7 and the click receipt for request 8 each say SDL events were
emitted and the application effect was unknown. Each operation also has its
own frame receipt. The frames show the wrong highlight followed by an
unassigned setup. They do not establish which particular input activated it.

## Setup fragment for the next Farm package

> Open New Game and inspect its submenu before confirming any starting
> option. Use selection-only navigation while another row is highlighted.
> Confirm Custom Character separately after a returned view visibly
> highlights that row. During loading or an ambiguous transition, observe the
> screen before sending further input.
>
> In the editor, select Safe Place, Farm, and the assigned Handy Man or
> Handy Woman profession. Before committing to play, read back the accepted
> scenario, starting location and profession on Description. Verify the
> confirmation prompt in its returned view before accepting it. If a
> selection is unclear, observe again. If the assigned setup cannot be
> established through ordinary controls, or an unassigned game opens, report
> inability to continue. After entry verify the survivor, clock, setting and
> visible starting capabilities and tools as specified by the mission.

The actor interprets these screens using the [ordinary player tools](../player-guide.md#calls-and-returned-evidence).
An existing returned view can satisfy a check. The extra wait for a rendered
choice before confirmation costs a decision boundary at that transition. It
addresses R-FALSE-CLAIM and R-STUDY-OVERRUN by exposing a wrong or unconfirmed
selection before an irreversible start. Existing custody and input-result
rules govern partial or unknown mechanical delivery.

## Offline readback and disposition

- Thedford frame 43 calls for opening the submenu without a confirmation.
  Frame 47 calls for selection only, since Play Now! has focus. Frames 92
  and 179 call for observation during loading and then an assigned setup
  stop when the cabin appears. The recorded post-batch frames cannot show
  what the proposed smaller operations would have done in that session.
- Regent frame 64 satisfies the Custom Character confirmation check. Frame
  65 leaves the transition unresolved. Later editor frames resolve it.
  Description shows why this case is an editor-entry reference only for
  the assigned Farm setup.
- Malvern frame 185 shows an available Farm choice with Random still
  selected. Frame 225 supports the accepted Farm readback. It has Survivor,
  which satisfies its own historical assignment and would fail the
  profession check for the proposed Farm assignment. Frame 229 shows the
  separate commit prompt, and frame 325 supports the post-entry readback.

All three sealed package manifests pin the same native executable SHA-256.
The two Farm manifests also pin identical `initial_files` maps. The recorded
editor and Farm references therefore apply to that same selected build and
Farm configuration.

Proceed to exact package staging in [#788](https://github.com/CVX-Hull/enactive/issues/788).
The retained evidence supports using the corrected brief on the next
acquisition's first admission with the original setup stop. An editor-only
check would be warranted if staging identifies a materially different
menu or build or a concrete question about the availability of an assigned
choice. The frozen package and its
spend envelope still require owner approval before any launch.
