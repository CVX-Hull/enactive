---
owner: harness maintainer
review_trigger: Responsibility, supported behavior, interfaces or qualification change
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
| [Tool schema](../../harness/player_tools.py) | Basic observe/input/result/stop and optional source/memory/program/context/handoff tools; no semantic gameplay API. |
| [Player client](../../harness/player_client.py) | Per-actor explicit `player-adapter/1`, ID assigned before submission, exact source retrieval and uncertainty; no native/process/provider ownership. |
| [MCP adapter](../../harness/player_mcp.py) | Official SDK transport and actual image blocks; cancellation requests independent permanent stop. |
| [Player host](../contracts/player-host.md) | Any conforming adapter: explicit model/context/MCP table, finite provider requests and host deadline, sequential tools and origin-bound handoff settlement. |
| [Campaign driver](../../tools/campaign_player.py) | Exact host/MCP process groups, aggregate original attempt/time limits, canonical handoff/context and verified quiescence before successor. |

The host loads no coding-agent shell/file tools, personal configuration, resource
discovery or resumed session. No coding-agent fallback is supported. Selected
OpenRouter / explicitly pinned provider / DeepSeek Flash1017 medium is frozen per finite run;
route selection and host conformance are separate from model/gameplay qualification.

## Context and failure boundaries

Initial context consists of the guide, frozen objective and actual selected tool
schema. The player uses optional typed memory/context and exact source reads as
needed. A program receives actual selected image pixels and optional player
interpretation, never engine facts. The provider image-history window retains all
text/IDs, marks omitted older pixels and protects the current result group; an
oversized protected group stops. Source availability does not prove the actor read it.

Current provider route is closed `player-host/1`, with explicit image allowance,
cost/capacity/effort metadata and default service tier for the current campaign.
OpenRouter uses exact selected full-tag routing, no fallback and required parameter
support. Credentials are injected only into the provider host; MCP/native children
receive no key. Missing usage stays unknown; configured estimates/reservations are
not invoices. The host reference owns maintained provider-only bounded429 behavior;
no tool retry/reconnect/replay follows uncertain transport.

Telemetry version2 keeps bounded visible assistant narration and mechanical
request/result references. It excludes private reasoning, credentials and raw
provider request/image histories. Original source images remain with their owner.
Host attempt/time counters are separate from custodian mechanical resources.

`player_handoff` seals this actor with canonical immutable context. Only its direct
originating issuance or exact original collection settles host handoff. After the
host closes its owned MCP child, the driver checks actual old process-group
quiescence and context digest before minting a successor under original limits.
No menu/save/identity check is required. User Pause, uncertainty or failed closure
cannot become resumable handoff. At most two hosts are permitted by `campaign-run/3`.

## Assurance and evidence

The [host contract suite](../../tests/test_player_host_contract.py) drives each listed
adapter only through `player-host/1`. [Adapter](../../tests/test_player_host_adapter.py),
[driver](../../tests/test_campaign_player.py) and [custodian](../../tests/test_campaign_run.py)
fixtures exercise real maintained libraries with synthetic provider/owned children.
They add configuration, image, settlement, accounting and cleanup evidence without
paid inference or game launch. [Actual prior host reports](../work.md#decisive-evidence)
retain failures on earlier source. The [production report](../acceptance/2026-10-29-computer-control.md)
adds bounded actual use, succession and normal lifecycle evidence. Useful cadence,
general model quality and independent campaign completion remain open.
