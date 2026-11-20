---
owner: lead
status: historical
kind: review
date: '2026-11-20'
scope: 'Offline screen of retained cutoffs in worlds other than Malvern for a second packet that can carry the paired replay (#831)'
---

# Screen for a second scoreable packet in the retained worlds (#831)

## At a glance

No retained cutoff outside Malvern is a second, independent packet for the paired replay.
Eight of the nine screened fail the first condition: the sent request already states the
fact, or sends the earlier frame. The ninth, Whitethorn's fishing rod, meets the
conditions a replay can use, but it is the same lineage and the same decision point that
[#755](2026-11-18-delayed-observation-cueing-755.md) already probed with and without the
earlier sighting, it has one context size and not two, and the age of its sighting is not
established by any rendered clock.

A replay on Whitethorn would therefore repeat a result the project has, at fuller
context, for about $0.11. It would not add a second world's evidence in the sense the
[paired replay](2026-11-20-malvern-trunk-paired-replay-829.md) asked for. This record
names no packet and proposes no run.

Offline development evidence only: no game, no model request, $0 spent.
[Paired replay design #824](2026-11-20-malvern-trunk-paired-replay-design-824.md) · [Lookup-effort review #804](2026-11-19-lookup-effort-at-retained-resource-choices-804.md) · [Retained review #791](2026-11-19-retained-memory-decision-791.md)

## The rule applied

The rule is the Malvern design's reading of the conditions in #804, not loosened:

1. the earlier sighting is absent from every text part and every image of the sent
   request;
2. an ordinary handle to it exists before the cutoff;
3. the action's own menu does not show it.

A packet must also allow a hand-written sentence in the Malvern form, stating the
sighting and its age and nothing else, written from a retained frame. And it must come
from a world and lineage not already replayed, since the purpose is a second world.

## What was read

Every figure below is a readback on 20 November 2026 of retained packs under
`.runtime/evidence/`, opened read-only and in place. Nothing was copied, rebuilt or
resealed. An explorer made the first pass; the lead then searched each pack again with
one read-only script, and the counts below are the lead's.

For each pack the script loads `common.json` at both sizes, counts the text parts that
contain the target's key words or its source identifier, and checks whether the earlier
frame's source is among the image parts. The packs are:

- `retained-memory-decision-791/review/earlier-studies/dry-pairs/` (`whitethorn-rod`,
  `townsend-food`) and `.../review/oceana/dry-pairs/` (`oceana-pond`, `oceana-jar`);
- `oceana-farm-memory-788/offline-packing/dry-pairs/` (`grove-route`, `microwave-return`,
  `marked-water-before-map`);
- `retained-two-wake-decision-audit-777/packing/dry-pairs/campground-tool`.

Joanna's matchbox has no retained pack; its row rests on the #804 record's statements.

## The cutoffs

Sizes are the packer's estimated input tokens at the current size and at the 64k target.

| Cutoff | World and lineage | Sizes, images | What the sent request carries about the target | Verdict |
| --- | --- | --- | --- | --- |
| Whitethorn fishing rod, request 19 | Whitethorn, the seven-day lineage | 42,269 at both; 18 | Nothing: no text part contains "rod", "fishing" or the earlier source's identifier, the earlier frame is not sent, and there is no omission record. A journal record committed before the cutoff holds the rod's location and the frame's identifier | Meets the three conditions. Not a second packet: see below |
| Townsend swamp, request 31 | Townsend | 56,119 at both; 29 | Six text parts name the cattail harvest, in the handoff and in delivered knowledge | Fails condition 1 |
| Oceana grove cache, request 45 | Oceana | 56,275 at both; 24 | Two text parts say "grove cache": the handoff and the player's own intent | Fails condition 1 |
| Oceana microwave, request 69 | Oceana | 64,502 and 63,385; 24 | Three text parts name the microwave, among them the intent to read its yield; one names the earlier frame. The earlier frame's list is cut off before the yield, as #804 found | Fails condition 1, and no sentence can be written |
| Oceana marked water, request 18 | Oceana | 33,318 at both; 15 | The handoff names the murky-water tile and its source identifier | Fails condition 1 |
| Oceana pond, request 200 | Oceana | 126,947 and 62,418; 34 and 28 | The earlier frame itself is sent, at both sizes | Fails condition 1 |
| Oceana jar, request 121 | Oceana | 99,103 and 63,128; 36 and 31 | The jar and the funnel are named in eleven and sixteen text parts at the current size, starting with the handoff | Fails condition 1 |
| Joanna matchbox, request 88 | Joanna's Campground | no pack | By #804: the sent intents name the matchbox, and the item menu at request 104 shows both ignition items | Fails conditions 1 and 3, on the record's word |
| Campground vehicle, request 322 | The two-wake Campground | 170,993 and 63,414; 25 | Eleven text parts say "screwdriver", and the earlier frame is sent | Fails condition 1 |

The grove cutoff in #804 is request 42; the retained pack ends one turn before request
45, so the pack read here is not the one #804 described. The handoff that names the cache
is the first part of both.

## Whitethorn

Whitethorn's rod is the one cutoff where the sighting is truly absent. The reasons it is
not the second packet:

- **It is not independent of a result already held.** #755 probed this decision point,
  with the same earlier frame and the same current frame, with and without a sentence
  about the rod. Both responses given the sentence moved from searching recipes to
  checking the earlier location. A replay here tests the same thing again.
- **It has one context size.** The current and 64k packs hold identical history, so the
  comparison of sizes that Malvern gave is not available.
- **The age is not established.** The earlier frame is an item list with a basic fishing
  rod highlighted seven tiles to the north-west, owned by the player's followers. No
  clock or date is rendered in it or in the current frame. #755 wrote "roughly 22 hours"
  from the evaluator's nearest clock readings; #804 treats the age as not established.
  The Malvern sentence states an age; one written here would have to leave it out or
  quote an estimate.
- **The handle belongs to the historical tool contract.** The journal query that could
  recover the rod was part of the earlier player host; the current player uses a
  different journal and delivery boundary, as #791 recorded.

**What a replay on it would add:** the retained request as it was sent, in place of
#755's reconstructed compact prompt; a sentence in the plainer Malvern form; and scoring
under the Malvern design's five ordered categories. **What it would not add:** a second
world's evidence, a second context size, or anything about benefit.

For scale only: four responses at 42,269 estimated tokens would cost about $0.11, taking
the charges the Malvern replay returned for its four requests of similar size ($0.053,
$0.049 and two cached repeats near $0.003). This is not a proposal.

## What a live acquisition would have to supply

No acquisition is proposed. For a retained or future cutoff to serve as a second packet
it needs, together:

- a world and lineage other than Malvern and Whitethorn;
- a sighting that is absent from the sent request at the cutoff: not in the handoff, not
  in delivered knowledge, not in the player's own intents, and with its frame not sent.
  The handoff is what defeated most cutoffs here: a report that states the fact carries
  it into every later request;
- a handle to it under the current tool contract;
- clocks rendered near both the sighting and the cutoff, so the age is read and not
  estimated;
- a cutoff chosen before its outcome is known. Several of the retained cases were picked
  after their branch had been seen.

Two worlds would still not make an effect across worlds.

## Limits

- This is a screen of retained evidence. It measures nothing new.
- "Absent from the text" means the key words and the source identifier were not found by
  a substring search of the pack's text parts. A fact stated in other words would be
  missed. Whitethorn's absence agrees with the cutoff data of #791, which found no prior
  pixels and no omission record.
- Joanna's row was not checked against a pack, because none exists.
- The ages cited for the Oceana cutoffs are taken from #804 and were not re-derived.
- The earlier frames of the Oceana and Campground cutoffs were not opened; none of those
  cutoffs reaches the point where a sentence would be written.
