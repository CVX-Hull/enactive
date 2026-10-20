---
owner: lead
review_trigger: Observer, memory-effect or mission-publication behavior changes
status: active
---

# Mission observer and nondelivery memory checkpoint

This is source and synthetic UI evidence for #140/#142/#143/#154, not native
gameplay or #144 acceptance. The first campaign's 2,109 inputs, interrupted craft
and ground/carried-water corrections supply development cases. They establish
neither model-call counts, a speedup baseline nor memory efficacy.

The viewer shows objective/player/control, separate live activity and historical
results, readable historical Claims/corrections/Work, source status, requested
reobservations and omissions. Raw JSON remains available. Long preview values
explicitly say they are truncated. Unchanged packets preserve their DOM during
polling. Process/source/exit details and cumulative breakdowns are expandable so
they do not obscure the mission overview. Existing mission locks and immediate
Pause remain; rendering sends no gameplay, retrieval, Resume or retry.

The writer projects retained SQLite rows into cached request counts by kind,
skill and state, and charged primitive counts by disposition. Read-only calls and
pre-admission rejections are excluded. Charged rejection/nondelivery/unknowns
remain counted. Model requests, tool calls and interventions remain unknown.
SQLite's aggregate query reuses the ledger; there is no new history/counter
database, dependency or global setup. The harness maintainer owns this small
projection; replace it if a future measured usage system supplies the same facts.

Known nondelivery no longer invalidates a Claim or Work premise as though an
input might have changed the game. Costs remain charged, while old observations,
other scopes and unknown deliveries still require verification. This repairs
misleading memory invalidation; it does not resolve an unknown ACK or infer stock.

## Verification and limits

Independent source review examined accounting/reopen, freshness, activity
revocation and DOM/input boundaries. The viewer review found silent truncation of
valid support lists; the correction now labels it and preserves raw context.
Source tests cover cumulative counts beyond the recent event window, restart,
unknown/nondelivery costs, cached status without storage reads, source freshness,
malformed/over-bound memory, repeated packet rendering and input locks. An
additional forced Pause between summary construction and cache publication checks
that old activity/lease summaries cannot reappear.

The existing project-local pinned Puppeteer browser inspected intercepted
synthetic viewer data at 1,280, 900 and 600 pixels, with no horizontal overflow,
JavaScript errors or write requests. Pause stayed enabled and Resume disabled.
The first inspection stopped on a probe-only unsupported locator method; its
owned browser closed, the probe was corrected to the DOM scroll method and all
three widths passed. Source, screenshots, results and that failure remain in
`.runtime/research/mission-observer/`. No server or native game was started.
This checks layout and passive behavior, not real game frames or native control.

The source checkpoint, full common checks, exact hosted checks and issue/project
readback belong in PR158 and the owning issues. Common outcome reconciliation,
native character/item/activity qualification, actual retained-memory player
replacement and the integrated supply-and-shelter mission remain open. This
checkpoint grants no gameplay admission or renewed time/input budget.
