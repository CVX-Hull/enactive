---
owner: lead
review_trigger: Player-facing tools, context boundaries, assurance limits, the player journal, hints, handoff context or delivery change
status: active
---

# Player interface: judgment in, bounded evidence out

One designated player runs in the player host adapter frozen by its package, with
current MCP tools and explicit frozen context/provider route. The player interprets
actual pixels and owns plans, tactics, knowledge and success claims. The
[player guide](../player-guide.md) is the compact working document. The
[player ports contract](../contracts/player-ports.md) owns player ports; the
[player host contract](../contracts/player-host.md) owns the substitutable host boundary;
the [current adapter reference](../../tools/player_host/README.md) owns its provider details.

## Internal responsibilities

| Part | Responsibility / limit |
| --- | --- |
| [Tool schema](../../harness/player_tools.py) | Basic observe/input/result/stop and source, knowledge, hint and handoff tools; no semantic gameplay API. |
| [Player client](../../harness/player_client.py) | Uses the [per-actor configuration](../operations/player-host.md), assigns the operation ID before submission, and handles exact source retrieval and uncertain delivery. |
| [MCP adapter](../../harness/player_mcp.py) | Official SDK transport and actual image blocks; cancellation requests independent permanent stop. |
| [Player host](../contracts/player-host.md) | Runs the model loop with frozen context and a fixed tool table. Dispatches tools sequentially. |
| [Campaign driver](../../tools/campaign_player.py) | Owns the run's limits, the host and MCP process groups, and actor succession. |

The host loads no coding-agent shell/file tools, personal configuration, resource
discovery or resumed session. The route is frozen per finite run and permits no
model fallback and no fallback outside its declared endpoints; the
[selected host configuration](../operations/player-host.md) names it.

## Journal and knowledge

The player journal (`harness/player/journal.py`) retains public calls,
fallible hints and referenced source images. It is not a player-authored knowledge
store. The curator writes knowledge through its gate; the player receives deterministic
briefings, substantive post-cut and mid-segment deltas, on-demand read/query tools,
same-lineage ancestor frame reads (`player-source-read/2`) and a host-local working-state
agenda (`player_agenda`, never projected into curator memory). A hint can inform later
curation but cannot publish a fact or grant input authority. Source references show
availability, not attention. [Player ports](../contracts/player-ports.md#player-knowledge-and-executable-proposals)
owns the exact journal, hint, source-read and handoff contracts.

The [player ports contract](../contracts/player-ports.md#player-journal)
governs reopening the journal across native sessions. Capacity or source
registration failure is reported; healthy basic control remains available. Digest
mismatch refuses source consumption. Unknown or partial physical delivery stops
further input and is never replayed. Handoff carries a labelled summary hint,
not a knowledge graph, and does not renew authority.

Journal and application tests cover the supported formats and composition. They do
not establish learning benefit. Sealed historical evidence retains its original scope.
The application serves knowledge reads from the delivered export. The host builds
deterministic briefings and substantive deltas from that same version under the
[delivery contract](../contracts/player-host.md#delivered-knowledge-and-player-working-state-agenda).
When the package sets live knowledge updates, the driver has the application serve a
newer version during play, and the host delivers non-empty substantive deltas to the
running actor while suppressing empty updates ([a newer version during play](../contracts/player-host.md#a-newer-version-during-play)).
Each knowledge read names the version it answers from.
The [player guide](../player-guide.md#delivered-knowledge-and-working-state) describes how to check
fallible leads and deltas against the current view. The
[curator repository](curator.md#facts-articles-and-grooming) stays outside the player
runtime. After play, the evaluator reads [delivery evidence](../contracts/measurement-tools.md#adjudication-and-the-standing-use-measures).

## Context and failure boundaries

Initial context consists of the guide, frozen objective and actual selected tool
schema. The objective is ongoing; experiment countdowns and final-actor policy
are absent from supplied prompt and tool views. The [typed MCP projection](../contracts/player-ports.md#mcp-projection-and-envelopes) gives the model a
short result and keeps the original evidence and uncertainty in the operation record while excluding global resource accounting;
canonical operator records remain unchanged. The player uses curated knowledge,
hints and exact source reads as needed; none supplies engine facts.

The host keeps a long context within its limits in three steps. On a route that enables
`context_cut`, a request that grows past the high mark or the image peak can first drop
the oldest complete turns that the curator has already covered, in favour of a fresh
briefing and a marker naming the dropped frames
([coverage-gated context cut](../contracts/player-host.md#coverage-gated-context-cut)).
When coverage does not reach far enough, the cut is held back and play continues.
Next, the image-history window evicts the oldest pixels in blocks; it keeps all
remaining text and IDs, marks omitted pixels and protects the current result group, and
an oversized protected group stops. Last, the host warns of approaching capacity and
offers a handoff, and it stops before a request that would not fit. Source availability
does not prove the actor read it.

The [route envelope](../contracts/player-host.md#route-envelope) sets the host's
limits and capabilities. Only the provider host receives credentials. The host
counts [provider-reported cost](../contracts/player-host.md#spend) toward the
run's dollar limit. Provider retry follows the [adapter reference](../../tools/player_host/README.md).
Uncertain tool transport permits neither retry nor replay.

[Host telemetry](../contracts/player-host-telemetry.md#telemetry) keeps bounded visible
assistant narration and mechanical request/result references. Original source
images remain with their owner.
Host attempt and time counters remain operator data, separate from the custodian's
mechanical limits. Context estimates can prompt a handoff and give no guarantee
that the next request fits the provider's token limit.

The driver can request [optional finish-up](../contracts/player-host.md#external-control)
independently of permanent Pause and hard cleanup. The player reports its
disposition through the host's [direct finish tool](../contracts/player-host.md#settlement-and-handoff).

The driver verifies [handoff custody](../contracts/computer-control.md#computer-operations-and-custody)
before starting a successor. The [run package](../operations/campaign-run.md#frozen-data)
sets the host limit. The [player journal](../contracts/player-ports.md#player-journal)
can span fresh native-child sessions.

## Assurance and evidence

The [host contract suite](../../tests/test_player_host_contract.py) drives each listed
adapter through the [current host contract](../contracts/player-host.md). [Adapter](../../tests/test_player_host_adapter.py),
[driver](../../tests/test_campaign_player.py) and [custodian](../../tests/test_campaign_run.py)
fixtures exercise real maintained libraries with synthetic provider/owned children.
They add configuration, image, settlement, accounting and cleanup evidence without
paid inference or game launch. [Actual prior host reports](../acceptance/index.md)
retain failures on earlier source. The [production report](../acceptance/2026-10-29-computer-control.md)
adds bounded actual use, succession and normal lifecycle evidence. Useful cadence,
general model quality and independent campaign completion remain open.
