---
owner: lead
review_trigger: Player-facing tools, context boundaries or assurance limits change
status: active
---

# Player interface: judgment in, bounded evidence out

One designated player runs in the player host adapter frozen by its package, with
current MCP tools and explicit frozen context/provider route. The player interprets
actual pixels and owns plans, tactics, knowledge and success claims. The
[player guide](../player-guide.md) is the compact working document. The
[computer-control contract](../contracts/computer-control.md) owns player ports; the
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
fallback. [Selected host configuration](../operations/player-host.md).

## Context and failure boundaries

Initial context consists of the guide, frozen objective and actual selected tool
schema. The objective is ongoing; experiment countdowns and final-actor policy
are absent from supplied prompt and tool views. The typed MCP projection gives the model a
short result and keeps the original evidence and uncertainty in the operation record while excluding global resource accounting;
canonical operator records remain unchanged. The player uses curated knowledge,
hints and exact source reads as needed; none supplies engine facts. The provider image-history window retains all
text/IDs, marks omitted older pixels and protects the current result group; an
oversized protected group stops. Source availability does not prove the actor read it.

The [route envelope](../contracts/player-host.md#route-envelope) sets the host's
limits and capabilities. Only the provider host receives credentials. The host
counts [provider-reported cost](../contracts/player-host.md#spend) toward the
run's dollar limit. Provider retry follows the [adapter reference](../../tools/player_host/README.md).
Uncertain tool transport permits neither retry nor replay.

[Host telemetry](../contracts/player-host.md#telemetry) keeps bounded visible
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
sets the host limit. The [player journal](../contracts/computer-control.md#responsibilities-and-current-data)
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
