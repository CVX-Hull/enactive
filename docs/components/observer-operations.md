---
owner: harness maintainer
review_trigger: Spectator, HTTP assembly, host accounting, setup, build or retention responsibilities change
status: active
---

# Spectator, host operations and delivery

Parent: [system architecture](../architecture.md). This view answers: “What am I
seeing, and what does it prove?” The spectator displays real Tiles frames plus
cached ownership, mission progress, uncertainty and cost. It does not choose
tactics or execute the player's plan. All services are local; public network
exposure is outside the supported deployment.

## Internal responsibilities

| Block | Responsibility and state | Implementation / operating reference |
| --- | --- | --- |
| Server/CLI | Assemble runtime/controller and expose local typed ingress, status, frame and Pause | [server.py](../../harness/server.py), [CLI](../../harness/__main__.py); [runbook](../runbook.md) |
| Viewer | Render actual image and cached projections, label current vs historical state, serialize polling, retain bounded timing samples | [app.js](../../web/app.js), [web](../../web/) |
| Host projection | Read existing driver receipts and distinguish original/successor observed events; no process discovery or activation | [host_status.py](../../harness/host_status.py) |
| Setup/build | Pinned project-local dependencies/native source, explicit windowed userdir, signed build provenance | [tools](../../tools/); [setup](../setup.md), [environment history](../environment.md) |
| Retention | Preserve run evidence and original saves; verify owned artifacts before retiring disposable worlds/processes | [runbook retention](../runbook.md#evidence-retention-and-cleanup) |

The wrapper requests background window startup; those child-process hints are not
global Mac settings or proof of OS focus. Prepared operation uses explicit project
userdir and windowed settings. Native input can still trigger takeover. The
spectator must show that ownership consequence accurately.

## Projection and failure semantics

Cached status performs no new memory/evidence retrieval. A displayed memory packet
is historical as of its ID; rendering cannot promote it to current truth. Counters
derive from the ledger/host receipts rather than a viewer accounting store. Host
start/exit events and a driver terminal report do not prove live process state,
independent memory application, native Save/cleanup or successful survival.

The viewer consumes frame/session/revision identity and rejects stale image
presentation. Mission-owned Observe/recovery use typed ingress; raw competing
input/Resume are disabled while nonterminal. Pause remains available. Unavailable
or malformed state must remain visibly uncertain instead of presenting a success.

Browser timing export supports bounded capture/decode/DOM-replacement proxies.
It is not physical-paint proof or independently assessed useful gameplay latency.
Dropped samples and unavailable clock/decision anchors limit joins. Use the
existing retained records before adding instrumentation; a browser automation
download stall is not automatically a native or model stall.

## Assurance and evidence

Review the user's question and state meaning, then projection ownership and image
ordering, then rendering/polling code. These selected consequences are not a
complete operations inventory. Projection/freshness guards implement
[C-RUNTIME](../controls.md#c-runtime--live-authority-and-input-guards-runtime);
[C-PORTABLE](../controls.md#c-portable--portable-regression-lane-automatic)
executes the Python fixtures and the separate Node viewer suite.

| User consequence | Invariant and contract | Mechanism, representative assertion and limit |
| --- | --- | --- |
| A driver ending is displayed as a verified host exit or new mission authority | Status projects existing receipts, retains unresolved exits and cannot mutate mission state. [Host projection contract](../protocol.md#quiescent-player-replacement). | HostStatus and server projection: [host status](../../tests/test_host_status.py) `test_unresolved_exit_stays_unknown_even_when_driver_ended` asserts unresolved exit; [server](../../tests/test_server.py) `test_status_projects_host_receipts_without_mutating_mission_or_exposing_process_details` asserts unchanged mission, no runtime calls and no private process data. `assurance_observer` uses controlled receipts/runtime, not process-liveness proof. |
| A delayed frame looks current or presentation triggers input | Frame/session/revision ordering gates presentation; passive rendering grants no authority. [Transport/state](../protocol.md#transport-and-state) and [ownership](../protocol.md#controller-run-ownership). | Viewer decode/authority guards: [Node viewer assertions](../../tests/test_viewer.cjs) retain the prior displayed revision when an obsolete decode completes, require the latest decode for authority and assert objective rendering sends no request. Controlled DOM/images are a separate executable lane from pytest; they do not prove real browser layout or physical paint. |
| An apparently responsive spectator is mistaken for watchable, useful play | Actual presentation and useful cadence require observed outcomes under the evaluation cohort. [Latency definitions](../evaluation.md#latency-budgets-for-interactive-play). | [C-USABILITY](../controls.md#c-usability--operator-understanding-review-manual) uses manual observation: [local refusal](../acceptance/2026-10-22-native-local-refusal.md#observer-and-timing) records actual STOPPED/HISTORY/DISCONNECTED presentation. The [useful-play assessment](../acceptance/2026-10-25-useful-play-readiness.md#latency-separate-measured-lanes) retains browser decode proxies but no qualifying routine cohort or physical-paint measurement. Neither tags nor Node passes qualify cadence. |

Actual graphical observation checks the relevant working flow, separately from
source fixtures and native build evidence. [#143](https://github.com/CVX-Hull/enactive/issues/143)
owns observer follow-through; [#164](https://github.com/CVX-Hull/enactive/issues/164)
owns whole-player responsiveness.

Full portable CI, native build and real gameplay remain separate. Delivery
automation and branch protection are described in [project management](../project-management.md),
not inferred from a local workflow file. Current pins belong in manifests/lockfiles;
historical setup exceptions are not permission for global changes.
