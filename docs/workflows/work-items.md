---
owner: lead
review_trigger: Changes to this delivery decision, ownership or review policy
status: active
---

# Work items and flow

GitHub Issues own scope, acceptance, the accountable owner, blockers and exceptions.
The linked Project owns each item's execution stage. Pull requests own implementation,
checks and review. There is no other tracker.

| Scale | Home |
| --- | --- |
| Outcome | An issue labelled `outcome` whose children carry execution; it owns the outcome's acceptance and limitations |
| Leaf | One issue for one independently reviewable result |
| Change | One pull request per leaf, or one for a coordinated S-MIGRATION batch |
| Runtime attempt | A frozen finite run; its run record owns the evidence |

## Outcome-focused iterations

Choose a valuable, inspectable outcome, not a number of cards, PRs or attempts. Shape a
required core, explicitly optional scope and a stop or rescope condition. Include work
only when it serves the goal, resolves a concrete risk or dependency, or shares setup
cheaply. Fund the reuse research, design, implementation, integration, checks, evidence,
review, current documentation and cleanup inside the outcome. Capability outcomes end
with the promised behaviour and evidence; discovery outcomes end with the named decision
or a stop condition. A negative investigation can complete its research goal; it never
satisfies a failed feature acceptance. If the core cannot fit, rescope or split it;
reduce optional scope before weakening required quality or evidence.

## Status, fields and dates

| Status | Meaning |
| --- | --- |
| Backlog | A problem and intended outcome; no commitment |
| Ready | The Ready brief is complete and needed decisions are made |
| In progress | Being built, checked, reviewed or validated; the PR shows which |
| Done | The lead verified acceptance, evidence and documentation on merged main |

- **Priority** on every leaf: *Urgent* for a broken user constraint or a failed
  control, *Important* for the next outcome, *Follow-up* for useful later work. **Horizon** on outcomes only: Now, Next, Later
  (with a revisit trigger). The Project's views select leaves by Status and outcomes by
  Horizon ([authority and review surfaces](authority.md)).
- **Dates:** none kept by hand. Cycle time comes from GitHub's own timestamps: a PR
  opened to merged, an issue opened to closed.
- **Review and validation** state lives on the PR (draft, checks, review threads) and in
  the issue's description.
- **An issue has one current description**, in the shape of the
  [Ready brief](#ready-brief-and-execution-capacity). When things change the description
  is replaced, not added to: no stacked state sections and no history narrative. GitHub
  keeps the edit history, comments record events, and owner decisions go in the
  [owner decision log](../decisions/owner-decisions.md). A description does not repeat
  Project fields.
- **Parking** returns an item to Backlog with its reason and resumption trigger.
  Duplicates and cancellations close as not planned and are excluded from delivery.
- A merged pull request never closes an issue: the repository's "Auto-close issues with
  merged linked pull requests" setting is off, and no merge-to-Done rule is used. A
  closing phrase once closed an issue before its validation
  ([the observed failure](https://github.com/CVX-Hull/enactive/issues/75)); with the
  setting off there is nothing to check before merging. Reference issues with
  `Refs #N`, and move an item to Done only after merged-main validation and its outcome
  evidence. If the setting is ever turned on again, this rule needs its manual check
  back.

## Ready brief and execution capacity

An issue's description has these parts, each a line or a short list; the issue form
asks for them in this order:

1. **Current state**: what is built, what is decided, what is next.
2. **Outcome** for an outcome, **Problem** for a leaf.
3. **Acceptance**.
4. **Owner and paths**.
5. **Stop condition**.
6. **Owner decision needed**, asked as the
   [approval request requirements](../operator-permissions.md#requesting-owner-approval) say.
7. **Depends on** and **Revisit when**.
8. **Links**: parent, design, at most three records.

A leaf is Ready when parts 2 to 6 are complete and the decisions it needs are made. A
worker handoff is a brief that follows the
[brief template](../standards/agents.md#brief-template).

Keep one active integration slice and at most two implementation workers, each in its own
project-local worktree (`.runtime/worktrees/<leaf>`, or where the host's worktree
isolation puts it: [environment facts](../operations/coding-agents.md#environment-facts-for-agents))
with disjoint named paths and one writer per checkout. A worktree installs its own npm
dependencies with `npm ci` and uses the main checkout's `.venv`; a leaf that changes the
Python lockfile builds its own. Explorers read only;
reviewers get fresh context. The lead alone integrates and serializes the game, saves,
bridge, ports, builds, dependency environments and caches; workers do not run native
demonstrations. Pull new work only when implementation, review and validation capacity
exist, and reconcile the Project when selecting work. After two unsuccessful repairs, or
drift beyond owned paths, the worker stops and the lead takes the work back.

Done includes removing the leaf's worktree and local branch once `git status` shows
nothing uncommitted.

## Estimates and forecasts

An appetite states how much effort an outcome merits; an estimate predicts the effort;
a forecast predicts completion under stated capacity. None of them grants run, token or
financial allowances. Estimate a range for the whole outcome when it helps a decision,
forecast from this project's own history with its sample and assumptions, and re-estimate
openly when scope or evidence changes. Lines, commits, PRs, tests and agent utilization
are activity, not success targets. Review the critical path, including review and the
serialized native lane: more workers do not shorten a shared bottleneck.

[Workflow index](../project-management.md).
