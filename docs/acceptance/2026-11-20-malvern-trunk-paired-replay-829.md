---
owner: lead
status: historical
kind: measurement
date: '2026-11-20'
scope: 'An eight-response paired proposal replay of the retained Malvern sedan-trunk decision at two context sizes, with and without one sentence stating an earlier sighting (#829)'
---

# Paired replay of the Malvern sedan-trunk decision (#829)

## At a glance

Supplying one sentence about what the trunk showed earlier moved every proposal to
checking the trunk, at both context sizes. All four responses given the sentence proposed
inspecting the sedan trunk and said its contents were unchecked. None of the four
responses without it mentioned the trunk; they proposed waiting for daylight, checking
carried items or getting light. Under the rule fixed in the
[design](2026-11-20-malvern-trunk-paired-replay-design-824.md) that is a shift in
proposed checks at the current size and at the 64k target.

The shift at the current size is the notable part. That request carries a handle to the
trunk frame and a hint naming four trunk items, and the original player made the lookup
at this point. In two ordinary responses here, the replayed player did not.

This shows that the sentence changes what is proposed. It does not show that checking the
trunk was the better move: the trunk holds tools and an extinguisher, the screen is a
scarf recipe that is too dark to craft, and the design counts both kinds of answer as
acceptable. All eight requests completed, for a returned $0.40415340 of the $2.00
maximum. No game was launched.
[Design #824](2026-11-20-malvern-trunk-paired-replay-design-824.md) · [Lookup-effort review #804](2026-11-19-lookup-effort-at-retained-resource-choices-804.md) · [Delayed-observation cueing #755](2026-11-18-delayed-observation-cueing-755.md)

## What was run

The run followed the design and the frozen `protocol.md` in the evidence. In short: the
retained `farm-source-before` packs of the two-wake audit, the context before request 287
of admission 3, at the current size and the 64k target; an ordinary condition and one
with the design's observation sentence in the closing text; two responses per cell; eight
first attempts in a predetermined interleaved order under opaque identifiers; no retry.

- **Route.** OpenRouter, `openai/gpt-6.1-terra`, provider OpenAI only, medium effort, at
  most 512 output tokens. Every response reported that model and provider.
- **Requests.** Built offline and hashed before any was sent. Within a size the two
  conditions are byte-identical outside the closing text; a script checked this. The
  pack's ten tool declarations were attached with `tool_choice` "none".
- **Order of work.** The first request in the frozen order was sent alone and inspected:
  HTTP 200, finished normally, a well-formed answer, a reported charge. The other seven
  followed in one pass. All eight started between 15:32:35Z and 15:33:30Z.
- **Stops.** None fired. No transport failure, missing charge, unexpected model or
  provider, incomplete response or malformed answer.
- **Scoring.** One clean-context reader, given the eight answers sorted by opaque
  identifier, the current frame and the sent hint about the trunk, and the design's five
  ordered categories. It was not given conditions, sizes, the protocol or the schedule.

## Results

In the frozen order. "Repeats the sentence" means the answer cites the earlier trunk view
or names trunk items the sent hint does not.

| Sent | Size | Condition | Category | Repeats the sentence | Proposed action |
| --- | --- | --- | --- | --- | --- |
| 1 | 64k | Ordinary | Grounded alternative | no | "Wait safely in the closed sedan until daylight, then reassess available materials for a warming garment." |
| 2 | 64k | Observation | Targeted grounded check | yes | "Inspect the sedan trunk for the previously seen glowstick and tools." |
| 3 | Current | Ordinary | Grounded alternative | no | "Check the carried inventory for wearable head or mouth protection." |
| 4 | Current | Observation | Targeted grounded check | yes | "Inspect the sedan trunk for the previously seen toolbox and other supplies." |
| 5 | Current | Ordinary | Grounded alternative | no | "Turn on a carried flashlight to enable equipment work in the dark." |
| 6 | Current | Observation | Targeted grounded check | yes | "Inspect the sedan trunk for the previously seen toolbox and other supplies." |
| 7 | 64k | Observation | Targeted grounded check | yes | "Inspect the sedan trunk for the previously seen glowstick and tools." |
| 8 | 64k | Ordinary | Grounded alternative | no | "Inspect whether a portable light is available to enable nighttime crafting." |

| Size | Ordinary: targeted checks | Observation: targeted checks | Under the design's rule |
| --- | --- | --- | --- |
| Current | 0 of 2 | 2 of 2 | Shift in proposed checks |
| 64k target | 0 of 2 | 2 of 2 | Shift in proposed checks |

No answer was scored as absence, unsupported certainty or ungrounded other. Every
observation answer treated the trunk's contents as past and unchecked.

The reader marked one ordinary answer, the fifth sent, as citing an earlier observation
because it says an earlier inventory showed flashlights. That is the carried inventory,
not the trunk, and the answer names no trunk item, so this record counts it as "no"; the
reader named that reading itself.

## Cost and tokens

| Sent | Prompt tokens | Of which cached | Output tokens | Returned charge |
| --- | --- | --- | --- | --- |
| 1 | 42,511 | 0 | 70 | $0.05347 |
| 2 | 42,595 | 3,812 | 69 | $0.0489956 |
| 3 | 116,796 | 3,812 | 64 | $0.14172185 |
| 4 | 116,880 | 3,812 | 74 | $0.14187685 |
| 5 | 116,796 | 116,721 | 152 | $0.00667105 |
| 6 | 116,880 | 116,805 | 72 | $0.00627525 |
| 7 | 42,595 | 42,520 | 78 | $0.002591 |
| 8 | 42,511 | 42,436 | 71 | $0.0025518 |

Returned total: **$0.40415340**. The provider counted fewer prompt tokens than the
packer's local estimates with the readout reserve (116,796 against 145,788, and 42,511
against 65,397). The first request of each kind was charged near the cache-write rate and
its repeat almost entirely at the cache-read rate.

## What it does for the memory study

The design's table gives the next step for a shift at the current size:
[#666](https://github.com/CVX-Hull/enactive/issues/666) stays open, and because one case
from one world cannot carry a claim, the next step is a second scoreable packet from
another world, under its own price. The owner's decisions of 20 November 2026 on a null
result and on a shift at 64k only do not apply, since neither happened
([decision log](../decisions/owner-decisions.md)).

## Limits

- One cutoff from one world. The two responses in a cell are repeats of one request, and
  the second of each pair was served almost wholly from the provider's cache. The two
  observation answers at each size are word for word the same action. These are not four
  independent observations.
- The sentence was written by hand from the trunk frame and names items. An answer that
  goes to look for those items is partly the sentence read back. Nothing here tests a
  memory forming, choosing or delivering it.
- Every observation answer revealed its condition to the reader by naming the earlier
  view. The reader was blind to the assignment, not to that.
- A shift is not a benefit. No action was carried out, and the design holds that a
  grounded alternative is as acceptable as a check here.
- Two ordinary responses at the current size did not propose the lookup the original
  player made. Two responses do not establish how often the ordinary player would.
- At the 64k target the sentence supplied both the sighting and the only handle to it.
- The lead saw the first answer before the blind pass; the scores are the reader's.
- The working folder was first created inside the evidence store's own directory. It was
  moved out, unchanged, before sealing, so the sealed copy is the first sealed state.

## Evidence

Sealed as `malvern-trunk-paired-replay-829` under `.runtime/evidence/`, manifest
`data/evidence/malvern-trunk-paired-replay-829.sha256`. The `replay` folder holds
`protocol.md`, `replay.py` (prepare and run), `assignment.json` with the frozen schedule
and hashes, the eight `requests`, `dispatches.jsonl`, `attempts.jsonl` with each receipt,
the raw `responses` and parsed answers, `blind-readout.json` as given to the reader, and
`blind-scores.tsv`. Assignment SHA-256:
`be835d36ea1e5790d2c0130243601e1acb3e358e6c99705f4ba7722a06fc05f5`.

The dispatch reused the prepare-then-run pattern, receipt fields and cost handling of the
#755 probe's script and the project's credential loader. The one new part is the
conversion of a pack's parts into chat-completions messages with the retained images.
