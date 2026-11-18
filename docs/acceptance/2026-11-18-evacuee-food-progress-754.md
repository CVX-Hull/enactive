---
owner: lead
status: historical
kind: review
date: '2026-11-18'
scope: 'Six frozen retained packets test scoring ration acquisition and use with a strict named living endpoint and an exploratory linked endpoint'
---

# Food progress and living endpoint feasibility (#754)

## At a glance

Both fresh #751 lineages support the food-acquisition-and-use component.
Neither meets the strict named-living endpoint rule in the frozen assignment.
One meets the exploratory rule that links an earlier named view to the endpoint.
The other assignment lacks an in-scope named view.

## Frozen packets

The [frozen assignment](assets/evacuee-food-progress-754-assignment.json)
pins six packets, covering 19 distinct PNGs, with source hashes and operation
intervals. Its SHA-256 is
`5320dca6aa60005edd8e2c89f21d9e5106d880d7fb7329e135d6c5073b4b1857`.
The independent clean-context reviewer verified the hashes and source bindings
and agreed on these dispositions. The control rules and outcomes from
[#690](2026-11-17-cdda-outcome-feasibility.md) are retained.

| Assessed interval | Ration task | Strict composite | Linked composite |
| --- | --- | --- | --- |
| Bowdle, ops 17–32 | Positive. No ration in 282, two acquired in 432, selected in 505, eaten in 507 with 800 kcal and one left in 509. | Unknown. The endpoint shows living inventory without the survivor's name. | Positive. Frame 277 names Morgan Vale in the same uninterrupted chain. |
| Bowdle early, ops 17–24 | Incomplete at the cutoff. Frame 389 shows flashlight use before food acquisition. | Boundary. Name unresolved at endpoint. | Boundary with living linkage from frame 277. |
| Nancy, ops 18–51 | Positive. Frame 1079 shows one pickup. Frame 1111 distinguishes it from 21 nearby. Frame 1113 shows consumption, 800 kcal, and the 21 still nearby. | Unknown. Frame 1127 shows active gameplay with no survivor name. | Unknown. The assigned identity role in frame 271 contains inventory only. |
| Nancy early, ops 18–22 | Incomplete during initial movement and a climb attempt. | Boundary with identity unresolved. | Boundary with identity unresolved. Melva Woodard is the nearby character. |
| #397 sd1a7, first/last | Unknown task. Load cannot supply a task baseline. | Negative from named death of Morgan Hale in 12318. | Negative from named death. The load frame supplies no earlier identity link. |
| #642 delivery, first/last | Unknown task at title/load. | Boundary with living endpoint unknown. | Boundary with living endpoint unknown. |

The early windows share their corresponding world. The two old controls share
one source cluster. All six are development evidence. The Nancy assignment
error illustrates why the next capture plan must explicitly require a
player-identifying view. A strict outcome needs a named living endpoint. The
exploratory outcome needs an in-scope name and a traceable uninterrupted chain.
Both also need genuine negative task cases, unresolved cases and a separately
frozen held-out split by world or lineage. Independent blind scoring and an
adjudicated reference must support a predeclared qualification criterion.

Defer reader qualification under [#681](https://github.com/CVX-Hull/enactive/issues/681).
This completes the bounded retained-source readback [#754](https://github.com/CVX-Hull/enactive/issues/754)
with zero provider calls.
