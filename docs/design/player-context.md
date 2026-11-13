---
owner: lead
status: active
date: '2026-11-13'
scope: 'Design of the playing model''s context (#591): what is always in front of the player, what the curator publishes and when it is delivered, and how the context stays small enough to be fast; five options compared on what the player knows, response time and cost, from the sealed traces, the audit of memory reads (#594), the trace reader''s figures (#592) and dated outside sources; the contract question for stated intent on tool calls (#384); the migration that follows; owner decisions. No run, game launch or model call was made'
review_trigger: A measurement of any estimate marked as such here, the memory screen's result, or the adoption migration that builds the briefing and the cut
---

# The player's context: delivery of curated knowledge and a bounded prompt

## At a glance

- **Question.** How should the playing model's context be built so that it holds what the
  player needs to know, and stays small enough to answer quickly?
- **What the traces show.** Three things, each from sealed evidence:
  1. **The player does not fetch knowledge, and uses it when it is put in front of it.** No
     actor that started an admission ever read its memory. A delivered record was used in
     10 of 33 cases and never shown ignored
     ([audit](../acceptance/2026-11-13-memory-read-audit.md)).
  2. **Most of a large prompt is the harness's own receipts, not the game.** In prompts over
     150,000 tokens, images are about 14% of the tokens. Text is the rest, and 81% of the
     text is tool results as the tool server returned them: a median of 1,827 bytes of
     identifiers and receipt fields for each input
     ([what the prompt is made of](#what-the-prompt-is-made-of)).
  3. **Most of the money goes to rewriting the prompt cache when old images are dropped.**
     Each time the host dropped a block of ten images, the whole conversation after the
     fixed head was written to the cache again. Those 145 requests are 7.3% of requests
     and 57.9% of the cost in the seven-day lineage.
- **Recommendation.** Three changes, in this order:
  1. **Short tool results.** The player gets the few fields it acts on. The full receipt
     stays in the trace.
  2. **A briefing from the curator's store** at the start of every actor: the facts that
     matter now in full, and one line for each of the others.
  3. **One cut for old turns and old images together**, made only up to the point the
     curator's store already covers, with a fresh briefing in the same request.
- **Expected effect, estimated and not measured.**
  - With the first change alone, a 150-request actor's prompt falls from about 180,000
    tokens to about 75,000. Short results are built: the median `computer_input` result
    is 135 bytes where it was 1,827, which at the fitted rate puts that prompt nearer
    66,000 tokens ([free checks](../acceptance/2026-11-13-memory-screen-free-checks.md#with-the-short-results-as-built)).
  - With all three, the prompt stays between about 20,000 and 40,000 tokens **only if the
    curator keeps within about 15 decisions of play**. That is not measured. At the lag
    computed for the one recorded curator run, 47 decisions, the cut would rarely free
    anything and the prompt would behave as with the first change alone.
  - Recorded responses to prompts of 20,000 to 60,000 tokens had a median of 5.1 s and
    cost \$0.0062 a request, against 7.0 s and \$0.0194 overall (seven-day lineage; 6.1 s
    and \$0.0056 against 8.3 s and \$0.0157 in the held-out lineage).
- **Not known.** Whether a player with a short window and a briefing plays as well as one
  that keeps its whole conversation, and what curator sessions during play cost. No
  recorded run tests either. The
  [memory screen](https://github.com/CVX-Hull/enactive/issues/590) is where they are
  measured.
- **Owner decisions.** The four questions under [owner decisions](#owner-decisions) are
  answered in the [owner decision log](../decisions/owner-decisions.md). This note is
  the working description of the design the memory screen tests.

Terms are in the [glossary](../glossary.md). A **request** is one call to the model; it
returns one tool call. A **turn** is a tool call with its result. The **window** is the
turns still in the prompt.

## Fixed inputs

The owner decided these on 13 November 2026
([owner decision log](../decisions/owner-decisions.md)); this note does not reopen them.

- The dedicated curator writes the store. The player does not maintain it.
- A bounded context is the first speed lever, and it is designed with memory.
- Memory comes before speed. The 2 s criterion is an aspiration that does not gate this
  work.
- The current route stays. A small model is not the player.
- No hard cap on delivered text unless experience shows a need.

## The context today

From the code and the [player host contract](../contracts/player-host.md), checked on
13 November 2026.

| Part | What it holds | Changes during an actor |
| --- | --- | --- |
| System prompt | The frozen player guide and the tool server's instructions; 9,291 bytes in the seven-day lineage | Never; identical for every actor of a package |
| Tool table | 14 tools and `player_finish` | Never |
| First message | The mission, the actor's audit identifiers and, for a successor, the handoff packet | Never |
| Turns | Every tool call and result since the actor started | Only grows. Nothing is removed or summarised |
| Images | One frame for most results | When more than 39 are held, the oldest ten become text markers |
| Notices | Warnings before a stop the host enforces | Appended, then kept |

- **No knowledge is put in front of the player.** A stored record reaches it only when it
  calls a memory tool, or in a handoff packet the outgoing actor chose.
- **A new admission starts with the previous final report only**, 333 to 1,503 bytes.
- **The curator is not part of play.** It has run only over sealed traces.
- **The prompt cache is reused only when a request extends the one before it**, byte for
  byte. On this route a change anywhere in the conversation loses the cache for all of
  it: after each image drop the provider read only the fixed head, about 3,900 tokens,
  from the cache.

## What the sealed traces show

### The player does not pull, and uses what is pushed

From the [audit of memory reads](../acceptance/2026-11-13-memory-read-audit.md) over 98
actor traces and 10,991 tool calls in four sealed lineages:

- **Eight reads in all, none by an actor that started an admission.** All eight were by
  successors, seven of which already had records in their handoff packet.
- **A delivered record was used in 10 of 33 cases; for the other 23 the trace cannot
  say.** No case shows a delivered record ignored where it applied.
- **Use meant going to look.** Eight of the ten uses are a search typed into the game or a
  fetch of a stored image. A delivered fact starts a check; it does not replace one.
- **A query by recency and kind returns what the actor already has.** Fifteen of the 33
  returned records were already in the reader's context, and a filter by kind hid the one
  record that held the water procedure.
- **In the seven-day lineage, 80 of 93 later re-observations of a stored fact were by an
  actor that had not been given the record.** Forty of the 80 are moving hazards or the
  identity check and are not losses; the rest are materials, recipes and places.
- **The trace cannot show use.** The model wrote no text beside its tool calls in any of
  11,048 responses, and its reasoning is counted but not kept.

### Response time and cost rise with the prompt

From the [trace reader's record](../acceptance/2026-11-13-host-response-time-by-prompt-size.md),
seven-day lineage, 1,978 responses:

| Prompt tokens | Responses | Median | Within 5 s | Mean cost per request |
| --- | ---: | ---: | ---: | ---: |
| Under 20,000 | 160 | 2.7 s | 93.8% | \$0.0030 |
| 20,000 to 60,000 | 386 | 5.1 s | 48.2% | \$0.0062 |
| 60,000 to 100,000 | 514 | 6.9 s | 10.3% | \$0.0150 |
| 100,000 to 150,000 | 421 | 7.7 s | 3.3% | \$0.0234 |
| Over 150,000 | 497 | 9.0 s | 0.4% | \$0.0362 |

The same pattern holds in the three other sealed sets. Across all 6,799 responses, none
to a prompt of 20,000 tokens or more finished within 2 s. Prompt size is confounded with
how far into its run an actor is, so the table shows an association, not a cause.

### What the prompt is made of

Computed for this note by the script in the [appendix](#appendix-the-script) from the
`request-start`, `context-manifest` and `response-complete` events. Token counts per part
are not recorded, so they are fitted: prompt tokens against text bytes and image count,
by least squares.

| Quantity | Seven-day lineage (#397) | Held-out lineage (#522) |
| --- | ---: | ---: |
| Responses | 1,978 | 1,813 |
| Fitted tokens per text byte; per image | 0.363; 758 | 0.376; 718 |
| Median absolute error of the fit, tokens | 1,145 | 452 |
| Prompts over 150,000 tokens: median share that is images | 14% | 14% |
| Tool result parts' share of all text bytes in each actor's last request | 88% | 88% |
| Median tool result part, bytes | 2,064 | 2,023 |
| Requests per actor, median | 154 | 109 |
| Request at which the prompt first passes 60,000 tokens, median | 39 | 38 |
| Requests that wrote over 30,000 tokens to the cache | 157 (7.9%) | 128 (7.1%) |
| Their share of cost at configured rates | 63.5% | 59.1% |
| Of those, straight after images were dropped | 145 | 128 |

- **The 88% includes the host's own markers.** When the host drops an image it adds a
  276-byte marker to that result. Counted as the tool server returned them, results are
  81% of the text, and the median `computer_input` result is 1,827 bytes (1,923 results;
  the independent review of this note computed both from the `tool-result` events).
- **A tool result is mostly identifiers.** A single key press returns about 1,360 bytes:
  four schema names, an operation identifier, the session identifier four times and
  again inside the source identifier, the actor identifier, two receipts, a source record
  with a hash, and the frame's geometry twice. None of it describes the game. By the
  fit, a 1,827-byte result is about 660 tokens, close to the 758 of the frame it comes
  with.
- **The player needs few of those fields.** It uses the status, the `source_id` (for
  clicks and to read a frame again) and, when delivery is uncertain, the operation
  identifier.
- **Each drop of ten images rewrites a median of about 120,000 tokens** in the seven-day
  lineage. The trace's list of prompt parts shows most of the conversation unchanged at
  a drop, and the provider still read only the fixed head from its cache (3,865 to 3,999
  tokens at all 145 drops). Cache expiry is not the cause: no gap before a request
  exceeds 3.6 s.
- **Twelve other large writes are not explained by the trace.** The request extended the
  one before it and the cache was still missed. They are 5.5% of the cost. A cut does
  not remove them.

## Outside evidence

Read on 13 November 2026 by an explorer; the lead did not open the pages. Provider
documentation pages carry no date.

| Source | Date | What it says | Limit |
| --- | --- | --- | --- |
| Anthropic, [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) | Undated | The cached prefix runs tools, then system, then messages; a change invalidates everything after it | A different provider from the route's |
| OpenAI, [prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) | Undated | A miss follows any change before the cached point, including a compaction setting | States no latency figure |
| OpenRouter, [prompt caching](https://openrouter.ai/docs/features/prompt-caching) | Undated | Requests stay on one provider while a session identifier or the first messages match | |
| Anthropic, [caching announcement](https://claude.com/blog/prompt-caching) | The page shows 14 August 2025; the feature was probably announced a year earlier | Time to first token for a 100,000-token prompt: 11.5 s uncached, 2.4 s cached | The vendor's own figures, another model |
| Anthropic, [context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing) | Undated | Clearing old tool results invalidates the cache, so clear enough at once to be worth it | |
| Anthropic, [context management](https://claude.com/blog/context-management) | 29 September 2025 | Clearing old tool results with a memory tool scored 39% above the baseline in an internal test | Internal test, not games |
| Vercel, [agent evaluations](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals) | 27 January 2026 | An index always in context scored 100%; the same knowledge behind a tool the model had to call scored 53%, and the tool was never called in 56% of cases | One coding task family |
| Bradshaw, [Pokémon research notes](https://www.greaterwrong.com/posts/8aPyKyRrMAQatFSnG/) | 21 April 2025 | Wrong notes misled models for hundreds of actions | Anecdote |
| Chroma, [Context Rot](https://www.trychroma.com/research/context-rot) | 14 July 2025 | 18 models answer worse as input grows; short focused prompts beat long ones | Simple recall tasks |

The memory note's [outside evidence](long-horizon-memory.md#evidence-from-outside-the-project)
adds Continual Harness (an index in every prompt; most entries never read) and AgenticSTS
(a prompt rebuilt at every decision; ten games per condition).

Not found: a provider's curve of response time against prompt length, or any measured
comparison of a rebuilt prompt against a growing conversation in a long game.

## The options

Each is judged on what the player knows, response time and cost. "Recorded" means from
the sealed traces; "estimate" means arithmetic on them.

| Option | What the player knows | Response time | Cost | Verdict |
| --- | --- | --- | --- | --- |
| **Index of stored knowledge kept in the conversation** | Everything stored is one request away, and the player sees that it exists. Outside evidence: an index in context is used where a tool alone is not | A line per item adds little. Re-sent in full only when the cache is rewritten anyway | Small | **Taken, as part of the briefing** |
| **Working set at each start** | Fixes the admission boundary, where 0.32 of what was held crossed. Bounded by what one text can hold, so over a week old facts need the index | None added per request | One cache write per actor of the briefing's size | **Taken, as the briefing** |
| **Compaction by a model's summary** | A summary by the playing model is what a handoff carries now, and handoffs kept 0.62. It would make the player the writer of its own memory | Good after each summary; the summary itself is an extra request | A rewrite at each summary plus the summary request | **Not taken.** The curator is the writer |
| **Short results and a larger image block only** | Nothing changes: the whole conversation stays, and nothing is delivered | Estimate: about 75,000 tokens at request 150, where recorded medians are 6.9 s | A rewrite of the whole conversation at each image drop, about half as often with a block of 20 | **Taken as the first layer.** It fixes no memory loss, so it is not the design |
| **Removing old turns without a summary** | Loses whatever in those turns the store does not hold. Safe only up to the point the store covers | Recorded: 5.1 s median at 20,000 to 60,000 tokens against 7.0 s overall | One rewrite of a small prompt per cut, against a 120,000-token rewrite every ten requests now | **Taken, tied to the store's coverage** |
| **Earlier handoff** | Each handoff discards the whole conversation, the most recent turns included; kept 0.62 without a briefing. With a briefing it would lose less. With short results, about three actors where there is one | The best: every actor starts at about 4,500 tokens plus the briefing | One small write per actor; the outgoing actor spends requests writing its packet, and the host and tool server restart | **Not the main lever.** The cut is a handoff that keeps the latest turns and asks the player to write nothing. Handoff stays for capacity, and is the fallback if the cut cannot be built soundly |
| **Prompt rebuilt at each decision** | Memory is the only carrier, so nothing can be skipped, and nothing the store lacks survives a single request | Unknown. Only the fixed head can be cached, so each request pays for the rest uncached | Unknown; likely higher per request | **Not now.** It is where the cut leads if the window can be made very short; decided after the screen |

## The recommended design

Three layers. Each can be built and judged alone, in this order.

### 1. Short tool results

- **Mechanism.** The tool server returns to the model the status, the `source_id`, the
  frame's size and, when a delivery is partial or unknown, the operation identifier and
  what to do next. The full receipt goes to the trace and the session database
  unchanged, and `computer_result` still returns it by identifier. The host reads
  `source_id` from a result and the full receipt of a handoff; both stay.
- **What the player loses.** Nothing it has been seen to use. The fields removed are
  identifiers of the session and actor, which are in its first message, and receipt
  internals.
- **Effect, estimate.** The recorded median prompt at request 150 is about 180,000
  tokens. With short results it is about 75,000: 150 results and calls at about 33,000,
  the host's markers for dropped images at about 11,000, 35 images at about 27,000 and
  the fixed head. Each image drop then rewrites well under half as much. A block of 20
  images in place of 10, which the [player host page](../operations/player-host.md)
  already recommends, halves how often that happens.
- **Risk.** A field the player does rely on is removed. The serialization tests and one
  short development run before any paid study would show it.

### 2. A briefing from the curator's store

- **Mechanism.** The first message of every actor, at an admission and at a handoff alike,
  carries a briefing built by software from the latest published snapshot:
  - **in full**: the facts a recall model chooses for this actor from the mission, the
    previous final report and the store's index
    ([general memory](general-memory.md#2-delivery-making-the-player-use-memory));
  - **as an index**: one line for every other fact, with its identifier, subject and
    order of sighting;
  - **a stamp**: the decision the snapshot covers.
- **Reminders during play.** After the briefing is built, a recall model may add short
  reminders as notices that stay in the history
  ([general memory](general-memory.md#2-delivery-making-the-player-use-memory)).
- **Reading more.** `player_memory_read` returns an item by the identifier on its index
  line. `player_memory_query` gains search by text. Both read the curator's store.
- **Between briefings.** When a newer snapshot is published, the next request carries the
  difference as a new message at the end. Earlier messages are untouched, so the cache
  holds.
- **Marking.** The briefing is labelled as fallible knowledge, not instructions, as
  [ADR 009](../decisions/009-curated-player.md) requires. The current screen wins on
  conflict.
- **No cap.** The split between full items and index lines is the curator's brief, not a
  byte limit. If briefings grow until they slow play, that is the experience the owner's
  decision asks for.
- **Size, from the one store that exists.** The shadow run's sealed store for the
  seven-day lineage holds 71 facts in 36,947 bytes, about 13,000 tokens if every fact
  were sent in full. That is most of a 20,000-token low mark, which is why the index
  matters even at two game days.
- **What it fixes.** The three stored losses of the seven-day lineage were records that
  existed and were not in front of the actor that needed them. A briefing at every start
  puts every stored item, or its index line, there. Whether the curator's store would
  have held those facts is a separate question, checked for free in the
  [replay](#what-the-memory-screen-should-check).

### 3. One cut, tied to what the store covers

- **Mechanism.** When the window passes a high mark, the host removes the oldest turns and
  their images down to a low mark, in one request. That request also carries a fresh
  briefing. The removed turns become one marker that says which decisions were removed
  and that frames stay readable by `player_source`.
- **The rule that makes it safe.** The host removes a turn only if the published snapshot
  covers it. If the curator is behind, the cut removes less, or nothing, and the window
  grows as it does today until the existing capacity handoff. The player never waits for
  the curator, and nothing leaves the prompt before the store has had the chance to keep
  it.
- **Images.** A cut removes the images of the turns it removes. The cut is made when the
  window passes the high mark or holds the image peak, whichever comes first, so that
  images are not dropped separately. The peak of 39 is set against the provider's image
  limit and stays.
- **Starting marks.** Low 20,000 tokens, which is about 16 turns; high 60,000. With
  short results a turn is about 950 tokens, so at a peak of 39 images the image peak
  comes first, near 40,000 tokens. The marks are parameters of the route, like the image
  limits now, and are set from measurement, not by this note.
- **Effect when the curator keeps up, estimate.** A cut about every 23 requests, which
  rewrites about 20,000 tokens plus the briefing. Today a rewrite of about 120,000
  tokens comes every ten requests once 39 images are held.
- **Effect when the curator is behind.** The window after a cut is the low mark or the
  turns not yet covered, whichever is larger. The one recorded curator run gives a lag
  of 47 decisions, computed from a session's median wall time of 189 s and the player's
  pace, not observed in play. At that lag, with one session after another, coverage
  trails by 47 to 94 turns, a cut frees almost nothing, and images are dropped in blocks
  as today. The prompt then behaves as with short results alone. For the cut to hold
  the marks, a session must finish within about 15 decisions, roughly two minutes of
  play. A session that reads 20 new turns should be much shorter than one that reads a
  whole admission, but that is not measured.
- **Two additions to the rule**, from the
  [free checks](../acceptance/2026-11-13-memory-screen-free-checks.md#where-the-cut-stops-working):
  a cut is made only if it frees at least ten turns, and both marks are counted above
  the briefing's size. Without the first, a curator about 39 decisions behind makes the
  host rewrite the window at most requests.
- **The cut is not built.** The session price pilot reported a median of \$0.20 and 99 s
  for 20 decisions, with coverage trailing play by about 23 decisions; the owner decided
  on 13 November 2026 to build delivery first and decide the cut after it is measured
  ([record](../acceptance/2026-11-13-session-price-pilot.md)).
- **Coverage is not recorded today.** A curator session records the frames of the window
  it was given, not the last decision its published facts reflect. The stamp is new.
- **Risk.** The player loses the thread of what it was doing. Two things carry it: the
  low mark keeps the most recent turns verbatim, and the briefing's open commitments.
  Whether that is enough is the main thing the screen measures.

### What the curator must publish, and when

| Requirement | Why |
| --- | --- |
| Facts in the game-neutral format `curator-fact/3`: free text with a type, citations, an optional subject and the order of sighting; retire and merge operations ([general memory](general-memory.md#1-the-fact-format-and-the-curator)) | Compound records cannot be kept current; a fixed set of kinds or a required place assumes one genre of game |
| A grooming session between admissions that reorganizes the whole store and ranks it | The store otherwise grows without bound: 279 records after about 1,900 decisions |
| A coverage stamp on every snapshot: the last decision it has read | The cut rule depends on it |
| A session at each admission boundary; the next admission waits for it | The game is saved and closed there, so waiting costs no play |
| A session at each handoff; the successor does not wait | It starts with the latest snapshot and its predecessor's summary as a labelled hint, and gets the difference when the session publishes |
| A session during play whenever the decisions not yet covered pass a trigger | So that cuts can proceed. The curator does not run in live play today. How short such a session can be, and what it costs, decide whether the cut holds its marks |
| A failed request charged at zero when the provider refused it | Done ([#556](https://github.com/CVX-Hull/enactive/issues/556)) |

**A first store for a game already in progress** comes from curator sessions over that
game's sealed trace, admission by admission, as the shadow runner does now. For the
screen's start on the held-out lineage's saved game that is a paid step. The shadow run
cost 0.61 to 0.87 of the actor's spend, which for that lineage's \$28.88 is about \$18 to
\$25. It is proposed and costed in the screen's protocol and is not approved by this note.

**Cost during play is not measured.** More frequent sessions cost more than one per
admission. With the player's own cost per request falling to about a third, the curator
may become the larger part of the bill. The screen's protocol must price it.

### Stated intent on tool calls

[ADR 009](../decisions/009-curated-player.md) proposes fields on the player's existing
tool calls: `intent` and `expectation` required; `cites`, `goal`, `confidence` and `flags`
optional; and a separate `player_hint` tool
([#384](https://github.com/CVX-Hull/enactive/issues/384)). They share this context,
because every field is output the player writes and then re-reads.

- **Why intent matters to this design.** The trace holds keys and frames and no words.
  The curator has to infer what the player was doing. After a cut, the player's own recent
  intents are also the cheapest record of its thread.
- **What it costs.** Output arrives at about 80 to 130 tokens a second. A one-line intent
  of about 20 tokens adds about 0.2 s to a response, and about 20 tokens a request to
  the window. An expectation doubles both.
- **Recommendation.**
  - `intent`: required, one line.
  - `cites`: optional. It names the stored items the call relies on, and is the only way
    the trace could show that delivered knowledge was used. The screen cannot rest on an
    optional field, so its use measure must not depend on it.
  - `expectation`, `goal`, `confidence`, `flags`: not added now. ADR 009 makes
    `expectation` required and names its first reader as the curator, which would attend
    to a wrong prediction. No curator brief or session reads it yet, and the other
    readers (programs, source reliability) are not built. Each field costs output on
    every call, so each is added with the work that reads it.
  - `player_hint`: added. It replaces the player's append as its one way to tell the
    curator something.

### The migration that follows

One change under S-MIGRATION, made when the design is adopted
([#463](https://github.com/CVX-Hull/enactive/issues/463)), except layer 1, which stands
alone:

| Area | Change |
| --- | --- |
| Tool results (layer 1) | The form of `player-computer-result` the tool server returns to the model; the host's reading of `source_id` and of the handoff receipt, which keep working; the [computer control contract](../contracts/computer-control.md); the player guide's table of calls; the image block in the route |
| Player host contract | A new version: the briefing in the first message, snapshot differences as tail messages, the cut and its coverage rule, the two marks in the route, image dropping folded into the cut. "No compaction" becomes "no summary; removal only of covered turns" |
| Tool table | `player_memory_append` and `player_memory_context` removed; `player_memory_read` and `player_memory_query` read the curator's store, with text search; `player_hint` added; `intent` required on every call |
| Handoff | The packet carries the summary as a labelled hint and no record roots |
| Driver and package | More than two actors in an admission are no longer needed for capacity; the driver passes the snapshot to each actor and waits for the boundary session |
| Player guide | Memory is no longer optional reading: what the briefing is, that it is fallible, how to read an index line, when to hint |
| Curator | Live triggers, the coverage stamp, the briefing builder ([#460](https://github.com/CVX-Hull/enactive/issues/460), [#461](https://github.com/CVX-Hull/enactive/issues/461)) |
| Tests | The host's serialization and prefix tests, the player-host contract suite, the memory and handoff tests |

The player's own store and its record format are retired in that change. Until then they
stay as they are.

## What the memory screen should check

Input to [#590](https://github.com/CVX-Hull/enactive/issues/590). The first four cost
nothing.

1. **Would the curator's store have held the four lost facts?** The shadow run's sealed
   store for the seven-day lineage exists. Search it for the roof tank, the rations, the
   fishing rod and the batteries, and record at which decision each first appears.
2. **Replay of the stored losses against this delivery.** For each, the first request at
   which a briefing or a difference would have shown the item, against when play needed
   it.
3. **Simulation of the cut.** Over the sealed traces, for assumed curator lags of 10, 20,
   47 and 94 decisions: how large the window would have been at each request, how often
   the cut would have been held back, and the rewrites it would have made. It is a
   simulation because the shadow run recorded no coverage by decision.
4. **Exact token counts for layer 1.** Rebuild a sample of recorded requests with short
   results and count tokens with the route's tokenizer, to replace the fit above.
5. **The live screen's arms.** The current player against the player with all three
   layers and a curator-written store. Layer 1 belongs in both arms, so that the
   difference measured is memory and the cut, not shorter receipts.
6. **A use measure that does not need the model's words.** The audit shows the trace
   cannot give one. Candidates: time and requests to reach a place or item the store
   holds, and the count of things found again.

## Owner decisions

These four questions were put to the owner with the recommendations shown. The answers
are rows in the [owner decision log](../decisions/owner-decisions.md).

1. **Direction.** Adopt the three layers as the design the memory screen tests.
   *Recommended: yes.*
2. **Short tool results first, as their own change.** They cost no knowledge, need no
   curator and make every later run cheaper, including the screen's baseline arm.
   *Recommended: build now; \$0 until a run uses it.*
3. **Curator sessions during play.** The cut and the snapshot differences need the
   curator to run while the game is being played, which it does not do today and whose
   cost is not priced. The alternative is a curator at boundaries only: the briefing
   still works, and the prompt is bounded by short results and handoff, not by a cut.
   *Recommended: design for sessions during play, priced in the screen's protocol before
   anything is spent.*
4. **Fields on tool calls.** `intent` required and `cites` optional now, the others with
   the work that reads them; or all of ADR 009's fields now, `expectation` required.
   *Recommended: intent and cites now.*

Not a decision: the player stops writing to the store. The owner decided that on
8 November 2026 and reaffirmed it on 13 November. The migration above carries it out at
adoption, and the timing is the lead's.

## Limits

- **Every effect size here is an estimate** from one route and one model. Token shares
  come from a fit, not from counts.
- **Response time by prompt size is an association.** A short prompt made by a cut may
  not be as fast as a short prompt at the start of an actor.
- **Nothing recorded tests play with a short window.** The player has always had its
  whole conversation.
- **The curator's cost and lag during play are not measured.** The coverage rule makes
  lag safe; it does not make it cheap.
- **The audit judged use from typed text without frames**, for eight reads.
- **Outside sources were read by an explorer through a summarising tool.**

## Appendix: the script

Run from the main checkout as
`.venv/bin/python SCRIPT .runtime/evidence/397-seven-day/computer-sessions/sd1a*` and
with `.runtime/evidence/522-held-out/computer-sessions/lh4*`. It reads sealed traces only.

```python
import glob, json, statistics as st, sys
rows, actors, results, causes = [], [], [], {"images newly omitted": 0, "other": 0}
for path in sorted(p for run in sys.argv[1:] for p in glob.glob(run + "/actors/*/host.jsonl")):
    start, seq, parts, omitted, was_omitted = {}, [], [], 0, 0
    for line in open(path):
        e = json.loads(line)
        if e["type"] == "request-start": start[e["request_id"]] = e
        elif e["type"] == "context-image-projection": omitted = e["omitted_images"]
        elif e["type"] == "context-manifest": parts = parts[:e["reused_prefix_parts"]] + e["parts"]
        elif e["type"] == "response-complete" and e.get("usage_available"):
            s, u = start[e["request_id"]], e["usage"]
            seq.append(dict(prompt=u["input"] + u["cacheRead"] + u["cacheWrite"], write=u["cacheWrite"], text=s["text_bytes"],
                            images=s["image_parts"], cost=u["cost"]["total"], ms=e["monotonic_ms"] - s["monotonic_ms"]))
            if u["cacheWrite"] > 30000: causes["images newly omitted" if omitted > was_omitted else "other"] += 1
            was_omitted = omitted
    actors.append(seq); rows += seq
    results += [q["bytes"] for q in parts if q["kind"] == "tool_result_text"]
n, cost = len(rows), sum(r["cost"] for r in rows)
xx, xy, yy = (sum(r[a] * r[b] for r in rows) for a, b in (("text", "text"), ("text", "images"), ("images", "images")))
xp, yp = (sum(r[a] * r["prompt"] for r in rows) for a in ("text", "images"))
a, b = (xp * yy - yp * xy) / (xx * yy - xy ** 2), (xx * yp - xy * xp) / (xx * yy - xy ** 2)
print(f"{n} responses; prompt tokens = {a:.3f} per text byte + {b:.0f} per image; median absolute error {st.median(abs(r['prompt'] - a * r['text'] - b * r['images']) for r in rows):.0f}")
big = [r for r in rows if r["prompt"] >= 150000]
print(f"over 150,000: median images {st.median(r['images'] for r in big):.0f}, median image share {100 * st.median(b * r['images'] / r['prompt'] for r in big):.0f}%, median text bytes {st.median(r['text'] for r in big):.0f}")
print(f"tool results in the final requests: {len(results)}, median {st.median(results):.0f} bytes, mean {sum(results) / len(results):.0f}; share of text bytes {100 * sum(results) / sum(s[-1]['text'] for s in actors):.0f}%")
print(f"requests per actor: median {st.median(len(s) for s in actors):.0f}; first request: median prompt {st.median(s[0]['prompt'] for s in actors):.0f}, median {st.median(s[0]['ms'] for s in actors) / 1000:.1f} s")
for limit in (40000, 60000, 100000):
    first = [i for i in (next((i + 1 for i, r in enumerate(s) if r["prompt"] >= limit), 0) for s in actors) if i]
    under = [r for r in rows if r["prompt"] < limit]
    print(f"{limit}: first reached at request {st.median(first):.0f} (median of {len(first)} actors); {len(under)} responses under it, median {st.median(r['ms'] for r in under) / 1000:.1f} s, mean ${sum(r['cost'] for r in under) / len(under):.4f}")
large = [r for r in rows if r["write"] > 30000]
print(f"mean cost per request ${cost / n:.4f}; writes over 30,000 tokens: {len(large)} requests ({100 * len(large) / n:.1f}%), {100 * sum(r['cost'] for r in large) / cost:.1f}% of cost at configured rates, median write {st.median(r['write'] for r in large):.0f}; preceded by {causes}")
```

The estimates in [short tool results](#1-short-tool-results) are arithmetic on its output:
150 short results of about 150 bytes and 150 calls of about 450 bytes at 0.363 tokens a
byte are about 33,000 tokens; about 112 markers of 276 bytes are about 11,000; 35 images
at 758 tokens are about 27,000; the fixed head is about 4,500. The independent review
reran this script and matched every figure in the table, and checked the fit another
way: from one request to the next, the prompt grows by 0.33 tokens for each byte of text
added and about 820 for a turn with an image.
