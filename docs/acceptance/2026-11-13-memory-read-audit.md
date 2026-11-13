---
owner: lead
status: historical
kind: review
date: '2026-11-13'
scope: 'Audit of every memory read in the sealed host traces of the seven-day lineage (#397), the long-horizon lineages (#382), the development-loop runs (#372) and the held-out lineage (#522): what each read returned, whether the calls that followed used each returned record, what triggered the reads, how old the records were, and which stored facts later actors found again without having been given the record (#594)'
---

# What the player did after each recorded memory read (#594)

## At a glance

**Question.** When a memory read puts a stored record in front of the player, do the
decisions that follow use it? Until now this had been examined for one record, the
batteries case in the [memory note](../design/long-horizon-memory.md).

**Answer.**

- **Reads are rare, and all of one kind.** The sealed traces hold 8 memory reads in 98
  actor traces and 10,991 tool calls. All 8 are `player_memory_query`; `player_memory_read`
  and `player_memory_context` were never called. The 8 reads returned 33 records.
- **A delivered record was used in 10 of 33 cases, and never shown unused.** For the
  other 23 the trace alone cannot say. Seven of the 8 reads returned at least one
  record that a later call used.
- **Use meant going to look.** Eight of the 10 uses are a search typed into the game or
  a fetch of a stored image the record cites. One is a procedure carried out and one a
  statement in the actor's closing record. In 3 of the 8 reads the next game inputs
  changed direction.
- **Reads did not happen where delivery was weakest.** Every read was made by an actor
  that had started from a handoff. None of the 52 actors that started an admission made
  one. Fifteen of the 33 returned records were already in the reader's starting
  context.
- **Most stored facts that were found again had not been delivered.** In the seven-day
  lineage, 80 of the 93 later re-observations of a fact held in a stored record were
  made by an actor that had not been given that record.

**Not known.**

- Whether the 23 unjudged records were used. The trace keeps tool calls and their
  results, not what the model wrote or reasoned.
- Whether any search that followed a read found what it looked for. No frame was viewed.
- Whether a read changed an outcome of play.

**Owner decisions needed.** None. One matter is for the lead: this audit read the
held-out lineage's traces and six of its records in detail
([limits](#limits)).

Terms are in the [glossary](../glossary.md). A **read** here is one call of
`player_memory_query`, `player_memory_read` or `player_memory_context`. A **first actor**
starts an admission; a **successor** starts from a handoff inside it.

## What was read and how

**Evidence.** Sealed evidence only, read where it lies, in the main checkout's
`.runtime/evidence/`. Nothing was run, launched, spent or changed.

| Lineage | Sealed study | Runs | Record of the lineage |
| --- | --- | --- | --- |
| Seven-day lineage (#397) | `397-seven-day` | `sd1a1` to `sd1a7` | [Seven-day record](2026-11-07-seven-day-397.md) |
| Long-horizon lineages (#382) | `372-382-dev-loop` | `lh1a1` to `lh1a3`, `lh2a1`, `lh2a2`, `lh3a1`, `lh3a2` | [Long-horizon record](2026-11-07-long-horizon-382.md) |
| Development-loop runs (#372) | `372-382-dev-loop` | 30 runs named `aid…` and `ceil…`; the six-run sample is `aidB3`, `ceil09`, `ceil07`, `ceil05`, `aidB9`, `aidA5` | [Development-loop record](2026-11-06-development-loop.md); sample drawn in the [probe baseline](2026-11-08-probe-baseline-449.md) |
| Held-out lineage (#522) | `522-held-out` | `lh4a1`, `lh4b1` to `lh4b7` | [Held-out record](2026-11-09-held-out-lineage-522.md) |

The six-run sample of #372 holds no read. The other 24 runs of #372 hold three; they
are audited here as well, because they are sealed in the same study and add cases.

**Every store could be read.** The lineage stores `player-memory-sd1.sqlite3` (11
records), `player-memory-lh1.sqlite3` (2), `player-memory-lh2.sqlite3` (3),
`player-memory-lh3.sqlite3` (2) and the held-out `player-memory-lh4.sqlite3` (15) all
open as `player-memory/2`.

**Reader.** [`memory_reads`](../../harness/evaluation/core/host.py) lists each read
with the records it returned and the reading actor's calls before and after it.
[`tools/memory_reads.py`](../../tools/memory_reads.py) prints that listing with wall
time, the evaluator's game clock, each record's age and whether the actor already held
it. Both count and list; neither judges use. The commands, from the main checkout:

```sh
PY=.venv/bin/python; E=.runtime/evidence; D=$E/372-382-dev-loop
# Seven-day lineage: reads, the store, and the tracked probe annotations
$PY -m tools.memory_reads $E/397-seven-day/computer-sessions --records $E/397-seven-day/evaluations \
  --store $E/397-seven-day/player-memory-sd1.sqlite3 --probes data/evaluation/probes/397 --before 400 --after 400
# All 37 runs of #372 and #382
$PY -m tools.memory_reads $D/computer-sessions --records $D/evaluations --before 400 --after 400
# One long-horizon lineage with its store (the same for lh1 and lh3)
$PY -m tools.memory_reads $D/computer-sessions/lh2a1 $D/computer-sessions/lh2a2 --records $D/evaluations \
  --store $D/player-memory-lh2.sqlite3
# The six-run sample of #372
$PY -m tools.memory_reads $D/computer-sessions/aidB3 $D/computer-sessions/ceil09 $D/computer-sessions/ceil07 \
  $D/computer-sessions/ceil05 $D/computer-sessions/aidB9 $D/computer-sessions/aidA5
# Held-out lineage
$PY -m tools.memory_reads $E/522-held-out/computer-sessions --records $E/522-held-out/evaluations \
  --store $E/522-held-out/player-memory-lh4.sqlite3 --before 400 --after 400
```

Unless a figure below says otherwise, it is printed by one of these commands. The
focused test is `tests/test_evaluation_memory_reads.py`.

**What the trace holds.** A `player-host` trace records each tool call with its
arguments and its result. It does not record what the model wrote. In these 98 traces
the model wrote no text beside its tool calls in any of 11,048 responses, and the host
counted reasoning in 4,205 of them without keeping it (the second line of each
command's output). So the evidence of use is what a later call shows: the text it
typed into the game, an image it fetched, a record or summary it wrote.

## How use was judged

The verdicts are the auditor's reading of the listing. Each verdict names the requests
that show it, so a reviewer can check it against the command's output.

- **Used.** After the read, a call of the same actor shows content of that record: it
  types text the record contains and that the actor had not typed before, it fetches
  an image the record cites, it carries out the steps the record describes with the
  record's own words, or it writes a statement that only that record holds among what
  the actor had been given.
- **Not used.** The trace shows the actor acting against the record, or without it,
  at a point where the record applied. No case met this.
- **Cannot be judged from the trace alone.** Neither holds. Where the later calls fit
  the record but have another possible source, the table says "fits".

**Already held** means the record was in the actor's context before the read: its
handoff context carried it, or the actor wrote it. Use of such a record shows that
the record's content was used, not that the read supplied it.

The reader marks a later call as a **reference** when it types text whose every word
is in a returned record, fetches a source the record cites, or names the record. A
reference is a place to look and is not a verdict. Two words match when they are equal
or share their first five letters, which is how "battery" finds "batteries".

Three limits apply to every verdict.

- **Records are compound.** One record holds a status, a place, a plan and a list of
  goods. "Used" means one clause was used.
- **Absence of a matching call is not evidence.** Most game input is key presses,
  which carry no words.
- **A status snapshot has nothing to act on.** Seven of the 23 unjudged records only
  report who the survivor is, or where it stood and what it held at an earlier time
  (`5653ae` three times, `bbdd48`, `2f9ecd`, `6a1f53`, `886e29`).

## Counts

| Scope | Runs | Traces | Tool calls | Appends | Reads | Records returned | Already held | Used | Not used | Cannot be judged |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Seven-day lineage (#397) | 7 | 14 | 1,969 | 12 | 3 | 17 | 5 | 4 | 0 | 13 |
| All of #372 and #382 | 37 | 69 | 7,216 | 67 | 4 | 10 | 9 | 3 | 0 | 7 |
| of which the three #382 lineages | 7 | 13 | 1,601 | 7 | 1 | 3 | 2 | 1 | 0 | 2 |
| of which the six-run sample of #372 | 6 | 12 | 1,392 | 11 | 0 | 0 | 0 | 0 | 0 | 0 |
| Held-out lineage (#522) | 8 | 15 | 1,806 | 15 | 1 | 6 | 1 | 3 | 0 | 3 |
| **All** | **52** | **98** | **10,991** | **94** | **8** | **33** | **15** | **10** | **0** | **23** |

- The verdict columns are the auditor's, from the per-read tables below. The other
  columns are the first and third lines of each command's output. The #382 row is the
  sum of the three per-lineage commands.
- The 33 returned records are 24 distinct records: 8 in #397, 10 in #372 and #382,
  and 6 in #522.
- Of the 18 returned records that were new to the actor, 3 were used. Of the 15 it
  already held, 7 were used.

## Reconciling the earlier query counts

Two earlier figures looked inconsistent. Both are right, and they count different
sets.

- **"Three queries returning 17 records"** (the issue, and the memory note's last
  sentence on the lineage) is the seven-day lineage alone: 3 reads, 17 records, in 14
  traces. The first command prints it.
- **"Seven queries in 83 traces"** (the memory note) is the seven-day lineage together
  with the sealed #372 and #382 runs: 14 + 69 = 83 traces and 3 + 4 = 7 reads. The
  first two commands print the parts.
- **The held-out lineage adds one**, so the sealed lineages hold 8 reads in 98 traces.
- **The seven-day lineage's 12 appends in 1,969 tool calls** are confirmed. Eleven are
  in the store; the twelfth stayed pending.

Eight further `host.jsonl` files are sealed in five other studies. A text search of
every sealed `host.jsonl` for a `tool-start` event naming one of the three read tools
finds only the 8 reads above. That search was a one-off script, not the tracked reader,
which does not read those older traces.

## Each read

Request numbers are the actor's own, the `N` of `request-N` in its trace. Game time is
the evaluator's clock in seconds from the sealed evaluation record, written as the day
and time the game shows; the conversion (86,400 seconds a day, days counted from one)
is the auditor's and matches the times the player's own records state at three of the
reads. The sealed #372 runs have no evaluation record, so those reads have no game
time. Ages are from the record's `created_wall` to the read.

### Seven-day lineage, `sd1a2`, second actor, request 112 of 196

- **When.** 8 November 2026, 00:27:03 UTC; game clock 5,247,196, spring day 61, 5:33 PM.
- **Asked.** `player_memory_query` with `limit` 30 and no kind.
- **Before.** Requests 104 to 111 are keys only. Earlier the actor had typed
  searches for "sandals", "footwrap", "shoe", "long pointy stick" and "foot rags"
  (requests 4 to 70): the plans of record `6aedc7`, which its handoff context carried.

| Record | Written by; age at the read | Already held | Verdict | What shows it |
| --- | --- | --- | --- | --- |
| `6aedc7` advice | `sd1a2`, first actor; 15 min, 58 game min | Yes | Used | Request 113, the next call, types "q:fine grinding", and 116 to 120 type "cattail starch" and "starch". The record says starch to flour needs "fine grinding 1". None of this had been typed before |
| `94ce47` work | The same | Yes | Used | Request 149 fetches image `507f7c…-3310`, which only this record cites |
| `5653ae` work | The same | Yes | Cannot be judged | A status snapshot of the day before |
| `f49b80` procedure | `sd1a1`, first actor; 54 min, 9.2 game hours | No | Cannot be judged; fits | Requests 128 and 129 type "splintered" as a search, 173 searches the crafting menu for "clean water", and the final report says the fire was relit and four portions of clean water made. That is the record's procedure. But the actor had typed "splintered wood" at request 49, before the read |
| `0c6e56` work | The same | No | Cannot be judged | Identity, status and starting inventory |

- **Next decisions.** They changed: from keys only to a typed search on the record's
  words, one request after the read.

### Seven-day lineage, `sd1a3`, second actor, request 128 of 151: the batteries case

- **When.** 8 November 2026, 01:24:29 UTC; game clock 5,318,923, spring day 62, 1:28 PM.
- **Asked.** `player_memory_query` with `limit` 20 and no kind.
- **Before.** Requests 111 to 124 type searches for something to carry things in
  ("backpack", "bindle", "bag", "sling", "pouch"). The final report says a bindle was
  made.
- **Its context carried no record.** The first actor's handoff named a record ID that
  differs in one character from the stored one (`ef2ead6a94b7…` for `ef2ead6a94f7…`),
  so the context lists an omission and all six returned records were new to this
  actor. The handoff summary did carry the first actor's text.

| Record | Written by; age at the read | Already held | Verdict | What shows it |
| --- | --- | --- | --- | --- |
| `f49b80` procedure | `sd1a1`, first actor; 112 min, 29.1 game hours | No | Used | Requests 129, 130 and 131 each type "battery" as a search, after three different keys. The record's data says the shelter locker holds batteries. Neither "batter" nor "locker" occurs in the actor's starting prompt |
| `ef2ead` work | `sd1a3`, first actor; 17 min, 2.5 game hours | No | Cannot be judged | Its plan, pine needle tea, had been typed at requests 9 to 50 from the handoff summary, before the read |
| `6aedc7` advice | `sd1a2`, first actor; 72 min, 20.9 game hours | No | Cannot be judged | Nothing typed after the read relates to it |
| `94ce47` work | The same | No | Cannot be judged | It holds the fishing rod on the floor; nothing typed relates to it |
| `5653ae` work | The same | No | Cannot be judged | A status snapshot |
| `0c6e56` work | `sd1a1`, first actor; 112 min, 29.1 game hours | No | Cannot be judged | |

- **Next decisions.** They changed: three searches for a battery in the three requests
  after the read. Only 22 calls followed the read; requests 132 to 150 are keys only.
- **Not known.** Whether the searches found batteries. The frames are
  `12ba39c8…-17311`, `-17314` and `-17317`.

### Seven-day lineage, `sd1a4`, second actor, request 76 of 190

- **When.** 8 November 2026, 01:49:07 UTC; game clock 5,320,576, spring day 62, 1:56 PM.
- **Asked.** `player_memory_query` with `kind` `work` and `limit` 20. The kind filter
  left out the procedure record `f49b80` and the advice record `6aedc7`.
- **Before.** Request 71 types "tinder" as a search; 72 to 75 are keys only.

| Record | Written by; age at the read | Already held | Verdict | What shows it |
| --- | --- | --- | --- | --- |
| `081a38` work | `sd1a4`, first actor; 11 min, 10 game min | Yes | Used | Requests 83, 90 and 153 type "matchbook" after typing "tinder" (81, 89, 151). The record says a matchbook lit tinder on the pavement. "matchbook" had not been typed before. The actor had begun the same steps at request 71, from its starting context |
| `bbdd48` work | The same | Yes | Cannot be judged | A status snapshot |
| `ef2ead` work | `sd1a3`, first actor; 41 min, 2.9 game hours | No | Cannot be judged | "pine bough" (88) and "pine needle tea" (100) are also in its starting prompt |
| `94ce47` work | `sd1a2`, first actor; 97 min, 21.4 game hours | No | Cannot be judged | Requests 167, 173 and 179 search for "plank", which the record lists near the shelter and the prompt also names. Nothing about fishing is typed in the 113 calls after the read |
| `5653ae` work | The same | No | Cannot be judged | A status snapshot |
| `0c6e56` work | `sd1a1`, first actor; 136 min, 29.6 game hours | No | Cannot be judged | |

- **Next decisions.** No change: the steps begun at request 71 continued, with
  "tinder" and "matchbook" typed in requests 81 to 90.
- **What the filter cost.** The final report says the actor then walked to the western
  lake, took dirty water and boiled it. The lake and the boiling procedure are in
  `f49b80`, which this query did not return. The roof tank's 18 L of clean water was
  never stored, so no query could have returned it.

### Development-loop run `aidB2` (#372), second actor, request 54 of 157

- **When.** 6 November 2026, 08:35:15 UTC. No game clock.
- **Asked.** `player_memory_query` with `limit` 50 and no kind.
- **Before.** Requests 44 to 52 type searches for "cattail stalk", "clean water" and
  "pot".

| Record | Written by; age at the read | Already held | Verdict | What shows it |
| --- | --- | --- | --- | --- |
| `6eb204` work | `aidB2`, first actor; 8 min | Yes | Used | Request 57 fetches image `30feab17…-1510`, which this record cites. The actor's closing record (156) names it as support |
| `c1bfad` procedure | The same; 17 min | Yes | Cannot be judged; fits | Requests 132 and 144 press the key the record gives for talking to a character. It had not been pressed before the read. The key may be known otherwise |
| `6a1f53` work | The same; 18 min | Yes | Cannot be judged | The world and identity at creation |

- **Next decisions.** A lookup, then no change: request 56 continues the typed
  searches with "clay", 57 fetches the image, and 58 onward return to the key
  patterns of the requests before the searches.

### Development-loop run `aidC2` (#372), second actor, request 7 of 96

- **When.** 6 November 2026, 18:04:37 UTC. No game clock.
- **Asked.** `player_memory_query` with `limit` 30 and no kind.
- **Before.** Requests 5 and 6 type searches for "river" and "pond".

| Record | Written by; age at the read | Already held | Verdict | What shows it |
| --- | --- | --- | --- | --- |
| `b9b834` advice | `aidC2`, first actor; 39 s | Yes | Cannot be judged | The record warns of two feral soldiers to the southeast and says to plan a route away. The actor's closing record (95) and final report say the survivor was killed by a feral soldier. The trace cannot show whether the route was planned with the warning in mind |
| `89fa54` work | The same; 48 s | Yes | Cannot be judged | The closing record names it as support. "clean water" (65) is too general to count |

- **Next decisions.** No visible change: keys only until request 65.

### Development-loop run `aidC5` (#372), second actor, request 88 of 132

- **When.** 6 November 2026, 19:16:07 UTC. No game clock.
- **Asked.** `player_memory_query` with `kind` `work` and `limit` 50. The filter left
  out the advice record `f8bea0`, which the actor's context also carried.
- **Before.** Requests 36 to 87 type searches for "pot", "fire drill", "crowbar",
  "hammer", "cordage", "purifier" and "sheet metal".

| Record | Written by; age at the read | Already held | Verdict | What shows it |
| --- | --- | --- | --- | --- |
| `a18ed7` work | `aidC5`, first actor; 11 min | Yes | Used | Request 91 fetches image `3f763f12…-1553`, which this record cites. The closing record (131) names it as support |
| `98acb4` work | The same | Yes | Cannot be judged | The closing record names it as support, and nothing else |

- **Next decisions.** A lookup, then no change: request 89 repeats the search for
  "pot", 91 fetches the image, and 92 onward continue the typed searches.

### Long-horizon lineage `lh2a2` (#382), second actor, request 18 of 217

- **When.** 7 November 2026, 09:55:31 UTC; game clock 5,242,517, spring day 61, 4:15 PM.
- **Asked.** `player_memory_query` with `limit` 50 and no kind.
- **Before.** Requests 6 to 17 are keys and one click, with no typed text.

| Record | Written by; age at the read | Already held | Verdict | What shows it |
| --- | --- | --- | --- | --- |
| `8be475` claim | `lh2a2`, first actor; 93 s, 65 game s | Yes | Used | Requests 22 and 23 type "survival" and "forag"; 101, 133, 134 and 186 type "digging", "stone hammer", "hammer" and "digging stick". The record says the survival skill was at zero, foraging mostly failed, roots need a digging tool and the shovel needs hammering. The final report says digging sticks were made |
| `2f9ecd` work | The same; 107 s | Yes | Cannot be judged | A status snapshot |
| `ec32ca` work | `lh2a1`, first actor; 42 min, 8.1 game hours | No | Cannot be judged; fits | It says the roof tank holds clean water. The final report says both bottles were refilled from the tank. The starting prompt already said so, in the previous final report and in `8be475` |

- **Next decisions.** They changed: from keys only to a run of typed searches
  (requests 19 to 24: "fire drill", "fire", "survival", "forag", "fish"), two of them
  on the record's subjects.

### Held-out lineage `lh4b3` (#522), second actor, request 16 of 104

- **When.** 10 November 2026, 01:35:56 UTC; game clock 5,218,997, spring day 61, 9:43 AM.
- **Asked.** `player_memory_query` with `limit` 20 and no kind.
- **Before.** Request 4 types "trap"; requests 5 to 15 are keys only.

| Record | Written by; age at the read | Already held | Verdict | What shows it |
| --- | --- | --- | --- | --- |
| `5f3be2` work | `lh4b3`, first actor; 96 s, 15 game s | Yes | Used | Requests 18, 19, 20 and 22 type "forage" or "forag" as a search, which the actor had not typed before. Request 23 fetches image `a0e3e64d…-5494`, which this record cites |
| `f3d815` work | `lh4b2`, second actor; 20 min, 12 game min | No | Used | Requests 77 to 86 type "fish", "q:grass cutting", "plant fiber", "basic fishing rod" and "cordage". The record describes the fishing rod recipe and says grass cutting needs a tool. "grass cutting", "fish" and "cordage" occur nowhere in the starting prompt |
| `598d0b` work | `lh4b2`, first actor; 44 min, 40 game min | No | Used | The closing record (102) says "empty can supplies boiling 1 per historical record". Only this record says so. No game input shows it |
| `505802` work | `lh4b1`, second actor; 72 min, 69 game min | No | Cannot be judged | "pot" (53) is too general to count |
| `262872` work | `lh4b1`, first actor; 88 min, 91 game min | No | Cannot be judged | |
| `886e29` work | The same | No | Cannot be judged | Which world to load; no later call loads a world |

- **Next decisions.** A lookup, then no change: the search for "forage" and the image
  fetch, then keys only, as before the read.
- **Delivery did not stop the re-check.** The actor typed searches for the fishing
  recipes that `f3d815` already describes and wrote their contents out again in its
  closing record.

## What triggered the reads

**Observed.**

- **No host message precedes any read.** Between the previous tool result and each
  read the trace holds only the routine request events (a one-off script listed the
  event types in that span).
- **Every read was a successor's.** Successors made 8 reads in 46 traces. First actors
  made none in 52. A first actor of a continued admission starts with the previous
  final report and no record.
- **Seven of the 8 readers already had records in their context.** Across the three
  studies, 48 of 49 handoff contexts carried records. The exception is the batteries
  case.
- **Handoff summaries point at the records, and that does not predict a read.** By a
  word search for "record", "records", "linked" or "work and advice", 48 of the 49
  summaries do so, and 8 of 46 successors read (a one-off script).
- **Three reads came in an actor's first 20 requests** (requests 7, 16 and 18) and five
  came later (54, 76, 88, 112 and 128).
- **Five reads came within six requests of a typed search** for a thing to make or a
  place (`aidB2`, `aidC5`, `sd1a4`, `sd1a3`, `aidC2`), and three after keys only
  (`sd1a2`, `lh2a2`, `lh4b3`).
- **At the five later reads the host had already dropped old images** from the
  actor's context, 20 to 90 of them. At the three early reads it had dropped none (a
  one-off script read `omitted_images` of the read's own request).
- **Two of the 8 reads asked for kind `work` only** and so left out records the actor
  could have had.

**Inferred.** Each read was the player's own initiative. No host prompt or handoff
step caused it. The five that follow a typed search look like an actor that had not
found what it was searching for. That is a reading of typed text, and the trace does
not give the reason.

## How old a record was when it was read

- **At its first read, no record was older than 88 wall minutes or 9.2 game hours.**
  The wall ages at first read run from 39 seconds to 88 minutes, with a median of 15
  minutes over the 24 distinct records. Game ages exist for 17 of them and run from 15
  seconds to 9.2 hours. The ages are the `first_read` field of the `--json` output; the
  median was taken by hand.
- **The oldest record any read returned was 29.6 game hours old**: `0c6e56` at the
  `sd1a4` read. The batteries record was 29.1 game hours old when it was used.
- **Half of the stored records were never returned by a read.** The five lineage
  stores hold 33 records. Seventeen were returned by some read. Of the 16 that were
  not, 12 were carried by a handoff to the next actor and 4 reached no actor at all
  (the `store` lines of the commands).
- **The 4 that reached no one are in the held-out lineage.** Each was written by the
  last actor of an admission. Such a record crosses to the next admission only if a
  later actor queries, and after `lh4b3` none did.

## Stored facts that later actors found again without the record

The [probe baseline](2026-11-08-probe-baseline-449.md) annotated the seven-day
lineage from its frames. The tracked annotations
([`data/evaluation/probes/397`](../../data/evaluation/probes/397)) mark each fact
with the stored record that holds it, and each later re-observation of a fact known
before a boundary. The first command joins them to the reads and the handoff contexts.

**Observed.**

- The lineage holds 93 re-observations of a fact that a stored record held. In all 93
  the record had been written before the frame.
- In 80 of the 93 the actor had not been given the record, by a handoff or by a read
  before that frame. Thirty-four of those were by a first actor of an admission and 46
  by a successor.
- In the other 13 the actor had been given it: 5 by its handoff, 6 by a read or its
  own write, 2 by both.
- By the annotators' category, the 80 are 32 hazards, 18 items, 12 resources, 8 about
  the survivor, 5 procedures, 4 places and 1 other.
- By record, `f49b80` accounts for 39, `0c6e56` for 19, `94ce47` for 14, `081a38` for
  7 and `6aedc7` for 1.
- By fact, counted from the command's `rediscovery` lines: the floor materials and
  fishing rod of `94ce47` 9 times, the calorie values 5, the clean-water recipe of
  `0c6e56` 4, the lake 4, the locker contents 3 and the stick recipe once.

**Inferred.**

- **Not every one is a loss.** The 32 hazards are sightings of animals and zombies that
  move, and the 8 about the survivor are the identity check each actor is told to
  make. A stored record does not replace those looks.
- **The stable ones are the cases a delivered record could have answered**: the
  materials, the recipes, the lake and the lockers listed above.
- **The three known costly losses fit the same pattern.** The rod record `94ce47` was
  last returned at the `sd1a4` read and reached no actor of `sd1a5` to `sd1a7`. The
  rations record `5db17f` was carried by one handoff and returned by no read. The
  batteries record reached `sd1a3` only at request 128 of its second actor.

The six-run sample of #372 has 2 re-observations of a stored fact, both by an actor
whose handoff had carried the record. No annotation exists for #382 or #522, so the
join cannot be made there.

## What share of reads changed the next decisions

This is the auditor's reading of the five requests after each read against the five
before it.

| What followed the read | Reads | Which |
| --- | ---: | --- |
| The next game inputs changed direction, on content of a returned record | 3 of 8 | `sd1a2` (starch and grinding searches), `sd1a3` (battery searches), `lh2a2` (a run of typed searches) |
| A lookup first, then the same activity as before | 3 of 8 | `aidB2`, `aidC5` (an image fetch three requests after the read), `lh4b3` (a search for "forage", then an image fetch) |
| No visible change | 2 of 8 | `sd1a4` (continued the steps it had begun), `aidC2` (keys only) |

- In one of the three changes, the batteries case, the read was the actor's only
  source of what it acted on. In the other two the record was already in its
  starting context, and the read put it in front of the actor again.
- **Four of the 8 reads were followed by a fetch of a stored image** that a returned
  record cites, 3 to 37 requests later (`aidB2`, `aidC5`, `lh4b3`, `sd1a2`). All four
  images belong to records the actor already held.

## What could not be judged, and what would settle it

Twenty-three of the 33 verdicts are "cannot be judged". Viewing the frames the reading
actor received after the read would settle some. The listing prints the source ID of
the frame each request returned. No frame was viewed for this audit.

| Read | Requests whose frames would help | Question |
| --- | --- | --- |
| `sd1a2` | 128 to 176 | Whether the water was boiled as `f49b80` describes, and whether the actor went to the lockers after fetching the image at 149 |
| `sd1a3` | 129 to 150 | Whether the three battery searches found batteries, and what the 19 key-only requests did |
| `sd1a4` | 166 to 183 | Whether the search for a plank went where `94ce47` says the planks are |
| `aidB2` | 132 to 146 | Whether the key from `c1bfad` opened the conversation |
| `aidC2` | 8 to 64 | Whether the route kept away from the threats `b9b834` names |
| `aidC5` | 92 to 125 | Whether anything from the shelter supplies in `a18ed7` and `98acb4` was acted on |
| `lh2a2` | The key-only requests after 25 | When the tank of `ec32ca` was visited |

Frames cannot settle the seven status snapshots, the three unjudged records of the
held-out read, or any case where the same content was already in the actor's starting
prompt. Those need the model's reasoning, which the trace does not keep.

## What this gives the context design and the memory screen

These are statements of evidence for the context design
([#591](https://github.com/CVX-Hull/enactive/issues/591)) and the screen's protocol
([#590](https://github.com/CVX-Hull/enactive/issues/590)). They propose no design.

1. **Delivery on request does not reach the actor that needs it.** No actor that
   started an admission read, and 80 of 93 re-observed stored facts had not been
   delivered. Where a record was delivered and held something specific, a later call
   used it in 10 of 33 cases and no case shows it ignored.
2. **A delivered record sends the player to look; it does not replace the look.**
   Eight of 10 uses are a search or an image fetch, and the held-out reader re-opened
   recipes its record already described. The player's guide tells it that memory is
   fallible. A design that counts on a delivered fact saving a decision should expect a
   check first.
3. **A query by recency and kind returns what the actor already has.** Fifteen of 33
   returned records were already in context, 7 of the 23 unjudged ones are status
   snapshots, and a `work` filter hid the one record with the water procedure.
4. **Nothing here is older than 29.6 game hours.** No read tests a fact days old.
5. **The trace cannot measure use by itself.** A screen that needs to know whether a
   delivered fact was used needs frames or the model's reasoning, or a measure that
   does not depend on either.

## Limits

- **Eight reads, in three lineages and three single runs, on one route and one model.** The shares above
  describe these reads and support no rate.
- **The verdicts are one auditor's reading**, made without frames and without the
  model's text. A second reader may move cases between "used" and "cannot be judged";
  the request numbers are given so that this can be done.
- **The lexical pointer is English word matching.** It misses paraphrase and matches
  general words. It was used to find places to look, not to decide.
- **"Already held" is what the handoff context and the actor's own writes show.** It
  does not cover what the previous final report or a handoff summary restated in
  other words; the per-read tables note where that matters.
- **The probe annotations are development data** and count every re-observation,
  including incidental ones.
- **The held-out lineage was read.** This audit read the #522 traces and the text of
  six of its records. Anything designed from this page has therefore seen that part of
  #522. The owner has allowed a copy of its saved game to be used for the screen,
  which already ends its held-out standing.
- **One adjacent observation is not a read.** In `sd1a3` the first actor's second
  append, the one holding the roof tank, names the same mistyped record ID in its
  `supports` (request 182) as its handoff does (request 186). The trace shows the
  append's transport as unknown and then pending. Whether the wrong ID is why it was
  never stored is not shown.
