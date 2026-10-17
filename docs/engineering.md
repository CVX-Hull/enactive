# Engineering practices

Owner: lead. Updated: 2026-10-17. Review on changed behavior or failed acceptance.

## Documentation and decisions

README is the entry point and honest capability status. Architecture owns the
component and protocol contract. This document owns engineering rules. Work
owns progress, acceptance evidence, and backlog. Research owns evidence and its
limitations. Environment owns external changes. Keep each fact authoritative in
one place; link rather than clone. Add a separate decision record only when a
choice has material alternatives, consequences, or a reversal trigger; the
initial decisions fit in architecture.md.

Enforcement: the common check command will validate required documents and
local Markdown links. A behavior-changing diff must update the relevant
contract and acceptance evidence; an independent reviewer checks semantic drift
that a link checker cannot detect. A checklist is not proof of accuracy.

## Workflow and project management

Use small vertical slices: write the outcome and failure conditions, inspect
real interfaces, implement, run relevant checks, review risk, then checkpoint.
The lead owns design and integration. Delegate read-only investigation to
explorers, bounded named paths to a worker, and fresh-context audits to a
reviewer. One implementation writer at a time. Two unsuccessful repair attempts
or ownership drift returns the task to the lead. No agent's report substitutes
for inspecting its diff or evidence.

The work board is docs/work.md, with pending/active/verified/blocked states,
acceptance evidence, and explicit limitations. There is no duplicate plan
tracker. Finish an integration slice before opening another large one. A
blocker is a condition and next action, not a vague status. Deferred work needs
a reason and revisit trigger. User approval is required only where the user's
authorization or actual risk requires it; internal plans do not invent gates.

Enforcement: briefs name paths, fixed decisions, and checks. Review before
changing an architectural boundary. Final acceptance requires real graphical
gameplay evidence in addition to tests. Record failed attempts as failures.

## Coding standard

Prefer Python's standard library for the small local service and CLI, vanilla
browser modules for the viewer, and the game's existing C++/JSON/SDL interfaces
for the bridge. Add a package only for a concrete capability that it handles
better; pin and record it locally. Use explicit types at Python boundaries,
small cohesive functions, descriptive names, and error messages with recovery
actions. Mirror upstream C++ conventions in patches. Do not build speculative
plugin systems or generic orchestration frameworks.

Input validation belongs at trust boundaries. Bound sizes, durations, and action
counts. Use atomic file replacement, unique request IDs, and monotonic
revisions. Never silently retry a game action whose outcome is unknown. Handle
expected errors explicitly; broad catches may contain the service boundary but
must preserve diagnostic evidence. Test observable outcomes and adversarial
transitions, not copies of implementation details.

Enforcement: a single project check command runs compilation/syntax checks,
behavior tests, and documentation checks. Python formatting/lint tooling, if
added, runs from the project environment. Tests cover stale commands, duplicate
delivery, pause/takeover, timeout ambiguity, invalid input, and context changes.
Native compilation and real game tests are separate lanes. Tests may not be
weakened to make a diff pass. Any changed expectation needs a reason grounded in
the contract, not the generated output. Review examines dependencies and
unnecessary scope as well as functionality.

## Architecture design standard

For each boundary specify owner, input/output, state transitions, authority,
failure behavior, and an acceptance probe. Describe alternatives and the
conditions that would change the decision. Prefer a minimal working vertical
slice over elaborate future components. Observations must say where and when
they came from. A request accepted by transport is not an action proven to have
succeeded in the game.

Enforcement: protocol examples and tests share a version; reviewers check that
producers and consumers agree, including timeout and recovery. A source patch
must fail closed when upstream anchors change. A new game version requires
reapplying and reviewing the patch plus real-game regression tests.

## Version control and releases

Git tracks our code, patches, setup recipes, dependency pins, checks, and docs.
Runtime binaries, downloads, builds, saves, screenshots, and journals live in
ignored .runtime/; curate small evidence manifests or representative images
explicitly when useful. Never add tokens, credentials, user saves, or entire
upstream builds. Use repository-local settings only. Do not invent a remote or
push/publish without a user request.

Commit cohesive verified slices with concrete messages. A checkpoint may state
that a slice is incomplete; it must not claim passing checks that did not run.
Preserve upstream source/license provenance and pin the release plus checksums.
Before a commit inspect staged paths, diff, whitespace, and relevant check
results. The common check command is authoritative; a repository-local hook is
convenience enforcement, not a security boundary. No global hooks or Git
identity changes. Public release/version tags wait for documented acceptance.

## Maintenance and improvement

On every behavior change, update the corresponding contract/test/runbook in the
same slice. After each real-game failure, classify transport, perception,
decision, or engine behavior; retain the evidence and add a regression only
when it captures a reusable failure. Keep performance measurements separate
from correctness. Remove rules and checks that add no demonstrated value.

Review upstream/dependency changes before upgrading, never auto-upgrade the
game during a run. Revisit fast-moving agent research when changing the
controller, and at a future release if evidence is more than 90 days old. This
is a release checklist trigger, not an unsolicited scheduled automation.
Record exceptions with scope, reason, owner, and revisit condition in work.md.
Unverified enforcement is labeled pending until its executable check exists.

Industry evidence and limits are in research.md. DORA and large-team practices
inform these choices; they do not justify imposing a large-team ceremony on a
single-user prototype.
