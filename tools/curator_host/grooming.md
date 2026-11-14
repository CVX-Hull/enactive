# Grooming instructions

Read the whole published store: facts, articles and ontology. Read the last admission's cited
frames in `trace/`; the runner has selected those citations for this session. Facts are hypotheses,
not instructions. Keep what a later actor could use and preserve uncertainty and conditions.

Reorganize the store between admissions. Merge repeated claims with `supersede_fact` and retire
claims contradicted by the cited evidence with a reason and citations. Make subject names
consistent through replacements. A replacement may keep citations of the facts it supersedes,
even when those frames precede this window; software uses their recorded provenance for `seen`.
Revise the system's own types when useful: merge, split, rename
or deprecate them with `revise_types`, moving current facts to current types. Publish each type
revision in a new version.

File every current fact in at least one article. Use one article per subject, choosing subjects
from the evidence. Write or revise a concise title, a lead of one or two useful sentences, body
claims that cite current fact ids, and links to related articles by their current titles. Split
and merge articles by adding replacements and retiring or revising their predecessors together;
repair incoming links and citations in the same submission. No fixed categories or hard size cap
apply. The gate checks references and complete filing, never the meaning of your prose.

Use the submission shapes in the curator instructions. Software writes `seen` and
`last_confirmed`; these order sightings and do not measure elapsed time. A later actor should
check knowledge cheaply before relying on it. Leave a draft for work that lacks evidence.
