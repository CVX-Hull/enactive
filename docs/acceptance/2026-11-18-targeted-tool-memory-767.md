---
owner: lead
status: historical
kind: run
date: '2026-11-18'
scope: 'Two fresh Evacuee equipment contrasts and three same-survivor reloads seeking a consequential delayed tool or supply choice'
---

# Delayed tool and supply decisions in two Evacuee worlds (#767)

## At a glance

The approved capture ran five admissions across two fresh worlds. Both
survivors saved alive. Villa Heights advanced 1h 12m 44s and Cheneyville
advanced 11m 39s in game. Neither reached a natural waking period or a
qualifying delayed choice. The longest in-game interval was a one-hour
wait in Villa Heights. The [run ledger](../../data/evaluation/runs.jsonl)
records OpenRouter returns and unpriced attempts.

## Frozen study and amendments

The owner approved $65 for two serial fresh worlds with at most two
eligible same-survivor reloads each. Every slot had an 80-minute custody
limit, 70 actor minutes including ten minutes of ending reserve, 400
combined attempts including up to 40 recall attempts, and an $8.00
provider-reported stop threshold. The pinned OpenRouter OpenAI Terra
medium route used ordinary knowledge v18, a configured 262,144-token
player window and a 39-image projection. The study sought an earlier
specific equipment or supply fact and a later consequential choice,
ordinarily after waking. Qualification required an auditable gap in the
ordinary sent inputs for that fact, an accounted ordinary access path or
uncertainty, a useful visible effect and a named living view near the effect.

The source was `260d98ce8a20fb37c9d202d3d6087c35fbba34b4`. The proposal
seal was
`171dd3bf78ab92da7f7c1f6a9ad4977abc4e7123ad44df4e9ab5c8ad2b85f555`.
The first two actors chose early saves well within the slot limits.
The lead added a prospective, independently reviewed timing clarification
for the remaining slots. It described early work as interim and asked
the player to continue through one natural waking period when feasible,
with the player retaining every choice and the option to end safely.
The amendment SHA-256 was
`e0949be49d3f7880ec78111b29734543505367f911bc27ae7f27854f97c39e0e`.
The study provides descriptive evidence across those conditions.

| World and admission | Session | Manifest SHA-256 |
| --- | --- | --- |
| Villa Heights fresh start | `499bb1a9389849a38b91f60171fd66f4` | `c7a9c4dee56a71c2413d42072c369e3afce1037ee97b93e34bfc708431ff9eb6` |
| Villa Heights first reload | `537a6c09ae6e44f5866fdc140025b600` | `b94a15001728ae06bc56b8891f0da4d092a17457945ee7c2c0e5e16d26e90d14` |
| Villa Heights second reload | `b438bc1127054ac6a4662277c370be93` | `e0a61dad285fbf16de1551e282b788a8df8874689e6294d5b63e6356b71d6331` |
| Cheneyville fresh start | `e3c8aeb37e804c8787d31bc3d8f4ad66` | `4d63758ebc83e0cac561862ff3b733bfa8fe5d9e753bdda18523a4f552fc0038` |
| Cheneyville first reload | `2c50abea682d472fb59bf55cbf9e20de` | `4857f9601043f9a929194da0a99594147c8e430f0815faf45d03de05cab37fb9` |

## Visible play and decision opportunities

**Villa Heights.** Setup frames 242, 305 and 455 confirm the Open
Floorplan Evacuee shelter, Home Mechanic and named Manuel Henderson at
08:00:00 on spring day 61. The first reload matches the 08:08:29 save
time and fists in frame 209, with Manuel named in 233. Manuel recruited
Curtis Dewitt, surveyed the basement and saved at 08:09:40 (1082 and
1538). The next reload matches the saved clock, equipment and name in
207 and 235. After finding the roof tank frozen, Manuel saw a broken
shelter window and a nearby threat (1760 and 1977), withdrew, and waited
one hour (2394–2563). Frame 2632 names Manuel alive at 09:12:44 and
2634 shows the Save. The world used all three slots.

**Cheneyville.** The fallback addressed the documented water and shelter
gap with a different interior and starting kit. It started in a fresh
world and journal. Frames 227, 281, 373, 375 and 381 show the
Compartmentalized Evacuee shelter, Electrician and Morgan Vale at
08:00:00 with the charged flashlight. Morgan obtained water and then
withdrew from a pursuing hostile. Frames 4125 and 4127 show a named
08:04:35 forest checkpoint and Save. The first reload matches the clock,
equipment and Morgan's identity in 210 and 242. The game log records
Rosaura's death at 08:05:51 (823), and the original pursuer's death by
08:06:14 (1030). Visible threats blocked the shelter return. The actor
sought another place to recover and saved alive at 08:11:39, injured and
still pursued (4799 and 4849). Frame 4851 shows the Save prompt and
4947 shows the return to title. Morgan's last displayed name was
earlier. Independent review found no name tied to the final checkpoint and no
feasible delayed objective from that state. The sixth slot stayed closed.

| Candidate | Earlier observation | Later input and outcome |
| --- | --- | --- |
| Return for Villa Heights rations | The kitchen cupboard showed 15 ordinary, five cold and one frozen box of protein ration (request 38, frame 785 around 08:00:04–14). Manuel took two boxes (794). | The handoff carried the collected rations. No later restock choice tested the earlier remainder. |
| Revisit Villa Heights roof water | The tank displayed 12.25 L of frozen clean water and unavailable drink and dispense actions (request 32, frame 1219 around 08:11:21–24). The operator recorded the candidate before any later recheck. | The breach and nearby threat displaced shelter work. No later refill decision or useful water effect was observed. |
| Return to Cheneyville lockers | Locker and pickup frames 2693 and 2699 show the water source and a picked-up bottle at 08:02:43. The intact handoff says Morgan had collected rations and clean water. | The reload tried to return and redirected west as threats intervened. The captured decisions at requests 62 and 69 have 219/219 and 228/228 exact sent parts, including the handoff and current map or threat cues. No replenishment or associated equipment effect followed. |

Villa Heights first-reload request 31 also had all 124 sent parts
reconstructed. The prior report and current conversation supplied
ordinary cues for the short recruitment interaction.
`python -m tools.evaluate evaluate-lineage` counted 145 decisions and
4,364 game seconds in Villa Heights, including the one-hour wait, and
210 decisions and 699 game seconds in Cheneyville. The sealed outputs
are `operator/evaluate-primary-lineage.json` and
`operator/evaluate-fallback-lineage.json`. Its three boundary readings
gave zero clock gaps and unknown identity. Named game views supply
the manual identity evidence for those reloads. The sealed
`operator/terminal-audit.py` sums provider-reported input, cache reads
and cache writes on each player call. The per-slot maxima ranged from
40,090 to 67,384 tokens within the configured window. Distinct starts
and exact input reconstruction improved development coverage. The short
game horizons and displaced objectives yielded zero qualifying decisions
and leave the memory comparison unresolved.

## Charges and custody

The [run ledger](../../data/evaluation/runs.jsonl) contains the five
study 767 rows, with attempts, wall seconds and reported and unpriced
charges. Run `python -m tools.run_ledger totals --study 767` to derive
the reported subtotal. Every attempt reconciled to one completion. The
settled HTTP 429s lacked provider-returned amounts and remain unknown.
Preflight accepted a descriptive primary start label that the ledger
rejected. The lead verified the settled receipts and recorded the
derived row under the ledger's `S1` code, preserving the original
manifest and receipt.
Successors used native-valid `S1` and `S2`. The validation gap is
tracked in [#768](https://github.com/CVX-Hull/enactive/issues/768).

All five saves returned to title. Each separate Quit had uncertain
delivery on native EOF and was collected on its original ID without
replay. The driver dispositions remain `interrupted`. Independent
custody receipts confirm native exit zero before signals, no live
owned actor and released input. All 30 owned process groups were absent,
all 15 bridge, viewer and gateway ports could bind, and the shared
game lock was available. Unused study authority closed.

The [evidence index](../../data/evidence/index.json) identifies the
sealed private packages, captures, userdir snapshots, cutoff evidence,
evaluator results and accounting. All 1,142 sealed file hashes passed
verification. The lead compared five working packages, six archive
directories and five spectator recordings with their sealed copies
and retired the verified duplicates under the game lock. The original
82-file Townsend userdir was restored byte for byte. Both study saves
were retained.
