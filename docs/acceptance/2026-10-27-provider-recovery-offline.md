---
owner: lead
review_trigger: Historical offline qualification; supersede with new evidence
status: historical
date: 2026-10-27
scope: Bounded provider HTTP429 recovery and attempt accounting; no external inference or native game
---

# Bounded provider recovery: offline evidence

The user selected an offline provider recovery repair under
[#264](https://github.com/CVX-Hull/enactive/issues/264) after
[native013](2026-10-25-program-breadth.md#fresh-creation013-http429-and-ineffective-nonempty-clear--27-october-2026)
ended on HTTP429. That response's subtype/body is unknown; this repair cannot
establish whether it would have recovered. Both native cases remain closed and
the corrected-routine useful-application outcome remains incomplete.

## Implementation and reuse

The [host contract](../../tools/player_host/README.md) owns current eligibility and
limits. Pinned Pi 1.4.0 already supplies an abortable provider retry helper,
Retry-After handling, a delay ceiling and a transient-error classifier. The host
uses those public exports with at most one retry, while keeping nested provider
retries disabled. Thin integration supplies the missing per-HTTP-attempt charging,
bounded refusal inspection and original-timer/trace joins. It adds no dependency,
generic retry framework, tool replay, model switch or closed-host revival. The
lead maintains this integration; re-evaluate it when the pinned library changes
or offers equivalent attempt accounting and bounded classification directly.

Each actual fetch consumes the original finite allowance and records its actual
serialized body under a unique request ID. Eligibility requires the first HTTP429,
a recognized transient JSON error and no explicit non-transient kind or retry
suppression. Classification reads at most 16 KiB; provider-requested delays over
five seconds fail immediately. One original request timer and host deadline span
both attempts, response inspection and backoff. Unknown refusal usage stays unknown.

The route remains `/2`: no fields or persisted formats change. CLI and driver
already forward host events and final actual-request counts without assuming one
HTTP fetch per assistant message. Their focused fixtures remain valid; zero-retry
histories retain their recorded counts. Source freezes distinguish the new retry
behavior. No persisted mission, native, memory or ingress migration applies.

## Local verification

The implementation starts from `c208fe952bfb7a7c454d1cfaf0c997400fbd2bf0`.
Tests use the installed pinned Pi serializer, injected fetch/Response fixtures,
loopback CLI fixtures and real owned MCP children. They send no external provider
requests, read no credentials and launch no game.

```sh
ENACTIVE_TEST_PYTHON="$PWD/.venv/bin/python" node --test tools/player_host/test/host.test.mjs tools/player_host/test/cli.test.mjs
```

All **63 cases passed** in 20.76 seconds on the permitted host route. The initial
sandboxed combined run could not bind the CLI loopback listener (`EPERM`); it is
retained as an environment failure, not a behavioral pass. The host-route run
exercised the actual listener and MCP children. Additional driver/host-status
fixtures passed **44 cases and 151 subtests** in 0.65 seconds. Fast checkpoint
checks passed; protected full regression and independent review are publication
gates whose exact receipts belong in the PR and tracker.

New cases establish:

- Eligible429 → success sends identical context under distinct charged IDs,
  records unknown refusal usage and reported success usage, then executes the
  requested tool once. A second429 is terminal; no third attempt occurs.
- Exhausted capacity stops after the first refusal without backoff or an extra
  request/completion. Explicit quota, authentication and invalid-request errors
  remain terminal even when their message also contains retry-looking words.
- Retry suppression, excessive delay, malformed/oversized JSON and unknown
  errors cannot authorize another fetch. Raw refusal text and key sentinels do
  not enter retained events or model context.
- Cancellation and request/host deadlines interrupt backoff; cancellation also
  interrupts a stalled refusal body whose cancel hook never settles. A controlled
  clock case proves the original timeout spans both attempts rather than renewing
  at retry. Partial assistant-stream failure neither retries nor dispatches its
  partial tool call.

Existing payload/image/history, current production MCP schema, sequential tool,
process closure, signal and secret-redaction cases also pass. The independent
design review identified a broad-classifier edge: explicit authentication or
invalid-request kinds could contain rate-limit words. Explicit negative checks
and mixed-message fixtures resolve it before publication. Independent implementation
review found a further message-only quota/payment/credit gap. Three actual-host
regressions first failed, then the negative message checks were extended to cover
those explicit non-transient refusals. Remaining lifecycle and trace review was clean.

## Limits and next boundary

This is offline source evidence. It does not qualify provider availability,
successful native creation, corrected-routine application, normal ending or
apparent gameplay latency. The retry's complete exposed wait remains a cost;
fewer assistant turns, cache hits or short API spans are not useful-effect evidence.
No new paid allocation or native admission follows. Historical cumulative requests
remain **642**, and closed unused partitions remain retired. Any later native
assessment needs its own finite scope and current source/configuration freeze.
