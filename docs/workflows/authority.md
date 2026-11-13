---
owner: lead
review_trigger: Changes to this delivery decision, ownership or review policy
status: active
---

# Authority and review surfaces

The public repository is [CVX-Hull/enactive](https://github.com/CVX-Hull/enactive), with
the [public Project](https://github.com/users/CVX-Hull/projects/2). Which document owns
which kind of fact is stated once, in the
[documentation map](../documentation.md#one-authoritative-home-per-kind-of-fact), and
[S-DOCS](../standards/documentation.md#current-pages-records-and-decisions) gives the
rules that follow; this page
owns what each summary may restate and the Project's views. Exceptions are issues linked
to their affected standard; the [work map](../work.md) is the navigation entry point.

Keep summaries purpose-specific: the overview explains capabilities and limits;
the work map routes to open outcomes and the evidence index; a design note or a pull
request records a change's design. Do not copy Issue status, assignment, estimates,
next-action queues or CI receipts into those pages. A concise evidence checkpoint
may link a dated record, but detailed attempt chronology belongs in that record, costs
in the run ledger, and publication receipts in the PR. At integration review, remove
mirrored fields, stale “current” claims and repeated narratives rather than append
another checkpoint. Semantic duplication is a review judgment (C-REVIEW), not a
parser or per-action check.

Use GitHub's issues, sub-issues, dependencies, milestones, pull requests, fields,
saved views and built-in workflows. No custom tracker or background scheduler.
Select work for the next independent-play outcome and the longer-term capabilities
that enable future outcomes. Resolve demonstrated obstacles and make deliberate
investments in useful accelerators. Apply P-CHANGE/S-CODE to available capabilities
beyond this repository; adoption, integration and deletion can be more valuable
than new implementation. Include setup, latency, review and ongoing operating cost
in the choice. Do not turn a speculative framework, exhaustive defense or process
improvement into a campaign prerequisite without a concrete outcome dependency.
The Project README links this contract, the overview and these four saved views:

| View | User question and contents |
| --- | --- |
| Current iteration | What is moving? Board by Status of open leaves that are Ready or In progress (aggregates excluded), sorted by Priority; show owner, Priority, parent issue and linked pull request. GitHub views have no dependency field: an issue blocked through GitHub's issue dependencies carries a Blocked mark on its card |
| Backlog | What is unselected? Open leaves in Backlog, sorted by Priority; show Priority, parent issue and sub-issue progress |
| Direction | What outcome comes next and why? Open `outcome` aggregates grouped by Horizon and sorted by Priority; show milestone, priority, outcome and decision needed |
| Needs attention | What needs intervention? Open items labelled blocked or decision-needed, or blocked through an issue dependency (`is:blocked`); a generic risk label alone does not qualify. The lead flags aging In progress work during checkpoint triage |

At a meaningful checkpoint, update the Project with outcomes achieved, next
outcome, risks/blockers, decisions needed and evidence links. Give consequences
in plain language; implementation detail belongs behind links. Routine authorized
work continues; changed user constraints or substantial commitments need user input.

Reconcile actionable discussion, research, review and campaign findings at those
checkpoints. Prefer updating an existing issue; create a new one only for distinct
owned work. Give each finding an implementation/follow-up, duplicate, deferred or
rejected disposition with its reason, next action/acceptance and dependencies.
Link affected design, principles/standards/controls, procedures and evidence;
update their authoritative sources when applicable, including the controls page.
Preserve current-versus-proposed status and unverified lanes.
C-REVIEW checks this coverage. A review finding is not fixed because it was filed,
and a document is not accurate merely because it has a recent date.

[Workflow index](../project-management.md).
