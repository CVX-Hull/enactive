---
owner: maintainer
review_trigger: Changes to this operating task, supported setup or recovery behavior
status: active
---

# Bounded player host activation

For maintained fresh admission/controller lifetime, start with the
[finite campaign custodian](campaign-run.md). After external mission admission, use the
[campaign player driver](../../tools/campaign_player.py) to run the frozen original
and at most one clean successor. The generic Pi core host is the sole current
campaign execution path. Install the [locked host package](../setup.md#install-the-generic-gameplay-host)
first. The current run directory must be exactly `.runtime/campaigns/<mission_id>`;
arbitrary descendants or aliases are unsupported. Prepare these run-local files:

- `frozen/player-host-configuration.json`: the explicit selected MCP server command,
  args, cwd, `enabled_tools` and finite startup/tool timeouts. The host discovers
  current schemas and server instructions from this process; it loads no ambient
  tool registry or personal coding-agent configuration.
- `frozen/original-player-prompt.txt` and `frozen/successor-player-brief.txt`: the
  distinct prospective assignments under the same original finite allowance.
- `frozen/pi-player-context.txt`: the actual frozen guide/context content supplied
  to both fresh hosts. The player has no shell or file-reading tools; paths to
  undeclared files are not supplied context.
- `frozen/player-pi-configuration.json`: closed `pi-player-host/3` route with
  `model`, `api_key_env`, `max_requests`, `request_timeout_seconds`, required
  `service_tier` (`default` or `priority`) and required
  positive integer `max_context_images`. Freeze the selected provider's verified
  image-part bound (30 for the tested DeepInfra route); this is not a universal
  limit. Historical version1/2 files are not accepted or rewritten. Freeze verified
  tier support/prices, including any surcharge in configured costs and the
  conservative request reservation; requested priority is distinct from the
  optional applied-tier stream echo. See the route contract below. The current
  supported provider contract is explicit Pi `openai-completions` metadata with
  text/image inputs, context/output capacities, cost and reasoning settings.
  Its ID must match `--model`; effort must be explicitly supported rather than
  silently clamped. Declared capabilities and prices require provider verification;
  metadata does not prove actual image understanding, quality or billing.
  The [host image-history policy](../../tools/player_host/README.md) preserves current
  result-group images and all text/IDs, explicitly marks omitted older pixels and
  retains originals privately. An oversized protected group stops before inference;
  neither omissions nor rereads restore input authority. Freeze this context change
  before requalifying actual continuation and whole-player responsiveness.

Choose the actual frozen model/effort/deadline and existing Node binary:

```sh
.venv/bin/python -m tools.campaign_player \
  --root "$PWD" --run-dir "$PWD/.runtime/campaigns/MISSION_ID" \
  --mission-id MISSION_ID --model MODEL --effort EFFORT \
  --timeout-seconds SECONDS --max-hosts HOST_COUNT --node /absolute/path/to/node
```

Both hosts always start fresh. The removed `--host`, `--codex` and
`--original-thread` options are rejected, including the old `--host pi` spelling;
prepare new current-source invocations rather than replaying historical frozen
argv. The driver requires all frozen inputs, exclusively reserves evidence and
uses the same Pi runner for original and successor. No coding-agent execution or
resumed conversation is a gameplay fallback.

`--max-hosts` is exactly1 or2, default2 (original plus at most one successor).
Select1 when only one actor is admitted: after that host ends, a nonterminal
mission is reported incomplete before handoff collection or successor assignment.
The per-host route request cap times this host-count bound must fit the total
approved provider allowance, including prior calls and failures; a prompt alone
is not a global request cap.

Supply only the selected credential-environment name in configuration; inject
its value securely into the dedicated process for an authorized live request.
No Keychain lookup, global credential/profile discovery or transfer of subscription
access is automatic. The MCP child receives only the minimal environment, without
the provider secret. Never put keys in model headers, URLs, files or argv.

The driver waits for actual host exit0, validates cached quiescence and current
controller/native Pause binding, and collects the exact completed handoff. It
records a distinct successor ID and preserves the issued role. The successor
retrieves memory/evidence, Claims and readmits itself. Historical diagnostics do
not replace current unresolved-effect and live-slot checks. Only the original
admitted bootstrap can use the controller's expected initial freeze. User Pause,
failed/uncertain hosts and unexpected state stop activation without fallback or
budget renewal. Timeout cleanup signals only the exact owned host and cannot
claim native cleanup. Outputs remain exclusive run-local files; a terminal report
describes observed phase, never acceptance.

The spectator's Deciding host and Assigned successor fields read these same
receipts. A successor may launch or fail before mission adoption; inspect that
separate row instead of inferring it from the mission actor. Launch evidence is
not current liveness, and missing receipts remain unknown. These fields never
activate an actor, change ownership or authorize another run.

There is no automatic compaction, pruning, session restore, model fallback or
transport reconnect/replay. Context/provider errors, request limits and transport
uncertainty stop the host nonzero. Known tool errors retain complete original
collection guidance for a deliberate next decision. A transport failure with no
result proves neither delivery nor nondelivery; never retry the action. Runtime
and driver guards still govern later continuation. Owned MCP closure cannot
establish native cleanup or authorize another actor. See
[host-event interpretation](../evaluation.md#pi-host-events).

Host migration is mandatory under [#240](https://github.com/CVX-Hull/enactive/issues/240);
model qualification is separate. The [first configuration pilot](../acceptance/2026-10-25-pi-configuration-pilot.md)
passed basic API compatibility and failed useful play/normal ending. Its failure
does not restore a Codex gameplay path. Any fresh provider/native check needs its
own prospective purpose, source, cumulative spending/execution limits and ending
reserve; source fixtures cannot qualify graphical outcomes or #145 readiness.
The [fresh generic-host qualification](../acceptance/2026-10-25-generic-host-qualification.md)
completed identity adoption but failed useful play and normal ending. All44 calls
in that allocation are consumed; another paid/live check needs a fresh concrete
allocation. The generic-only host remains mandatory.

For a separately admitted adviser, freeze its actual active stdin prompt,
current source, mission, actor, role-specific generic-host configuration,
allowlisted MCP tools and finite request/time/spending limits. Use the same Pi
core runner; the mandatory gameplay host also covers advisory model roles. No
adviser is automatically created by the campaign driver or covered by a
player-only paid allowance. State activation explicitly
after external admission; do not send a standby-only brief and infer activation
from process launch. Check that the launched argv and stdin match the frozen
inputs. A passive capability check needs the current schema's required arguments;
an argument error proves availability at most, not claimed computation. An exited
standby actor with zero calls supplies no advice or overlap evidence, as in017.
Use the existing host receipts/claimed jobs; no second approval gate is added.

The [stopped functional continuation](../acceptance/2026-10-18-seven-day-continuation-stop.md)
and [ordinary menu repair](../acceptance/2026-10-18-ordinary-menus.md) retain historical
coverage and failures. Their old CLI/recorders and expired admissions cannot authorize
current play. #156 freezes the actual candidate; #157 owns deciding mission evidence.

[Operations index](../runbook.md).
