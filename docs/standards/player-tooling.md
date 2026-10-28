---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# Structured player tooling and host context

For gameplay requests, use the structured player tools over the current typed
ingress. The adapter derives opaque source/session/revision/boundary fields from
one explicitly chosen returned snapshot/source using the pure canonical producer.
Choose intent, finite limits, scope and support IDs explicitly. MCP request IDs
and transport collection waits belong to software, using the existing staged
request and original-result path. A new invocation is not a retry; retain and
collect the original identity through uncertainty, including producer errors.
Do not substitute JSON-RPC correlation for durable operation identity or infer a
new source/budget from this automation. Specialized memory,
handoff and recovery use their same current receiver schemas. Request retention,
serialization, bounded result collection and actual-image presentation belong to
software; routine player-authored files/private scripts are not the operating path.
Repeated opaque-ID copying and actor activation bookkeeping are evidence for thin
software binding through the existing SDK/cache/host lifecycle. Preserve explicit
evidence selection and verify the actual old host has exited before activating a
fresh deciding successor. Software cannot infer tactics, memory adoption, successful
outcomes, new resources or permission from the automation. Focused negative tests
and actual handoff evidence enforce this boundary; no new per-action review applies.
Consume the standard MCP result envelope: retain and surface text, images and
`isError` before inspecting optional `structuredContent`. Never discard an error
by assuming a success-only payload. Tool errors alone do not prove nondelivery;
collect the original operation when delivery is uncertain. Reuse the official SDK
and existing ingress tests rather than creating another result protocol.
Never carry individual fields across a focus change or replay an uncertain action.
The protocol's binding checks and portable/native evidence enforce consistency;
review still checks that the chosen source supports the player's interpretation.
Choose meaningful bounded targets, interactions and activities when visible
evidence supports them. Per-primitive checks belong in software; one model request
per arrow is not evidence that higher-level skill composition improved play.

Use the maintained host/model defaults for context capacity and compaction unless
an explicit measured need justifies an override. Freeze any override with the run;
inspect actual host events before attributing stalls to gameplay or model choice.
Host context summaries are fallible working context, not campaign memory or a
substitute for source-linked retrieval. Requalify the whole configuration after
changes; a larger window or smaller response is not a latency pass.

Standard and principle/control mapping: [S-AGENT Accountable agent-assisted work](../engineering.md#s-agent-accountable-agent-assisted-work).

[Standards index](../engineering.md).
