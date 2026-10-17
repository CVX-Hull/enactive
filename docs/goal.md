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
[consolidated acceptance](acceptance/2026-10-17-completion.md) maps all outcomes;
[MVP](acceptance/2026-10-17-mvp.md),
[engineering](acceptance/2026-10-17-engineering-system.md) and
[documentation](acceptance/2026-10-17-documentation-review.md) reports supply
milestone evidence; they must not be mistaken for fresh execution.
