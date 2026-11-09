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

- **Priority** on every leaf: P0 urgent constraint or control failure, P1 the next
  important outcome, P2 useful follow-up. **Horizon** on outcomes only: Now, Next, Later
  (with a revisit trigger). The Project's views select leaves by Status and outcomes by
  Horizon ([authority and review surfaces](authority.md)).
- **Dates:** none kept by hand. Cycle time comes from GitHub's own timestamps: a PR
  opened to merged, an issue opened to closed.
- **Review and validation** state lives on the PR (draft, checks, review threads) and in
  the issue's current-state block.
- **Parking** returns an item to Backlog with its reason and resumption trigger.
  Duplicates and cancellations close as not planned and are excluded from delivery.
- Do not use automatic close or merge-to-Done rules. Use `Refs #N`, and before merging
  read `gh pr view <number> --json closingIssuesReferences` and require an empty list;
  prose negation does not disable GitHub's keyword parsing
  ([the observed failure](https://github.com/CVX-Hull/enactive/issues/75)). Move an item
  to Done only after merged-main validation and its outcome evidence.

## Ready brief and execution capacity

A Ready leaf's issue states, in about five lines: the problem; acceptance; the owner and
owned paths; the stop condition; and any owner decision needed, asked as the
[approval request requirements](../operator-permissions.md#requesting-owner-approval)
say. A worker handoff adds the base revision, worktree, fixed decisions, exact checks
and return evidence, as S-AGENT requires.

Keep one active integration slice and at most two implementation workers, each in its own
worktree under `.runtime/worktrees/<leaf>` with disjoint named paths and one writer per
checkout. A worktree installs its own npm dependencies with `npm ci`; it may link the main
`.venv` only if the leaf leaves the Python lockfile unchanged. Explorers read only;
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
