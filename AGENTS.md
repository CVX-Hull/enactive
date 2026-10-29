---
owner: maintainer
review_trigger: Engineering standards or contributor workflow changes
status: active
---

# Enactive

Designated deciding players start with [the compact player guide](docs/player-guide.md),
their frozen mission brief and the selected current tool schema. They do not need
the engineering document set or recursive runtime/source searches for routine play.
For engineering work, start with [the overview](docs/overview.md), then [engineering standards](docs/engineering.md).
Use the [documentation map](docs/documentation.md) to scope a change from the
highest affected responsibility through component design/contracts to code and
select proportionate review. Current architecture is not an attempt log.
Read [architecture](docs/architecture.md), [protocol](docs/protocol.md) and
[current work](docs/work.md) before changing relevant boundaries. Follow S-AGENT
for delegation: the lead owns design/integration/verification; parallel workers use
separate worktrees and disjoint ownership; one integrator and shared-runtime owner;
named agent_type; clean-context workers/reviewers; bounded briefs.
For gameplay, the lead may explicitly designate one general-purpose campaign
operator under the protocol's bounded actor/handoff procedure. The waypoint
planner remains candidate-only; explorers/reviewers never send game inputs.

- User instructions take precedence. Global skills are optional references;
  do not import ceremony without a concrete project need.
- Apply the charter's CDDA-class portability constraint and P-GENERALITY.
  The selected harness boundary is basic computer observation/control only;
  game semantics belong in the playing system. Follow [ADR006](docs/decisions/006-computer-control-boundary.md)
  for the coordinated cutover; current semantic contracts are not yet migrated.
  Keep shared player/memory/learning/orchestration separate from game bindings;
  document existing coupling rather than claiming unqualified portability.
- Follow S-MIGRATION: one current contract; migrate every caller and persisted format
  together, remove old paths, and reject unsupported versions. No compatibility shims.
- New dependencies, saves, caches and outputs stay project-local or in explicitly
  recorded owned temporary builds. No global installs/profiles/application changes.
- Verify public commit identities and full messages, including co-author trailers,
  before pushing. Use explicitly configured repository-local identity; never infer
  the maintainer's public identity from the Mac account or publish its local email.
- Never launch fullscreen. Use the prepared wrapper and explicit project userdir.
- Preserve real CDDA behavior: player-visible observations only; no save editing
  or engine-validation bypass to manufacture a demonstration.
- Tests, native builds and graphical acceptance are separate evidence lanes.
  Record failure and uncertainty; never replace a real failure with a passing mock.
- Keep the overview and authoritative contracts current with behavior. Historical
  reports, proposals and superseded ADRs are evidence, not current instructions.
- Apply S-CODE's reuse review to tools, documentation and controls. Git owns tracked
  source history; custom infrastructure needs a concrete gap and maintenance owner.
  Rely on configured DB/OS/library contracts; justify residual checks and recovery
  against actual deployment, failure evidence, latency and maintenance cost.
- Use the [development-first workflow](docs/workflows/development.md#development-first-delivery):
  fast checkpoint checks and relevant focused tests before development play;
  independent review and the appropriate protected CI profile before formal acceptance/merge;
  broad source changes require full regression before merge.
  Freeze each finite run and retain failures. Inspect staged changes before commits.
  Control coverage and gaps are in [the control map](docs/controls.md).
