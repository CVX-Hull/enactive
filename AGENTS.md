---
owner: maintainer
review_trigger: Engineering standards or contributor workflow changes
status: active
---

# CDDA Player

Start with [the overview](docs/overview.md), then [engineering standards](docs/engineering.md).
Read [architecture](docs/architecture.md), [protocol](docs/protocol.md) and
[current work](docs/work.md) before changing relevant boundaries. Follow S-AGENT
for delegation: the lead owns design/integration/verification; parallel workers use
separate worktrees and disjoint ownership; one integrator and shared-runtime owner;
named agent_type; clean-context workers/reviewers; bounded briefs.

- User instructions take precedence. Global skills are optional references;
  do not import ceremony without a concrete project need.
- Follow S-MIGRATION: one current contract; migrate every caller and persisted format
  together, remove old paths, and reject unsupported versions. No compatibility shims.
- New dependencies, saves, caches and outputs stay project-local or in explicitly
  recorded owned temporary builds. No global installs/profiles/application changes.
- Never launch fullscreen. Use the prepared wrapper and explicit project userdir.
- Preserve real CDDA behavior: player-visible observations only; no save editing
  or engine-validation bypass to manufacture a demonstration.
- Tests, native builds and graphical acceptance are separate evidence lanes.
  Record failure and uncertainty; never replace a real failure with a passing mock.
- Keep the overview and authoritative contracts current with behavior. Historical
  reports, proposals and superseded ADRs are evidence, not current instructions.
- Apply S-CODE's reuse review to tools, documentation and controls. Git owns tracked
  source history; custom infrastructure needs a concrete gap and maintenance owner.
- Run the common checks and inspect staged changes before checkpointing. Control
  definitions, coverage limits and gaps are in [the control map](docs/controls.md).
