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
named role; clean-context workers/reviewers; bounded briefs. These instructions
are host-neutral; [coding-agent hosts](docs/operations/coding-agents.md) maps
roles, tools and permissions for each supported coding agent.
For gameplay, the lead may explicitly designate one general-purpose campaign
operator under the frozen player host's bounded actor/handoff procedure.
Explorers/reviewers never send game inputs.

- User instructions take precedence. Global skills are optional references;
  do not import ceremony without a concrete project need.
- Apply the charter's CDDA-class portability constraint and P-GENERALITY.
  The selected harness boundary is basic computer observation/control only;
  game semantics belong in the playing system. Follow [ADR006](docs/decisions/006-computer-control-boundary.md)
  for the coordinated cutover and the current computer-control contract.
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
- Enactive is a local player on a personal computer; the charter's
  [scope of use](docs/charter.md#scope-of-use-and-what-is-guaranteed) says what is and
  is not guaranteed. Do not add a test, check, guard, gate or procedure step unless it
  names a risk in the [risk register](docs/risks.md), a realistic way it reduces that
  risk, and its cost ([control rule](docs/standards/authority.md#control-review));
  remove a control when what it protected is finished. Existing controls and their
  gaps are in [the controls page](docs/controls.md).
- Give everything a [descriptive name](docs/standards/documentation.md#names): no
  bare ordinals such as `P1` or `study 3` for phases, studies, files, branches or issues.
- Put each fact in its one home, following the seven-step
  [checklist](docs/documentation.md#before-writing-or-changing-a-document): current
  pages say what is true in the present tense; an owner decision is a row in the
  [owner decision log](docs/decisions/owner-decisions.md), added in the change that
  acts on it; a dated record is only for evidence from a run, measurement or study; an
  issue has one description, replaced and not appended to.
- A delegated agent reads its brief, the [glossary](docs/glossary.md) and the row for
  its code area in [from code to its documents](docs/documentation.md#from-code-to-its-documents),
  not the whole document set. Briefs follow the
  [template](docs/standards/agents.md#brief-template) and the
  [environment facts](docs/operations/coding-agents.md#environment-facts-for-agents).
