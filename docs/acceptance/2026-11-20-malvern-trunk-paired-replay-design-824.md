---
owner: lead
status: historical
kind: review
date: '2026-11-20'
scope: 'Offline readback of the retained Malvern sedan-trunk cutoff and the design and price of one paired proposal replay on it (#824)'
---

# Paired replay design for the Malvern sedan-trunk decision (#824)

## At a glance

The Malvern cutoff can carry a paired replay, and the replay is cheap: eight responses,
at most $0.87 at listed rates, under a $2.00 maximum. It has not been run and is not
approved.

The readback changes what the replay can show. At the current context size the sent
request already names four items from the trunk in a player hint and says all four were
picked up; it never names the fire extinguisher, and it carries a handle to the trunk
frame. At the 64k target the request carries nothing about the trunk at all: no text, no
handle, no pixels. So the two sizes ask different questions. The current size asks whether
the player recovers an unnamed remainder through an ordinary lookup it can already make.
The 64k size asks what is lost when old turns are dropped, which is the context-cut
question owned by [#664](https://github.com/CVX-Hull/enactive/issues/664).

The trunk fact is also only loosely tied to the decision. The objective at the cutoff is
equipment or shelter work, the screen shows a scarf recipe that is too dark to craft, and
the trunk holds tools and an extinguisher, not cloth. A proposal that checks the trunk is
therefore not clearly better than one that does something else useful. The replay can
show whether supplying the observation changes what is proposed. It cannot show that the
change helps.

Offline development evidence only: no game, no model request, $0 spent.
[Lookup-effort review #804](2026-11-19-lookup-effort-at-retained-resource-choices-804.md) · [Two-wake audit #777](2026-11-18-retained-two-wake-decision-audit-777.md) · [Retained review #791](2026-11-19-retained-memory-decision-791.md) · [Delayed-observation cueing #755](2026-11-18-delayed-observation-cueing-755.md) · [Delayed-memory design](../design/delayed-memory-assessment.md)

## What was read

Everything here is a readback on 20 November 2026 of retained files under
`.runtime/evidence/`, opened read-only. Nothing was rebuilt or resealed.

- The four dry packs of the two-wake audit:
  `retained-two-wake-decision-audit-777/packing/dry-pairs/farm-source-before/` and
  `farm-source-after/`, each with `current-history` and `compact-history`, and
  `packing/packing-result.json`.
- The trunk frame
  `two-wake-memory-772/admission-3/sources/2bfa0eb2d8534a0a9df874625c1238cc-7401.png`,
  SHA-256 `f46b2913f377a828195d4f4812df83751a6efa4af4bc46d5741453ef0b5567bc`, which
  matches the hash in the packs.
- The earlier probe's protocol and dispatcher,
  `delayed-observation-cueing-755/replay/protocol.md` and `pilot.py`.
- The listed route rates in `data/curator/openrouter-prices-2026-11-08.json`.

Each pack's `common.json` was searched for the strings `7401`, `trunk`, `extinguisher`
and `flashlight` in every text part. Image parts are references to retained files, so
which frames a pack carries was read from those references.

## What the request carries about the trunk

The cutoff is request 287 of admission 3. `farm-source-before` is the context before that
request; `farm-source-after` is the context before request 288, one lookup later.

| Pack | Size read from `packing-result.json` | Turns kept | About the trunk |
| --- | --- | --- | --- |
| Before, current size | 143,740 tokens, 22 images | request 1 to 286 | The two intents that opened and inspected the trunk. One omission record for frame 7401 ("Historical pixels omitted from this request by frozen image policy"). One player hint, present in its call and in its result: "Sedan trunk contained a Pocket Survival Guide, a bottle with 14 water purification tablets, multitool and heavy-duty flashlight; all were actually picked up (-7401, -7410)." No part contains "extinguisher". The trunk frame is not among the images. |
| Before, 64k target | 63,349 tokens, 22 images | request 236 to 286 | Nothing. No part contains `7401`, "trunk", "extinguisher" or "flashlight". |
| After, current size | 145,809 tokens, 23 images | request 1 to 287 | As before, plus the `player_source` call on 7401, its result and the trunk frame. |
| After, 64k target | 63,408 tokens, 23 images | request 241 to 287 | Only the `player_source` call on 7401, its result and the trunk frame. |

The trunk frame is a pickup list headed SEDAN TRUNK: a lug wrench, a small fire
extinguisher (10/10 extinguishing agent), a survival kit box holding a glowstick, the
Pocket Survival Guide, a bottle with 14 water purification tablets and a whistle
multitool, and a toolbox holding an adjustable wrench, a heavy-duty flashlight, a
multitool, a pocket knife, a screwdriver and pliers.

Common to all four packs: model `openai/gpt-6.1-terra` at medium effort, an output cap of
512 tokens, the objective "Choose viable equipment work or another useful shelter task.",
the current frame 13982, and the permission text "Propose actions only. Ordinary lookup
and fresh observation may be proposed on equal terms. No tools will be dispatched." Each
pack reserves 2,048 input tokens for a readout, and its `ordinary.json` and `memory.json`
point at one `common.json` by the same hash.

## Does the cutoff meet the condition in #804

[#804](2026-11-19-lookup-effort-at-retained-resource-choices-804.md) asks for a cutoff
where the target fact is absent from the sent context and from the action's own menu,
where an ordinary handle exists before the cutoff, and where both routes are observed.

- **Current size: yes, narrowly.** The fact that the trunk still holds an extinguisher and
  other tools is in no text part and the frame is not sent. The handle is sent. But the
  hint's "all were actually picked up" refers to the four items it names and can be read
  as saying the trunk is empty. The absent fact is the remainder of a list the request
  partly describes.
- **64k target: the fact is absent, and so is the handle.** The player cannot name source
  7401 from this request. An ordinary lookup of that frame is not available from the
  context; only a journal or source search, or walking to the trunk, would recover it.
  This row meets the first condition and not the second.
- **The action's own menu:** the scarf recipe on screen shows nothing from the trunk, as
  #804 recorded.
- **Both routes:** only the lookup route was observed, once, in the original run. That is
  what the replay would add.

The leaf's first stop condition does not fire: the cutoff qualifies at the current size.

## The two conditions

Both use the retained `farm-source-before` pack at each size. Within a size the common
context is byte-identical, already built and already hashed.

- **Ordinary:** the context as sent, with the readout reserve left empty.
- **With the observation:** the same context plus one readout in the reserved space.

The readout is rewritten for this replay. The retained fixture says "The earlier sedan
trunk view showed a full small fire extinguisher and a heavy-duty flashlight. Verify which
is useful and still available." It tells the player what to do, and it names a flashlight
that the sent hint says was picked up. The replay's readout states the observation and
its age and nothing else:

> Earlier observation, source 2bfa0eb2d8534a0a9df874625c1238cc-7401, about 11 hours 40
> minutes before the current view: the sedan trunk's pickup list also showed a lug wrench,
> a small fire extinguisher (10/10), a glowstick and a toolbox of hand tools. Whether they
> are still there has not been checked.

It is written by hand from the frame, as the #755 cues were. It is a stand-in for what a
memory would deliver, not a test of a memory choosing it.

The request-288 context is not used as the second condition. It differs from request 287
by a whole turn, and that turn is the lookup itself, so it would compare the cutoff with
its own ordinary recovery and not with a supplied observation.

Held equal within each size: model, effort, guide, tool declarations, objective, handoff,
current frame, permission text, kept turns, images, readout reserve and output cap.

## Outcome and scoring, fixed before any call

The outcome is the proposed next action in each response. A reader scores each response
without seeing its condition or size, under opaque response identifiers, into exactly one
category. The category names are those of the #755 protocol; no tracked codebook exists,
so the case text is written here.

| Category | For this case |
| --- | --- |
| Targeted grounded check | Proposes re-reading source 7401, searching the journal or sources for the trunk, or going to the trunk to see what remains, and treats what was there as past and unchecked. |
| Grounded alternative | Proposes other equipment or shelter work supported by the current frame or the sent context: for example getting light before crafting, finding cotton sheets, or another task the context supports. |
| Unsupported certainty | States that the trunk holds or lacks something now, or proposes using or picking up a trunk item as if its presence were known. |
| Absence | No concrete proposal: a refusal, a malformed answer or an empty one. |

A targeted check and a grounded alternative both count as acceptable decisions here,
because the trunk holds nothing the scarf needs. The replay reports counts per cell. It
supports statements about proposed decisions only, not about what would have happened in
play.

**Effect, per size.** With two responses per cell: an effect at a size means both
responses with the observation are targeted checks and neither ordinary response is.
Anything else at that size is no effect. No response is added after results are seen.

## Cells and price

The [delayed-memory design](../design/delayed-memory-assessment.md#calibrate-on-retained-play-then-replay-paired-choices)
sets two samples per cell. One packet, two sizes and two conditions give eight responses.

| Size | Responses | Input each, with the full reserve | Input total |
| --- | --- | --- | --- |
| Current | 4 | 145,788 tokens | 583,152 |
| 64k target | 4 | 65,397 tokens | 261,588 |

At the listed rates for `openai/gpt-6.1-terra` ($1 per million input tokens, $5 per
million output tokens, below the long-prompt tier), 844,740 input tokens cost $0.845 and
eight capped outputs cost $0.02: **$0.87** with no cache read assumed. The token counts
are the packer's local estimates, not the provider's. Two measured figures bracket it: the
original request-287 turn returned $0.00817 with cache reads, and the #755 probe returned
$0.02214230 for twelve single-image responses.

Proposed envelope: a **$2.00 maximum**, a stop when the returned subtotal reaches $1.50,
eight first attempts in a fixed interleaved order with no automatic retry, and a stop
with receipts kept on a transport failure, a missing cost, an unexpected model or
provider, or a malformed response. A missing charge is recorded as unknown. Scoring is one
blind pass by a host agent and costs nothing at the provider.

## What each result does

The owner decided on 20 November 2026 that a null result closes
[#666](https://github.com/CVX-Hull/enactive/issues/666) as a feasibility stop
([decision log](../decisions/owner-decisions.md)). Applied to the two sizes:

| Result | Reading | Next step |
| --- | --- | --- |
| Effect at the current size | The ordinary player did not go back for a recoverable fact that a supplied observation made it check, under normal context. | #666 stays open. One case from one world cannot carry a claim, so the next step is a second scoreable packet from another world, under its own price. |
| No effect at the current size, effect at 64k only | The observation matters only once old turns are dropped. | #666 closes as a feasibility stop. The finding goes to #664 as evidence for the context cut. |
| No effect at either size | Supplying the observation does not change the proposal here. | #666 closes as a feasibility stop. |
| Stopped early or malformed | Partial coverage is reported as partial. | Treated as no effect for #666 unless the owner says otherwise; no repeats are added. |

Whether the second row counts as null for #666 is the lead's reading of the decision, not
its words. It is put to the owner with the price.

## Machinery and the one gap

Reused as they are: the four dry packs and their hashes, the packer's sizing, the
readout reserve, the #755 category names, and the campaign credential loader the #755
probe used.

The gap is the dispatcher. The only retained code that sends proposal requests is
`delayed-observation-cueing-755/replay/pilot.py`. It is untracked, written for the three
#755 cases, and builds a compact prompt with one image. This replay needs a script of
about that size that turns one pack's `common.json` and readout into one provider request
with its retained images, fixes the order, and writes requests, responses and receipts
beside the result. It is kept with the replay's sealed evidence as `pilot.py` was. It adds
no evaluation stack and no tracked module.

## Limits

- One cutoff from one world. Two responses in a cell are repeats of one packet, not
  independent observations.
- The readout is hand-written. Nothing here tests a memory forming, selecting or
  delivering it.
- A targeted check is not clearly the better decision at this cutoff, so a shift in
  proposals is not a benefit.
- The 64k row lacks the handle, so it is not the efficiency comparison #804 described.
- Token counts are local estimates; the provider's count and cost may differ.
- The later pickup of the extinguisher in the original run supports that executed branch
  only, and the avatar's identity near it stays unverified, as #804 recorded.
- The replay is unrun. This record authorizes nothing.
