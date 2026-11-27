---
owner: lead
review_trigger: Boundary-leaf discovery, review or owner-decision settlement workflow changes
status: active
---

# Design discovery and decision settlement

Use this workflow for **open-design and boundary leaves** — changes that introduce or
alter ownership, persistence, schema, memory, protocol or harness boundaries
([boundary review trigger](review.md#risk-based-assurance)). Skip it for editorial
edits, bug fixes inside unchanged boundaries and implementation leaves whose design is
already settled. This page operationalizes existing review, evidence and documentation
rules without adding a new standing gate (`R-CONTROL-BLOAT`).

## 1. Pre-decision discovery bar

Before bringing an open boundary leaf to the owner for a decision, run four independent
lenses in parallel through delegated read-only roles
([S-AGENT](../standards/agents.md#the-leads-duties),
[model routing](../operations/model-routing.md)) so the lead's thread stays focused on
synthesis and trade-offs:

1. **Primary repo, history and sealed-evidence audit.** Inspect current code and
   contracts, relevant prior PRs or narrowed decisions (why earlier approaches were
   changed or dropped), and the raw sealed data or frames themselves rather than relying
   solely on secondhand summaries.
2. **Open-horizon primary-source literature discovery.** Follow
   [evidence standards](../standards/evidence.md) and the
   [research cutoff rules](../research.md): actively search for current primary
   literature relative to today's date, split into focused tracks when a leaf spans
   distinct axes (for example, formal or mathematical representations vs. empirical
   systems), fetch every cited source verbatim to scratch before citing it, reject
   unverified snippet identifiers, and actively hunt for negative results and failure
   modes (what *not* to build).
3. **Cross-family independent architectural critique.** Start clean-context explorers
   from distinct model families (`tools/delegate.py --role explorer`) on the same scoped
   questions, testing portability across game genres and paces (`P-GENERALITY`),
   latency/hot-path budgets and migration boundaries (`S-MIGRATION`).
4. **Targeted Round 2 when Round 1 exposes real tensions.** If Round 1 reveals a sharp
   disagreement between model families, an unverified empirical assumption (such as
   uninspected frames or past-PR causes) or an under-explored formalism, run a focused
   Round 2 on those exact tensions before recommending a design. Do not smooth over
   disagreements silently.

Synthesize findings concisely for the owner: separate directly verified facts from
inferences, highlight negative results, lay out concrete trade-offs where options
diverge, and recommend one concrete option per open choice.

## 2. Owner-decision settlement

Once the owner settles a design choice, close the loop in one clean pass:

1. **Worktree and documents.** Create a dedicated worktree under
   `.runtime/worktrees/<descriptive-name>` and apply the seven-step
   [document checklist](../documentation.md#before-writing-or-changing-a-document):
   - Add one row to the [owner decision log](../decisions/owner-decisions.md) with a
     concise accurate quote of the owner's answer, distinguishing approved targets from
     current enforced behavior and cross-referencing any narrowed prior decision.
   - Update only affected current-page or research-index pointers; keep live issue
     status on GitHub and the Project rather than duplicating it on current pages.
2. **Attempts ledger.** Append every explorer's `attempt-row-draft.json` to
   `data/evaluation/coding-agent-attempts.jsonl` with exact `issue`, verbatim
   `kind_of_work` from [model routing](../operations/model-routing.md), `outcome` and
   `brief_extent: null` unless recorded before the run.
3. **Local checks and Commit 1.** Run `.venv/bin/pytest tests/test_coding_agent_attempts.py`
   and `.venv/bin/python tools/documents.py`, then commit through the repository hook.
4. **Clean-context review.** Run one clean-context document review from a non-author
   model family (`tools/delegate.py --role reviewer`; see
   [decision-log review limit](review.md)). Fix every confirmed finding in Commit 2,
   record dispositions (`confirmed`/`rejected`) and append the reviewer's attempt row.
5. **Pull request and tracker sync.** Verify repository-local commit identity and full
   commit messages, open the pull request with a complete `Models:` line, replace
   affected GitHub issue descriptions cleanly (never append) and verify Project fields.
   After CI passes and the pull request merges, fast-forward `main` and remove the
   worktree and local branch.

[Workflow index](../project-management.md).
