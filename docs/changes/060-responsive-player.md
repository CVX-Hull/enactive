---
owner: lead
review_trigger: Player host, tool presentation, context, model configuration or responsiveness evidence changes
status: proposed
---

# Responsive independent play

## Decision and user consequence

The present player is too slow. Successful input delivery, a large token cache or
an asynchronous adviser does not establish watchable progress. Admit the complete
player configuration against useful progress and quality, rather than selecting
a model by its capability, size or name. A slow model belongs on the active path
only when genuinely useful execution covers its delay and the whole configuration
meets the same responsiveness target. The engineering lead remains outside play.

This is a proposed implementation change. The [standards](../engineering.md)
state the requirement; current behavior remains in [architecture](../architecture.md)
and [protocol](../protocol.md). No source, budget, acceptance condition or actor
brief in an already deciding campaign is changed by this proposal.

## Evidence and diagnosis

The completed original player of campaign010 made 122 post-admission MCP calls,
including 84 skill calls. Across 121 adjacent nonoverlapping calls, the gap was
6.665 seconds median, 18.091 seconds nearest-rank p95 and 117.428 seconds maximum.
These gaps include reasoning, other work, scheduling and transport; they do not
isolate inference. Skill tool duration had a 1.166-second median and 6.953-second
p95. This actor is only a campaign prefix, including lifecycle work, not a whole
campaign or representative routine-play cohort.

Its 128 activated-role responses accumulated 30,937,286 input tokens, of which
30,230,272 were cached. Counts include repeated context and reporting through
FINAL; they are neither unique context nor billing measurements. The closed host
also contains 91 nested result envelopes: 5,472,271 serialized text characters
versus 1,453,376 in their inner result text. These are persisted event envelopes,
not measured model-facing duplication. A subsequent audit of 137 forwarded exec
outputs parsed 260 JSON text blocks and found no nested MCP result envelopes.
For example, event line164 wraps a result whose adjacent forwarded output at
line165 is the direct 12,294-character value. The earlier inference that nesting
was model-visible is retracted. Raw events and model-forwarded records are
different observation layers; typed images must not be counted as textual base64.

The private original trace is pinned by SHA-256
`dd87845904c3287e8b3a77ed3fcc9b4cd2b34e083e83f2111aabb51421bd3a21`.
Its actor-evidence analysis and independent measurement review are retained with
campaign010. Raw host transcripts remain private. This assessment does not accept
an elapsed survival day or the seven-day outcome.

Code inspection confirms `_finish` retrieves another snapshot after every write;
`snapshot` returns nearly the full mission and selected source/image. The MCP
adapter returns JSON text and structured content. That SDK shape is not by itself
proof that the model receives both; actual host presentation must be tested.
The producer already derives common wire bindings and some skills already batch
primitives. The remaining problem is not solved by claiming no automation exists.

## First source slice and its limits

The current source adds the `player-view/1` MCP projection described in
[the protocol](../protocol.md#integrated-mission-lifecycle). It preserves complete
selected evidence, operations, obligations and uncertainty; removes matching
native visible-state duplicates; and references progress only when identical to
the included operation result. Independent review caught lost progress when an
ID was absent and lost native details when source retrieval failed. Both were
corrected, with regression cases also retaining a genuinely different latest view.
This is a presentation change; cached canonical results and dispatch stay intact.

An offline paired canonical-JSON measurement on120 parsed original-player results
reduces1,754,116 to1,308,602 UTF-8 bytes;253 parsed successor results reduce4,623,962
to3,759,209. Four original and32 successor records were unparsed and excluded.
These include preflight and different tool families. They are reconstructed inner
result bytes, not actual model token counts, outer host envelopes or measured
latency. Advisory values are not shortened by this projection; adding the marker
slightly increases their size. Actual loaded-host framing remains to qualify.

Passive advisory next reads can now wait up to40 seconds on the existing condition
variable. Other waits remain15 seconds; claim/collection retains the original
remaining allowance and stable identity. This can reduce idle model round trips
without a new daemon. It neither eliminates idle turns nor qualifies responsive
play. The next short trial uses the user's Luna/low selection; bounded context,
automatic plumbing, useful execution coverage and actual performance remain the
broader tracked work below.

The integrated player/presentation/lifecycle/reflection focused lane passes91
tests in162.415s. Separate clean-context source reviews found no remaining
material findings after the presentation fixes. These are component and SDK
results; no loaded-host performance or new graphical acceptance is inferred.

## Selected implementation direction

| Responsibility | Owner and change |
| --- | --- |
| Intent, novel interpretation, raw-input discovery, applicability and revision | Deciding player; compact current context, ordinary-input fallback and optional useful skills |
| IDs, request binding, submit/collect, cursors, serialization and presentation | Existing adapter/software; preserve stable admitted identity and uncertain-delivery handling |
| Confirmed supported execution and stop conditions | Existing single writer; finite closed-loop continuation, current observations and interruption, without a model round trip per primitive |
| Trajectory selection, exposure/selection/result attribution and idle waiting | Software; existing receipts, bounded jobs, event-driven wakeup rather than model polling |
| Candidate procedures, contradictions and longer-horizon advice | Bounded background model jobs; provisional, source-linked and independently consumable |
| Source history and audit | Existing ledger/archive; complete canonical records retrievable by reference |

The model's default result should contain the decision-relevant disposition,
operation/source handles, current control state, relevant limits, unresolved
effects and next decision. Supply the applicable image as an image part when the
decision requires it. Avoid nested transport JSON, repeated mission histories and
unnecessary new screenshots. Full receipts stay available to machines and audit.
Do not strip fields needed for an actual decision or silently truncate complete
handoff obligations. Migrate the presentation and all callers/tests together;
no legacy result mode is retained as a compatibility path.

Use existing SDK result types and a thin explicit presentation boundary. The
official [event-export issue](https://github.com/openai/codex/issues/44126) and
[current source](https://github.com/openai/codex/blob/main/codex-rs/core/src/mcp_tool_call.rs)
separate event truncation from the returned model/tool result. They corroborate
the distinction, not exact parity with this host version. No production unwrap
fix is justified by the event wrappers. Test errors, partial/unknown settlement, image blocks
and actual loaded-host forwarding. Reduce bookkeeping fields by software binding,
without allowing a newer snapshot to silently retarget an existing operation.

Context is a working set, not the archive. Preserve objective, selected plan/skill,
current source, obligations, unknown effects, relevant procedure versions and
invalidators; retrieve older detail on demand. Use fresh-context continuation to
test sufficiency. The current Codex coding host also injects instructions, tools
and accumulated conversation: changing MCP responses alone cannot promise control
of that host's context. Assess supported host/runtime capabilities before choosing
a dedicated player host. No paid provider or new spending is authorized here.

An already justified closed-loop skill can execute while another bounded model
job prepares a future decision. If its useful remaining work lasts W and planning
takes L, overlap requires L to fit W at the relevant tail, with production keeping
pace with consumption over time. Stale queued work supplies no coverage. When no
justified action exists, expose deliberation; do not hide it with filler movement,
Waits or animation. Never speculate native input, fork saves for rollback or
replay uncertain delivery. Larger batches are not a substitute for feedback.

## Admission experiment and controls

Before the next responsiveness experiment, #164 must freeze finite scenario
cohorts, exact host/model/reasoning/context/tool settings, repeated attempts,
numerical thresholds and quality/ending requirements. Suggested initial targets
are routine new-decision-to-visible-effect p95 at most 2 seconds, no unexplained
routine stall over 5 seconds, and useful visible effects within 500 ms during
supported local execution. These are engineering starting points, not literature
constants or passed gates. Loading, intentionally long activities and novel
reasoning need separately declared cohorts and finite ceilings; retain their
frequency and costs in the whole-run result instead of excluding inconvenient
samples. The existing native ACK and browser targets remain separate measurements.

Measure full event-to-confirmed-effect intervals, calls per meaningful outcome,
visible progress/stalls, response bytes and actual model-visible context, p50/p95/
maximum and deadline misses, refusals, failures, unknowns and resource cost.
Disclose sample counts and unsupported clocks; do not substitute tool gaps for
isolated inference or browser decode for actual paint. Predeclare how useful
progress and permissible exceptions are assessed. Reject configurations that fail
the frozen target; test faster configurations or improve useful execution before
another long responsiveness qualification. Do not weaken outcome or authority
requirements to pass a speed target.

C-REVIEW checks the boundaries, actual-host result shape, prior-research crosswalk
and action-item dispositions. C-USABILITY checks cadence and honest visible
deliberation. Existing focused portable/SDK tests should cover presentation and
continuation invariants; native graphical evidence must establish actual host
behavior and measured progress. These tests are planned work, not implemented
latency enforcement. Full CI remains an integration gate, never a latency proof.

## Delivery, reuse and maintenance

GitHub owns live scope: [#164](https://github.com/CVX-Hull/enactive/issues/164)
owns result/host/context automation and configuration admission;
[#178](https://github.com/CVX-Hull/enactive/issues/178) event-driven advisory work;
[#177](https://github.com/CVX-Hull/enactive/issues/177) memory working-set and
procedure continuity; [#145](https://github.com/CVX-Hull/enactive/issues/145) the
independent campaign outcome. This is not a second status tracker.

Lead owns interface design/integration. After contracts freeze, one worker may own
the adapter/presentation/tests and a second the disjoint advisory scheduling/tests,
in separate worktrees; shared runtime changes stay with one integrator. A clean
reviewer tests model-facing and machine-facing evidence separately. Changes remain
isolated until the deciding run closes and every actual player/adviser/successor
is FINAL. Preserve partial outcomes and costs if a run ends before its objective.

Retain the existing MCP SDK, ledger, archive, memory store, observer timing and
test lanes. No new workflow engine, history store, tool-search service, vector DB
or robot runtime is justified by these findings. A dedicated small player runtime
can be a useful accelerator if the current host cannot meet the measured need;
compare actual capabilities and recurring cost before building it. Retire custom
presentation glue when supported SDK/host capabilities cover the gap.

Refresh research on a host/model/context redesign or before claiming current
performance; requalify affected cohorts after material changes or a measured
regression. Revisit numerical budgets with prospective evidence, retaining old
failures and reasons. Do not renew controls merely by changing dates. The
[research synthesis](../research-responsive-gameplay.md) owns external sources,
read scope, transfer limits and the prior-document crosswalk.
