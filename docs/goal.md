---
owner: lead
status: active
review_trigger: User changes scope, constraints or acceptance; milestone completion
---

# Project goal

Implement the complete CDDA Player project discussed with the user: a researched,
maintainable MVP that lets an agent play authentic Cataclysm: Dark Days Ahead while
the user watches through a good graphical interface, supported by an understandable,
enforced and maintainable engineering system. Carry work through implementation,
independent review and a real graphical gameplay demonstration.

## Active continuation: seven-day survival

The user extended the goal to complete the entire
[seven-day campaign path](work.md#campaign-delivery-path), outcome
[#10](https://github.com/CVX-Hull/enactive/issues/10): bounded pilot/review,
continuity and first-day rehearsal, independently reviewed readiness, then a real
normally created fresh character alive after seven elapsed in-game days with
essential needs maintained, meaningful supply/travel decisions, ordinary rest,
save/restart and player handoff, watchable progress and user Pause/takeover.
Routine play and recovery must not require user intervention. Reduce unnecessary
approval friction through tested narrow project-scoped permissions while respecting
managed restrictions; preserve one executor and explicit handoff if delegating
play to a dedicated sub-agent.

Carry the work through implementation, truthful graphical acceptance, findings
routing, protected publication and cleanup. Preserve finite prospective resource
limits, failed/partial/unknown attempts and current authority rules. Intermediate
demonstrations and completed research do not complete this continuation. GitHub
Issues #78–#83 own scope, gates and acceptance; the current path links their briefs
and evidence. MVP completion below remains historical scoped evidence.

## Required outcomes

1. **Research and choose the right setup.** Investigate CDDA, integration/reuse
   options and alternative platforms on capability and lifetime cost, rather than
   convenience with the current Mac. Use current primary sources, distinguish
   findings from inference, and record consequential choices and reversal triggers.
2. **Build the engineering system.** Establish high-level purpose, constraints and
   principles; derive standards and concrete controls at architecture,
   implementation, testing, operations, delivery, agent workflow and project
   management levels. Define ownership, evidence, failure responses and limitations.
   Prefer mature tooling over custom generic infrastructure and unnecessary ceremony.
3. **Address agentic failure modes.** Research recent experience with agentic coding
   and GPT behavior, account for rapidly changing models, and translate credible
   findings into the workflow, contracts, tests and review practices. Do not treat
   agent reports, self-written tests or historical benchmarks as sufficient proof.
4. **Maintain documentation and controls themselves.** Give documents clear authority,
   status, ownership, audience and review/retirement rules. Keep one authoritative
   home for facts and update guidance with behavior. Give controls lifecycle,
   exercise evidence, effectiveness/cost review, due dates and event triggers.
   Detect mechanical drift with tools; retain semantic and usability review.
   Improve, replace or retire practices based on failures and maintenance burden.
5. **Make the project easy for the user to review.** Provide progressive detail:
   concise purpose/capabilities/limits first, then architecture, rationale, risks,
   changes and evidence. Include useful context, interaction and recovery diagrams,
   editable sources, readable rendered output, text equivalents, walkthroughs and
   dated gameplay evidence. High-level review must not require reading the code.
6. **Implement and demonstrate the graphical play MVP.** Reuse CDDA's real graphical
   renderer and engine behavior. Support observation, bounded actions, visible
   control ownership, pause/takeover, uncertainty reconciliation and persistence.
   Research recent robotics, VLA and related approaches to choose efficient
   closed-loop play; validate applicable ideas in CDDA instead of assuming robot
   models transfer directly. Measure planner effort/latency separately from safety
   and survival. Demonstrate real play, meaningful interactions and recovery.

## Non-negotiable constraints

- Never launch fullscreen. Keep the experience usable in ordinary windows.
- The user must not have to supply keys or routine recovery to keep the agent's
  campaign running. Verify the agent's control and recovery access before play.
  Required human rescue is a failed autonomy case and blocks campaign readiness;
  voluntary user Pause/takeover remains available.
- Keep new dependencies, binaries, environments, caches, saves and outputs under
  this project or an explicitly recorded owned temporary build directory. Do not
  install global packages, edit shell profiles or modify unrelated applications.
  Record and resolve any accidental global changes honestly.
- Use Git for source, configuration, documentation, pins and reviewable checkpoints.
- Follow the repository's delegation policy: lead owns design, briefs, adjudication,
  integration and verification; explorers read, workers have bounded disjoint paths,
  reviewers use fresh context, parallel implementation uses isolated worktrees and
  bounded ownership under S-AGENT, and one lead integrates and owns shared runtime.
- Evaluate global skills for relevance; do not import a generic lifecycle or
  framework merely because it is available.
- Preserve authentic gameplay: no hidden-state advantage, save editing to win,
  bypassed engine validation, or mock substituted for a failed real demonstration.

## Completion and continuing maintenance

Completion requires implemented outcomes, relevant passing checks, rendered and
user-oriented inspection, resolved material independent-review findings, a real
windowed gameplay demonstration, scoped dated evidence, reproducible local setup,
and reviewable Git checkpoints. Report limitations and failed attempts explicitly.
Configured CI is not an executed remote check; policy is not proof of effectiveness.

The MVP permits Codex in an active chat to plan and interpret play. It does not
promise unattended general survival, a trained VLA, every host, or every native
error screen. These capability boundaries must remain visible; research does not
by itself justify a broader claim. Maintenance is an ongoing obligation with
owners and triggers, not a reason to claim the project is permanently finished.

This document owns the consolidated requested outcome. The [charter](charter.md)
owns principles; [standards](engineering.md) own requirements; [controls](controls.md)
expose enforcement and gaps; [work](work.md) links GitHub's current progress and priorities.
Start at the [overview](overview.md) to assess what currently exists. Dated
[consolidated acceptance](acceptance/2026-10-17-completion.md) maps the original MVP outcomes;
[MVP](acceptance/2026-10-17-mvp.md),
[engineering](acceptance/2026-10-17-engineering-system.md) and
[documentation](acceptance/2026-10-17-documentation-review.md) reports supply
milestone evidence; they must not be mistaken for fresh execution.

## Memory and continuous-learning investigation

The user extended the requested work on 2026-10-18: thoroughly explore memory and
self-learning representations through mathematics, statistics and other applicable
fields, critically assess their CDDA fit, and simulate competing mechanisms before
choosing a coherent design. The [investigation brief](changes/013-memory-representation-study.md)
defines the research lenses, operational meaning of elegance, falsifiable
comparisons, reproducibility, independent review and completion evidence. It
includes adopt/test/defer decisions and bounded implementation follow-ups; it does
not equate a research or synthetic result with a live gameplay capability.

The [study synthesis](research-memory-representations.md) and
[dated research acceptance](acceptance/2026-10-18-memory-representations.md) map
this extension to primary-source review, reproducible comparisons, independent
checks, a proposed representation/learning loop and staged follow-ups. Real-game
memory or policy benefit remains a separate evaluation obligation.
