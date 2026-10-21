---
owner: lead
review_trigger: Player tool, mission contract, MCP SDK, Codex permissions or evidence presentation changes
status: active
---

# Structured player tools and review-free operation

## Problem and chosen boundary

Independent004 exposed two separate costs: the player manually prepared request
files, submitted them, polled results and opened images; a fresh successor also
reached automatic approval review on a passive call. The latter denial was resolved
by supplying the existing direct human authorization for the same action. Absence
of routine review is still unproved. #164 owns client automation and #166 owns the
actual-host permission requirement. Neither source tests nor a fresh diagnostic
process can establish that the active player has no review round trips.

Use the official MIT-licensed MCP Python SDK 2.3.0 as a small project-local stdio
adapter. The runtime dependency lock includes its transitive dependencies; no SDK,
server framework or protocol implementation is vendored. Its low-level Server
accepts the existing closed JSON Schemas and text, structured data and PNG result
blocks. This avoids a new schema framework, web server, action executor, agent
framework, history database or custom tool protocol. The harness maintainer owns
this adapter; review the dependency on SDK/host changes and retire it if supported
host tooling covers the gap with less maintenance.

The adapter calls the same authenticated loopback mission ingress. One
MissionRuntime, ledger and evidence archive remain authoritative. The existing
pure producer derives ordinary wire bindings from a chosen returned snapshot and
source. Specialized memory and handoff fields retain their current schemas;
software supplies common headers and exact selected issuance/readmission bindings.
The model continues to choose goals, interpretations, source-read declarations,
memory content, scopes and finite limits. No tactical decision, new allowance,
automatic Resume, source substitution or lesson promotion is added.

## Delivery and evidence

Retain a stable caller-selected request ID and exact canonical request in the
existing mission-request directory before its first POST. A repeated identical
request file permits result collection only; a conflicting body refuses. A lost
response is uncertain and queries the same operation ID. Missing results never
cause another action POST. The existing ledger owns all admitted operation
history; local descriptive handles are bounded, disposable caches and restore no
authority after restart.

Return admission separately from settlement, including original unknown and later
reconciled dispositions. Return concise status, source IDs and the actual selected
PNG together, with complete memory packets kept intact. Read an exact historical
source by indexed ID through a token-authenticated reader of the same retained
archive. Verify its original PNG hash, including when bridge frames were evicted;
missing/changed bytes fail. Read-only presentation neither renews source receipt
time nor mutates a lease. Source interpretation and runtime freshness remain the
existing receiver's responsibility. Raw receipts stay in the ledger/archive.

Use bounded waits, retain the stable ID before a cancellable host tool call, and
expose result collection explicitly. Host cancellation does not prove a committed
native action was cancelled; user Pause retains its independent control channel.
No source change or second runtime writer is permitted during deciding play.

## Setup, controls and acceptance

The supported project MCP configuration explicitly allows only the named player
tools. It changes no global approval default, arbitrary-shell rule or machine-wide
security setting. The original resolved denial is not routed around; this is a
new explicitly configured integration under standing human authorization.
Managed policy remains authoritative. A matching setting or successful approved
call does not establish review-free operation.

C-REVIEW checks transport/semantic boundaries, idempotency, source integrity and
settings scope. C-PORTABLE exercises real runtime/controller/ledger fixtures plus
a real SDK stdio handshake, catalogue and text/structured/image result. C-NATIVE
separately verifies the actual designated player's loaded tool path, two passive
calls, representative action/result/image/memory/lifecycle and no human or automatic
approval/guardrail review. If the host cannot provide or expose this, retain the
specific limitation and do not call permission readiness accepted. Native CDDA and
full independent mission acceptance remain separate.

Lead owns schemas, indexed read API, tool adapter, lock, documentation, project
settings and final verification. One worker in an isolated worktree owns only the
thin transport and focused tests; a clean reviewer checks the integrated delta.
No full campaign, source migration pass or SDK fixture substitutes for the real
fresh successor and normal ending required by #144/#145.
