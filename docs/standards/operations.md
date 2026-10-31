---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# S-OPS Observable operation and recovery

Document startup, pause, timeout reconciliation, restart, save/quit, diagnostics
and cleanup in the runbook. Never replay an uncertain gameplay action or edit a
save to demonstrate recovery. Retain evidence of failures; clean only identified
project-owned resources after checking retention obligations. Saves require
explicit user-directed deletion. Test relevant recovery paths when they change.
The survival campaign must not depend on user keystrokes or routine rescue.
Verify automated control/recovery access before admission; required human help is
a retained autonomy failure, not accepted recovery. Native UI operation still uses
ordinary engine input and current visible evidence; it cannot relax remote guards.
Routine admitted gameplay, observation, memory, lifecycle, handoff and supporting
request/result plumbing must incur neither human approval nor automatic approval/
guardrail-review round trips. Configure the supported project-scoped execution
path during setup. Verify the selected host's effective configuration and a
harmless live call through the actual designated player's configured tool entry
point. Reuse unchanged verified setup as the operator procedure permits; recheck
changed host/tool/permission boundaries. Coding-agent project trust, rule and
permission loading applies only to the lead's coding agent through the
[supported host setup](../operations/coding-agents.md); the player host loads no
coding-agent configuration. A rule match alone does not establish usable access.
Resolve recurring reviews in setup; do not normalize
them as the gameplay loop. Preserve native freshness, single-executor and Pause
checks. [Operator permissions](../operator-permissions.md#preflight-for-every-campaign)
owns the procedure and its limits.

[Standards index](../engineering.md).
