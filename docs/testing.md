---
owner: maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
status: active
---

# Testing: responsibilities, selection and overlap

Start with the changed [responsibility](architecture.md), then the exact
[computer/player contract](contracts/computer-control.md) and assertions.
[Testing standards](standards/testing.md) and [protected CI policy](workflows/ci-profiles.md#protected-ci-profiles)
own mandatory checks. This page explains selection, not a passing-run inventory.

## What the test families add

| Layer | Representative current assertions | Limit |
| --- | --- | --- |
| Mechanical schema/wire | [Protocol](../tests/test_computer_protocol.py), [wire](../tests/test_computer_wire.py) and [channel](../tests/test_computer_channel.py) tests | Synthetic packet/socket cases cannot establish real game effects. |
| Writer and composition | [Runtime](../tests/test_computer_runtime.py), [application](../tests/test_player_application.py), [level custody](../tests/test_player_level.py), [MCP](../tests/test_player_host_adapter.py) | Exercise original resources/IDs, custody, reader class, log projection, level commit, service isolation and collection using explicit doubles. |
| Player knowledge and programs | [Memory](../tests/test_player_memory.py), [programs](../tests/test_player_programs.py) | Pure provenance, image views, bounded evaluation/context and proposals; no usefulness claim. |
| Player host and orchestration | [Contract suite](../tests/test_player_host_contract.py), [adapter](../tests/test_player_host_adapter.py), [driver](../tests/test_campaign_player.py), [custodian](../tests/test_campaign_run.py) | Each listed adapter through `player-host/2` only, plus actual adapter/MCP with synthetic provider/owned children; no paid inference or game quality claim. |
| Compiled adapter | [Native check](../tests/computer_native_check.py), [lock check](../tests/computer_lock_check.py) | Actual SDL/socket/inherited-lock behavior in a fixture; separate from CDDA usability. |
| Spectator | [Passive projection](../tests/test_observer_activity.py), [HTTP boundary](../tests/test_server.py), [viewer races](../tests/test_viewer.cjs) | Verified passive reads, coverage, links and session/Pause behavior under explicit doubles; rendered browser/native evidence remains separate. |
| Recorded investigation | [Export](../tests/test_investigation.py), [live snapshot](../tests/test_investigation_live.py), [worker/reader](../tests/test_investigation.cjs), [session attachment](../tests/test_investigation_session.cjs) | Closed schema, bounded images/rows/read subprocess, clocks, explicit links, inert text, cancellation and stale-session attachment; neither fixtures nor imported integrity prove authorship or gameplay efficacy. |
| Real game | [Native acceptance](operations/native-acceptance.md) | Actual visible input effects, authentic useful work, save/new-child reload and separate normal exit on frozen source. |

## Select checks from the changed responsibility

For a development checkpoint, run `.venv/bin/python tools/check.py --fast` and
relevant focused tests. The default `.venv/bin/python tools/check.py` runs full
portable regression. Use the explicit CI profiles only under the policy; exact
commands/membership stay in the existing runner and shared manifest. Broad
source changes require full regression before merge. Checks never install packages.

A schema change needs ingress/version/negative cases at each affected consumer.
A custody or handoff change needs original collection, cancellation, permanent
Pause, quiescence and no renewed limits. A program change needs real image-view
inputs, bounded failures and original child-operation retention. A source/native
change needs compiled interoperability and real-game qualification as applicable.

## Responsibility assurance

Parent [architecture assurance](architecture.md#responsibility-assurance) routes
to component-specific invariants and evidence limits. Tests should observe failure
responsibility, not mirror implementation literals. Native7's literal-count/AST
protocol check is retired with its producers; strict ingress/version tests,
compiled interoperability and independent migration review own the new boundary.

## Engineering assurance

The strict lane includes metadata/local references, governance, import boundaries,
syntax/lint, whitespace and diagrams in the declared profile. Metadata, diagram
hashes and parser success cannot establish content truth. Independent review
compares changed claims/flows with actual contracts and source.

## Advisory test-impact experiment

The optional historical test-impact/verification pilots are retired. Their
measurement records remain historical; no old pilot executable or environment is
part of the current check/acceptance route.

## Review overlap by failure responsibility

Keep a test at the layer that owns the invariant; retain another only where it
adds a distinct consumer/failure boundary. The portable suite, compiled native
fixtures, actual gameplay and protected PR/main checks are separate lanes.
Record each executed command, exact result and unrun lane. A passing double never
replaces a real failure; a repaired source does not relabel prior outcomes.

## Keep state, clocks and cost honest

Tests and reports preserve original operation/source IDs, deadlines, capacities,
partial delivery and unknowns. Do not replay uncertain input or reopen a used
package. Host HTTP attempts, configured estimates, conservative reservations and
invoices are distinct. Monotonic elapsed time, original capture time and read
time are distinct. [Production outcomes](acceptance/2026-10-29-computer-control.md)
retain actual play and its limits separately from source and protected CI receipts.
