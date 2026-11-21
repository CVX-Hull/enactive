---
owner: lead
status: active
review_trigger: The matched-run exception, routing triggers or attempt ledger changes
---

# Compare two coding agents on one leaf

This procedure covers selecting a leaf, comparing the two attempts blind and recording
the result under the [matched-run exception](../standards/agents.md#the-leads-duties).

## Matched runs on this repository's leaves

A matched run gives one leaf to two coding agents and keeps both results, so a row can
change on how its models did on this repository's own work. It is the control
C-MATCHED-RUNS on the [controls page](../controls.md), which owns its risk and cost.

### When and on what

A [trigger](model-routing.md#keeping-this-page-current) may start a matched run on the rows it changes,
and so may a routing row never observed here; the lead names the row and decides
whether the run is worth its cost. It applies to rows whose leaf ends in a diff that
can merge, not to review, research or reading rows. The lead picks one Ready leaf
([work items](../workflows/work-items.md#ready-brief-and-execution-capacity)) of that
row's kind of work that needs no game runtime and no paid model call. At most three
leaves are run per trigger. Where a row's first choice is a role and not one model, the
first choice is the model that role runs on in the lead's session.

### Running it

1. The leaf goes to the row's first choice and to one challenger the lead names. These
   are the two implementation workers
   [work items](../workflows/work-items.md#ready-brief-and-execution-capacity) allows,
   under its exception for a matched run: the two share owned paths and one merges.
2. Both get the same brief and the same base commit, each in its own worktree on its own
   branch ([environment facts](coding-agents.md#environment-facts-for-agents)). The
   branch name says the leaf, not the coding agent.
3. The lead reruns the brief's acceptance check on both final commits, whatever each
   attempt reported, and counts the repairs it had to ask for.
4. A clean-context reviewer compares the two diffs under neutral labels, such as "left"
   and "right", that name no model or coding agent. It gets the diffs as files
   (`git diff <base> <head>`) outside the checkout, and its brief forbids reading
   branches or history, because commit trailers and branch logs name the model. The lead
   alone keeps the mapping from label to attempt.
5. The lead merges one attempt and discards the other. When neither passes, the lead
   discards both and takes the leaf back.
6. In the pull request that merges the chosen attempt, or in the lead's own pull request
   for the leaf when both are discarded, the lead adds one row per attempt to
   `data/evaluation/coding-agent-attempts.jsonl`, in the shape of
   `schemas/coding-agent-attempt.schema.json`, each with its `blind_preference`. The
   kind of work is the [routing table](model-routing.md#route-by-kind-of-work)'s first cell. `tests/test_coding_agent_attempts.py`
   refuses a row the [ledger reading rules](model-routing.md#reading-the-ledger) cannot use.
