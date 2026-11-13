---
owner: lead
status: historical
date: '2026-11-13'
scope: 'Historical: the three gates ran and reported on 13 November 2026, and the owner replaced the comparison described here with the withholding design in general-memory.md. Protocol for testing memory in play (#590): three gates that cost little and are decisive, and a comparison of short starts from a copy of the held-out lineage''s saved game whose size is not requested until the gates have measured what it depends on. Arms, the first store, the start, the measure and its judge, the decision rule, a simulation of what the measure can detect, the interface the build shares, cost and stop rules.'
review_trigger: A gate in this note reports, the comparison is sized, or the context design it tests changes
---

# Memory screen: protocol

## At a glance

- **Question.** Does a player that is given stored knowledge at the start of each actor
  miss less of what its game has already found than the current player does?
- **What the free checks found**
  ([record](../acceptance/2026-11-13-memory-screen-free-checks.md)).
  1. **The curator's recorded store holds one of the four lost facts.** It has the roof
     tank and not the rations, the rod or the batteries, although each was on screen in
     admissions it read. A briefing would have reached the actor before the need in all
     four cases. So what failed in the record is what the curator writes, not when it
     is delivered.
  2. **The player's own records hold the three stored losses**, but only as phrases
     inside whole records, about 21,000 bytes in all.
  3. **Short tool results do most of the work on prompt size.** The cut adds a further
     saving only if the curator stays within about 24 decisions of play.
- **The comparison cannot be sized yet.** At the sizes this project can afford, the
  measure detects a halving of missed knowledge about half the time (simulated:
  0.54 with twelve starts per arm, 0.38 with three arms). The simulation rests on three
  numbers nobody has measured: how many known items a start touches, how often the
  current player misses them, and how often the judge is wrong.
- **Proposal.** Approve three gates now. Each is cheap, and each can stop the work.
  1. **Brief gate, about \$22, stop at \$45.** A curator with a brief for places and
     goods runs over the seven-day lineage. It must store at least three of the four
     lost facts with their places.
  2. **Measure gate, \$0 on the provider.** On sealed admissions, measure the three
     numbers above.
  3. **Session price pilot, about \$12, stop at \$20.** Ten curator sessions over sealed
     windows of 20 decisions, to price sessions during play.
- **Then** the lead returns with measured numbers and either a comparison sized to
  detect its effect, with its envelope, or a plain statement that no affordable
  comparison can, and what to do in its place.
- **Not requested now.** The first store for the held-out lineage, any game launch, and
  the comparison's envelope.
- **Owner decisions.** The four questions under [owner decisions](#owner-decisions) are
  answered in the [owner decision log](../decisions/owner-decisions.md): both paid gates
  are approved inside one \$65 envelope, the cut stays out of the first comparison, and
  the owner labels the judge's calibration set. This note is the working description
  of the gates.

Terms are in the [glossary](../glossary.md). A **start** is one run of one actor from
the copied saved game. A **known item** is one entry in the frozen list described under
[the measure](#the-measure).

## What this tests and what it does not

- **It tests the briefing**, the context design's second layer. Short tool results, the
  first layer, are in every arm.
- **It does not test the cut**, the third layer. This departs from the owner's "test
  all three" and is put to the owner below
  ([the reasons](#the-cut-and-curator-sessions-during-play)).
- **Its result holds for one saved game**, on one route and one model. It is a screen
  for the owner's next decision, not evidence that the design generalises.
- **It does not test a week**, or writing during play. The oldest fact in the start
  state is about 28 game hours old, and a start is one actor.

## The gates

### Brief gate

- **The change.** The curator's brief asks for where goods and useful things are, one
  fact per item. The fact format gains `subject`, `place`, `game_time` and a kind (place
  with goods, hazard, open commitment, how the game works). This is a contract change:
  the gate closes the set of fact keys today, and the curator's prompt defines a fact as
  not a log of what was seen.
- **What runs.** The curator, on the actor's model, over the seven-day lineage's
  admissions `sd1a1` to `sd1a6`, one session per admission. Those six sessions cost
  \$22.32 in the shadow run.
- **The check.** Frozen before the run: for each of the four lost facts, a pair of
  patterns on the new `subject` and `place` fields. A fact passes when both match and a
  clean-context reviewer who reads it confirms that it says where the thing is. The
  search on free text is not used; on today's store it matches facts under all four
  labels although three are absent.
- **Kept honest.** The brief does not name the four items or their places. One brief is
  tried; a second attempt is a deviation and is reported. The store's size is reported
  with the result.
- **Pass:** at least three of the four. **Fail:** stop and report.
- **Sessions.** The first session is read end to end before the others run. Each
  session's cap holds at least two worst-case requests. A session that reaches its cap
  is recorded and its admission is run once more with twice the cap; a second cap
  stops the gate.

### Measure gate

No game runs and nothing is spent on the provider. It uses the seven-day lineage's
sealed admissions `sd1a5` to `sd1a7`.

- **It builds the known-item list** for those admissions as [the measure](#the-measure)
  says, from the frames up to the end of `sd1a4`.
- **It measures three numbers**, each with an interval:
  - known items touched per 200 decisions;
  - the share the recorded player missed;
  - the judges' agreement with each other and with the owner's labels, and the share of
    "cannot tell".
- **It re-runs the simulation** on those numbers and reports the smallest comparison
  that detects a halving four times in five, with its cost.
- **Limits.** Three admissions of another game cannot fix these numbers closely, and two
  of them hold known misses. The result sizes a comparison; it does not show a benefit.

### Session price pilot

Ten curator sessions, each over a sealed window of 20 new decisions of the seven-day
lineage with the store as it stood, and no game running. It reports dollars and seconds
per session.

- **Measured.** Ten sessions over windows of 20 decisions cost a median of \$0.20 and
  took a median of 99 s, \$2.34 in all against \$2.98 for the recorded play in the same
  windows. Where the player's prompt was under 80,000 tokens a session cost two to
  three times its window of play ([record](../acceptance/2026-11-13-session-price-pilot.md)).
- **What it settles.** Whether the cut, which needs the curator within about 24
  decisions of play, is affordable at all.

## The comparison, if the gates pass

### Arms

| Arm | First message | Tool results | Store tools |
| --- | --- | --- | --- |
| Current | The mission and the previous final report, as a new admission gets today | Short | The player's own store, unchanged |
| Curator briefing | The same, plus a briefing built from the curator's store | Short | Unchanged |
| Own-records briefing (ablation) | The same, plus the player's own current records in full | Short | Unchanged |

- **One thing changes per arm.** The package, route, model, effort, limits and mission
  text are identical. Nothing is removed from the player.
- **Why the ablation.** Delivery and curation fail separately. With it, the result can
  say which one worked. It does not change who writes the store in the design.
- **Order and budget.** Starts run one after another, cycling through the arms. Every
  start has the same request limit and dollar limit. Spend is reported per arm, with
  the curator's spend beside it.

### The first store and the start

- **The store.** Built only after all three gates: the same curator over the held-out
  lineage's seven played admissions, about \$23. The offline runner refuses held-out
  lineages today and is changed to accept this one. Reading it ends that lineage's
  held-out standing, which the owner allowed.
- **The state.** The held-out lineage's saved game as sealed after its last admission:
  alive at 27.76 game hours, in the world `Verdon`.
- **The copy.** A tool copies `user/` and the player's store from the sealed study into
  a fresh project-local directory, checks every file against the study's tracked hash
  manifest, and makes the copy writable. The sealed original is never opened for
  writing. One game runs at a time.
- **Disposal.** When a start ends, its traces, evaluation record and final saved game
  are sealed into the evidence store, and the working directory is deleted.
- **An invalid start** is one in which no input reached the game, or the copy did not
  load to the recorded character and time. It is reported and replaced once.

### The measure

The trace keeps no words from the model, so use cannot be read from it
([audit](../acceptance/2026-11-13-memory-read-audit.md)). The measure is what the
frames show.

- **Known items come from the frames, not from either store.** Two clean-context
  annotators, who see neither store, list the places with goods that the lineage's
  frames show before the start state. An item is kept when both list it. The list is
  frozen by hash. This keeps the list from favouring an arm.
- **Coverage is reported.** For each arm, how many known items its briefing holds. This
  is what tells a missing fact from an unused one.
- **Labels.** For each start and each known item, a judge answers one closed question:
  - **Straight:** the player went to the known place without first looking elsewhere.
  - **Missed:** the player looked for the same kind of thing elsewhere, or got it by
    another route, while the known source stayed unused.
  - **Not engaged**, or **cannot tell**.
- **Primary metric.** Missed items per start. A share of engaged items is not used: a
  briefing prompts visits to known places, which would lower a share without one fewer
  miss.
- **Secondary, reported and not decided on.** The missed share; items acted on that the
  frames show were out of date; deaths; time with a severe need; decisions and dollars
  per game hour; response time by prompt size.

### The judge

- **Who.** Two clean-context agents of the lead's coding host, model pinned and
  recorded, with a third where they differ. They cost nothing on the provider's
  account; their use of the coding host is not priced here and is reported.
- **Blind to the arm.** A judge receives frames and inputs only, under shuffled names.
  The briefing is never in a frame.
- **Packets.** Every third changed frame with the inputs before it, in windows that fit
  one context, and the list of known items.
- **Record.** Each verdict is a `judge` event: start, item, label, cited frames, judge
  and packet hash ([#386](https://github.com/CVX-Hull/enactive/issues/386)).
- **Calibration, in the measure gate.** The owner labels 20 pairs of item and
  stretch, drawn at random from all pairs, "not engaged" included, and 10 more drawn at
  random from the pairs any judge labelled straight, missed or cannot tell. The lead
  presents all 30 on one page, interleaved in a random order drawn once, which does not
  say which group a pair is from: each pair shows its frames and the item, and each
  label is one click. The owner opens no file and types nothing. The owner labels in
  two passes. In pass one every pair gets a blind label, with nothing of the judges'
  work anywhere on the page. Pass two starts only when every pair has one: it shows each
  pair again with the judges' labels, notes and cited frames, and the owner keeps or
  changes the label. Only blind labels count below. The judge is used only if the two
  judges agree on at least 80% with κ of at least 0.6, and the adjudicated label
  matches the owner's blind label on at least 18 of the random 20. The error on touched
  items, which the sizing uses, comes from the blind labels of every owner-labelled pair
  that the owner or the judges called straight or missed, random and engaged together,
  and is reported on the random pairs alone beside it. The engaged pairs cannot contain a
  pair every judge called not engaged, so the pooled error is conditional on a judge
  noticing engagement and is likely low.

### Decision rule

- **Test.** A one-sided permutation test on missed items per start, permuting starts
  between arms, at 0.05, with Holm's correction over the two briefing arms.
- **No conclusion** if more than 30% of labels on touched items are "cannot tell" in
  any arm, or if the envelope ends the comparison before every planned start has run.
  What was run is then reported without a test.
- **A start that reaches its dollar limit is not a failed arm.** It is kept and
  counted. The curator memory study's registered no-go was a cost-cap event.
- **After the first cycle of starts**, a check that does not look at arms stops the
  comparison if the starts touch fewer known items than the measure gate found.

| Result | Meaning | Next |
| --- | --- | --- |
| Curator briefing has fewer misses | A curator-written store, delivered at the start, reduces missed knowledge in this state | Build delivery at handoffs; plan the longest-horizon test |
| Own-records has fewer, the curator arm does not, and the curator's coverage is low | Delivery works; the store lacks what play needs | Improve the brief on development data |
| Neither, with coverage high | Delivered facts are not being used | A different design before any long run |
| A briefing arm acts on more out-of-date items | Currency is the limit | Retire facts before delivery widens |

## What the measure can detect

Simulated with the script in the [appendix](#appendix-the-simulation). Each start
touches a Poisson number of known items; each is missed with the arm's probability,
which varies between starts (correlation 0.2); the judge flips a label with the stated
probability; the test is the permutation test above.

| Starts per arm | Items touched per start | Current player's missed share | Judge wrong | Detects a halving | The same at Holm's first step | Detects a cut of one third | False alarm |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 12 | 5 | 0.7 | 0.1 | 0.54 | 0.38 | 0.25 | 0.045 |
| 12 | 5 | 0.7 | 0 | 0.67 | 0.52 | 0.36 | 0.038 |
| 12 | 5 | 0.7 | 0.2 | 0.35 | 0.24 | 0.21 | 0.035 |
| 12 | 8 | 0.7 | 0.1 | 0.67 | 0.55 | 0.38 | 0.043 |
| 16 | 5 | 0.7 | 0.1 | 0.65 | 0.52 | 0.33 | 0.037 |
| 8 | 5 | 0.7 | 0.1 | 0.38 | 0.25 | 0.21 | 0.037 |

- **At these guesses the measure cannot detect a halving reliably** at any size shown.
  Twelve starts per arm of 200 decisions would cost about \$86 for two arms at recorded
  rates.
- **The judge's error matters most.** From no error to one label in five wrong, the
  chance of detecting a halving falls from 0.67 to 0.35.
- **The false alarm rate stays under 5%.**
- **So no comparison is requested now.** The measure gate replaces the three guesses.
  If the measured numbers still give less than four chances in five inside an envelope
  the owner accepts, the lead says so and proposes development play in its place: one
  or two admissions with the briefing, read for whether briefed facts are stored and
  acted on, with no claim of benefit.

## The cut and curator sessions during play

The comparison has neither. This departs from "test all three", for these reasons:

- **A briefing at the start of one actor needs no session during play.** Keeping a
  start to one actor is this protocol's choice, made to keep starts short and alike.
- **Simulated with short results and a 13,000-token briefing**, no cut keeps 71.6% of
  requests under 60,000 tokens with cache writes at 0.240 of the recorded total. A cut
  with the curator ten decisions behind keeps all of them under 60,000 at 0.136. With no
  briefing the figures are 94.9% and 0.188 against 100% and 0.123.
- **The saving has a measured price.** The session price pilot found about \$0.20 a
  session and a trail of 8 to 40 decisions, about 23 on average, at the edge of what
  the cut needs ([record](../acceptance/2026-11-13-session-price-pilot.md)).
- **The rule needs two additions before it is built**: a minimum number of turns a cut
  must free, and marks that include the briefing.

Until the pilot shows otherwise, the fallback stands: sessions at admission boundaries
and handoffs only, with the prompt bounded by short results.

## The interface the build shares

The host's part ([#461](https://github.com/CVX-Hull/enactive/issues/461)) and the
curator's part ([#460](https://github.com/CVX-Hull/enactive/issues/460)) meet at one
file, so they can be built side by side.

- **Snapshot.** One immutable JSON file per published version: the version, the game,
  what it covers (session, actor, last request read, and the game time as text), and
  the items. Each item has an identifier, a kind, a subject, a place, a game time, the
  text, and whether it is shown in full or as an index line.
- **Briefing.** Software renders a snapshot to text: a header that says the knowledge
  is fallible and what it covers, the full items, then the index lines. The same
  renderer serves the own-records arm from the player's store.
- **Package option.** A package's first message already differs per package. A study
  package names the snapshot, or the player's store, or neither; with neither, the
  request is byte for byte what it is today.
- **One offline fixture.** A sealed development trace goes through a curator session
  against the stand-in provider, the gate, a snapshot, the renderer and the host's
  request serialization. The test asserts that the briefing is in the first message,
  that later requests extend it, and that text in a fact cannot become an instruction.

| Built before | What |
| --- | --- |
| The brief gate | The brief, the fact fields and the gate's keys; the frozen check |
| The session price pilot | Sessions over a window of decisions; the coverage stamp |
| The measure gate | The annotators' and judge's packets and events; the simulation on measured numbers |
| The comparison | The renderer and package option; the copy tool ([#388](https://github.com/CVX-Hull/enactive/issues/388)); the runner's acceptance of the held-out lineage |

## Cost and stop rules

| Step | Expected | Stop at |
| --- | ---: | ---: |
| Brief gate: six sessions on the seven-day lineage | \$22 | \$45 |
| Session price pilot: ten short sessions | \$12 | \$20 |
| Measure gate | \$0 on the provider | – |
| **Requested now** | **\$34** | **\$65** |
| First store: seven sessions on the held-out lineage | \$23 | not requested |
| Comparison: 13 starts per arm of 200 decisions | \$43 an arm at recorded rates | not requested |

- **Envelope requested now: \$65.** It equals the sum of the two stops.
- **Accounting.** The run ledger records game runs only. Curator spend is taken from
  the proxy's ledger and subtracted from the envelope by hand in the gate's record.
- **Frozen before each paid step**, with hashes in its record: this protocol, the
  brief, the check's patterns, the windows of the pilot and the session caps.
- **Deviations.** Any change after freezing is recorded as a deviation.
- **Review.** A clean-context reviewer checks each step's frozen inputs before it
  spends, and its report against them afterwards.

## Owner decisions

These four questions were put to the owner with the recommendations shown. The answers
are rows in the [owner decision log](../decisions/owner-decisions.md).

1. **The brief gate.** Run it, stopping at \$45. *Recommended: yes. The free checks
   point at the brief as what failed, and nothing else is worth building if it cannot
   be fixed.*
2. **The session price pilot.** Run it now, stopping at \$20, or leave sessions during
   play unpriced until the comparison is decided. *Recommended: run it. It is the
   measurement "priced first" asks for, and it settles whether the cut is affordable.*
3. **The cut.** Leave it out of the comparison and decide on it when the pilot reports,
   or require it in the comparison. *Recommended: leave it out.*
4. **Calibrating the judge.** The owner labels 20 pairs, about half an hour, during the
   measure gate; or the lead labels them and the owner checks five. *Recommended: the
   owner labels 20.*

## Limits

- **The simulation's inputs are guesses** until the measure gate replaces them.
- **The brief is tuned on the seven-day lineage.** Passing the brief gate does not show
  that the store will hold what another game needs.
- **The judge is a model**, calibrated against 20 labels.
- **One saved game** for every start of the comparison.
- **Cost figures predate short results** and are upper estimates.
- **The independent review of this protocol** found the first version's measure, gates
  and costs unsound. This version answers its findings; it has not been reviewed
  again.

## Appendix: the simulation

Run as `.venv/bin/python SCRIPT`. It reads nothing.

```python
import numpy as np
rng = np.random.default_rng(590)
def starts(n, lam, p, rho, wrong):
    """Missed known items per start: a Poisson number engaged, each missed with a probability that varies by start;
    the judge flips each label with probability `wrong`."""
    a, b = p * (1 - rho) / rho, (1 - p) * (1 - rho) / rho
    engaged = rng.poisson(lam, n); missed = rng.binomial(engaged, rng.beta(a, b, n))
    return missed - rng.binomial(missed, wrong) + rng.binomial(engaged - missed, wrong)
def p_value(a, b, draws=400):
    both, n = np.concatenate([a, b]), len(a); seen = a.mean() - b.mean(); hits = 0
    for _ in range(draws):
        order = rng.permutation(2 * n); hits += both[order[:n]].mean() - both[order[n:]].mean() >= seen
    return (hits + 1) / (draws + 1)
def rate(n, lam, pa, ratio, wrong=0.1, level=0.05, rho=0.2, sims=1500):
    return np.mean([p_value(starts(n, lam, pa, rho, wrong), starts(n, lam, pa * ratio, rho, wrong)) <= level for _ in range(sims)])
print("starts | engaged | baseline missed | judge wrong | halving at 0.05 | halving at 0.025 (Holm, first step) | one-third cut at 0.05 | false alarm")
for n, lam, pa, wrong in ((12, 5, 0.7, 0.1), (12, 5, 0.7, 0.0), (12, 5, 0.7, 0.2), (12, 5, 0.6, 0.1), (12, 3, 0.7, 0.1), (12, 8, 0.7, 0.1), (16, 5, 0.7, 0.1), (8, 5, 0.7, 0.1)):
    print(f"{n} | {lam} | {pa} | {wrong} | {rate(n, lam, pa, .5, wrong):.2f} | {rate(n, lam, pa, .5, wrong, .025):.2f} | {rate(n, lam, pa, 2/3, wrong):.2f} | {rate(n, lam, pa, 1, wrong):.3f}")
```
