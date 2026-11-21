---
owner: lead
status: active
date: '2026-11-13'
scope: 'Design rationale for delivering curated knowledge to the player and a proposal for a context cut bounded by the curator’s published coverage'
review_trigger: Measurement of the curator's lag behind play or changes to the delivery contracts
---

# The player's context: delivery of curated knowledge and a bounded prompt

## At a glance

How can the player keep useful knowledge in context as the prompt grows? Curated
knowledge delivery is adopted. The player receives a briefing and reminders based
on a frozen export of the curator's store, as defined by the [player host contract](../contracts/player-host.md#delivered-knowledge-and-recall)
and demonstrated in the [recall delivery check in play](../acceptance/2026-11-14-recall-fix-delivery-check.md).
The [evaluation contract](../contracts/evaluation.md) owns how delivery is measured.

The curator's lag beside real play and the benefit of delivered memory remain
unknown. The open decision is whether to cut old turns only through the point
the store covers. The owner revisits the cut once lag in play is measured.
[Decision on measuring curator lag before the cut](../decisions/owner-decisions.md#context-cut-waits-for-curator-lag-measurement)

A **request** is one call to the model. A **turn** is a tool call and its result.
The **window** is the turns still in the prompt. [Glossary](../glossary.md)

## The baseline before delivery

In the 13 November 2026 comparison, an actor could get an earlier record through
a memory read or a predecessor's handoff. The baseline appended all turns and
replaced old images with markers in blocks of ten. The memory-read audit shows
why the design puts knowledge in front of the player without requiring a lookup
first. [Memory-read audit](../acceptance/2026-11-13-memory-read-audit.md)

### What the prompt is made of

The baseline fit used text bytes and image counts from `request-start` and
reported tokens from `response-complete` in the sealed seven-day and held-out
lineages. In the seven-day lineage, least squares estimated 0.363 tokens per
text byte and 758 per image. In both lineages images accounted for an estimated
14% of tokens in prompts over 150,000 tokens. The `tool-result` events put
unabridged tool results at 81% of text and the median `computer_input` result
at 1,827 bytes. Each ten-image drop in the seven-day trace rewrote a median of
about 120,000 cached tokens. The 145 requests written to the cache straight after an
image drop were 7.3% of the seven-day lineage's requests and 57.9% of its cost at
configured rates. These comparisons explain why short results and
grouped image eviction matter. In the same lineage, the 20,000–60,000-token
band averaged \$0.0062 per request. The association between smaller prompts and
faster responses may also reflect what the player was doing at that point in play.
[Response time by prompt size](../acceptance/2026-11-13-host-response-time-by-prompt-size.md).
The script that produced the fit, and its full output, are in
[this page as of commit 8326573f](https://github.com/CVX-Hull/enactive/blob/8326573f/docs/design/player-context.md#appendix-the-script).

## Outside evidence

| Source | Date | What it says | Limit |
| --- | --- | --- | --- |
| [Anthropic, prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) | Undated | The cached prefix runs tools, then system, then messages. A change invalidates everything after it | Evidence from a different route |
| [OpenAI, prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) | Undated | A miss follows any change before the cached point, including a compaction setting | Gives no latency figure |
| [OpenRouter, prompt caching](https://openrouter.ai/docs/features/prompt-caching) | Undated | Requests stay on one provider while a session identifier or the first messages match | Describes routing |
| [Anthropic, caching announcement](https://claude.com/blog/prompt-caching) | 14 August 2025 | Time to first token for a 100,000-token prompt was 11.5 s uncached and 2.4 s cached | Vendor measurements on another model |
| [Anthropic, context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing) | Undated | Clearing old tool results invalidates the cache, so clear enough at once to be worth it | Describes cache behavior |
| [Anthropic, context management](https://claude.com/blog/context-management) | 29 September 2025 | Clearing old tool results with a memory tool scored 39% above baseline in an internal test | Internal test outside games |
| Vercel, [agent evaluations](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals) | 27 January 2026 | An index always in context scored 100%. The same knowledge behind a tool scored 53%, and the tool was never called in 56% of cases | One coding task family |
| Bradshaw, [Pokémon research notes](https://www.greaterwrong.com/posts/8aPyKyRrMAQatFSnG/) | 21 April 2025 | Wrong notes misled models for hundreds of actions | Anecdote |
| Chroma, [Context Rot](https://www.trychroma.com/research/context-rot) | 14 July 2025 | Across 18 models, answers worsened as input grew and short focused prompts beat long ones | Simple recall tasks |

The [long-horizon memory review](long-horizon-memory.md#evidence-from-outside-the-project)
also covers an always-present index and a system that rebuilds the prompt for each
decision. The sources do not measure the relative cost and latency of a growing
conversation and a rebuilt prompt in a long game.

## The recommended design

### 1. Short tool results

Short results reduce the cost of every turn while preserving the fields the player
acts on and retaining full receipts for inspection.
[Computer operation results](../contracts/computer-control.md#computer-operations-and-custody)

For the seven-day comparison, the free checks measured a median short result
of 135 bytes. In their simulation, short results and larger image blocks kept
94.9% of requests under 60,000 tokens with no cut, up from 27.6% in the record.
[Short-results measurement and estimate](../acceptance/2026-11-13-memory-screen-free-checks.md#with-the-short-results-as-built)

### 2. A briefing from the curator's store

An article lead brings useful knowledge into view and the index lets the
player discover the rest. The briefing helps at actor starts and reminders
can surface a fact when it applies during play. Both are fallible knowledge.
The player checks them against the current view.
[Articles over facts](world-scoped-memory.md#articles-over-facts)

### The delivery boundary

Delivery keeps the curator's repository outside the player runtime. The host
handles recall, the application serves reads from the frozen export and
the evaluator reads trace evidence after play.
[Delivery boundary design and implementation (#461)](https://github.com/CVX-Hull/enactive/issues/461)

The [knowledge exporter](../../tools/knowledge_export.py) defines the unit layout
for withholding. The [migration standard](../standards/migration.md) governs
version changes across the package, its readers and evaluation.

A recall route that requests structured output depends on a pinned upstream that
accepts strict JSON schemas. [Player host operations](../operations/player-host.md)

### 3. One cut, tied to what the store covers

The proposed cut removes old turns and their images together, then supplies a
fresh briefing in the same request. One marker identifies the removed decisions
and tells the player that the frames remain available through `player_source`.
Keeping the most recent turns verbatim helps the player maintain its current task.
A player-written summary would put durable memory writing in the player's hands,
and an earlier handoff would also discard the recent turns. A prompt rebuilt at
every decision would depend on memory for anything outside the current view.

The host would cut only turns covered by a published snapshot. Coverage records
what the curator has read. Whether the store preserves the distinctions the
player needs is a separate question. If the snapshot is behind play, the host
cuts less or defers the cut and continues to use the existing image eviction
and capacity handoff. The player never waits for a publication.

The proposed trigger is the high token mark or the route's image peak, whichever
comes first. The cut works toward the low token mark, frees at least ten turns
and counts both marks above the briefing's size. The free checks use low and
high marks of 20,000 and 60,000 tokens. At about 950 tokens per turn and a peak of
39 images, they put the first trigger near 40,000 tokens. The values are
comparison parameters. [Cut simulation and minimum useful cut](../acceptance/2026-11-13-memory-screen-free-checks.md#where-the-cut-stops-working)

In the simulation with back-to-back curator sessions, sessions of 15 decisions
avoided dropping image blocks. The computed lag of 47 decisions for the sealed
curator run and the roughly 23 decisions of lag inferred from the session price
pilot both exceed that target. Measure lag beside play and check whether the
retained turns and briefing preserve enough context to continue the current task.
[Session price pilot](../acceptance/2026-11-13-session-price-pilot.md)

### What the curator must publish, and when

The cut needs a published snapshot that identifies the covered decisions and
is fresh enough to release old turns. The proposal uses the latest available
publication at a handoff without delaying the successor. A separate
within-admission delivery proposal appends the difference when a later snapshot
is published, preserving the prefix already sent. The [live curator design](live-curator-integration.md#the-window)
owns window selection. The runner's accounting depends on the rule for
[charging provider refusals (#556)](https://github.com/CVX-Hull/enactive/issues/556).
The [curator component](../components/curator.md#facts-articles-and-grooming)
owns the current store and routes to the grooming rules.

### Stated intent on tool calls

Public intent helps the curator interpret a tool call and can preserve the
thread of recent play across a cut. Each extra field costs output tokens and
then takes space in the window, so the design ties new fields to a reader that
can use them. The [player knowledge and tool call contract](../contracts/computer-control.md#player-knowledge-and-executable-proposals)
owns intent, citations and hints. [Stated intent on tool calls (#384)](https://github.com/CVX-Hull/enactive/issues/384)

<a id="the-migration-that-follows"></a>

### The adopted boundary

The [curator runner](../components/curator.md) is built and tested offline only
and has yet to run beside a real custodian. Within-admission delivery of new
knowledge and the coverage-gated cut are unbuilt.
