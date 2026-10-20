---
owner: lead
status: historical
date: 2026-10-19
scope: Bounded issue71 development extraction and label-readiness pilot; two correlated episodes and seven questions; no runtime memory implementation or held-out policy result
---

# First-campaign memory trace pilot

[#71](https://github.com/CVX-Hull/enactive/issues/71) asks whether actual retained
player-visible traces support a small extraction/label protocol. **Yes, with
important limits:** two episodes from one supervised campaign supply seven useful
questions. Hashes establish the selected byte lineage, while visual interpretation
still needs correction. This does not establish an autonomous player, a complete
benchmark or causal memory benefit.

[Selected labels and source hashes](../assets/memory-trace-pilot.json) contain the
exact7questions and20source references. Raw PNGs/JSON stay project-local and are
unavailable in a fresh checkout. No saves/hidden engine state were read, new game
launched, provider called, package installed or persistent runtime changed.

## Selection and extraction

The source family is `.runtime/campaigns/seven-day-campaign-028/`: the interrupted
water craft/output observations at185/238/297/304 and the final rest alarm,
timeout and later effect at589/590/592. These are diagnostic episodes, not
independent samples: both belong to the same normally created Ned/Belgium campaign.
Its [campaign report](2026-10-19-seven-day-survival.md) and
[water report](2026-10-19-water-coverage.md) preserve the broader sequence.
The episode prefix is not a complete transcript of every intervening action.

Reused Python `json`, `hashlib` and existing image viewing. For each selected row:
read `NNNN-stdout.json` and `NNNN-capture.json`; normalize stdout's direct native
observation versus `state`-wrapped status without treating timeout as a frame;
resolve the frame basename inside that episode's retained `frames` directory;
compare actual bytes/SHA256 with the exact committed historical manifest entry;
check session/revision/boundary correspondence; inspect pixels for the selected
claim. Do not trust capture's absolute local path as a portable location or blindly
follow an arbitrary external path.

All20selected files matched byte lengths/hashes from the committed
[water manifest](2026-10-19-water-coverage-manifest.json) and/or
[campaign manifest](2026-10-19-seven-day-survival-manifest.json). The selected JSON
records name native session `1792428799127-24221-1`. Normal observations have visible
scene provenance; menu frames have null scene. Capture timestamps, receipt order,
historical source commits and game time are different identities. This pilot does
not independently rebuild the historical binary or audit every campaign artifact.

## What the questions show

| Question family | Source and adjudicated result | Consequence |
| --- | --- | --- |
| Historical message versus current progress |185has a start-at0% message and fire-loss message. It does not establish current59% progress.238's wielded unfinished-water sidebar separately shows59%, while its log references starting at24%. | Retain observed time/coverage; do not move a later label onto an earlier frame or call a log line current state. |
| Output versus completed storage |297prompts for six hot clean-water charges and asks pour/ground. Storage is not yet established by that prompt. | Track produced/pending-storage/available independently. |
| Aggregate stock versus craft attribution |304consume menu shows18clean-water charges,2water charges and12rations. It does not attribute all stock to this craft or prove a bottle-fill count. | Inventory coverage and provenance are distinct; do not infer yields from aggregate stock. |
| Acknowledgment versus later effects |590reports timeout for UUID `907f35e9-661d-4c7d-b3f9-8fa445c82517`;592still contains that pending/unknown request. | Later wake evidence does not rewrite the delivery record or permit replay. |
| Request versus elapsed/asleep duration |589highlights an8-hour alarm.592shows a later wake frame; visible calendar clocks differ by10h00m01s. Exact asleep duration remains unknown. | Requested duration, elapsed game time and sleep are different quantities. |
| Partial present visibility |592shows Rest blank, Chilly/Thirsty/Peckish/Fresh and an empty structured visible-creature list. | No global safety or absence of unseen threats follows. |

The dataset separates answer/unknown dispositions and explicitly fallible
interpretation. A mixed question may contain supported counts and an unknown
causal attribution; its answer preserves both rather than forcing a single truth
label over the whole sentence. Unknown is an acceptable label, not an extraction
failure to hide. The free-text form remains a development protocol; a later
benchmark should split such mixed questions into atomic scoring units.

## Errors found and corrected

The first read-only extraction conflated185with a later59% craft state and described
six output charges as though they were the inventory total. It also inferred bottle
fills without sufficient selected evidence. Lead pixel inspection rejected those
claims; source reinspection confirmed the mismatched frames. Even a later correction
calling the logged0% the exact current progress was too strong: the final label
keeps current percentage at185unknown. Original archive bytes remain unchanged.

This is useful negative evidence for correction lineage: genuine files/hashes and
a second reading do not automatically make a semantic claim right. Do not promote
the discarded extraction into a procedural lesson. A clean-context reviewer independently checked20/20source byte/hash/manifest
matches, the14JSON records, six PNGs and all seven labels, with no actionable
defects. The reviewer used committed manifest entries via Git and checked that
raw sources remain untracked. That verifies the narrow label/provenance scope, not
historical capture authenticity or every prior actor's access. Protected publication
and issue closeout retain their separate checks.

## Readiness, limits and next work

Useful families are temporal state, coverage/provenance, unfinished work/output,
unknown transport and outcome attribution. Full-history packet, existing TaskMemory
and exact scoped replay can be diagnostic inputs, but current TaskMemory accepts
only normal-play evidence; it cannot faithfully ingest these menu/activity cases
without the reviewed change in [mission design](../design/player-owned-mission.md).
A matching schema or replay answer is not actual decision/execution utility.

No extraction pipeline or new database was necessary. The labels cost manual
source opening, hash checks, pixel interpretation and correction. External model
tokens, inference latency and cost were not exposed and remain unknown; measured
whole tool gaps cannot supply them. Original frame files are ~native screenshot
size; the committed dataset stores references/hashes, not a second raw archive.
Existing retention/publication/licensing rules govern any later image redistribution;
this pilot publishes no new raw screenshot, absolute Mac path or hidden data.

For #70, narrow the next research design to these temporal/coverage/unknown-effect
families only if additional independent episodes can be legitimately acquired.
Keep that aggregate Backlog/L/Low until source-separated acquisition and scoring
are scoped; its full experiment is not a #140 functional delivery gate. There are
no independent campaign splits, rarity coverage, frozen causal comparisons or
controlled model rankings here. All selected episodes/questions are development
data excluded from future deciding memory/policy tests. No hypothetical action
can inherit the recorded future after its trajectory diverges.

For #137/#140, implement source-linked semantic correction and pending-work/current
state views, preserve uncertainty, and obtain fresh native continuity evidence in
#144. Additional acquisition is needed for source-separated efficacy, broad menus,
relocalization ambiguity, latent threat/supply uncertainty and independent campaigns.
Do not invent labels for missing context. A working mission store still cannot
claim memory learning benefit from this pilot.
