# Grooming instructions

Start from the brief's **Grooming worklist** instead of scanning the whole store. It lists records
from `knowledge/current-facts.jsonl` in two parts, one line each with the record's ID, its state and
the IDs it names. Read only the records and frames a repair needs. The trace holds the last
admission's cited frames and each actor's first and last framed operations. Treat facts as
hypotheses. Keep what a later actor could use, and preserve uncertainty and conditions.

**Must clear.** Every current record with non-empty `stale_citations` cites or `depends_on` a record
that is no longer current. The grooming fails while one remains at the version you leave, so clear
every one. A batch may not add a stale citation to any record, including moving one from a record
you repair to another.

- A one-to-one `restated` supersession: check that the replacement says the same thing, then use
  `remap_citations` (`from` the stale ID, `to` its replacement, `in` every slug that cites it).
- A restated merge or a `corrected` supersession: rewrite the affected claims with
  `edit_article`'s `replace_claims`, copying `index`, `old_text` and `old_facts` exactly.
- A narrowed fact: cite the child or children whose scope matches the article, with
  `replace_claims`.
- A retired fact (`wrong` or `ended`): there is no successor. Remove the claim with
  `remove_claims`, rewrite it with `replace_claims` so that it cites only current facts (for
  example, saying when the state held), or retire the article with `retire_article`.
- A stale `depends_on` link: repoint or drop it (`edit_article`'s `add_links` and `remove_links` for
  an article; a `restated` supersession with new `links` for a fact).

**Advisory.** These may remain when the evidence cannot resolve them: `contested` records and
records flagged `needs review` only because of them; world-bound records whose `lineages` hold
several labels or `null`; and `unfiled` facts. Resolve a contradiction only with evidence, by a
`corrected` supersession, `narrow_fact` (splitting a claim by a declared axis or by
`"binds": ["world"]` when each side holds under a different condition) or `retire_fact`.

**Filing rule.** File every current unbound fact in at least one current article. File a
world-bound fact once an article bound to its world exists. Use one article per subject, choosing
subjects from the evidence. Each article has a concise title, a lead of one or two useful sentences,
body claims that cite current facts, and links to related records. Prefer surgical `edit_article`
changes (`add_claims`, `replace_claims`, `set_lead`) to rewriting a body with `revise_article`.
Split and merge articles by adding the new ones and retiring or editing their predecessors in the
same submission, and repair the citations and links that pointed at them. No fixed categories or
size cap apply.

**Other repairs.** Merge repeated claims with a `restated` `supersede_fact` (the replaced facts must
share one scope and `when`), then repair their citing articles. Make subjects consistent in the
same way. Retire a world-bound fact that stopped holding with `retire_fact` as `ended`, citing frames
from its own world that show the change. Use `retag`, once per submission, to make tags consistent
with the brief's tag list and its nearest-tag pairs.

Use the `curator-submission/2` operations and `curator-fact/5` shapes in the curator instructions.
Several ordered submissions may repair the store step by step. Run `validate_submission` on each
before `finish`: it reports the gate's diagnostics, including any stale citation a batch would add.
Leave a draft for work that lacks evidence.
