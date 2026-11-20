---
owner: lead
status: historical
kind: review
date: '2026-11-20'
scope: 'Offline screen of retained cutoffs in worlds other than Malvern for a second packet that can carry the paired replay (#831)'
---

# Screen for a second scoreable packet in the retained worlds (#831)

## At a glance

None of the retained cutoffs considered here is a second, independent packet for the
paired replay. Nine were screened against the packs. Eight of them fail the first
condition: the sent request already states the fact, or sends the earlier frame. Ten
more had already been set aside by the records that built them, because an ordinary cue
or the fact itself was in the sent request.

The ninth screened cutoff, Whitethorn's fishing rod, meets the conditions a replay can
use. It is not a second packet: it is the lineage and the decision point that
[#755](2026-11-18-delayed-observation-cueing-755.md) already probed with and without the
earlier sighting, it has one context size and not two, its handle belongs to an earlier
tool contract, and the age of its sighting has not been established.

A replay on Whitethorn would re-test a decision point the project has probed, at fuller
context. It would not supply a second world. This record names no packet and proposes no
run.

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

A cutoff that fails condition 1 was not taken further: its menu, its handle and whether a
sentence could be written were not assessed, except where a row says so.

## What was read

The counts below are a readback on 20 November 2026 of retained packs under
`.runtime/evidence/`, opened read-only and in place. Nothing was copied, rebuilt or
resealed. An explorer made a first pass; the lead then searched each pack again, and the
counts are the lead's.

The search was one short read-only script, written for this screen and not kept: it is
neither tracked nor sealed. For each pack it loaded `common.json` at both sizes, counted
the text parts containing each of a few strings, without regard to case, and checked
whether one named earlier frame was among the image parts. It did not look for the fact
in other words, and it did not inspect what the other sent images show.

The packs are:

- `retained-memory-decision-791/review/earlier-studies/dry-pairs/` (`whitethorn-rod`,
  `townsend-food`) and `.../review/oceana/dry-pairs/` (`oceana-pond`, `oceana-jar`);
- `oceana-farm-memory-788/offline-packing/dry-pairs/` (`grove-route`, `microwave-return`,
  `marked-water-before-map`);
- `retained-two-wake-decision-audit-777/packing/dry-pairs/campground-tool`.

Joanna's matchbox has no retained pack; its row rests on the #804 record's statements.
The lead opened one frame, Whitethorn's earlier frame.

## The cutoffs screened against the packs

Sizes are the packer's estimated input tokens at the current size and at the 64k target.
Counts are text parts containing the string, at the current size and then at 64k where
they differ.

| Cutoff | World and lineage | Sizes; images | What the sent request carries about the target | Verdict |
| --- | --- | --- | --- | --- |
| Whitethorn fishing rod, request 19 | Whitethorn, the seven-day lineage | 42,269 at both; 18 | No text part contains "rod", "fishing" or the earlier frame's identifier, at either size. The earlier frame is not among the images, and no part is an omission record. A journal record committed before the cutoff holds the rod's location and the frame's identifier. The current frame is the short-cordage recipe search, which shows no rod | Meets the three conditions. Not a second packet: see below |
| Townsend swamp, request 31 | Townsend | 56,119 at both; 29 | Six text parts contain "cattail": the handoff, which names the harvest, and delivered food guidance about cattails | Fails condition 1 |
| Oceana grove cache, request 45 | Oceana | 56,275 at both; 24 | Two text parts say "grove cache": the handoff and the player's own intent | Fails condition 1 |
| Oceana microwave, request 69 | Oceana | 64,502 and 63,385; 24 | At both sizes three text parts name the microwave, among them the intent to read its yield, and one names earlier frame 938. Neither earlier frame is sent. By #804, the yield list in the other earlier frame, 939, is visible only in part: seven items and "and 1" before a scroll marker, with no sheet metal in the visible part | Fails condition 1, and the frame cannot support a sentence about sheet metal |
| Oceana marked water, request 18 | Oceana | 33,318 at both; 15 | One text part, the handoff, names the murky-water tile and its source identifier | Fails condition 1 |
| Oceana pond, request 200 | Oceana | 126,947 and 62,418; 34 and 28 | The earlier frame is sent at both sizes, and one text part names it | Fails condition 1 |
| Oceana jar, request 121 | Oceana | 99,103 and 63,128; 36 and 31 | "jar" is in eleven text parts and "funnel" in sixteen at the current size, nine and fourteen at 64k, starting with the handoff. The earlier frame is not sent | Fails condition 1 |
| Joanna matchbox, request 88 | Joanna's Campground | no pack | By #804: the sent intents name the matchbox, and the item menu at request 104 shows both ignition items | Fails conditions 1 and 3, on the record's word |
| Campground vehicle, request 322 | The two-wake Campground | 170,993 and 63,414; 25 | At both sizes eleven text parts say "screwdriver", three name the earlier frame, and the earlier frame is sent | Fails condition 1 |

The grove cutoff in #804 is request 42; the retained pack ends one turn before request
45, so the pack read here is not the one #804 described. The handoff that names the cache
is the first part of both.

Four of the eight failures are carried by a handoff across a reload: Townsend, the grove,
the marked water and the jar. The other four fail inside one admission: two because the
earlier frame is still sent, two because the player's own earlier intents name the
target.

## Retained cutoffs set aside by their own records

These have retained packs or windows and were not searched again. Each was already
classed by the record that built it as having the fact or an ordinary cue in the sent
request, or as following a lookup.

| Cutoff | Record | Why it was set aside there |
| --- | --- | --- |
| Townsend tea recheck | [#765](2026-11-18-retained-memory-replay-765.md) | "Related status sent": the prior report states the recipe was unavailable |
| Scipio roof-water recheck | [#765](2026-11-18-retained-memory-replay-765.md) | "Sent": the intact report carries the fact |
| Oceana grove re-find, request 74 | [#788](2026-11-19-oceana-farm-memory-788.md) | Map note and route preview are in the sent request at both sizes |
| Oceana first-wake recheck, request 51 | [#788](2026-11-19-oceana-farm-memory-788.md) | The current scene includes the place |
| Oceana hearth, request 225 | [#788](2026-11-19-oceana-farm-memory-788.md) | An ordinary menu choice carries it |
| Oceana marked water after lookup, request 19 | [#788](2026-11-19-oceana-farm-memory-788.md) | It follows the lookup; the map note is visible |
| Two actor handoffs, cupboard water and pot search | [#757](2026-11-18-delayed-decision-feasibility-757.md) | The successor's prompt or the carried record already holds the fact |
| Landover companion and washroom | [#757](2026-11-18-delayed-decision-feasibility-757.md) | The earlier views were still sent, seconds earlier |

## Whitethorn

Whitethorn's rod is the one cutoff where this screen and
[#765](2026-11-18-retained-memory-replay-765.md) both found the sighting absent. #765
bound all 74 parts, found no location or source identifier for the rod in the text, and
reviewed all 18 sent frames, finding hook and rod recipes and no visible rod location.
The reasons it is not the second packet:

- **It is not independent of a result already held.** #755 probed this decision point,
  from the same earlier frame to the same current frame, with and without a sentence
  about the rod. Both responses given the sentence proposed checking the earlier
  location. A replay here would probe that decision point again. It would not be the same
  test: #755 used a compact reconstructed prompt with one image and told the other
  condition that no earlier observation was available, where the retained request has 74
  parts and 18 images and says nothing. What it would show is not known.
- **It has one context size.** The current and 64k packs hold identical history, so the
  comparison of sizes that Malvern gave is not available.
- **Its age has not been established.** Neither Malvern's frames nor Whitethorn's render
  a clock. For Malvern, #804 bracketed both frames between clock readings a few seconds
  and about a minute apart, which gave "about 11 h 40 min". For Whitethorn, #755 gives 22
  hours as an approximate separation, and #804 records no clock near either frame and
  treats the age as not established. A sentence written here would leave the age out or
  quote that approximation.
- **The handle belongs to an earlier tool contract.** The journal query that could
  recover the rod was part of the earlier player host; the current player uses a
  different journal and delivery boundary, as #791 recorded.

The lead opened the earlier frame. It is an item list with "basic fishing rod"
highlighted at seven tiles north-west, the detail pane giving its owner as "Your
Followers", in a room with benches. No clock or date is on it. A sentence could state
that sighting.

**What a replay on it would add:** the retained request as it was sent, in place of
#755's reconstructed prompt; a sentence in the plainer Malvern form; and scoring under
the Malvern design's five ordered categories. **What it would not add:** a second world's
evidence, a second context size, or anything about benefit.

For scale only, and not a proposal: four responses would cost about $0.11 if the provider
counted and cached them as it did Malvern's four smaller requests ($0.05347, $0.0489956,
$0.002591 and $0.0025518). Those were about 42,500 tokens as the provider counted them,
from a packer estimate of 65,397 with the reserve. Whitethorn's 42,269 is a packer
estimate before the reserve, so its provider count would be lower. The two cheap charges
were cache reads on repeats; without them the figure roughly doubles.

## What a second packet would have to supply

No acquisition is proposed. For a retained or future cutoff to serve as a second packet
it needs, together:

- a world and lineage other than Malvern and Whitethorn;
- a sighting absent from the sent request at the cutoff: not in the handoff, not in
  delivered knowledge, not in a tool result or a player hint, not in the player's own
  intents, and with its frame not sent;
- an action menu that does not show it;
- a handle to it under the current tool contract;
- an earlier frame that shows the sighting whole and legibly, so the sentence can be
  written from it;
- clock readings in, or closely bracketing, both the sighting and the cutoff, so the age
  is bracketed and not guessed;
- enough history to exceed the 64k target, if the two sizes are to be compared;
- a cutoff chosen before its outcome is known. Several of the retained cases were picked
  after their branch had been seen.

A replay on such a packet would support claims about proposed decisions only, not about
what would happen in play. Two worlds would still not make an effect across worlds.

## Limits

- This is a screen of retained evidence. It measures nothing new.
- The conclusion covers the cutoffs listed in the two tables. Other retained material may
  hold decision points no record has yet framed as a cutoff.
- "Absent" for the screened packs means a few strings and one frame identifier were not
  found. A fact stated in other words, or visible in another sent image, would be missed
  by the script. For Whitethorn the absence also rests on #765's review of the text and
  all 18 frames.
- The script and its output are not sealed, so the counts can be reproduced only by
  searching the named packs again.
- Joanna's row was not checked against a pack, because none exists.
- The cutoffs in the second table were not searched again; their rows repeat their own
  records.
- Only Whitethorn's earlier frame was opened. The earlier frames of Townsend, Oceana and
  the Campground were not; none of those cutoffs reaches the point where a sentence would
  be written.
- A paired replay supports claims about proposed decisions only.
