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
estimated at $0.87 at listed rates, under a $2.00 maximum. It has not been run and is not
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
| Before, current size | 143,740 tokens, 22 images | request 1 to 286 (285 turns; request 187 has no retained turn) | The intents that opened and inspected the trunk, took the four items and left it. One omission record for frame 7401 ("Historical pixels omitted from this request by frozen image policy"). One player hint, present in its call and in its result: "Sedan trunk contained a Pocket Survival Guide, a bottle with 14 water purification tablets, multitool and heavy-duty flashlight; all were actually picked up (-7401, -7410)." No part contains "extinguisher". The trunk frame is not among the images. |
| Before, 64k target | 63,349 tokens, 22 images | request 236 to 286 (51 turns) | Nothing about the earlier pickup list, its handle or its contents: no part contains `7401`, "trunk", "extinguisher" or "flashlight". The sedan itself is still named and shown, for example in frame 12352. |
| After, current size | 145,809 tokens, 23 images | request 1 to 287 (286 turns) | As before, plus the `player_source` call on 7401, its result and the trunk frame. |
| After, 64k target | 63,408 tokens, 23 images | request 241 to 287 (47 turns) | Only the `player_source` call on 7401, its result and the trunk frame. |

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

The target fact is an earlier sighting: frame 7401 showed an extinguisher and other tools
in the trunk about 11 hours 40 minutes before the cutoff. Whether they are still there is
not known from any retained frame before the cutoff.

- **Current size: the first two conditions hold, narrowly.** That sighting is in no text
  part and the frame is not sent. The handle is sent. But the hint's "all were actually
  picked up" refers to the four items it names and can be read as saying the trunk is
  empty. The absent fact is the remainder of a list the request partly describes.
- **64k target: the first condition holds and the second is not shown.** The sighting is
  absent, and so is the handle: the player cannot name source 7401 from this request. The
  retained tool declarations offer a source read by exact identifier and a search of
  delivered articles and facts; whether either recovers the sighting from this smaller
  request is unverified. In this row the supplied observation adds both the sighting and
  its handle.
- **The action's own menu:** the scarf recipe on screen shows nothing from the trunk, as
  #804 recorded.
- **Both routes: neither size supplies the third condition.** #804 asks for a lookup and
  a re-observation or trip observed from one decision point. Only the lookup was
  observed, once, in the original run. The replay adds proposals under two conditions,
  which is not that observation.

The leaf's first stop condition does not fire: the current size meets the two conditions
a replay can use.

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

**Response shape.** Both conditions ask for the same thing, as the #755 probe did: one
JSON object with three non-empty strings, `action`, `evidence` and `uncertainty`, naming
one proposed next action. A response that does not parse into that shape is a dispatch
failure: it is kept, it stops the run, and it is not scored.

**Scoring.** The outcome is the proposed next action. A reader scores each well-formed
response under an opaque identifier, without being told its condition or size, into
exactly one category. The reader is given the current frame 13982, the objective and
the sent hint about the trunk as the common reference for what is supported. A response
can reveal its condition by repeating the readout; the reader scores what is proposed
all the same, and the record of the run says how many responses did so. The category
names are those of the #755 protocol; no tracked codebook exists, so the case text is
written here. The categories are tried in this order and the first that fits is used.

| Order | Category | For this case |
| --- | --- | --- |
| 1 | Absence | The `action` names no concrete next step: an abstention or a request for more information with no proposed act. |
| 2 | Unsupported certainty | The response states that the trunk holds or lacks something now, or proposes using or picking up a trunk item as if its presence were known, whatever else it proposes. |
| 3 | Targeted grounded check | The action is to re-read source 7401, to search delivered knowledge for the trunk, or to go to the trunk to see what remains, treating what was there as past and unchecked. |
| 4 | Grounded alternative | Any other action that the current frame, the objective or the reference supports: for example getting light before crafting or finding cotton sheets. |
| 5 | Ungrounded other | Any other action, which none of those supports. |

A targeted check and a grounded alternative both count as acceptable decisions here,
because the trunk holds nothing the scarf needs. The replay reports the counts in every
cell. It supports statements about proposed decisions only, not about what would have
happened in play.

**Shift in proposed checks, per size.** With two responses per cell, a shift at a size
means both responses with the observation are targeted checks and neither ordinary
response is. A size whose four responses are all scored and miss that pattern shows no
shift. A size with fewer than four scored responses is inconclusive. No response is
added after results are seen.

## Cells and price

The [delayed-memory design](../design/delayed-memory-assessment.md#calibrate-on-retained-play-then-replay-paired-choices)
sets two samples per cell. One packet, two sizes and two conditions give eight responses.

| Size | Responses | Input each, with the full reserve | Input total |
| --- | --- | --- | --- |
| Current | 4 | 145,788 tokens | 583,152 |
| 64k target | 4 | 65,397 tokens | 261,588 |

At the listed rates for `openai/gpt-6.1-terra` ($1 per million input tokens, $5 per
million output tokens, below the long-prompt tier), 844,740 input tokens cost $0.845 and
eight capped outputs cost $0.02: an estimate of **$0.87** with no cache read assumed. The
token counts are the packer's local estimates, which include the images, not the
provider's count. Provider tokenization, request framing or a cache-write rate ($1.25 per
million) can raise the bill; at the cache-write rate the same input costs $1.06. Two
measured charges exist for other request shapes and both are far smaller: the original
request-287 turn returned $0.00817 with cache reads, and the #755 probe returned
$0.02214230 for twelve single-image responses.

Proposed envelope: a **$2.00 maximum**. Before each request the dispatcher computes that
request's worst charge from its estimated input at the cache-write rate plus its capped
output, checks that no request reaches the long-prompt tier of 272,000 prompt tokens, and
sends it only if the returned subtotal plus that worst charge stays within $2.00. There
are eight first attempts in a fixed interleaved order with no automatic retry. The run
stops with receipts kept on a transport failure, a missing cost, an unexpected model or
provider, or a malformed response. A missing charge is recorded as unknown. Scoring is
one blind pass by a host agent and costs nothing at the provider.

## What each result does

The owner decided on 20 November 2026 that a null result closes
[#666](https://github.com/CVX-Hull/enactive/issues/666) as a feasibility stop
([decision log](../decisions/owner-decisions.md)). Applied to the two sizes:

| Result | Reading | Next step |
| --- | --- | --- |
| Shift at the current size | Under normal context, the supplied observation moved the proposals to checking the trunk, and the ordinary player did not propose it. | #666 stays open. One case from one world cannot carry a claim, so the next step is a second scoreable packet from another world, under its own price. |
| No shift at the current size, shift at 64k only | The observation changes proposals only once old turns are dropped. | The lead's reading: #666 closes as a feasibility stop and the finding goes to #664 as evidence for the context cut. |
| No shift at either size, all eight responses scored | Supplying the observation does not change what is proposed here. | #666 closes as a feasibility stop. |
| Inconclusive at either size | Partial coverage is reported as partial, with the counts that exist. | #666 stays open and the owner is asked; no response is added. |

The decision covers a null result. Whether the second row is one is the lead's reading,
not the decision's words, and an inconclusive run is not a null result. Both are put to
the owner with the price.

## Machinery and the one gap

Reused as they are: the four dry packs and their hashes, the packer's sizing, the
readout reserve, the #755 category names, and the campaign credential loader the #755
probe used.

Retained code already sends one-shot proposal requests and keeps receipts in three
places, none tracked: `delayed-observation-cueing-755/replay/pilot.py`, written for the
three #755 cases with a compact prompt and one image;
`2026-11-03-iteration164-runs/trace-cadence-2026-11-04/run-screen.mjs`, which verifies
frozen payloads before sending them; and
`2026-11-05-candidate-research/candidate-research-2026-11-05/identity-current-player/collect.mjs`.
The replay's preparation compares these three and reuses the dispatch and receipt path
that fits, before writing anything.

The gap is narrower than a dispatcher: turning one pack's `common.json`, its retained
images and the optional readout into frozen provider requests. That conversion is a
script kept with the replay's sealed evidence, as those three were. It adds no evaluation
stack and no tracked module.

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
