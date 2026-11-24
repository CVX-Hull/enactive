# Grooming instructions

Read `knowledge/current-facts.jsonl` and `knowledge/ontology/types.json`. Use the last admission's
cited frames and each actor's first and last framed operations in `trace/` to check changes.
Treat facts as hypotheses. Keep what a later actor could use and preserve uncertainty and conditions.

Reorganize the store between admissions. Merge repeated claims with `supersede_fact` within
the same scope level and, for world facts, within the same world. Retire stale world facts with
`retire_fact`. Check for changes or rollbacks in the boundary observations. Cite a frame from
the fact's own world and explain why the fact no longer applies. You may also cite a frame
already cited by the retired world fact, even if it precedes this window. Use current
observations when they show the change. Make subject names consistent through replacements. A replacement
may keep citations of the facts it supersedes, even when those frames precede this window.
Software uses their recorded provenance for `seen` and `scope.world`. Submit `known`
and the `scope.game` and `scope.level` fields on each replacement.

Merge, split, rename or deprecate types with `revise_types`. Give each resulting
`curator-type/2` definition its `identity` and `reason`. When rewriting an existing
name (if deprecating and re-adding a name, list `revise_types` before `add_type`),
assign all facts that were current under that name at the base version and stay current,
even if their type name stays the same. Publish each revision in a new version.

File every current game fact in at least one article. World facts stand alone. Use one article per subject, choosing subjects
from the evidence. Write or revise a concise title, a lead of one or two useful sentences, body
claims that cite current game facts, and links to related articles by their current titles. Keep
article prose true in any world. Split
and merge articles by adding replacements and retiring or revising their predecessors together;
repair incoming links and citations in the same submission. No fixed categories or hard size cap
apply. The gate checks references and complete filing, never the meaning of your prose.

Use the `curator-fact/4` submission shapes in the curator instructions. Software writes
`seen` and `last_confirmed` to order sightings. A later actor should
check knowledge cheaply before relying on it. Leave a draft for work that lacks evidence.
