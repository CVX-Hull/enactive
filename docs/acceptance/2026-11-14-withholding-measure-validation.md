---
owner: lead
status: historical
kind: study
date: '2026-11-14'
scope: 'The withholding measure revision (#653): the judge codebook (a miss is acting against a fact or an active lookup), re-judged on the pilot''s sealed blind packets by three host Opus judges as development evidence; a frozen known-groups set; the prompt check; binary agreement with specific agreement and AC1; the misses left by arm and unit; the anchor re-judged; and the full study re-sized with the blocked within-unit design and its simulation, with its sensitivity to the anchored rate. No play, no provider spend'
---

# The withholding measure, validated and re-sized (#653)

## At a glance

- **Question.** After the pilot ([record](2026-11-14-withholding-pilot.md)) showed that
  most misses were passive re-exposure and that misses follow the unit, not the arm: does
  the revised judge codebook label misses consistently and as intended, does it leave
  enough misses to size a study, and what size and price does the blocked within-unit
  design ([contract](../contracts/evaluation.md#the-withholding-studys-design-withholding-study-draw1))
  need? This is development evidence about the measure. It does not re-score the pilot,
  whose sealed results stand.
- **The codebook** (in the judge instructions since `d64128b6`): `found_again` is an
  action spent only to learn what the fact says; seeing it on a screen opened to do
  something else, or in a message the game showed on its own, is not a miss. Five
  ordered decision rules and five worked examples, two of them the pilot's disputed
  cases (a list of things to make opened in order to make one; a companion's help shown
  in the game's messages).
- **Re-judged:** the pilot's 15 sealed blind packets, rebuilt unchanged except for the
  instructions (`prompt-check packets`), judged by two host Opus judges and a third on
  the 13 packets holding disputes; all 1,155 pairs resolved, 6 by a label neither of the
  first two gave.
- **Agreement improved.** The first two judges: label κ **0.790 → 0.861** (difference
  +0.071, 95% interval over starts −0.018 to 0.147). On missed vs not missed, positive
  specific agreement **0.705 → 0.889**, negative 0.988 → 0.997, and Gwet's AC1 on the
  pairs that drive the outcome **0.698 → 0.900**.
- **Misses left: 15 of 50 touched units** (0.30), all lookups (the one `against` label
  is on a shared fact, outside the units): withheld 6 of 22, delivered 9 of 28 (before: 8
  of 25 and 13 of 28). This is not only misses removed: 11 unit misses went and 5 came,
  and the touched counts of 8 of the 12 units below changed. Nine distinct units are
  missed at least once (before: eleven). Enough to size a study.
- **Known groups: 20 of 20** under the codebook, 13 of 20 under the pilot's
  instructions. All seven passive-message windows moved from a miss to not missed; the
  three active lookups, five in-line and five did-not-apply windows were right both
  times. The set was picked from the same pilot data that shaped the codebook, and the
  codebook's companion and terrain examples describe the very passive-message windows in
  it, so 7 of 7 there is close to automatic: it shows the rules are applied as written,
  not that they generalize.
- **The anchor, re-judged: no shift.** One clean-context Opus judge re-judged the
  measure gate's 30 owner-labelled pairs (`anchor packets`, the gate's six packets): 20 of
  30 match the owner's blind labels against the gate's adjudicated 21 (shift −1; exact
  interval 0.47 to 0.83), 18 of 20 on the random draw as the gate, and 27 of 30 match the
  owner's checked labels as the gate (shift 0); agreement with the gate's adjudicated
  labels 0.910 (κ 0.711) over 210 pairs. The anchor's prompt is the gate's frozen one, a
  different question, and does not contain the codebook: this shows the judges are as
  the gate's, not that the codebook is right.
- **The study, re-sized.** Each unit withheld in half of the starts of each block,
  analysed within units. At the pilot's price of \$1.476 a start (play and recall):
  - a halving of misses (withheld 0.65 vs delivered 0.33): 80% power at **10 to 12
    starts** (\$15 to \$18);
  - a cut of one third (0.49 vs 0.33): 80% power at **48 to 52 starts** (\$71 to \$77):
    at slope SD 1, 0.80 with one block and 0.79 with two at 48, 0.82 and 0.84 at 52;
  - a cut of one fifth (0.41 vs 0.33): 0.53 to 0.55 at 100 starts, out of reach;
  - with no effect and no unit slope the test rejected in 3.5% to 6.8% of 400 simulated
    studies at 0.05 (standard error about 1.1 points).
- **Why these are smaller than the pilot's 53 starts for a halving.** Three things
  changed at once: the within-unit comparison removes the between-unit spread the
  pilot's pooled test carried; the pilot's sizing started from its observed withheld rate
  (0.32) and halved it, while this one takes the pooled rate as the *delivered* rate, so
  a halving means withheld 0.65, about twice any rate the pilot saw; and the pilot added
  a judge error of 0.10, this one none. The last two favour a small study. With the
  delivered rate anchored lower ([sensitivity](#sensitivity-to-the-anchored-rate)), a
  halving needs about 27 starts and a cut of a third about 95.

## What was run

| Step | Command (at `d64128b6`) | Output |
| --- | --- | --- |
| Rebuild the packets with the codebook | `prompt-check packets codebook-653 --before pilot-619-blind` | 15 judge packets; windows, frames, inputs and facts unchanged |
| Judges A and B | host Opus agents, packet directory only, clean context | 15 answers each |
| Prompt check | `prompt-check report --judges opus-a opus-b` | `prompt-check.json` |
| Judge C | the same, on the 13 packets with disputes | 13 answers |
| Adjudication | `agreement --judges opus-a opus-b --third opus-c` | `adjudicated.json`, 0 unresolved |
| Unit outcomes | `pilot` over the six sealed pilot packages (`knowledge-units/1`) | `pilot.json`, under the codebook labels |
| Binary agreement, known groups, units | `validate_653.py` (sealed with the evidence), using the tool's `binary_agreement` | `validation.json` |
| Study inputs | `study-inputs` over the same packages | `study-inputs.json`: 32 units, spread 0.161 |
| Sizing | `simulate-study --price 1.476`, seed 653 unless stated | `simulation-*.json`, `sim-*.json` |
| Anchor | `anchor packets anchor-653 --gate …/memory-screen-gates-460-386/memory-measure`, one host Opus judge, `anchor events`, `anchor report` | `anchor/report-opus-anchor.json` |

`judged-facts.json` was copied unchanged from the sealed pilot run (SHA-256 `b34f569f…`,
as the pilot's evidence manifest records). The known-groups set
(`known-groups/1`, SHA-256 `ef63b4e1…`) was frozen and posted on #653 before any judging
under the codebook: three windows where the player looked a fact up, seven where the
fact reached the player in a message or on a screen opened for something else, five
clearly in line and five drawn at random (seed 653) from `did_not_apply`. The pilot has
no `against` case, so that group is empty.

## Labels and agreement

| | Pilot instructions | Codebook |
| --- | ---: | ---: |
| Adjudicated labels: `in_line` | 78 | 81 |
| `against` | 0 | 1 |
| `found_again` | 38 | 29 |
| `did_not_apply` | 1,021 | 1,033 |
| `cannot_tell` | 18 | 11 |
| First two judges, label κ (all 1,155 pairs) | 0.790 | 0.861 |
| Dispute rate | 0.048 | 0.028 |
| Missed vs not missed, all pairs: table (both no, A no B yes, A yes B no, both yes) | 1,098, 21, 5, 31 | 1,120, 2, 5, 28 |
| positive / negative specific agreement | 0.705 / 0.988 | 0.889 / 0.997 |
| AC1, all pairs / driving pairs | 0.976 / 0.698 | 0.994 / 0.900 |
| Judge A, B: share of own labels changed | | 6.1%, 6.6% |

The improvement is in the positive side: under the pilot's instructions the second
judge called 21 windows a miss that the first did not; under the codebook, 2. On the 116
pairs that drive the outcome, the five-label κ is 0.680 with 18 disputes, 11 of them
between labels that are not misses but decide whether a unit counts as touched. κ is
reported beside AC1 because misses are rare (the first judge called 33 of the 1,155
pairs a miss; 30 adjudicated labels are), where κ falls even when the judges agree.

## Misses by unit

| Unit | Pilot instructions: missed / touched (withheld; delivered) | Codebook |
| --- | --- | --- |
| article-boiled-egg-2 | 0/0; 3/3 | 1/1; 4/4 |
| article-bindle-2 | 1/1; 2/2 | 0/0; 1/1 |
| article-short-cordage-3 | 0/0; 1/1 | 1/1; 1/1 |
| article-long-cordage-1 | 0/0; 1/1 | 0/0; 2/2 |
| article-burdock-2 | 1/2; 0/0 | 1/1; 0/1 |
| article-cattail-4 | 1/1; 0/1 | 1/1; 0/1 |
| article-shelter-6 | 2/2; 1/1 | 1/1; 0/1 |
| article-textile-crafts-3 | 1/1; 0/1 | 1/1; 0/1 |
| article-footwear-3 | 0/0; 0/1 | 0/0; 1/1 |
| article-companion-4 | 1/1; 3/3 | 0/0; 0/1 |
| article-hauling-2 | 1/1; 1/1 | 0/0; 0/1 |
| article-fishing-6 | 0/0; 1/1 | 0/0; 0/1 |

The misses the codebook removed are the companion's help and terrain messages shown by
the game, and recipe screens opened in order to make the thing. The unit missed most is
one recipe looked up in all five starts that touched it, four of them with its article
delivered: a habit of looking up that delivery did not stop in these starts (the arm
says the article was delivered, not that the player read it). Six starts make no claim
about benefit; the arm comparison above is descriptive.

## The re-sized study

The simulation draws each start's touched units from the per-unit shrunk rates (a beta
prior of strength 2 toward the pooled 0.26 touched and 0.30 missed), adds a start effect
on the log-odds (SD 1.29, matching the measured spread 0.161), and gives withheld units a
shift `log_or` with a per-unit deviation (slope SD 0, 0.5 or 1). `log_or` is solved so
that the delivered missed share is the stated fraction of the withheld one; the pilot's
pooled rate is taken as the delivered rate (0.326 after the start effect). Each
simulated study is analysed with the primary test (2,000 re-draws).

| Effect | Withheld vs delivered | log_or | Power (1 block; 2 blocks), slope SD 1 | Starts for 80% |
| --- | --- | ---: | --- | --- |
| Halving | 0.651 vs 0.326 | 2.15 | 10: 0.83; 0.78 · 12: 0.85; 0.86 · 16: 0.93; 0.93 | 10 to 12 |
| One third | 0.488 vs 0.326 | 1.04 | 40: 0.77; 0.75 · 48: 0.80; 0.79 · 52: 0.82; 0.84 · 60: 0.86; 0.86 | 48 to 52 |
| One fifth | 0.407 vs 0.326 | 0.49 | 100: 0.53 (1 block) | over 100 |
| None | 0.326 vs 0.326 | −0.10 | 20: 0.05; 0.06 · 40: 0.05; 0.08 | |

With slope SD 1 the "none" row is null only on average: each unit has its own effect, so
its 0.08 cell (2.5 standard errors above 0.05) is not a pure false-alarm rate. The pure
null (slope SD 0) rejected 0.07 and 0.05 with one block and 0.04 and 0.04 with two, at 20
and 40 starts. Slope SD 0.5 gives the same sizes as 1 within simulation error; of the effects, slope SD
0 was run only for a halving at 20 starts or more, where power is already 0.96 or above. Blocking by saved moment
costs no power here, because the simulation draws no block effect; its value is that
the result is not one saved game's.

### Sensitivity to the anchored rate

The study inputs were copied with every unit's shrunk missed share scaled down (by 0.5
for a halving and 0.667 for a third; `scale_inputs.py`, sealed), so that the withheld
rate under each effect comes nearer the pilot's 0.27 to 0.32. The start effect lifts the
delivered rate above the scaled pooled value, so it lands at 0.19 and 0.24, and the
withheld rate at 0.39 and 0.36: still above the pilot's, so this too leans small. One
block, slope SD 1, 400 simulated studies each, seed 653.

| Effect | Withheld vs delivered | log_or | Power by starts | Starts for 80% |
| --- | --- | ---: | --- | --- |
| Halving | 0.386 vs 0.193 | 1.31 | 10: 0.47 · 20: 0.74 · 30: 0.84 · 40: 0.90 · 60: 0.96 | about 27 |
| One third | 0.356 vs 0.238 | 0.75 | 40: 0.54 · 60: 0.70 · 80: 0.75 · 100: 0.82 · 140: 0.94 | about 95 |

So the size rests mostly on how many misses delivery can remove, which six starts
cannot say: a halving needs 10 to 30 starts across the two anchorings, a cut of a third
48 to 100.

**Price** at \$1.476 a start, play and recall only, reusing store `v18`; judges are host
agents at no provider spend: 12 starts \$17.71, 30 starts \$44.28, 48 starts \$70.85,
52 starts \$76.75, 60 starts \$88.56, 100 starts \$147.60. The 44 to 52 start points (600 simulated studies each, seed 6531) are
in `sim-e0.667-fine.json`. A second saved moment needs a load check first (one short
custodian run).

## Assumptions

- The pilot's units, touch rates and missed rates hold for the full study's starts; the
  pilot's pooled missed rate is the delivered rate.
- The start spread is a normal effect on the log-odds shared by every unit of a start;
  no block (saved-moment) effect is simulated.
- Judge labels are as consistent as on these packets; the simulation does not add judge
  error, because the measured missed shares already carry it.

## Threats

- **The codebook was written from the same packets it was validated on.** The known
  groups and the agreement gain are in-sample; the full study's labels are the first
  out-of-sample use.
- **The effect sizes are assumptions.** The pilot's codebook labels show no effect
  (withheld 0.27, delivered 0.32 missed), and six starts cannot say how large one is.
- **The sizing favours a small study**: the delivered rate is anchored at the pilot's
  pooled rate and no judge error is added (above and the sensitivity). Judge error in
  the study itself also pulls the arms' judged rates together, so a true effect shows
  smaller than it is.
- **Delivery may change what is touched.** The simulation draws touch independently of
  arm; in the pilot delivered units were touched 28 times and withheld ones 22. The
  primary estimand conditions on touch, so the study reports touch balance beside it.
- **Blocks of an odd number of starts** cannot withhold each unit in exactly half: with
  two blocks the halving needs 12 starts, not 10 (0.78 at 10). A second saved moment may
  also change which units are touched at all, which the simulation does not model.
- **Judging is not free in time.** At the pilot's 43 judgings over 6 starts, 48 to 52
  starts mean about 345 to 375 clean-context host judgings; no provider spend, but host capacity and hours.
- **Some misses may be habits delivery does not change** (the recipe looked up in four
  delivered starts), which would dilute any effect over the store's units.
- **The examples name a companion and eating.** They pass the game-neutral word test
  and name kinds of action general to games of this class, but they lean on this game's
  vocabulary; changing them now would void this validation.
- **The judges are models without human audits**, by the owner's decision "Judges
  without audits".

## Deviations

- The anchor was re-judged with one judge, as the contract's
  [check of a changed judge](../contracts/evaluation.md#checks-of-a-changed-judge)
  compares one new judge with the gate's. The contract and the controls page's
  judge-shift control call for it on a model change; the owner decision "Judges without
  audits" on a change of "prompt or model", so it was run for this prompt change.
- The simulation grid was narrowed from the tool's defaults (sims 400 to 600, chosen
  starts and blocks) to fit the time, unevenly: one and three blocks for the first
  halving grid, one and two for the smaller sizes and the cut of a third, one only for a
  fifth. The seeds and every output are sealed.
- The lead made the review repairs' smallest edits (label text, two error types, a
  lineage check) instead of sending them to the code worker.

## Evidence

Sealed as `withholding-measure-653`
([manifest](../../data/evidence/withholding-measure-653.sha256)): the codebook run
(`memory-measure/codebook-653`: packets, the three judges' events, adjudication, prompt
check, unit outcomes, validation, study inputs and every simulation output), the judges'
answer files, the known-groups set and the validation script. Sealed after the reviews
as `withholding-measure-653-checks`
([manifest](../../data/evidence/withholding-measure-653-checks.sha256)): the anchor run
(`memory-measure/anchor-653`: the gate's six packets, the judge's events and report),
the anchor judge's answers, and the sensitivity inputs, script and outputs.
