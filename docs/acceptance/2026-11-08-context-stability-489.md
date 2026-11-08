---
owner: lead
status: historical
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

## Limitations

- **One session, one route, one model.** The cached share is a single measurement.
- **The actor's cache is unmeasured.** Its changes are proven offline only, because an actor
  run is a separate gameplay-spend decision.
