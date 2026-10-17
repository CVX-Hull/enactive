---
date: '2026-10-17'
owner: maintainer
scope: ADR 001 — Native Tiles integration
status: historical
---

# ADR 001 — Native Tiles integration

Owner: maintainer. Status: accepted; extracted from the implemented MVP design
on 2026-10-17. This records a decision, not a new platform evaluation.

## Context and decision


| Candidate | Benefits for this goal | Costs / evidence limits | Decision |
| --- | --- | --- | --- |
| Native arm64 SDL Tiles with a source bridge | Original renderer, direct window, lowest component count, controllable input boundary | Local compilation; source patch must be maintained | MVP |
| Linux container + Xvfb + noVNC | Clean-room runtime, parallel headless sessions, browser streaming | VM/display/transport layers; startup and input integration; no measured advantage for this single-user run | Revisit for unattended or multi-instance evaluation |
| Upstream Emscripten | Browser-native viewing, upstream build support exists | Asyncify, persistence and browser execution add integration work; not benchmarked here | Revisit if browser delivery becomes primary |
| Screen-only native automation | No source patch | OCR/context ambiguity, high interaction cost, weak action acknowledgment | Fallback/manual diagnostic, not primary transport |

This is a requirements decision, not a claim that native is universally faster.
Pinned upstream 0.I-1 includes native and Emscripten build support. We choose
native because the user wants a visible local game and reliable closed-loop
control. We can move the file protocol and controller to Linux later without
designing a general deployment system now.


## Consequences and revisit triggers

The user sees CDDA's original renderer and can intervene through its native
window. We own a pinned source patch, native build recipe, and upgrade testing.
One successful Mac build does not establish support for other operating systems
or older macOS versions. Measured integration costs for alternatives remain unknown.

Reopen this decision for multi-instance evaluation, unattended operation, broader
platform support, browser-first distribution, or excessive patch maintenance.
Compare clean setup, control reliability, display quality, recovery, upgrade cost
and operating cost under the new requirements. Convenience of the existing setup
is insufficient justification. No migration is implied until that comparison.

Current structure is in [architecture](../architecture.md); dated evidence is in
[MVP acceptance](../acceptance/2026-10-17-mvp.md).
