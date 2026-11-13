---
owner: lead
status: historical
kind: review
date: '2026-11-13'
scope: 'The three free checks for the memory screen (#590) on sealed evidence: whether the curator shadow run''s stores for the seven-day lineage (#397) hold the four lost facts, a replay of the three stored losses against the context design''s briefing and snapshot differences, and a simulation of the design''s cut over the recorded request sequences of the seven-day and held-out lineages for curator lags of 10, 20, 47 and 94 decisions. No run, game launch or model call was made'
---

# Free checks for the memory screen: the lost facts, their delivery and the cut (#590)

## At a glance

**Question.** Before a paid memory screen is designed: would the
[context design](../design/player-context.md) have prevented the four recorded memory
losses of the seven-day lineage, and can its cut work at the curator's speed?

**Answers.**

- **The curator's sealed store holds one of the four lost facts, the roof tank.** The
  shadow run with the actor's model wrote "18 L of clean water" on the shelter roof
  into its third version, from the admission in which the player saw it. The ration
  boxes in the cupboard, the fishing rod on the floor and the batteries in the locker
  are in neither shadow store, although the probe annotations show each was on screen in
  admissions the curator read. No fact is present but wrong. The store grew from 17
  facts (8,316 bytes) to 71 facts (36,947 bytes) over six admissions.
- **The design's delivery is early enough for all four.** A briefing built from the
  player's own records would have put each of the three stored losses in the first
  message of the actor that needed it: 6 requests before the need for the batteries, 17
  for the rod and 49 for the rations. That holds only if the records are sent in full;
  each fact is one phrase inside a status record, and an index line would not name it.
  The curator's store would have delivered the tank 129 requests before it was needed,
  and none of the other three.
- **The cut holds its marks only when coverage trails play by fewer than about 24
  decisions (simulated).** At lags of 10 and 20 the simulated prompt has a median near
  29,000 tokens, never passes 42,000, and no image block is dropped. At 47 and 94 the cut
  prevents no image drop at all (76, the same as with no cut), and at 94 it writes more
  to the cache than no cut does. As the lag nears 39 decisions the rule as written cuts
  ever more often: at 39 it cuts at 1,263 of 1,978 requests and writes 2.15 times the
  recorded total.

**Not known.**

- The exact tokens of a turn with short results; the simulation takes it as a parameter
  (950 by default) until [#606](https://github.com/CVX-Hull/enactive/issues/606) reports
  it.
- The curator's lag during play, and whether a session at a handoff or during play
  would write the facts a whole-admission session wrote. No such session has been run.
- Whether a player acts on a fact that a briefing puts in front of it. The replay shows
  when the text would have been in the prompt, not that it would have been used.

Terms are in the [glossary](../glossary.md). A **request** is one call to the model, a
**turn** is a tool call with its result, and a **lineage request** numbers the requests
of the seven-day lineage's 14 actors in order, from 1 to 1,978.

## What was read and how

Everything below comes from one read-only tool,
[`tools/memory_screen_checks.py`](../../tools/memory_screen_checks.py), and two existing
readers. The commands were run from a worktree at main `e97c22f` plus this change, with:

```sh
PY="$(git rev-parse --git-common-dir)/../.venv/bin/python"
EV="$(git rev-parse --git-common-dir)/../.runtime/evidence"
RUNS="$EV/397-seven-day/computer-sessions"
HELD="$EV/522-held-out/computer-sessions"
TERRA="$EV/curator-shadow-454/knowledge/run-terra-397/terra/397/cdda"
OPUS="$EV/curator-shadow-454/knowledge/run-opus-397/opus/397/cdda"
```

| Name used below | Command |
| --- | --- |
| Store command | `"$PY" -m tools.memory_screen_checks store "$TERRA" "$OPUS" --runs "$RUNS" --find 'tank=tank\|roof' --find 'rations=ration\|cupboard\|cardboard' --find 'rod=fishing rod' --find 'batteries=batter\|locker\|flashlight'` |
| Place command | The store command with `--find 'place=shelter\|locker\|cupboard\|roof\|basement\|bench\|B-19'` in place of the four patterns |
| Replay command | `"$PY" -m tools.memory_screen_checks replay "$RUNS" --records "$EV/397-seven-day/evaluations" --knowledge "$TERRA" --loss rations:need=910bb98c06461865f5a73e3574cdd95a-1375,record=5db17f --loss rod:need=3c6acb3817ebc5b0fced8f7a122b7bbf-351,record=94ce47 --loss batteries:need=12ba39c88fbb4da11264b8d2c4634db1-216,record=f49b80 --loss tank:need=92505965fcbd23adda6919b8a38decc4-5615,fact=evac-roof-water-tank` |
| Cut command | `"$PY" -m tools.memory_screen_checks cut "$RUNS"`, with the options each table names; `"$HELD"` for the held-out lineage |
| Reads command | `"$PY" -m tools.memory_reads "$RUNS" --records "$EV/397-seven-day/evaluations" --store "$EV/397-seven-day/player-memory-sd1.sqlite3"` |
| Probe search | `grep -h -i -E 'ration\|fishing rod\|batter\|flashlight\|tank\|basement' data/evaluation/probes/397/*.jsonl` |

The patterns are written here with `\|` so that the table renders; in the shell each
bar is a plain `|` inside the quotes.

**The sealed store was not changed.** The knowledge repositories are Git repositories
in a read-only directory. The tool reads their loose objects with `zlib` and starts no
Git process, so nothing can be written there; it refuses a packed repository. Both
repositories hold loose objects only.

**What the two shadow stores are.** The
[shadow record](2026-11-08-curator-shadow-454.md) describes them, and the store command
confirms the sessions:

- `run-terra-397`: the curator on the actor's own model. One session per admission
  after the admission ended, seven run and six sealed. The store's last version, `v6`,
  covers `sd1a1` to `sd1a6`; the session over `sd1a7` was stopped by the cap and
  published nothing.
- `run-opus-397`: the curator on the second model, for `sd1a1` to `sd1a3` only. Its last
  version is `v3`.

Neither curator was given the player's memory store, and the brief held no game
knowledge.

## The curator's stores and the four lost facts

The four facts are those of the
[memory note](../design/long-horizon-memory.md#where-it-failed-in-recorded-long-play).
Observed, from the store command:

| Lost fact | Store on the actor's model (`run-terra-397`) | Store on the second model (`run-opus-397`) |
| --- | --- | --- |
| A roof tank held 18 L of clean water | **Present and right.** `evac-roof-water-tank`, first in `v3`, from the session over `sd1a3`: "An evac shelter rooftop can have a clean-water tank. In one observed shelter, examining it showed 18 L of clean water and offered drinking, dispensing or dumping the tank's contents; no water was taken in that observation." It cites one frame, returned at request 58 of 186 of `sd1a3`'s first actor (lineage request 679). It names no particular shelter | **Present, hedged.** `f209`, first in `v3`, filed as a note about autosave: "The roof of evac shelter B-19 has a large white tank … The actor reported that the tank held about 18 L of clean water. That claim is not visible in the cited frame." It cites a frame returned at request 164 of 186 of the same actor (lineage request 785) |
| 20 ration boxes in a cupboard | **Absent.** The one fact about rations, `protein-ration-food` (`v5`, session over `sd1a5`), says the consume menu lists a ration at 800 calories. It names no cupboard, box or place | **Absent.** No fact mentions rations |
| A fishing rod on the floor nearby | **Absent.** Three facts mention a rod: its recipe (`v1`), fishing with a wielded rod (`v1`) and the recipe of the hook (`v5`). None says a rod exists in the shelter | **Absent.** `f011` (`v1`) records that a rod was crafted and wielded in `sd1a1`, and `f012` describes fishing. Neither says where the rod was left |
| Batteries in the locker | **Absent.** The only fact with the word says a smartphone "ran out of batteries" (`v2`). No fact mentions a locker | **Absent.** `f003` (`v1`) says the shelter "has benches, lockers and a counter" and nothing about their contents |

- **Nothing was changed or retired.** In both stores every version only added facts,
  except one fact about saving and quitting in each (`save-and-quit` in `v3` of the
  first store, `f014` in `v3` of the second). None of the facts in the table changed
  after it first appeared.
- **The decision a fact comes from can be placed only through its cited frames.** A
  session read a whole admission after it ended, so a fact "first appears" at the
  admission boundary; the request numbers above are where the cited frame was returned.
- **The frames were within the curator's reach.** The probe search shows the cupboard's
  boxes on screen in `sd1a2`, `sd1a3` and `sd1a5`, the rod in the shelter in `sd1a2`,
  `sd1a3`, `sd1a4` and `sd1a6`, and the lockers' contents in `sd1a1` and `sd1a2`. Each of
  those admissions was the window of a session of the first store. A session views only
  the frames it chooses, so this shows the facts were available, not that the curator
  looked at them.

Inference: the three absences come from what the sessions looked at and chose to write,
not from frames out of reach. The place command finds 3 of the first store's 71 facts that name a place in the
shelter at all (the tank, a window's curtains and the save point), and 7 of the second
store's 30. The stores hold recipes, controls and screens. The design already lists "a
brief aimed at places and goods" and place and game time on a fact as requirements; this
check says the screen's delivery arm depends on them.

### Size of the store at each admission boundary

A briefing would be built from the version published at each boundary. Bytes are of
`facts.jsonl`, which carries each fact's identifier, citations and schema fields as well
as its statement, so they overstate a briefing that sends statements only. Tokens are
bytes times 0.363, the design's fitted rate for the seven-day lineage.

| After the session over | First store: version, facts, bytes, tokens | Second store: version, facts, bytes, tokens |
| --- | --- | --- |
| `sd1a1` | `v1`, 17, 8,316, about 3,000 | `v1`, 14, 9,021, about 3,300 |
| `sd1a2` | `v2`, 30, 15,408, about 5,600 | `v2`, 22, 15,612, about 5,700 |
| `sd1a3` | `v3`, 43, 22,563, about 8,200 | `v3`, 30, 22,531, about 8,200 |
| `sd1a4` | `v4`, 52, 27,136, about 9,900 | not run |
| `sd1a5` | `v5`, 62, 31,936, about 11,600 | not run |
| `sd1a6` | `v6`, 71, 36,947, about 13,400 | not run |

The first store adds about 520 bytes a fact and 9 to 17 facts an admission, with no sign
of levelling off in six admissions.

## Replay of the stored losses against the design's delivery

**Assumptions.**

- **The briefing.** The first message of every actor, at an admission and at a handoff,
  holds every stored item in full or as an index line, as the design says. No cap.
- **Two stores.** For the player's own store, the briefing holds each record from the
  first actor that starts after the record was written. This needs no curator session.
  For the curator's store, the briefing holds what the shadow run published.
- **Curator sessions.** The shadow run is the case "sessions at admission boundaries
  only": a version is in the briefing of the next admission's first actor. For "sessions
  at handoffs too", a session over the first actor's trace is assumed to publish the
  same fact, and the successor gets the difference after the lag. That is an assumption;
  no session over one actor's trace was ever run.
- **When play needed the fact.** The request that returned the frame of the fact's first
  `needed` event in the tracked probe annotations (probe search). For the rations, the
  batteries and the tank the lead adjudicated the event from the seven-day record.
- **"In front of the actor" means the text is in the prompt.** It does not mean the
  actor acts on it.

Observed positions, from the replay command and, for the last column, the reads command:

| Loss | Play needed it at | The player's record | A briefing from the player's store reaches the actor that needed it | The curator's store | Recorded |
| --- | --- | --- | --- | --- | --- |
| Rations (`5db17f`) | `sd1a6`, first actor, request 50 of 90; lineage request 1,533; game day 62 16:49. It weighs foods with cattail stalks at hand | Written at request 49 of 50 of `sd1a5`'s first actor; lineage request 1,280; day 62 15:00 | At its first request: lineage request 1,484, day 62 15:40. **49 requests before the need** | Never. It would have briefed that a ration is 800 calories, which the actor already saw in its own menu | No actor from `sd1a6` on was given the record |
| Fishing rod (`94ce47`) | `sd1a5`, first actor, request 18 of 50; lineage request 1,249; day 62 14:52. It searches cordage recipes for a rod's line | Written at request 83 of 85 of `sd1a2`'s first actor; lineage request 423; day 61 16:34 | At its first request: lineage request 1,232. **17 requests before the need** | Never. It would have briefed the rod's recipe and the hook's recipe | No actor from `sd1a5` on was given the record |
| Batteries (`f49b80`) | `sd1a3`, first actor, request 7 of 186; lineage request 628; day 62 07:30. It finds no working light | Written at request 135 of 136 of `sd1a1`'s first actor; lineage request 135; day 61 08:20 | At its first request: lineage request 622. **6 requests before the need** | Never | A query returned it at request 128 of 151 of `sd1a3`'s second actor; lineage request 935, 307 requests after the need |

**The tank cannot be replayed from the player's store,** because the player never
stored it. From the curator's first store:

- Play needed it at request 47 of 190 of `sd1a4`'s second actor (lineage request 1,088,
  day 62 13:51), when it filled a bottle with lake water to boil.
- With sessions at admission boundaries only, `v3` is in the briefing of `sd1a4`'s first
  actor (lineage request 959, day 62 13:29), **129 requests before the need**, and again
  in the first message of its second actor (lineage request 1,042), 46 requests before.
- With sessions at handoffs too, the difference reaches `sd1a3`'s second actor at its
  request 11, 21, 48 or 95 for lags of 10, 20, 47 and 94 decisions (lineage requests 818
  to 902), all before the need.
- The second store gives the same positions with its hedged fact `f209`.

**What changes with sessions at admission boundaries only.** Nothing for the three
stored losses under the player's store, which needs no session. For the tank, delivery
moves from `sd1a3`'s second actor to the next admission's start, still before the need.
In this lineage every one of the four needs fell in a later admission than the fact, so
boundary sessions would have been enough. A fact seen by a first actor and needed by its
successor in the same admission is the case that needs a handoff session, and none of
the four is that case.

**Two limits on reading the table.**

- **The stored facts are phrases inside status records.** The rod is the sentence
  "Basic fishing rod on floor 7 tiles NW of last position" in a 1,048-byte record about
  starch and foraging. The batteries are one word in a data field of a 931-byte record;
  its text says the lockers hold "clean water, rations and supplies". The ration boxes
  are one sentence of a 1,323-byte record. An index line with a subject and a place
  would not name any of the three, so this delivery works only with the records in full.
  The whole player store is 11 records and 11,441 bytes of text, about 4,200 tokens, so
  sending it in full is affordable. (Sizes: `"$PY" -c "import sys; from pathlib import
  Path; from harness.evaluation.core.sources import read_memory; [print(i[:6],
  len(r['text'].encode())) for i, r in read_memory(Path(sys.argv[1])).records.items()]"
  "$EV/397-seven-day/player-memory-sd1.sqlite3"`.)
- **Being in the prompt was not always enough in the record.** The
  [audit](2026-11-13-memory-read-audit.md) found the batteries record used at once when
  a query returned it. The rod record was returned to three actors that did not need a
  rod, and nothing they typed relates to it.

## Simulation of the cut

Every figure in this section except the rows named "Recorded" is **simulated**. The
shadow run recorded no coverage by decision, so this is a model run over the recorded
request sequences, not a replay.

**The model.** Its parameters are options of the cut command; the defaults are the
design's figures.

- **Sequences.** Each actor makes the requests it made in the record, in the same
  order, and each turn carries as many images as the trace shows it added. Actors hand
  off where they did in the record.
- **What a turn costs.** 950 tokens with one image: 758 for the image and 192 for the
  call and its short result. A turn without an image costs 192.
- **The prompt.** The fixed head (4,500 tokens), the briefing (0 by default, to match
  the design's marks) and the turns still in the window.
- **Image drops outside a cut.** As the host does today: when the window holds more
  than 39 images, the oldest block (20) become markers of 100 tokens each.
- **When a cut is due.** At a request whose window is over the high mark (60,000
  tokens) or holds more than 39 images, which is the request at which the host would
  otherwise drop a block.
- **What a cut removes.** The oldest turns, with their images, until the window is at
  or under the low mark (20,000 tokens), and only turns the snapshot covers. A cut is
  **held back** when it is due and no turn can be removed. If the window still holds
  more than 39 images after the cut, a block is dropped in the same request.
- **What "covered" means at lag L.** When the actor has made t turns, the snapshot
  covers its first t − L. This is the "steady" case: the curator is always exactly L
  decisions behind. The "sessions" case runs one session after another, each L decisions
  long and covering what existed when it started, so coverage is L × (⌊t ÷ L⌋ − 1) turns
  and trails by L to 2L.
- **Cache writes.** A request that extends the one before it writes the new turn. A
  request that cuts or drops images writes everything after the 3,900 tokens of head
  that the provider still read from the cache in the record. An actor's first request
  writes its whole prompt.

**A check of the model against the record.** With a turn of 1,750 tokens and blocks of
10 images, which is roughly the recorded turn, the no-cut row gives 145 image drops
(recorded: 145) and 22.45 million tokens written to the cache (recorded: 22.40
million), with a median prompt of 106,502 tokens against 93,808 (cut command with
`--turn-tokens 1750 --image-block 10`). The 1,750 was chosen from the growth of one
actor's text, not fitted.

### Seven-day lineage, steady coverage

Cut command with no options. 14 actors, 1,978 requests.

| Row | Prompt tokens: median; 95th percentile; maximum | Cuts made | Of those, freed fewer than ten turns | Cuts held back | Image blocks dropped | Tokens written to the cache, millions (share of recorded) | Requests under 40,000; under 60,000 |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| Recorded | 93,808; 214,025; 234,818 | none | none | none | 145 | 22.40 (1.000) | 17.3%; 27.6% |
| No cut: short results, blocks of 20 | 45,630; 76,164; 88,462 | none | none | none | 76 | 5.09 (0.227) | 39.0%; 75.1% |
| Lag 10 | 28,442; 40,600; 41,742 | 64 | 0 | 0 | 0 | 2.86 (0.128) | 93.4%; 100% |
| Lag 20 | 30,342; 40,792; 41,742 | 76 | 0 | 0 | 0 | 3.32 (0.148) | 91.9%; 100% |
| Lag 47 | 36,992; 48,484; 50,394 | 62 | 0 | 14 | 76 | 3.90 (0.174) | 65.9%; 100% |
| Lag 94 | 45,008; 58,312; 59,550 | 70 | 39 | 37 | 76 | 6.16 (0.275) | 39.0%; 100% |

- **At lags of 10 and 20 the cut does what the design says.** The image peak triggers
  it, about 39 turns in; it removes turns down to the low mark; no image block is ever
  dropped separately. A lag of 15 gives the same row as 10, because the low mark and not
  the coverage limits each cut.
- **At 47 and 94 the cut prevents no image drop.** By the time a turn is covered, its
  image has already been dropped as part of a block. The cut then removes only old text.
- **At 94 the cut costs more than it saves.** Its 70 cuts are extra rewrites on top of
  the 76 image drops, and it writes 6.16 million tokens against 5.09 million with no
  cut.
- **Most of the saving against the record is short results.** The no-cut row already
  writes 0.227 of the recorded tokens.

### Where the cut stops working

Cut command with `--lags 15 23 25 30 35 38 39 40`, steady coverage, seven-day lineage:

| Lag | Cuts made | Of those, freed fewer than ten turns | Image blocks dropped | Share of recorded cache writes | Requests under 40,000 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 23 | 87 | 0 | 0 | 0.168 | 91.2% |
| 25 | 99 | 0 | 0 | 0.188 | 89.9% |
| 30 | 144 | 0 | 0 | 0.265 | 84.9% |
| 35 | 275 | 275 | 0 | 0.488 | 71.1% |
| 38 | 657 | 657 | 0 | 1.131 | 31.5% |
| 39 | 1,263 | 1,263 | 0 | 2.150 | 27.3% |
| 40 | 298 | 247 | 64 | 0.550 | 64.7% |

- **Up to about 23 decisions each cut reaches the low mark.** 39 turns at the image
  peak less the 16 or so the low mark keeps is 23.
- **From about 30 to 39 the rule as written is worse than no cut.** The cut is due at
  the image peak, can free only the few turns covered, and is soon due again; the closer
  the lag is to 39, the sooner. At a lag of 39 it runs at 1,263 of 1,978 requests, each a rewrite of the
  whole window, and writes 2.15 times the recorded total.
- **A minimum size removes the cliff and not the limit.** With `--min-free 10`, a cut
  that would free fewer than ten turns is not made. Lags of 35, 38 and 39 then write
  0.226, 0.250 and 0.260 of the recorded tokens, about what no cut writes, and drop 62 to
  72 image blocks. A lag of 30 is unchanged at 0.265, and 94 is 0.281.

### Seven-day lineage, one session after another

Cut command with `--coverage sessions`. A lag here is the length of a session, and
coverage trails by one to two sessions.

| Session length | Prompt tokens: median; 95th percentile; maximum | Cuts made | Cuts held back | Image blocks dropped | Share of recorded cache writes | Requests under 40,000; under 60,000 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 10 | 29,200; 40,600; 41,934 | 65 | 0 | 0 | 0.130 | 93.0%; 100% |
| 20 | 30,342; 40,600; 41,742 | 78 | 0 | 0 | 0.151 | 92.1%; 100% |
| 47 | 40,884; 55,126; 59,872 | 19 | 61 | 76 | 0.198 | 47.2%; 100% |
| 94 | 45,630; 73,932; 83,582 | 5 | 74 | 76 | 0.235 | 39.0%; 77.1% |

With `--coverage sessions --lags 12 15 25 30`, sessions of 12 and 15 decisions drop no
image block (64 and 99 cuts), and sessions of 25 and 30 drop 62 and 54. At 94 a cut
stayed due and held back over 517 requests in 74 stretches. No cut in this table freed
fewer than ten turns, because coverage arrives a whole session at a time.

### Held-out lineage, steady coverage

Cut command on `"$HELD"`. 15 actors; 1,813 recorded responses with usage and 1,814
simulated requests, because one response carries no usage.

| Row | Prompt tokens: median; 95th percentile; maximum | Cuts made | Of those, freed fewer than ten turns | Cuts held back | Image blocks dropped | Tokens written to the cache, millions (share of recorded) | Requests under 40,000; under 60,000 |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| Recorded | 86,348; 181,327; 243,801 | none | none | none | 129 | 16.05 (1.000) | 18.4%; 29.5% |
| No cut: short results, blocks of 20 | 42,640; 68,180; 87,320 | none | none | none | 68 | 4.30 (0.268) | 43.3%; 86.8% |
| Lag 10 | 28,250; 40,600; 41,742 | 58 | 0 | 0 | 0 | 2.62 (0.163) | 93.6%; 100% |
| Lag 20 | 30,150; 40,600; 41,742 | 68 | 0 | 0 | 0 | 3.02 (0.188) | 92.1%; 100% |
| Lag 47 | 36,134; 47,582; 49,626 | 54 | 0 | 14 | 68 | 3.53 (0.220) | 67.3%; 100% |
| Lag 94 | 42,640; 57,536; 59,454 | 44 | 26 | 42 | 68 | 4.99 (0.311) | 43.3%; 100% |

The pattern is the same as in the seven-day lineage.

### The briefing counts against the marks

The design's low mark of 20,000 tokens "is about 16 turns" only if the briefing is
empty. With `--briefing-tokens 13000`, the first store's 71 facts in full, and the marks
unchanged (seven-day lineage, steady coverage):

- **Lag 10:** the median prompt is 38,400 tokens and 53.5% of requests are under 40,000,
  against 93.4% with no briefing. The cache writes are 0.147 of the recorded total.
- **Lag 47:** 126 cuts, 62 of them freeing fewer than ten turns; 0.372 of the recorded
  cache writes.
- **Lag 94:** 707 cuts, every one freeing fewer than ten turns; 2.058 times the recorded
  cache writes. The window sits over the high mark, so a cut is due at every request.

With both marks raised by the briefing's size (`--low-mark 33000 --high-mark 73000`), the
rows return to the shape of the main table, 13,000 tokens higher: a median of 41,442 at
a lag of 10, and 0.226 and 0.345 of the recorded cache writes at 47 and 94.

## What this means for the screen's protocol

Inference from the three checks:

1. **The curator's brief decides the delivery arm.** As the shadow run wrote it, the
   store would have prevented one of the four losses. The delivery mechanism was early
   enough for all four. A store aimed at recipes and screens, delivered perfectly, would
   not have told the player where the rations, the rod or the batteries were.
2. **The cut needs a number for the curator's lag before it is worth building in.** In
   this model it holds the design's marks when coverage trails by fewer than about 24
   decisions, or with sessions one after another of 15 decisions or fewer. The one
   computed lag is 47.
3. **The cut rule needs two additions the design does not state.** A minimum that a cut
   must free, since without one a lag approaching 39 decisions makes it rewrite the
   window at most requests. And marks that say whether they include the briefing.

## Limits

- **The simulation is a model.** It uses one cost for every turn, treats the briefing as
  a fixed size, ignores snapshot differences appended between briefings, and keeps each
  actor's recorded length although a bounded window would change where actors hand off.
  The record's twelve large cache writes that the trace does not explain are not
  modelled.
- **Lag is taken as a constant.** A real curator's lag would vary with what it reads.
- **One lineage has losses to replay.** The four facts are from the seven-day lineage,
  one route and one model.
- **The need moments are annotations.** Three were adjudicated by the lead with
  knowledge of the outcome; the rod's is the annotator's first `needed` event.
- **Absence was searched by pattern.** A fact that describes one of the three absent
  items without the words searched would have been missed. The patterns are in the
  store command. Every match was read; the 101 statements were not all read in full.
- **The second store covers three admissions.** It could not have held the ration
  record's wording from `sd1a5`, though the cupboard was on screen in `sd1a2` and `sd1a3`.
