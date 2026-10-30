---
owner: lead
review_trigger: Investigation evidence boundary, shared reader or delivery scope changes
status: historical
date: 2026-10-30
scope: Implemented investigation design and owner-directed live attachment amendment
---

# Investigate current and recorded gameplay intervals

## Outcome and impact

The [consolidated evidence](../acceptance/2026-10-30-spectator-investigation.md)
retains actual outcomes, failures and assessed limits. Current interfaces live in
the component/contracts below; this brief preserves the design decisions.

[#295](https://github.com/CVX-Hull/enactive/issues/295) selects a bounded reader
that explains a gameplay slowdown and exposes the original evidence without raw
log searches. The owner-directed amendment makes Analysis attach an as-of current-session snapshot
automatically; older closed-case import is optional. The shared reader shows measured spans,
public statements and reviewed assessments separately, and retains absent data.
The lead owns integration and the shared native lane. The existing issue owns
scope, appetite, experiments and remaining acceptance, not this dated design brief.

The highest changed responsibility is passive observer investigation. The
[observer component](../components/observer-operations.md) and
[measurement contract](../evaluation.md) remain its parents. Computer custody,
game semantics, native wire, actor capabilities and player memory are unchanged.
No game input or actor capability is added. Explicit snapshot refresh performs
read-only evidence work; the existing independent permanent Pause is unchanged.

## Selected design and reuse

| Part | Change and limit |
| --- | --- |
| `tools/evaluate.py` / `tools/investigation.py` | Thin one-shot selected-case export, reusing host/control/observer analysis, current read-only stores and original program result projections. No collector or archive database. |
| `web/investigation-worker.js` | Validate/index a bounded imported artifact and verify image bytes in a dedicated worker, with termination on supersession/timeout. No requests or authority. |
| `web/investigation.js` / `investigation.css` | One shared native-DOM/SVG reader for live import and a self-contained recorded-only HTML export. Paged exact records, selected interval lanes and original evidence inspector. |
| `web/app.js`, `index.html`, `style.css` | Add Analysis; compact live control/header, filters and explicit actor-scoped request grouping in Timeline. Preserve frozen selection/focus/scroll and current/previous retention. |
| `harness/server.py` / `tools/investigation_live.py` | Explicit static assets and an injected finite GET/POST current-session snapshot; no arbitrary path/archive/capture/actor API. Existing Pause bypass remains untouched. |

Existing analyzers already supply measurement definitions and exact original IDs;
copying raw traces would disclose arguments and obscure coverage. Perfetto/Grafana,
Sentry/Rerun and Langfuse inform navigation, not a deployment dependency. A small
DOM/SVG reader addresses the selected local, sparse-image workflow without a new
observability platform or chart framework. Browser Worker, Web Crypto, Blob,
image decode and filesystem/SQLite APIs own their respective platform guarantees.
Retire/reassess the thin adapter if actual query/archive needs exceed four selected
cases; do not grow a private tracing platform. Source history stays in Git.

## Frozen implementation interface

The implemented closed artifact and selection shapes now live in the
[recorded investigation contract](../contracts/observer-investigation.md).
The producer, worker and shared reader migrate together; this brief retains the
design rationale and acceptance plan rather than a second schema copy.

## Shared reader integration

The renderer exposes `EnactiveInvestigation.mount(root, options)` returning
`loadFile(file)`, `loadText(text)`, `loadSnapshot(text, expectedSession)`,
`cancelPending()` and `destroy()`. Replacement validation is staged with one active
and at most one pending worker; failure retains the validated selection and image. Options use either `workerURL` for the live
same-origin static worker or `workerSource` for an owned Blob worker offline,
plus optional `initialText` (unparsed JSON passed to the worker). A worker reads
the selected File or text, parses/validates/hashes off the UI path and returns a
bounded validated model or an error. Superseded work is terminated; a finite
30-second import watchdog reports unavailable without touching live custody.
No `eval`, HTML from data, network, storage mutation or actor credential exists.

The live page loads scripts/styles from explicit static routes and passes its
Analysis root to the shared renderer. It never copies live actor/status objects
into imported state. Selecting Analysis or importing malformed data cannot await,
disable or change current Pause. Existing live transport continues independently.

The recorded HTML is generated from the same renderer/CSS/worker assets and safely
embedded JSON, with inert data escaping including script terminators. Its restrictive
CSP permits only its generated scripts/styles and owned worker/image Blobs, no
network. It has no live current-target bar or pretend Pause. Output is generated
atomically after validation; existing outputs are not overwritten accidentally.
There is no separate offline renderer or automatic schema compatibility reader.

## Owner-directed amendment and review decisions

The owner requested fastest-first provider choice without treating historical
failure as a future ban, and automatic attachment instead of mandatory file choice.
The first DeepInfra development admission was genuinely Paused from historical
Analysis and closed; it remains interrupted evidence. A separately authorized six-call
fresh probe selected BaseTen for the next gameplay admission; Fireworks recovered
after its429 and remains eligible. The issue owns actual finite allowances/accounting.

The current [artifact contract](../contracts/observer-investigation.md#attached-current-session-snapshot)
owns the exact live envelope/resource interface. A tools-owned injected view runs
one finite credential-free child, reads a coherent read-only DB backup and identical
newline-complete trace prefixes, and removes its parent's temporary copy. It reuses
the same projection and validator without inventing a closed receipt or driver.
HTTP delegates; no collector, semantic/control port or tools dependency in the server.

Boundary review resolved three concrete risks: retain latest rows per kind instead
of a host-first prefix; stage candidate validation before replacing usable evidence;
and treat every loaded/pending bundle as inspection intent rather than guessing
from selectedId. Automatic first attachment is followed by explicit Refresh; polling
and admission turnover cannot replace loaded evidence. File choice supersedes live
fetch intent. Clock cutoffs, omitted lanes/images and unknown live totals stay visible.
Live evidence later showed spare capacity going unused and a censored tail absent
from the default axis. The bounded refinement retains every row when the2000-row
case fits, then redistributes spare lane capacity under pressure; the derived live
axis includes an explicitly unmeasured tail without changing original endpoints.
Available version IDs also link preparation/read records without exporting code,
and failed optional import is reflected in both shell and reader feedback.

One new finite main admission after the owner-directed stop is a new allocation,
not revival of its retired allowance; the separate normal-ending lane remains.

## Verification, iteration and ownership

Before commitment, independent review checks new export/import trust/resource
boundaries and concrete fit. Backend and reader workers own separate worktrees and
disjoint new modules/tests. The lead integrates CLI/assets/contracts, current
Watch/Timeline and actual cases, serializes all writes to the integration checkout
and owns native runtime. No worker launches gameplay.

First fit checkpoint: actual B interval, original water image and organic005 program
children must join and render with truthful coverage. Reduce optional plots before
expanding scope. Focused tests cover strict versions/fields, hostile text, secret/raw
data exclusion, original IDs/images, missing/censored/invalid-clock cases, limits,
worker cancellation/paging and independent Pause during import/error. Use the
existing Python/Node runners, not a new test framework. Actual browser keyboard,
frame/interval investigation and gameplay remain separate from fixtures.

The issue freezes substantive organic play, genuine Pause from Analysis and a
separate short normal ending with existing finite envelopes and standing approvals.
Admission still records exact source/configuration/current metadata/accounting.
No source writes while native/player is live. Include all failed chains and unknown
acknowledgments. The deciding Pi player owns tactics and all game semantics.

Independent source/outcome review, full protected PR/main for this broad source
change, current component/contracts/evaluation/operations and a consolidated
evidence family precede Done. Reuse unchanged native qualification. Closeout uses
the evidence to choose the next gameplay experiment, explicit no-change or missing
data result. Optional usage plots, broader Knowledge and comparisons do not delay
the promised bounded core. Adopted design transfers to current docs; retain this
brief as dated rationale at completion.
