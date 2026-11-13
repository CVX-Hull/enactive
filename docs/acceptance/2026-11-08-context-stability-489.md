---
owner: lead
status: historical
kind: change
date: '2026-11-08'
scope: 'Request stability and clarity for the actor and curator hosts, the no-spend serialization proof, and one paid curator session checking whether session affinity raises the cached share (#489)'
review_trigger: None; dated record
---

# Context stability and clarity (#489)

ADR 009's P1.0 asked for the actor's and the curator's request contexts to be stable and
clear before P1. The owner allowed changes to the running actor host for cache and clarity
only, with no change to game semantics. This record covers what changed, how it was proven
without spend, and the one paid curator session that checked the cache. No game ran, and the
actor spent nothing.

## What changed

**Both hosts.**
- **Affinity.** One affinity value per session.
  - **Actor host.** A digest of the mechanical session ID, shared by the session's actors.
    The serializer sends it as `x-session-id` on the OpenRouter route. A request without it
    fails closed before any charge.
  - **Curator proxy.** A random value per proxy, set by the proxy itself. The host's own
    header is never forwarded, and the ledger keeps only a digest.
- **Image eviction.** Omission markers name the frame's source ID, so the frame can be read
  again.
- **Tail notices.** Notices go at the tail, persist once their threshold is crossed, and are
  never stored. They warn before every forced stop:
  - actor: context capacity, the request allowance and the work deadline;
  - curator: budget, wall time and context. The wall time only warns; it never refuses
    tools.

**Actor host only.**
- **A byte-stable system prompt and tool table.**
  - The session and actor IDs moved from the MCP instructions to the first user message.
  - Every actor gets the same tool table.
  - The final actor keeps `player_handoff`, and the service refuses its call with no state
    change.
- **The handoff packet.** The successor's prompt labels it as its predecessor's. The stored
  format, `player-handoff-context/1`, is unchanged. A first version renamed its fields
  instead, which would have made every sealed trace unreadable to the projection, the
  evaluator and the probe timeline. It was reverted.
- **Validation feedback.** It keeps the validator's own wording and adds the narrowed
  diagnostic after it.

**Curator command line.** The default image window is now 16 images, evicted 8 at a time:
- sixteen of the largest recorded frames fit the proxy's 8 MiB request limit;
- the #454 runs, and this check, passed 24/12 explicitly.

## No-spend proof

- **Actor host.** [`serialization.test.mjs`](../../tools/player_host/test/serialization.test.mjs)
  serializes consecutive requests through Pi's real provider serializer against a local
  upstream. It covers:
  - first request, appends, eviction and a retry;
  - the three tail notices;
  - a handoff successor and a new admission.

  It proves that each request's messages, minus the tail, extend the previous request's byte
  for byte, and that the system prompt and tool table are identical across actors.
- **Curator host.** Its host tests do the same.
- **Real adapter.** A Python test proves that its instructions are identical across actors
  and name no identity.
- **Results.**
  - Actor-host tests: 224 pass. Curator-host tests: 18 pass.
  - The full regression (`tools/check.py --profile full`) passed: 951 Python tests.

## The paid check

**Setup.** One terra session over #397 `sd1a1`:
- the first session of #454's terra run, so it starts from the same fresh knowledge
  repository;
- the #454 settings: effort medium, a 24/12 image window and 120 requests at most;
- a $2 proxy cap.

The session sealed after 15 requests, and the gate accepted its one submission.

| | #454 `sd1a1` | #489 check |
| --- | ---: | ---: |
| Requests | 67 | 15 |
| Cost | $7.08 | **$1.39** |
| Cost per request | $0.106 | $0.093 |
| Prompt tokens | 5,781,993 | 1,130,499 |
| Cached prompt tokens | 180,230 | 37,660 |
| **Cached share** | 3.1% | **3.3%** |
| Affinity value sent | No | Yes, one constant value on all 15 requests (proxy ledger) |

**Result: affinity did not raise the cached share.** The missing affinity header was the
#454 record's leading hypothesis. It was not verified, and it is now refuted as the whole
cause.
- **Where the cache stops.** Every request from the second on reads exactly 2,690 cached
  tokens, about the system prompt, tool table and brief. The cache never reuses the growing
  history after them, although the request prefix is byte-stable in the offline tests.
- **Not images.** Every request in this session carried text only.
- **Why it cost less.** This session made fewer requests. The cost per request is about the
  same as #454's.

**What remains open.** One of two things is happening:
- the real request bodies diverge right after the brief in a way the fake-upstream tests do
  not reproduce;
- or the route does not cache past that point.

**Candidate checks.**
- **No spend.** Capture per-message digests of the real request bodies at the proxy.
- **Needs approval.** Allow a `prompt_cache_key` through the proxy. Pi derives one from the
  affinity value only for a direct `api.openai.com` route, and the proxy's body allowlist
  refuses the field today. This is a proxy change plus a further paid check, so it needs
  the owner's decision.

**Spend.** $1.39 of the approved $2.

## Deviations

- **The worker's packet rename.** It renamed the handoff packet's fields and refused the old
  version in every reader. That would have broken reading sealed traces. The lead reverted it
  and kept the labelling in the successor's prompt only.
- **Affinity scope.** The worker first derived the affinity value per actor. The lead changed
  it to per session, as the goal states, so that successors can reuse the shared prefix.
- **Wall time.** The worker made the curator's wall-time limit move the budget phase, which
  refuses reading tools. That was a behaviour change nobody asked for, so it was made a
  warning only.
- **Validation wording.** The worker left this item undone, and the lead completed it.
- **Review.** An independent review found three issues: the 24-image default's reservation
  and body size, a test gap for the real adapter's instructions, and an over-broad handoff
  description. All three were fixed before the paid check.

## Follow-up: the cause found

Added on 8 November 2026, after the owner's P1 decision to fix caching first. The owner approved
up to $1.50 for the diagnosis, and it spent **$0.535**. The figures above stand as measured.

**Free checks.** These ruled out the host and narrowed the suspects.
- **The actor caches.** In the sealed #397 trace, on the same terra route, the actor host
  cached 89.9% of prompt tokens over 85 requests (`sd1a2`, actor 001). Each request read the
  whole previous prompt.
- **The curator's bodies are stable.** Its real request bodies were captured from a capped
  4-request session ($0.069) through the proxy's own reservation hook. Each request's history
  was a byte-identical prefix of the next, and every other field was identical. An offline run
  with parallel tool calls and encrypted reasoning details also showed stable bodies.
- **Not Pi's breakpoints.** Pi marks Anthropic-style cache breakpoints only on `anthropic/`
  routes. Terra's route has none.

**Paid replays.** The captured bodies were re-sent through an in-process curator proxy. Each
sequence ran in fresh cache space (a nonce in the system prompt) with output capped low.
Cached prompt tokens:

| Variant | Request 2 | Request 3 |
| --- | ---: | ---: |
| As sent (budget note rewritten at the tail) | 2,700 | 2,700 |
| No tail note | **2,845**, all of request 1 | **6,327**, all of request 2 |
| No `reasoning_details` in history | 2,702 | 2,702 |
| `service_tier: "default"` | 2,701 | 2,701 |
| `prompt_cache_key` | 2,701 | 2,701 |
| **Notes kept where first sent** | **2,881**, all of request 1 | **6,400**, all of request 2 |

An identical body sent twice read 48,945 of its 48,948 prompt tokens on the second send.

**Cause.** This provider reuses a cached request only when a later request extends it. The
curator ended every request with a budget note that the next request replaced. So no earlier
request was ever extended, and only the static opening, read from earlier entries, was reused.
- **The actor.** Its notices were rare, so it was unaffected. But #489's own design,
  notices that persist once their threshold is passed, would have broken caching for every
  request after the threshold.
- **Not the cause.** Session affinity, `service_tier`, `prompt_cache_key` and the encrypted
  reasoning are not the cause.

**Fix.** Both hosts keep every note and notice in the history, unchanged, at the place where
it was first sent. A retry resends the same body below that step. Each request then extends
the previous one byte for byte. The serialization tests of both hosts now assert that the
whole previous request, notes included, is a prefix of the next.

**Accumulation.** Notes accumulate in the context. In the actor host, only the first notice of
each kind carries the wrap-up instructions; later ones update the figure. A curator note is
about 40–80 tokens, so 120 requests add at most about 10k.

**Raw figures.** Every token figure above and the spend are tracked, usage only, in
[`data/curator/cache-diagnosis-489.json`](../../data/curator/cache-diagnosis-489.json). The charges
come from the proxy ledgers: $0.0686 for the capped session, $0.4024 for the replays and $0.0639
for the notes-kept run. The driver scripts and captured bodies were scratch and are not retained.

**Not yet measured.** The fixed hosts have not run a paid session. The P1 pilot measures the
cached share, as the pre-registration requires.

## Limitations

- **One session, one route, one model.** The cached share is a single measurement.
- **The actor's cache is unmeasured.** Its changes are proven offline only, because an actor
  run is a separate gameplay-spend decision.
