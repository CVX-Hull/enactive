---
owner: lead
status: historical
date: '2026-10-24'
scope: Design and development record preserved on this date; current architecture/protocol
  and GitHub own behavior and remaining work
---

# Make gameplay permission readiness a setup requirement

The user observed approval review on every player action despite the published
narrow recorder rule. Ordinary gameplay must avoid that recurring cost, including
future campaigns. Rule matching had been verified; active loading had not.

## Diagnosis and correction

The desktop-bundled Codex CLI explicitly reported that this checkout's local
configuration, hooks and execution policies were disabled until the exact project
was trusted. The broader ancestor trust entry did not enable this project layer.
The independently installed CLI used for earlier matching checks was a different
version; matching was never evidence of desktop activation.

With the user's authorization, the lead added only this checkout's exact project
table with `trust_level = "trusted"` in Codex's documented user configuration.
TOML parsing and a semantic comparison verified every unrelated setting unchanged.
No global permission default, user command rule, network setting, native code,
recorder or gameplay guard changed. The allow rules stay project-local.

A fresh desktop-bundled process then successfully returned `config/read`: this
checkout's project layer was present with no disabled reason. Its effective
workspace-write/on-request/auto-review settings were unchanged; the diagnostic
reported no managed requirements. This process did not inspect or change active
chat overrides. Its documented read-only APIs started no model thread/turn; its
temporary state/log directories stayed project-local and the owned process exited.
The first default-sandbox diagnostic failed and was retained, not called a pass.

Active-chat startup/reload and a harmless call by the actual designated player
must still verify absence of recurring approval before claiming that behavior.
The [lasting preflight](../operator-permissions.md#preflight-for-every-campaign)
is enforced manually by S-OPS/C-NATIVE, with mature Codex parsing/configuration
tools. No new permission parser or generic policy framework is needed.

## Preserved campaign checkpoint

The same Ned Meyers/Belgium remains paused in supported normal play, native59507,
session1792370882551-59507-1. Player99 and lead100/101 have empty live request,
control and lease slots. All tools terminated and input authority was relinquished.
The owned controller stopped normally; the native game remains alive. No Save,
Quit, restart, rewind or new character was used for this permission interruption.

Actual normal turn5217025 / Spring61 09:10:25 is4225seconds after originalT0.
Crowbar and sling were crafted, the sling worn and crowbar carried. One carving
job finished; Fabrication2 and Carving1% were observed. This is useful partial
progress, not day1 acceptance. At checkpoint whole333/day308/lifecycle97 inputs,
lifecycle3816.987seconds,72current-v3+one archived-v2 gameplay unknown and two
control unknowns remain. Original clocks and every cost/cap are retained.

The user's permission/documentation request explicitly interrupts the source
freeze; no gameplay is authorized during this work. Prior admission/source are
archived privately. Resumption requires reviewed clean publication, unchanged
native/recorder, actual fresh paused state, live permission preflight, remaining
whole-day feasibility and explicit reassignment. The seven-day goal remains open.

## Maintenance and evidence limits

Lead owns the preflight and retirement of obsolete recorder allowances. Prefer
stable entry points; review a changed wrapper during setup rather than accepting
per-action review as normal operation. Recheck on configuration/entry-point/player
changes, without repeatedly restarting an unchanged verified setup. A product or
managed-policy limit is reported, not bypassed through a different actor/transport.

Private005 permission evidence retains the actual diagnostic warning, enabled-layer
response, before/after configuration hashes and unrelated-setting comparison,
checkpoint receipts and normal controller exit. Machine configuration and private
transcripts are not public artifacts. Portable checks can validate documentation
and contracts; they cannot prove active desktop rule loading or gameplay success.

Official sources checked2026-10-18: [rules](https://learn.chatgpt.com/docs/agent-configuration/rules),
[auto-review](https://learn.chatgpt.com/docs/sandboxing/auto-review),
[project configuration](https://learn.chatgpt.com/docs/config-file/config-advanced#project-config-files-codexconfigtoml),
[configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference),
[app-server configuration API](https://developers.openai.com/codex/app-server).
