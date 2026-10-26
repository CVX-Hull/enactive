---
owner: lead
review_trigger: Deciding host, provider requests, tool presentation or process custody changes
status: historical
date: 2026-10-25
scope: Pi offline host conformance; existing mission/native contracts and campaign gates unchanged
---

# A controllable gameplay host

[#235](https://github.com/CVX-Hull/enactive/issues/235) owns this iteration under
[#164](https://github.com/CVX-Hull/enactive/issues/164). The
[player interface](../components/player-interface.md) remains the responsibility
boundary: a player chooses intent through the existing MCP process and mission
ingress. The runtime still owns input, Pause, bounds, original collection and
memory. The [architecture](../architecture.md) is unchanged at those boundaries.
The user requested completion of this iteration and noted a DeepInfra credential
in Keychain. This offline core needs no credential retrieval or inference; the
separate [comparison #236](https://github.com/CVX-Hull/enactive/issues/236) owns
provider/model, spending and graphical decisions. #222 remains independent.

## Reuse decision and scope

Registry inspection on 25 October resolves Pi agent-core, AI and MCP to 1.4.0,
requiring Node >=22.19.0. Install/package-lock ownership is project-local;
lifecycle scripts are disabled. These packages use MIT licenses. Inspect actual
published exports before implementation; mutable upstream documentation is
research, not a dependency pin. npm metadata initially failed under restricted
network access; the project-cache registry read and isolated install succeeded.
No global cache/install was created by the refused metadata commands.

Use Pi's `Agent`, its provider request construction and maintained `McpClient` /
`StdioTransport` / `toLlmContent` directly. The coding-agent application would add
file/shell tools, resource discovery, sessions and a 20 KB direct-MCP text
projection that this player does not need. Agent-core supplies the same supported
loop and explicit hooks with no such defaults. A thin Enactive adapter is needed
for exact role filtering, full text/image/error presentation, original-operation
uncertainty and bounded host-event receipts. It does not implement MCP framing,
model streaming, a planner, mission execution or a second persistent session store.
Do not fork Pi or implement DSH unless an observed gap changes this decision.

Host maintenance belongs to the lead. Reassess on upstream upgrade, material
provider/MCP incompatibility, repeated upkeep cost or a simpler maintained bridge
that meets the exact presentation and lifecycle contract. Keep the existing
Codex host as baseline; both hosts use one current mission and MCP contract.
This is an offline Pi capability, not an accepted live campaign configuration.

## Implemented host seams

`tools/campaign_player.py` supports an explicit `codex` / `pi` host choice. Preserve
the existing loop, exclusive outputs, status/custody guards, exact handoff
collection, original-host terminal check, one fresh successor and cleanup limits.
Only argv/frozen-context construction differs. Pi rejects original-thread resume:
the prototype has no persisted host sessions. Existing driver receipts and
`harness.host_status` remain unchanged; stdout JSONL can retain Pi host events.

`tools/player_host/` owns a separate private Node package with exact 1.4.0
dependencies and an integrity-bearing npm lock. Its subprocess CLI reads a frozen
route config, current MCP command config, explicit frozen player context and stdin
mission prompt; writes the final response to the driver's existing output path;
and emits timestamped JSONL events. No credential values, request headers or raw
provider errors go into argv, config, stdout or final receipts. Provider keys are
resolved only from one explicitly named environment variable when a live call is
separately admitted. No Keychain discovery or personal settings loader is added.

The initial frozen route schema was `pi-player-host/1`; current version2 adds the
required explicit image-history allowance after the measured30-image provider
limit in the [program-breadth assessment](../acceptance/2026-10-25-program-breadth.md).
Version1 is rejected; closed run artifacts remain historical. The current
[route contract](../../tools/player_host/README.md) owns the coordinated migration.
The route retains exact Pi `model` metadata for an
`openai-completions` route, a credential-environment name, finite request timeout
and maximum provider requests. Model ID and effort must match the driver's frozen
selection. Unsupported config versions/API shapes refuse; no alias/downgrade
reader. Route metadata is not proof of actual provider capabilities or price.
Require declared text and image input for this graphical player: a text-only
Pi model would otherwise suppress returned images during serialization.
The whole-host timeout also covers startup, prompt and cleanup. Ordinary current
MCP config provides command/args/cwd, tool allowlist and finite startup/tool waits.
The Pi host does not inherit unrelated process secrets into its MCP child.

Frozen `pi-player-context.txt` supplies guide/context content directly, because
the player has no shell/read tools. Advertise only the exact allowlisted current
server schemas and server instructions; fail before inference if required tools
are missing. Never fill a tool-argument shape from a guessed/old catalog. Preserve
full returned text, images and `isError` once using the maintained converter;
do not duplicate structuredContent beside its already-present text. Provider
serialization may position images as that API requires, with the corresponding
tool call retained. No local image resize/offload or text truncation is selected.
Pi's OpenAI-compatible serializer does not transmit `isError` metadata, so add
one explicit error-status text marker when MCP reports an error, keeping original
content unchanged. Also compare Pi's validated arguments with the original call
using Node's deep strict equality; refuse before MCP if SDK coercion/optional-null
normalization changed them. Neither SDK convenience may silently change meaning.

Use sequential tool dispatch. A known MCP error is presented for the player's
next deliberate decision, including original-collection arguments when returned.
A transport failure without a result stops further dispatch and inference; it
does not establish nondelivery or permit reconnect/replay. Cancellation stops
new work and closes the owned MCP child through the maintained transport. Abort
and process exit are not native cleanup or lease restoration. Do not activate a
successor until the old host really exited and existing handoff guards pass.
Latch and abort on client/transport errors as well as rejected calls: Pi normally
continues after a thrown tool error, and a per-result termination hint does not
stop a mixed batch. Retain the first failure, block every later dispatch and end
nonzero; do not wait for another model decision to stop ambiguous input.
Inspect terminal assistant stop reason and the host failure latch before reporting
success: Pi's prompt promise can resolve after an error or abort. Resolution alone
does not establish successful host completion.

Core has no automatic compaction or host-session restoration. Retain that default
explicitly: context pressure/provider errors stop the bounded pilot; no silent
summary/pruning, fallback model or host recovery is introduced. This limits long
campaign suitability and is a decision for #236 rather than a hidden capability.

## Evidence and acceptance

Use actual Pi provider request construction against an injected fetch/loopback
fixture returning declared synthetic SSE. The fixture is not an inference model
or game and cannot qualify perception/competence. Use real MCP clients and current
production server discovery; controlled MCP responses supply boundary cases.

Required cases cover exact selected schemas and no ambient tools; >28 KB text
without truncation; PNG parts; `isError` and original collection through the next
constructed request; sequential batches and no replay after transport loss;
request/host bounds; cancellation and owned-process closure; and the unchanged
driver original/successor sequencing. Test consequences rather than SDK internals.
Offline measurements record instrumented overhead with sample definition and
limitations, not a hardware-independent speed threshold or gameplay claim.

Events use host wall/monotonic timestamps and request/tool correlation. Record
request construction/start, first received response evidence, completed response,
tool start/result, cancellation/host settlement and actual usage when available.
Report request text/image sizes, actual model/backend identifiers and missing
endpoints. Existing operation/source references remain in full tool results;
do not invent server inference, physical paint or model attention timestamps.
No tracing service, duplicate mission ledger or per-key model annotation.

Independent boundary review preceded implementation. Integration uses fast checks,
focused Node/driver/MCP tests and source review. CI installs the separate locked
package and executes its Node tests through the existing Python/full check lane.
Changes to tooling/dependencies require full PR and main checks under the current
[profile policy](../project-management.md#protected-ci-profiles). No native rebuild
or gameplay is needed to qualify this deliberately offline support. Current
component/setup/runbook/evaluation guidance must state these limits.

Adoption requires a working conformance host plus reviewed tests, evidence,
documentation, protected publication and owned cleanup. An early reject/defer
requires retained incompatibility/probe evidence, reviewed alternatives and a
named revisit trigger; it cannot claim delivered host support. The complete
iteration has a six-active-hour appetite with a 60–90 minute feasibility checkpoint;
CI/queue elapsed time and unavailable historical active effort stay separate.

## Boundary review disposition

Independent pre-implementation review confirmed two SDK-specific blockers: error
metadata was absent from the constructed OpenAI-compatible payload, and normal
Pi tool-error continuation could dispatch after transport uncertainty. The adopted
design adds the visible error marker and permanent transport stop/abort latch. A
focused recheck passed those dispositions. The same review identified image-input
metadata, terminal stop-reason inspection and actual child closure as acceptance
points; they remain explicit conformance cases, not assumed SDK guarantees.
Source/integration review subsequently passed after the repairs below. Exact
protected checks and publication receipts belong to the PR; this brief does not
claim their result.

Integration review found three concrete gaps: the direct provider stream omitted
the frozen output-token cap, missing provider usage appeared as SDK-initialized
zero, and rejected HTTP status was outside the SDK's success-only response hook.
The host now sends the cap explicitly, records unavailable usage/cost as null and
observes status at the fetch boundary. Actual-payload/response tests cover these
cases; a focused independent recheck passed. The direct route also requires its
declared OpenAI reasoning format rather than silently inheriting endpoint detection.
