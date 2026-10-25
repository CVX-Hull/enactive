---
owner: lead
review_trigger: Historical offline qualification; supersede with new evidence rather than rewriting results
status: historical
date: 2026-10-25
scope: Pinned Pi host request/MCP/process conformance; no inference, native game or cadence qualification
---

# Pi host: adopt for bounded offline use

[#235](https://github.com/CVX-Hull/enactive/issues/235) delivers a project-local
Pi agent-core host through the existing player MCP boundary. The
[brief](../changes/069-controllable-player-host.md) owns design/reuse decisions;
[player interface](../components/player-interface.md), [setup](../setup.md) and
[runbook](../runbook.md#bounded-player-host-activation) own current behavior.
The decision is to adopt this bounded offline capability for the separate
[configuration comparison #236](https://github.com/CVX-Hull/enactive/issues/236).
DSH was not implemented: the maintained Pi core/MCP seams met the tested need
without a fork or another application/runtime. No comparative superiority is shown.

## What was exercised

Pi agent-core, AI and MCP are exactly 1.4.0; the separate npm lock contains
93 integrity-bearing dependency entries. This Mac used existing Node 26.9.0 and
the project Python/MCP environment. The host advertises only frozen allowlisted
schemas and loads explicit context without coding-agent defaults or personal
resources. The existing mission writer, schema, source bindings, memory, Pause
and input authority are unchanged.

The focused integration command at candidate `b54d6c2` was:

```sh
.venv/bin/python -m pytest -q tests/test_pi_player_host.py tests/test_campaign_player.py tests/test_host_status.py tests/test_ci.py
```

It passed **65 Python cases and 206 subtests in 15.25 seconds**. One Python case
executes the **30-case Node conformance suite**; after the fixture-only clock
repair below, that wrapper passed again in 7.64 seconds. Do not count it as another
independent model evaluation. Tests exercised actual Pi serialization and MCP
clients with synthetic SSE, a loopback HTTP endpoint and official Python MCP
fixture children. Current production MCP discovery compared exact nested schemas
from `tool_specs`, including server instructions, without a controller/game launch.

The conformance assertions cover:

- Complete >28 KB tool text, unchanged PNG bytes, one error-status marker and
  original-collection content in subsequent provider requests, without duplicating
  structuredContent beside its text.
- Exact restricted schemas, SDK normalization refused before dispatch, deliberate
  corrected calls and sequential mutation batches.
- Transport loss and malformed-wire errors suppressing queued mutation and later
  provider requests; known returned tool errors remain available for a deliberate
  next decision. No reconnect or replay is performed.
- Explicit output-token limits through both supported provider fields, finite
  request/host bounds, stalled initialization, cancellation, actual CLI SIGINT /
  SIGTERM and closed owned MCP children before settlement.
- Missing usage/cost stays unknown, HTTP refusal status is retained, raw provider
  errors/credential sentinels are not emitted, and ambient SDK logging/header
  configuration is refused. Exact reasoning mapping requires its declared format.
- Unchanged driver original-exit-before-successor and original handoff collection,
  failed-host refusal and fresh Pi contexts. Driver custody tests still use fake
  subprocess handles; the separate CLI tests use real owned test children.

Fast structural checks passed. Independent pre-implementation review found and
resolved the missing outgoing error-status and fatal transport-stop requirements.
Independent source/integration review found the missing output cap, false zero
usage and lost HTTP refusal status; fixes and actual-request assertions passed a
focused recheck. The final reasoning-format/code-document alignment also passed
independent recheck. These are agent reviews, not independent human approval.
The PR owns exact protected full PR/main check and publication receipts; source
tests and this report alone do not establish those hosted results.

## Fixture timing and retained data

The [small JSON receipt](2026-10-25-pi-host-offline.json) retains twelve successive
synthetic hosts, two constructed provider requests per host and fifteen emitted
events per host. Each host used the official Python fixture process, one returned
30,001-character text block plus collection text and a 68-byte PNG, and a final
synthetic response. The second payload contained 30,270 UTF-8 text bytes, one
image and 31,114 serialized payload bytes in this particular fixture.

| Measured lane | Median | Maximum |
| --- | ---: | ---: |
| Complete fixture host, including MCP startup/cleanup | 378.335 ms | 394.189 ms |
| Cumulative event-sink serialization and synchronous append callback per host | 0.251 ms | 0.335 ms |

The sink timer covers only JSON serialization and synchronous file append,
without fsync. It excludes payload-size computation, other hooks, SDK work and
external display; it is not complete instrumentation overhead. Whole-host timing
includes fixture scheduling and process startup, with no model inference or native
input. This is one local cohort, not a baseline speedup, statistical model ranking
or a pass against the interactive-play targets. Provider usage in synthetic
responses is declared fixture data, not measured tokens or actual spend.

Private raw event/call/PID receipts and the one-off measurement script remain in
project `.runtime/pi-host235/`; the public JSON contains derived fixture receipts,
not a claim that all private evidence is published. Earlier pre-review measurement
directories remain distinct from this receipt. This cohort preceded the later
fixture-only deadline synchronization repair; production host code is unchanged,
and the cohort is not a post-repair startup/performance comparison.

## Failures and limits retained

Initial npm registry reads were blocked by restricted network access; a later
project-cache read/install succeeded. A scratch discovery probe initially used
URL.pathname and could not spawn a path containing an escaped space; correcting
it to fileURLToPath allowed actual current-server discovery. Early worker fixture
failures included the obsolete FastMCP import and corruption written to the SDK's
diverted stdout; the final fixture uses current MCPServer and an owned original
wire descriptor. The isolated worker's first npm install targeted its root rather
than the package; generated files were removed, and no tracked root dependency
change was integrated. Its first commit hook lacked the dev interpreter; rerunning
the unmodified hook with the existing project interpreter passed without bypass.

The first lead driver test run had two failures from a misplaced assertion block
and the old CLI-default expectation; both were corrected against the new explicit
host arguments. The first integrated Node run passed nineteen non-listener cases
but eight CLI cases stopped at sandbox loopback `EPERM`, before assertions. The
same real fixtures passed after loopback permission was granted; no passing mock
or weaker assertion replaced that failure. Review findings above remain part of
the evidence rather than being erased by later passes.

The first protected full PR run [40225983226](https://github.com/CVX-Hull/enactive/actions/runs/40225983226)
failed at `b54d6c2`: 2,120 Python cases and 4,006 subtests passed, while the wrapper
reported 29/30 Node cases. The one-second tool-deadline test could expire during
heavy fixture imports before PID publication under CI load. Its earlier local pass
also lacked proof that tool execution had started. The fixture now records PID
before those imports. The tool-deadline test holds Node timeout timers during real
initialization, observes actual `mutate-start` with a bounded real-timer poll, then
advances host work/cleanup before the longer MCP tool timeout. It asserts no tool
completion and actual child exit, retaining the independent real startup-timeout
and signal cases. An outer real watchdog remains. Production timeouts were not
changed. Targeted checks and independent causal-test review passed; the failed
protected result remains failed and a new candidate requires fresh full CI.

No game, native build, live provider call or credential retrieval occurred.
The user's reported DeepInfra credential was not read or stored. The core has no
automatic compaction/session restore, and currently admits only the documented
OpenAI-compatible reasoning format. It therefore does not establish long-campaign
suitability, live endpoint compatibility, vision comprehension, organic learning,
normal game ending or improved cadence. #222 remains independent; #145 retains
its actual #164 readiness gate. #236 must freeze real provider/model capabilities,
exact configuration, financial/execution ceilings and useful outcomes before a
live comparison. Revisit Pi adoption on upgrade, incompatibility, measured upkeep
or a simpler maintained integration; the lead owns that decision and cleanup.
