---
owner: lead
status: proposed
date: '2026-11-13'
scope: 'Protocol for a live memory screen (#590): whether a player given stored knowledge at the start of each actor misses less of what its game already found; arms, the first store, the start from a copy of the held-out lineage''s saved game, the measure and its judge, the decision rule, a simulation of what the measure can detect, the interface the build shares, cost, envelope and stop rules. Nothing here is approved, built or run'
review_trigger: An owner decision on the list in this note, a gate in it that fails, or a change to the context design it tests
---

# Memory screen: protocol

## At a glance

- **Question.** Does a player that is given stored knowledge at the start of each actor
  miss less of what its game has already found than the current player does?
- **What the free checks changed**
  ([record](../acceptance/2026-11-13-memory-screen-free-checks.md)).
  1. **The curator's recorded store would have prevented one of the four recorded
     losses.** It holds the roof tank and not the rations, the rod or the batteries,
     although each was on screen in admissions it read. Delivery was early enough for
     all four. So the curator's brief is the first thing to fix and prove.
  2. **The player's own records, sent in full, would have covered the three stored
     losses** at about 4,200 tokens.
  3. **The cut adds little once tool results are short.** Simulated, short results and
     a larger image block alone keep 94.9% of requests under 60,000 tokens. The cut
     helps further only if the curator stays within about 24 decisions of play.
- **Proposal.** Three gates before any game is played, then a screen of short starts.
  1. **Brief gate, about \$20.** Run a curator with a brief aimed at places and goods
     over the seven-day lineage. It must store at least three of the four lost facts,
     each with its place. If it does not, stop.
  2. **Measure gate, \$0 to the provider.** On sealed admissions, show that a start
     touches enough known items and that two judges agree. If not, stop and propose
     another form.
  3. **Pilot.** One start per arm, read end to end.
  4. **Screen.** Twelve starts per arm of 200 decisions each, from a copy of the
     held-out lineage's saved game, one game at a time.
- **Arms.** The current player; the same player with a briefing from the curator's
  store; and, proposed as an ablation, the same player with a briefing of its own
  records in full. All three have short tool results. No arm has the cut.
- **What it can detect.** A halving of missed knowledge, with about 80% power, and only
  if a start touches about five known items and the current player misses about 70% of
  them. The measure gate checks both before anything is spent on starts. It cannot
  detect a small effect.
- **Cost.** Expected about \$110 for two arms and \$150 for three; proposed envelopes
  \$170 and \$230. Nothing is spent without the owner's approval of this protocol.
- **Owner decisions needed.** Five, under [owner decisions](#owner-decisions).

Terms are in the [glossary](../glossary.md). A **start** is one run of one actor from
the copied saved game. A **known item** is one fact in the frozen list built from the
store ([the measure](#the-measure)).

## What this screen is and is not

- **It is a screen.** It tells the owner whether to go on building the curator's
  delivery, not whether the design is adopted. Every start comes from one saved game,
  on one route and one model, so the result holds for that state only.
- **It tests the briefing, the design's second layer.** The first layer, short tool
  results, is in every arm. The third layer, the cut, is not in this screen
  ([why](#the-cut-and-curator-sessions-during-play)).
- **It does not test a week.** The oldest fact in the start state is about 28 game
  hours old.
- **It does not test writing during play.** A start is one actor and reaches no
  handoff. The store is written before the starts and does not change during them.

## Arms

| Arm | First message | Tool results | Store tools |
| --- | --- | --- | --- |
| Current | The mission and the previous final report, as a new admission gets today | Short | The player's own store, unchanged |
| Curator briefing | The same, plus a briefing built from the curator's first store | Short | Unchanged |
| Own-records briefing (ablation) | The same, plus the player's own current records in full | Short | Unchanged |

- **One thing changes per arm.** Nothing is removed from the player in any arm. The
  package, route, model, effort, limits and mission text are identical; only the
  briefing differs.
- **Why the ablation.** The free checks show that delivery and curation fail
  separately. Without this arm, a null result could not say which failed. It needs no
  curator and no new machinery beyond the briefing builder. It does not change who
  writes the store in the design.
- **Order.** Starts run one after another, cycling through the arms, so that the time
  of day and the provider's load fall evenly across them.
- **Budget matching.** Every start has the same request limit and dollar limit. Spend
  per arm is reported beside the outcome; the curator's spend is reported separately.

## The first store

- **Brief.** The curator's brief gains one instruction: record where goods and useful
  things are, one fact per item, each with the place and the game time as the screen
  shows them. The fact format gains `place`, `game_time`, `subject` and a kind (place
  with goods, hazard, open commitment, how the game works).
- **Brief gate, on development data.** The curator runs over the seven-day lineage's
  admissions `sd1a1` to `sd1a6`, one session per admission as in the shadow run. The
  check is mechanical: the command in the free-checks record, on the new store, finds
  the roof tank, the rations, the fishing rod and the batteries.
  - **Pass:** at least three of the four are stored with a place.
  - **Fail:** stop. The screen is not run, and the result is reported.
  - **Cost:** the shadow run averaged \$3.28 a session on this model, so about \$20;
    stop at \$45.
- **The held-out lineage's store.** After the gate passes, the same curator runs over
  `lh4b1` to `lh4b7`, seven sessions: about \$23 expected, stop at \$50. The offline
  runner refuses held-out lineages today; it is changed to accept this one. Reading it
  ends that lineage's held-out standing, which the owner allowed.
- **Model.** The actor's model, as in the shadow run's cheaper arm. The second model
  cost 1.24 times the actor against 0.69 and stored the tank only as hearsay.
- **Sizing a session's cap.** Each session's cap holds at least two worst-case
  requests, so that a refused or timed-out request cannot end a session by itself. A
  refused request counts at zero ([#556](https://github.com/CVX-Hull/enactive/issues/556)).

## The start

- **State.** The held-out lineage's saved game as sealed after its last admission:
  alive at 27.76 game hours.
- **Copy.** A tool copies `user/` from the sealed study into a fresh project-local
  directory, `.runtime/screen/<start>/user`, checks every copied file against the
  study's tracked hash manifest, and makes the copy writable. The sealed original is
  never opened for writing.
- **One game at a time.** A start begins only after the previous start's game process
  has ended.
- **Disposal.** When a start ends, its traces, evaluation record and final saved game
  are sealed into one study in the evidence store. Then the working directory is
  deleted. Nothing from a start is reused by another.
- **Pilot check.** The pilot confirms that the copy loads to the same character at the
  recorded time. If it does not, stop.

## The measure

The trace keeps no words from the model, so use cannot be read from it
([audit](../acceptance/2026-11-13-memory-read-audit.md)). The measure is therefore what
the frames show.

- **Known items.** Before any start, a tool builds the list from the curator's first
  store for the held-out lineage: every current fact whose kind is a place with goods or
  how the game works. The list is frozen by hash. Nobody picks items by hand. The same
  list is used for every arm.
- **Labels.** For each start and each known item, a judge answers one closed question
  from that start's frames and inputs:
  - **Straight:** the player went to the known place or applied the known fact without
    first looking elsewhere.
  - **Missed:** the player searched for it again, or got the same kind of thing by
    another route while the known source stayed unused.
  - **Not engaged:** nothing in the start concerned the item.
  - **Cannot tell.**
- **Primary metric.** The missed share: missed, divided by straight plus missed, pooled
  over an arm's starts.
- **Secondary, reported and not decided on.** Items acted on that the frames show were
  out of date; deaths; the share of time with a severe need; decisions and dollars per
  game hour; response time by prompt size; typed searches.

### The judge

- **Who.** Two clean-context agents of the lead's coding host, with the model pinned
  and recorded. They cost nothing on the provider's account. A third adjudicates where
  the two differ.
- **Blind to the arm.** A judge receives a start's frames and inputs only. The briefing
  is in the prompt, not in any frame, and the starts are given under shuffled names.
- **Packet.** Every changed frame of the start with the input before it, and the list
  of known items. The judge returns, for each item, its label and the frames that show
  it.
- **Record.** Each verdict is a `judge` event in the evaluation record: start, item,
  label, cited frames, judge and packet hash.
- **Calibration, before any verdict is used.** On sealed development admissions
  (`sd1a5` to `sd1a7`, with the list built from the brief gate's store through
  `sd1a4`), the two judges label every item. The owner labels 20 item-and-admission
  pairs drawn at random from those with a label other than "not engaged".
  - **Pass:** the two judges agree on at least 80% with κ of at least 0.6, and the
    adjudicated label matches the owner's on at least 16 of 20.
  - **Fail:** the judge is not used and the screen is not run in this form.

### The measure gate

The same sealed admissions answer two questions the simulation depends on:

- **How many known items does a stretch of 200 decisions touch?** At least five,
  averaged over the three admissions.
- **How often does the current player miss them?** At least 60%.

If either fails, the screen is not run in this form. The lead then proposes another:
longer starts, or a start state with more stored places.

## Decision rule

- **Test.** For the curator briefing against the current player, a one-sided
  permutation test on the difference in missed share, permuting starts between arms,
  at 0.05. With the ablation arm, the own-records comparison is tested the same way and
  both are corrected by Holm's method.
- **Validity.** If more than 30% of engaged items are "cannot tell" in any arm, no
  conclusion is drawn.
- **A start that reaches its dollar limit is not a failed arm.** It is reported, kept
  with whatever it reached, and counted. This is unlike the curator memory study, whose
  registered no-go was a cost-cap event.

| Result | Meaning | Next |
| --- | --- | --- |
| Curator briefing lower, test passes | A curator-written store, delivered at the start, reduces missed knowledge in this state | Build delivery at handoffs and decide on the cut; plan the longest-horizon test |
| Own-records lower, curator not | Delivery works; the curator's store does not yet hold what play needs | Improve the brief on development data before any further run |
| Neither, and the gates passed | Delivered facts are not being used | A different design is needed before any long run |
| Either arm acts on more out-of-date items than the current player | Currency is the limit | Address retirement of facts before delivery widens |

## What the measure can detect

Simulated with the script in the [appendix](#appendix-the-simulation). Each start
touches a Poisson number of known items; each is missed with the arm's probability,
which varies between starts (correlation 0.2 within a start); the test is the
permutation test above.

| Starts per arm | Items touched per start | Current player's missed share | Detects a halving | Detects a cut of one third | False alarm when the arms are equal |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | 5 | 0.7 | 0.69 | 0.41 | 0.051 |
| 10 | 5 | 0.7 | 0.77 | 0.49 | 0.055 |
| 12 | 5 | 0.7 | 0.84 | 0.56 | 0.046 |
| 12 | 8 | 0.7 | 0.91 | 0.63 | 0.041 |
| 12 | 5 | 0.5 | 0.63 | 0.36 | 0.043 |
| 12 | 3 | 0.7 | 0.72 | 0.44 | 0.052 |

- **Twelve starts per arm detect a halving about four times in five**, if a start
  touches five items and the current player misses 70%.
- **It does not detect a cut of one third** at any affordable size.
- **The false alarm rate stays near 5%.** A bootstrap bound, tried first, raised it to
  between 6% and 9% with so few starts, so the permutation test is used.
- **The two inputs are unknown**, which is why the measure gate measures them first.

## The cut and curator sessions during play

The screen has neither. The reasons are from the free checks:

- **A start is one actor**, so a briefing at its start needs no curator session during
  play.
- **Simulated with the short results as built**, no cut already gives a median prompt
  of 38,516 tokens and cache writes at 0.188 of the recorded total. A cut with the
  curator ten decisions behind gives 26,782 and 0.123. At the one computed lag, 47
  decisions, it prevents no image drop.
- **The rule needs two additions before it is built**: a minimum number of turns a cut
  must free, and marks that include the briefing.

**Price and speed of sessions during play are not measured.** What is recorded: a
session over a whole admission took a median of 189 s and \$3.28, which is 47 decisions
of play. A session over 20 new decisions should be shorter and cheaper, and no such
session has been run. A pilot would measure it at about \$12: ten sessions over sealed
windows of 20 decisions, with no game running. It is offered as a decision below and
is not part of the screen. Until it passes, the fallback stands: sessions at admission
boundaries and handoffs only, with the prompt bounded by short results.

## The interface the build shares

The host's part ([#461](https://github.com/CVX-Hull/enactive/issues/461)) and the
curator's part ([#460](https://github.com/CVX-Hull/enactive/issues/460)) meet at one
file, so that they can be built side by side.

- **Snapshot.** One immutable JSON file per published version: the version, the game,
  what it covers (session, actor, last request read, and the game time as text), and
  the items. Each item has an identifier, a kind, a subject, a place, a game time, the
  text, and whether it is shown in full or as an index line.
- **Briefing.** Software renders a snapshot to text: a header that says the knowledge
  is fallible and what it covers, the full items, then the index lines. The same
  renderer serves the own-records arm from the player's store.
- **Package option.** A study package names the snapshot file, or the player's store,
  or neither. The host puts the rendered briefing in the first message. With neither,
  the request is byte for byte what it is today.
- **One offline fixture.** A sealed development trace goes through a curator session
  against the stand-in provider, the gate, a snapshot, the renderer and the host's
  request serialization. The test asserts that the briefing is in the first message,
  that later requests extend it, and that text in a fact cannot become an instruction.

**Built before the brief gate:** the brief and fact fields, and the runner's selection
of lineages. **Before the measure gate:** the known-item list and the judge's packet
and events ([#386](https://github.com/CVX-Hull/enactive/issues/386)). **Before the
pilot:** the renderer and package option, and the copy tool
([#388](https://github.com/CVX-Hull/enactive/issues/388)).

## Cost, envelope and stop rules

Expected figures use recorded rates: \$0.0165 a decision for the held-out lineage's
actor, which short results should lower, and \$3.28 a curator session.

| Step | Expected | Stop at |
| --- | ---: | ---: |
| Brief gate: six sessions on the seven-day lineage | \$20 | \$45 |
| First store: seven sessions on the held-out lineage | \$23 | \$50 |
| Measure gate and judging | \$0 on the provider | – |
| Pilot and screen, two arms: 26 starts of 200 decisions | \$86 at the recorded rate; less with short results | \$5 a start |
| The ablation arm: 13 more starts | \$43 | \$5 a start |

- **Envelopes proposed.** \$170 for two arms; \$230 for three. The lead admits a start
  only while spend so far plus twice the largest admission stays inside the envelope,
  as [operator permissions](../operator-permissions.md) require.
- **Frozen before the first start**, with their hashes in the pre-registration: this
  protocol, the package, the route, the mission text, the snapshot, the known-item
  list, the judge's prompt and the analysis script.
- **Stop rules.** A gate fails. The pilot shows the briefing missing from the first
  message, the copy not loading, or a start unable to finish inside its limits. The
  envelope is reached. Sealed evidence fails verification.
- **Deviations.** Any change after freezing is recorded as a deviation. A changed rule
  is not a refinement.
- **Review.** A clean-context reviewer checks the pre-registration before the first
  start, and the report against it afterwards.

## Owner decisions

1. **Run the gates and the screen as written.** *Recommended: yes, in the order above,
   stopping at the first gate that fails.*
2. **The ablation arm.** Three arms at an envelope of \$230, or two at \$170.
   *Recommended: three. Without it a null result cannot say whether delivery or the
   store failed.*
3. **The cut.** Leave it out of this screen and decide on it after the result, or price
   live sessions now with the \$12 pilot. *Recommended: leave it out and decide after.*
4. **Calibrating the judge.** The owner labels 20 item-and-admission pairs, about half
   an hour, or the lead labels them and the owner checks five. *Recommended: the owner
   labels 20.*
5. **Exact token counts for short results.** No tokenizer for the route's model is
   installed, so [#606](https://github.com/CVX-Hull/enactive/issues/606) reports bytes
   and a fitted rate. Accept that until the pilot's recorded usage gives the exact
   figure, or add a tokenizer as a dependency. *Recommended: accept; the pilot measures
   it at no extra cost.*

## Limits

- **One saved game.** All starts share it, so they are correlated in ways the test does
  not see, and the result does not generalise beyond it.
- **The simulation's inputs are guesses** until the measure gate replaces them.
- **The judge is a model.** Its calibration is against 20 owner labels.
- **Short starts.** Two hundred decisions are about three game hours.
- **The brief is tuned on the seven-day lineage** and then used on the held-out one.
  Passing the brief gate does not show that the store holds what the held-out game
  needs.
- **Cost figures predate short results.** They are upper estimates.

## Appendix: the simulation

Run as `.venv/bin/python SCRIPT`. It reads nothing.

```python
import numpy as np
rng = np.random.default_rng(590)
def starts(n, lam, p, rho):
    a, b = p * (1 - rho) / rho, (1 - p) * (1 - rho) / rho
    engaged = rng.poisson(lam, n); return rng.binomial(engaged, rng.beta(a, b, n)), engaged
def share(missed, engaged): return missed.sum() / max(1, engaged.sum())
def p_value(a, b, draws=400):
    missed, engaged, n = np.concatenate([a[0], b[0]]), np.concatenate([a[1], b[1]]), len(a[0])
    seen = share(*a) - share(*b); hits = 0
    for _ in range(draws):
        order = rng.permutation(2 * n); x, y = order[:n], order[n:]
        hits += share(missed[x], engaged[x]) - share(missed[y], engaged[y]) >= seen
    return (hits + 1) / (draws + 1)
def rate(n, lam, pa, pb, rho=0.2, sims=1500):
    return np.mean([p_value(starts(n, lam, pa, rho), starts(n, lam, pb, rho)) <= 0.05 for _ in range(sims)])
print("starts per arm | engaged per start | baseline missed share | detects halving | detects a one-third cut | false alarm when equal")
for n in (8, 10, 12):
    for lam in (3, 5, 8):
        for pa in (0.5, 0.7):
            print(f"{n:>2} | {lam} | {pa} | {rate(n, lam, pa, pa / 2):.2f} | {rate(n, lam, pa, pa * 2 / 3):.2f} | {rate(n, lam, pa, pa):.3f}")
```
