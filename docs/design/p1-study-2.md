---
owner: lead
status: proposed
date: 2026-11-09
scope: 'Pre-registration of the reshaped ADR 009 P1 offline study (p1-study/2): p1-study/1 unchanged except that one new held-out lineage, lh4 (#522), joins #382 lh1–lh3 behind a re-run power gate (#178)'
review_trigger: Any change to the data, the new lineage's rules, the power plan, the stages or caps, or a section adopted from p1-study/1
---

# P1 offline study, second protocol: pre-registration

Protocol **p1-study/2**, written 9 November 2026 for [ADR 009](../decisions/009-curated-player.md#phases)
P1 (#178). It decides the same question as [p1-study/1](p1-study.md):

> Does a curator (arm B) put in front of a successor actor more of the information that actor
> later went back for than the simpler path without one (arm A)?

**Why a second protocol.** p1-study/1 stopped at its power gate before any replay or spend
([record](../acceptance/2026-11-09-p1-gate-178.md)). #382's three held-out lineages give 27
scoring units (11, 7 and 9), nearly all singleton clusters. Criterion 3 needs at least one lineage
with 20 or more units, so a go was impossible. The owner chose to reshape P1 by adding one held-out
lineage ("Add one held-out lineage", 9 November). Nothing else about the study changes.

**Nothing here runs until the owner approves this page** and the decisions under
[Owner decisions](#owner-decisions). The page is `proposed` until then.

## What carries over unchanged

These sections of p1-study/1, as frozen at
[`5ca2ab9`](https://github.com/CVX-Hull/enactive/blob/5ca2ab90f54b33ab3b09bdaaef46f5f646dd75dd/docs/design/p1-study.md),
are part of this protocol word for word, except where [Deviations](#deviations-from-p1-study1)
says otherwise:

| Section | What it fixes |
| --- | --- |
| [Units](https://github.com/CVX-Hull/enactive/blob/5ca2ab90f54b33ab3b09bdaaef46f5f646dd75dd/docs/design/p1-study.md#units) | Boundaries, primary probes, information clusters (16 bits, complete linkage), scoring units; the lineage as the independent unit |
| [Probes](https://github.com/CVX-Hull/enactive/blob/5ca2ab90f54b33ab3b09bdaaef46f5f646dd75dd/docs/design/p1-study.md#probes) | probe-protocol/1 steps 1–4 unsampled; the tightened blinded confirmation |
| [Arms](https://github.com/CVX-Hull/enactive/blob/5ca2ab90f54b33ab3b09bdaaef46f5f646dd75dd/docs/design/p1-study.md#arms) | Reference, A and B; identical received text; one renderer; the 2,000-token cap; D2 timing; B's settings; two B repeats; freezing after development |
| [Judges](https://github.com/CVX-Hull/enactive/blob/5ca2ab90f54b33ab3b09bdaaef46f5f646dd75dd/docs/design/p1-study.md#judges) | Pinning, the scoring judge, re-judging, the arm-guess check, the auditor and the four frozen briefs |
| [Metrics](https://github.com/CVX-Hull/enactive/blob/5ca2ab90f54b33ab3b09bdaaef46f5f646dd75dd/docs/design/p1-study.md#metrics) | The primary metric, guards and descriptive figures |
| [Decision rule](https://github.com/CVX-Hull/enactive/blob/5ca2ab90f54b33ab3b09bdaaef46f5f646dd75dd/docs/design/p1-study.md#decision-rule) | Criteria 1–7 and the other outcomes, with criterion 3 worded as below |
| [Spend and stop rules](https://github.com/CVX-Hull/enactive/blob/5ca2ab90f54b33ab3b09bdaaef46f5f646dd75dd/docs/design/p1-study.md#spend-and-stop-rules) | Stages 1 and 2, the reserve and every stop rule, with the held-out caps and additions below |
| [Analysis and reporting](https://github.com/CVX-Hull/enactive/blob/5ca2ab90f54b33ab3b09bdaaef46f5f646dd75dd/docs/design/p1-study.md#analysis-and-reporting) | `score`, its refusals, and what a go means |

The rule's constants in [`tools/p1_analysis.py`](../../tools/p1_analysis.py), #462's arms
(`tools/curator_host/p1_arms.py`, `p1_replay.py`) and #519's held-out probe tooling are reused.

**Criterion 3, as coded since p1-study/1 was frozen.** At least one held-out lineage has **20 or
more** units, and every such lineage is above A on the mean. p1-study/1's text left "at least one"
implicit; `primary` has always required it.

## Data and split

| Use | Lineages | Role |
| --- | --- | --- |
| Development | #397 `sd1a1`–`sd1a7` and the six-run #372 sample | Unchanged: build, debug and pilot; decide nothing |
| Held out | #382 `lh1`, `lh2`, `lh3`, and **`lh4`** (#522) | The only data the decision uses |

- **lh1–lh3.** Their probes and ledgers are frozen as #178 wrote them
  ([`frozen.json`](../../data/evaluation/p1/held-out/frozen.json)) and are reused unchanged. The
  lead has read only their counts, digests and cluster structure.
- **lh4 is held out before it starts.** Until scoring, the lead and any operator read only
  counts, digests, cluster structure and the run-health aggregates listed under
  [Running lh4](#running-lh4). Nobody who writes probes, judges or develops the arms sees its
  frames, memory records, notes or reports.
- **The curator's access** is unchanged: probe and ledger files never enter a session.

## Running lh4

#522 runs one lineage under the [campaign-admission](../workflows/campaign-admission.md)
procedure, by the lead alone, through the prepared wrapper with its own project userdir, never
fullscreen. The frozen inputs are #397's
([record](../acceptance/2026-11-07-seven-day-397.md#frozen-inputs)) except where this list says
otherwise. #522 posts its frozen addendum (source, binary and tool digests) before any spend.

- **Source.** The current `main` at #522's freeze, in a clean run worktree, with a fresh adapter
  build and its native check. This is the player any P1 adoption would migrate (an owner decision;
  the alternative is #397's `db38b30`).
- **Start.** S1 Evacuee, no aid, the unchanged player guide; a pristine userdir and a fresh
  `player-memory/2` store. #382's continuation prompt, byte for byte.
- **Route and limits.** #397's: terra, medium effort, at most 400 charged attempts, 7,200 host
  seconds and 7,800 custodian seconds per admission.
- **Names.** Admissions `lh4a1`, `lh4a2`, …, one lineage, one userdir and one store.
- **Envelope.** **$60** under the actual-spend admission rule: an admission starts only while the
  lineage's actual spend plus twice its largest admission stays within $60, the largest taken as
  $7.06 (#382's largest) until one completes. The cumulative total stays within the standing
  $1,000, checked at the freeze.

**Stop rules** (the lineage ends at the first):
1. **Size.** The admission after which the lineage has **10 boundaries** (handoffs inside an
   admission plus admission boundaries, counted from actor directories). At lh1–lh3's 2.3–3.0
   units per boundary this gives about 23–30 units.
2. **Death.**
3. **Eight admissions.**
4. **The envelope.**
5. **Slow:** two consecutive custody stops with one cause.

The lead stops and asks the owner on a continuity failure, a third custody stop, any needed change
to the frozen package, or a lineage that ends under 8 boundaries.

**What the lead may read** between admissions: attempts, decisions, dollars, wall and host seconds,
custody stops, outcome codes, boundary and actor counts, the evaluator's aggregate metrics in the
run ledger, and the run monitor's answers. Not frames, memory records, notes, handoff summaries or
final reports; the operator tooling passes the continuation prompt without displaying it.

**The run monitor.** Every check #397's lead made from frames (a setup restart, continuity at each
boundary, a death) is made instead by a fresh development agent per admission, pinned as the
judges are, that writes probes for no study and develops no arm. Its brief is frozen:

> **Run monitor.** You check one segment of a recorded game session for its operator. Read only
> the file named here and the image files it lists; do not open any other file, run any command
> other than viewing files, or read documents or issues. The file [batch] lists the previous
> segment's last frames, if any, and this segment's first frames, last frames and the frames around
> each handoff. Answer only: (1) does this segment continue the same character in the same world
> as the previous segment's last frames (null if there is none)? (2) does the first segment show a
> new game being set up and saved before play, rather than play? (3) is the character dead in any
> listed frame? (4) does any listed frame show something other than the game in a window (an error
> dialog, a system screen, a full-screen game)? Do not describe the game or what the character
> does. Output only one JSON line:
> {"continues":true|false|null,"setup_restart":true|false,"dead":true|false,"fault":true|false,"frame":"<source id or null>"}.

**Records.** A dated run record with only the aggregates above, ledger rows, and the raw evidence
sealed as its own study. The record names no game content.

## lh4's probes and the gate before replay

#178 then writes lh4's probes exactly as it wrote lh1–lh3's: every probe-protocol/1 candidate
(steps 1–4), unsampled; blinded confirmation in batches of at most 15 pairs under the frozen brief;
the two descriptive ledgers; then a freeze by digest, beside and not replacing lh1–lh3's. The
lineage map (`HELD_OUT` and the probe tooling's held-out lineages) gains `lh4` with its actual
admission names in that change.

**The gate before replay.** `python -m tools.p1_analysis simulate --probes <lh1–lh4 probes>`
re-runs the power simulation on the four lineages' actual units and clusters, with the unchanged
rule. If it fails, no held-out replay starts and the design goes back to the owner. Nothing is
retuned on held-out data.

## Power

The plan is `python -m tools.p1_analysis plan --probes data/evaluation/p1/held-out/probes.jsonl`,
written to [`power-study-2.json`](../../data/evaluation/p1/power-study-2.json): lh1–lh3's actual
units and clusters, plus a simulated lh4 of a given size whose units repeat an earlier lh4 cluster
with probability 1 − 1/(cluster mean). 2,000 simulations per figure (standard error at most 0.011);
everything else as p1-study/1's simulation.

| lh4 units, cluster mean | 0 | 0.10 | 0.15 | 0.20 | 0.25 | 0.30 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 16, any of 1.04 / 1.4 / 3.0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| **20, 1.04 (planning)** | 0.027 | 0.173 | 0.332 | 0.489 | 0.675 | 0.818 |
| 20, 1.4 | 0.034 | 0.177 | 0.306 | 0.467 | 0.620 | 0.777 |
| 20, 3.0 | 0.042 | 0.167 | 0.266 | 0.378 | 0.533 | 0.645 |
| 25, 1.04 | 0.024 | 0.190 | 0.358 | 0.520 | 0.730 | 0.857 |
| 25, 1.4 | 0.032 | 0.172 | 0.310 | 0.484 | 0.661 | 0.815 |
| 25, 3.0 | 0.039 | 0.180 | 0.282 | 0.415 | 0.523 | 0.657 |
| 30, 1.04 | 0.026 | 0.186 | 0.350 | 0.554 | 0.746 | 0.878 |
| 30, 1.4 | 0.025 | 0.186 | 0.337 | 0.505 | 0.689 | 0.818 |
| 30, 3.0 | 0.040 | 0.167 | 0.279 | 0.404 | 0.535 | 0.666 |

**Reading it.**
- **Below 20 units a go is impossible**, whatever the effect: no lineage then meets criterion 3.
- **The planning assumption** is the smallest usable lh4 (20 units), clustered as lh1–lh3 were
  (1.04 units per cluster). Its gate passes, narrowly: 0.818 at the effect of interest and 0.027
  with no effect.
- **Why 10 boundaries.** 25–30 units keep the gate above 0.80 if lh4 repeats somewhat more (1.4).
  If it repeats as much as p1-study/1's planning assumed (3.0), no size in reach passes, and the
  re-run gate will say so before any replay.
- **This plan was made after seeing lh1–lh3's structure,** which the held-out discipline allows; no
  outcome of theirs has been read.

## Stages and caps

| Stage | Data | Cap |
| --- | --- | ---: |
| 0. lh4 (#522) | The new lineage's gameplay | $60 envelope |
| 1. Pilot | #372 `aidB3`, `ceil09` | $12 |
| 2. Development | #397 `sd1a1`–`sd1a7` | $26 |
| 3. Held-out B, repeat 1 | `lh1`–`lh4` | 1.0× the actor's spend on lh1–lh4: $30.44 plus lh4's actual, fixed when #522 ends |
| 4. Held-out B, repeat 2 | `lh1`–`lh4` | The same |
| Reserve | | $20 |

**Added stop rules,** enforced by the operator, as #462's review noted the code does not:
- if repeat 1 reaches its cap, repeat 2 does not start;
- an isolation incident in any stage stops every later stage;
- each stage's cap is passed explicitly and recorded with the stage's label.

**A format check before the arms freeze ($0).** lh4 is recorded on a newer player than every
trace the arms were built on. After #522 ends and before stage 2 freezes the arms, arm A's items
and arm B's per-admission schedule are built on lh4 without any curator session. The lead sees only
counts and exception types. A failure is fixed in the arms before the freeze and recorded as a
deviation.

## Cost estimate

| Item | Basis | Estimate |
| --- | --- | ---: |
| lh4 | About 6 admissions at #382/#397's $5–7 | $30–42 |
| Pilot and development | p1-study/1's estimates | $33–36 |
| Each held-out repeat | 0.61–0.87× the actor's ~$61–72 on lh1–lh4 | $37–63 |
| **Expected total** | | **$137–204** |

The caps sum to $179.88 plus twice lh4's actual spend: about $264 if lh4 spends $42, and $300 if
it spends its whole envelope.

Development-agent tokens, reported in tokens: lh4's probes and ledgers about 3M (lh1–lh3's 3.37M
for 13 chunks); the run monitor under 0.2M; scoring, re-judging, audit and the guess check about
4M.

## Deviations from p1-study/1

1. **Data.** A fourth held-out lineage, lh4, run for the study (#522).
2. **Criterion 3's wording** made to say what the code computes (above).
3. **Planning.** The power plan uses lh1–lh3's actual structure and a simulated lh4; p1-study/1's
   used development data and assumed cluster sizes.
4. **Held-out caps** re-based on the four lineages' actor spend.
5. **The run monitor** replaces the lead's frame checks for a held-out lineage.
6. **The format check** before the arms freeze.
7. **Operator-enforced stop rules,** written out above.
8. **#462's choices,** which p1-study/1 left open, adopted as listed under Owner decisions.

## Owner decisions

Put to the owner with this page:
1. **Approve p1-study/2**, its $60 lh4 envelope and the replay caps above.
2. **lh4's source.** The current `main` at the freeze (recommended: the player an adoption would
   migrate) or #397's `db38b30` (closest to the development data).
3. **#462's recorded choices:** tokens counted as ceil(UTF-8 bytes ÷ 4); a record's `data` folded
   into its statement as `text. key: value; …`; no kind label on rendered lines; a $12 cap per
   curator session; a boundary's cutoff at the successor's first operation.
4. **A's punctuation tell.** When a record's text ends in `!` or `?`, A adds a `.` before its
   data, which only A can produce. Fix it in stage 2, before the freeze (recommended), or leave it
   to the arm-guess check.

## Limitations

p1-study/1's limitations stand, and:
- **lh4's player differs from lh1–lh3's** (`509a9fd7`): `player_handoff` is always listed, the host
  warns before it must stop the actor, and notes keep their first-sent place (#496). Lineage-level
  variation is modelled; a systematic change in where handoffs fall is not.
- **The design followed a failed gate.** It was reshaped after the lh1–lh3 counts were seen, but
  before any outcome.
