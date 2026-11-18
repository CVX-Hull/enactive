---
owner: lead
status: historical
kind: measurement
date: '2026-11-18'
scope: 'A twelve-response paired probe of earlier visible observations and later proposed CDDA decisions in one retained lineage'
---

# Delayed observation cueing in retained CDDA decisions (#755)

## At a glance

In the retained Whitethorn lineage, the earlier rod observation changed both
fishing proposals from recipe search to checking its earlier location. All
lighting responses began with flashlight inspection, and one cue response
added a contingent locker check. The food answers deferred eating. These
are developmental decision proposals with deliberately supplied observations.

## Exact probe

Three later views in [#397](2026-11-07-seven-day-397.md) each kept the same
current frame, compact reconstructed task context, guide, tool descriptions,
model, and one-response allowance. The treatment added one observation from
an earlier visible frame. The control stated that an earlier observation was
unavailable. The request included no scoring labels, later actions, save
data, or callable game tools. Both arms used pinned OpenRouter/OpenAI Terra,
medium effort and up to 512 output tokens. The six pairs were interleaved
before dispatch. Assignment SHA-256
`7f255e90e36b63f047562811d04aaeee1a5798d2f19e3f13f57b72c2fc821e52`
pins the request bodies, sources and rubric. All source moments were previously
inspected. No model answer was fed into gameplay or the curator's store.

| Case | Prior frame → decision view | Approximate game-time separation | Observation available | Observation absent |
| --- | --- | --- | --- | --- |
| Lighting | sd1a2 3312 → sd1a3 216 | 15 hours | Both responses checked the flashlight first. One proposed checking the earlier locker location if fit and power required it. The other cited the old battery and proposed a generic search. | Both checked the flashlight's current power or tried it if charged. |
| Fishing | sd1a2 3312 → sd1a5 351 | 22 hours | Both proposed checking the earlier bench area and verifying the rod's condition. | Both continued a practical recipe search. |
| Food redundancy | sd1a2 12079 → sd1a6 1375 | 9 hours 40 minutes | Both saw enough current food, deferred eating and proposed no cupboard detour. | Both saw enough current food and deferred eating. |

The clock estimates subtract the nearest non-null `steps.game_time`
readings by `seq` in the sealed evaluation records. The decision menus
occlude the clock. Cases cross admission and actor boundaries. Their repeats
and cases remain nested in one world. The independent reviewer scored 12
opaque replies before unblinding. Three targeted checks fell in the treatment
condition. The other nine responses supplied grounded alternatives. There
were no unsupported certainty labels or low-value diversions. One lighting
response cites the earlier location in evidence while choosing a generic check.
It was scored as a grounded alternative under the frozen action rubric.

## Cost, limits and next evidence

All 12 responses returned HTTP 200 from the pinned OpenAI route and a usable
provider charge. Summing `reported_usd` from the sealed `attempts.jsonl`
as decimals gives **$0.02214230** with zero unknown charges. The [evidence index](../../data/evidence/index.json) identifies the
private sealed protocol, assignment, all request and response bodies,
dispatch and charge ledgers, blind readout and ratings.

This test isolates the effect of supplying a hand-selected cue on a proposed
next action with compact common context. It exercises neither the curator's
ability to capture and select that observation nor the effect of executing
the proposed action. It supplies no independent evaluation world or evidence
about several-day retention. Repeat the comparison on independent world
groups after selecting genuinely consequential decisions and their visible
effects. Include current context and stale or contradicted facts so a plausible
cue only counts when it improves a feasible choice. Use real execution to
test those effects. See [#755](https://github.com/CVX-Hull/enactive/issues/755)
and [#666](https://github.com/CVX-Hull/enactive/issues/666).
