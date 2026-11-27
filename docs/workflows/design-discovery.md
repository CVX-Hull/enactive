---
owner: lead
review_trigger: Boundary-leaf discovery, review or owner-decision settlement workflow changes
status: active
---

# Design discovery and decision settlement

Use this playbook for **open-design and boundary leaves** — changes that introduce or
alter ownership, persistence, schema, memory, protocol or harness boundaries
([boundary review trigger](review.md#risk-based-assurance)). Skip it for editorial
edits, bug fixes inside unchanged boundaries and implementation leaves whose design is
already settled. This page operationalizes existing review, evidence and documentation
rules without adding a new standing gate (`R-CONTROL-BLOAT`).

## 1. Pre-decision discovery

Before bringing an open boundary leaf to the owner for a decision, the lead selects
the smallest useful set of read-only discovery lenses for the leaf's risk and
uncertainty ([S-AGENT](../standards/agents.md#the-leads-duties),
[model routing](../operations/model-routing.md)), delegating them in parallel so the
lead's thread stays focused on synthesis and trade-offs:

1. **Primary repo, history and sealed-evidence audit.** Inspect current code and
   contracts, relevant prior pull requests or narrowed decisions (why earlier designs
   changed), and raw sealed data or retained frames directly rather than relying solely
   on secondhand summaries.
2. **Open-horizon primary-source literature discovery.** Follow
   [evidence standards](../standards/evidence.md) and the
   [research cutoff rules](../research.md): search current primary literature relative
   to today's date, split into focused tracks when a leaf spans distinct axes (for
   example, formal representations vs. empirical systems), read every cited primary
   source directly and report its identifier, date and read scope, reject unverified
   snippet leads, and actively look for negative results and failure modes.
3. **Cross-family independent architectural critique.** Start clean-context explorers
   from distinct model families (`tools/delegate.py --role explorer`) on the same scoped
   questions, testing portability (`P-GENERALITY`), latency/hot-path budgets and
   migration boundaries (`S-MIGRATION`).

**Contingent follow-up (Round 2).** When initial discovery exposes a sharp disagreement
between model families, an unverified empirical assumption (such as uninspected frames
or past-change causes) or an under-explored formalism, run a targeted follow-up on
those specific tensions before recommending a design. Do not smooth over material
disagreements silently.

Synthesize findings concisely for the owner: separate directly verified facts from
inferences, highlight negative results, state concrete trade-offs where options
diverge, and recommend one option per open choice.

## 2. Owner-decision settlement

Once the owner settles a design choice, close the loop following the owning procedures:

1. **Worktree and documents.** Work in a dedicated worktree under
   `.runtime/worktrees/<descriptive-name>`
   ([environment facts](../operations/coding-agents.md#environment-facts-for-agents))
   and walk the seven-step
   [document checklist](../documentation.md#before-writing-or-changing-a-document):
   - Add one row to the [owner decision log](../decisions/owner-decisions.md) with a
     concise accurate quote of the owner's answer, keeping approved targets distinct
     from current enforced behavior and cross-referencing any narrowed prior decision.
   - Update owning current-page text when behavior changes, retire settled design notes
     or research pages where applicable, update affected links, and keep live issue
     status on GitHub and the Project.
2. **Attempts ledger.** When the work ran tracked delegates for an issue, append each
   `attempt-row-draft.json` to `data/evaluation/coding-agent-attempts.jsonl` per
   [model routing](../operations/model-routing.md#reading-the-ledger) (leaving
   `brief_extent: null` unless recorded before the run).
3. **Checks and commit.** Run `tools/documents.py` (and
   `tests/test_coding_agent_attempts.py` when the ledger changed) using the main
   checkout's Python from [environment facts](../operations/coding-agents.md#environment-facts-for-agents),
   then commit through the repository hook.
4. **Review and disposition.** Select review scope, reviewer family and finding
   dispositions under [review by decision and risk](review.md) (including its
   decision-log review limit). Resolve material findings before advancing, track
   nonblocking follow-ups, and record dispositions and any reviewer attempt row.
5. **Pull request, tracker sync and cleanup.** Open the pull request with verified
   repository-local commit identity and a complete `Models:` line
   ([review policy](review.md)), replace affected GitHub issue descriptions cleanly and
   reconcile Project fields ([work items](work-items.md)). After merge, fast-forward
   `main` and remove the worktree and local branch.

[Workflow index](../project-management.md).
