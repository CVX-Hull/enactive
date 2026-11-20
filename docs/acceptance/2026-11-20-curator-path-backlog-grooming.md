---
owner: lead
status: historical
kind: review
date: '2026-11-20'
scope: 'Backlog grooming after the paired replay: what the memory studies support, the order of the curator work the owner chose, and the reconciliation of issues and the Project'
---

# Backlog grooming for the curator path (20 November 2026)

## At a glance

The grooming reorders the curator's work around one finding. The curator can store only
facts scoped to the game, and that kind of knowledge showed no benefit in the withholding
study. The one positive signal, in two small studies, is for a fact about one world: an
earlier sighting, stated in a sentence, changed what the player proposed every time. The
store has no place for such a fact, and nothing in a trace says which world a frame came
from.

The owner chose "world memory first", left belief out of the fact store, and parked the
procedures line behind one design brief. Nine issues were registered and three are Ready:
the search for a second scoreable packet
([#831](https://github.com/CVX-Hull/enactive/issues/831)), the fact store's field table
([#832](https://github.com/CVX-Hull/enactive/issues/832)) and the live curator
integration brief ([#836](https://github.com/CVX-Hull/enactive/issues/836)). All three
are documents at $0. No study, run, spend or later phase was adopted. This is queue
selection and registration, not implementation.

The source baseline is `15cde02808c2193a88f275557730e89345e5b455`. Before: 32 open issues
and 336 cards, 304 Done and 32 Backlog, nothing Ready. After: **39 open issues and 344
cards: 305 Done, 36 Backlog and three Ready.** Each open issue has one card.
[Paired replay #829](2026-11-20-malvern-trunk-paired-replay-829.md) · [Withholding study](2026-11-14-withholding-study.md) · [Previous grooming](2026-11-19-coding-agent-lead-backlog-grooming.md) · [ADR 009](../decisions/009-curated-player.md)

## Method

Five clean-context agents read in parallel, each with a written brief and read-only
access: one over the dated records about memory; one over the curator's code, contracts
and designs; one over the programs, monitor and practice line; one auditing every open
issue against [work items](../workflows/work-items.md) from a snapshot; one listing local
state for cleanup. Two more drafted the new descriptions and the corrected ones. The lead
checked the claims the plan rests on against code and records before using them, asked
the owner four questions, and made every change to GitHub through REST. The snapshots,
the agents' reports and the drafts are sealed as evidence.

Two agents reached their turn limit before reporting and were resumed with an instruction
to write from what they had read. Their later sections are thinner, as the limits say.

## What the studies support

Each line names its record. "Not established" lines matter as much as the others.

| Statement | Status | Record |
| --- | --- | --- |
| Delivered knowledge reaches the player and is acted on: in line with a delivered lead in 611 of 724 windows, model-judged | Established | [Withholding study](2026-11-14-withholding-study.md) |
| That knowledge improves play | Not established: the frozen primary result was null | [Withholding study](2026-11-14-withholding-study.md) |
| One sentence about an earlier sighting in the same world changes the proposed check | Established in two small studies: both fishing proposals in #755; four of four against none of four in #829, at two context sizes | [#755](2026-11-18-delayed-observation-cueing-755.md), [#829](2026-11-20-malvern-trunk-paired-replay-829.md) |
| That the changed proposal is a better decision | Not established: "A shift is not a benefit" | [#829](2026-11-20-malvern-trunk-paired-replay-829.md) |
| An ordinary lookup is cheap: one or two calls inside a 5 to 11 second turn | Established | [#804](2026-11-19-lookup-effort-at-retained-resource-choices-804.md) |
| A curator forming knowledge during play: its lag, cost and uptake | Not measured: the study used a fixed store and no curator runs during play | [Withholding follow-up](2026-11-16-withholding-follow-up-and-grooming.md), [curator component](../components/curator.md) |
| Any effect across worlds | Not established: each study is one world or one lineage | [#755](2026-11-18-delayed-observation-cueing-755.md), [#829](2026-11-20-malvern-trunk-paired-replay-829.md) |
| Stuck or looping play that a monitor would catch | Not found in sealed play | [Process measures](2026-11-14-process-measures.md) |

Three facts about the code, each checked by the lead:

- A fact's scope must hold a game and nothing else (`harness/curator/gate.py`, the scope
  check), and the trace projection, the window code and the gate mention no world or
  lineage.
- The curator reads only sealed traces: `harness/trace/stores.py` refuses a store with an
  un-checkpointed write-ahead log. The [curator component](../components/curator.md) page
  says sessions triggered during live play are not implemented.
- No program runtime exists (`harness/player/programs.py` is gone), and the curator's
  gate refuses any program or test content in a snapshot.

Runs also ended for reasons other than play: a stalled stream (#794), a provider refusal
during backoff (#803), unknown input delivery at the opening menu (#799), and short
horizons in most starts. Ordinary access made a real gap rare, which is why acquisitions
kept producing controls.

## The owner's decisions

All four are rows in the [decision log](../decisions/owner-decisions.md) dated
20 November 2026.

1. **World memory first.** The curator's memory work starts with facts about one world.
   Belief calculus and procedures wait.
2. **No belief value in the fact store.** Facts carry source links and supersession. A
   belief model, if the comparison under #677 later supports one, is a second migration
   with its own justification. This is what had kept #457 marked blocked with no open
   blocker.
3. **Procedures: one brief, the rest parked.** The bounded program interface brief that
   ADR 009 names is registered. The programs and monitor phase and the practice instance
   stay in Backlog, revisited when the field table is merged.
4. **Housekeeping.** #808 closed with its last acceptance point dropped; #42 closed as not
   planned; old files in the temporary directory removed. The owner did not choose to
   close #336, which stays open.

## The plan and its order

#457 (fact store) and #664 (live curator updates) were each too large for one leaf. Each
is now an outcome with bounded leaves; parts that cannot start yet are named in the
parent's description and not registered.

| Issue | What it is | Status | Starts after |
| --- | --- | --- | --- |
| #831 | Search the retained worlds other than Malvern for a second packet that can carry the paired replay | Ready | nothing |
| #832 | The one field table for a fact and a type: asserter, how known, time, world and lineage scope, type identity; no belief | Ready | nothing |
| #836 | The live curator integration design and a $0 price proposal for one bounded run | Ready | nothing |
| #833 | Type usage, unused-type flags and nearest types in the curator's brief; no schema change | Backlog | nothing; held back by capacity |
| #834 | A world and lineage identity on a cited frame that the gate can read | Backlog | #832 |
| #835 | The single migration of the fact and type contract with every reader | Backlog | #832, #834 |
| #837 | A growing trace made readable under the same projection | Backlog | #836 |
| #838 | A newer delivered-knowledge version reaching a running actor | Backlog | #836, #835 |
| #839 | The bounded program interface brief ADR 009 names | Backlog | #832 |

**Why this order.** #832 is the gate on everything in the store: the migration rule
allows one migration of a shared contract, so the fields must be settled once on paper.
#836 answers the largest undesigned question for live curation, how a trace that is still
being written becomes readable. #831 is the next step the paired replay's design set.

**Shared files, so not in parallel.**

- `docs/design/curator-session.md` belongs to #832. #836 writes a new design page and
  does not edit it.
- `harness/curator/gate.py` is touched by #835 and later by the program leaves #465, #468
  and #469.
- The delivered-knowledge and host input contracts change in #838 and in the later
  ontology card. They move as one migration, after #835, not two.
- `harness/viewer/` and `web/app/` are shared by #464, #471 and #336.
- `harness/player/programs.py`, to be created, is shared by #465, #466, #467 and #469.

**Shared test machinery to reuse, all existing:** the synthetic sealed sessions in
`tests/curator_trace.py`; the local stand-in in `tests/curator_stand_in.py`, which runs a
curator session end to end at $0; `tools/knowledge_export.py` with its empty
delivered-knowledge fixture; the player host's scripted scenarios; `tests/spectator_replay.py`;
the belief replay cases; and the lag simulation in `tools.memory_screen_checks`. The
program leaves should share one recorded-segment fixture and one replay cache keyed by an
exact content digest.

**Capacity.** The three Ready leaves are documents the lead writes, with no worker. #831
and #836 touch different pages from #832 and can proceed together; each still gets its one
review.

## Changes made

| Change | Issues |
| --- | --- |
| Registered, with a card each | #831 to #839 |
| Made an outcome, with Horizon set and Priority cleared | #457 (Now), #664 (Next) |
| Description replaced whole | #136, #177, #387, #445, #457, #465, #664, #666, #677, #681 |
| `blocked` label removed, no open blocker | #457, #677, #681 |
| Dependency edges to closed issues removed: 41 edges | #25, #42, #143, #145, #164, #177, #309, #384, #457, #464, #465, #664, #677, #681 |
| Edge #664 on #457 replaced by leaf edges | #838 on #835 |
| Closed as complete, card Done | #808 |
| Closed as not planned, card removed | #42 |

Left as they were: the edges of #464, #465 and #177 on the whole of #457. ADR 009 says to
keep that blocker until a bounded brief freezes the interface choices; #839 is that brief.
After the changes the open dependency graph has no edge to a closed issue and is acyclic.

## Cleanup

The checkout was already clean before the grooming: only `main`, no worktree, stash or
stray process, no open pull request, five routine check logs, and the evidence store
consistent with its manifests. With the owner's approval, six old project files and two
stale tool folders holding dead sockets were removed from the temporary directory. They
were outside the project and were not evidence.

## Limits

- This record selects and registers work. It measures nothing.
- The evidence table rests on the records' own summaries and limits, read by an agent and
  spot-checked by the lead, not on raw evidence.
- The descriptions of #831 and #832 were checked against the repository in detail. #836
  was spot-checked. #833, #834, #835, #837, #838 and #839 are shorter and say "paths to
  confirm when the leaf is made Ready" where a path was not verified.
- Whether any retained trace already carries a world identity was not determined. #832
  and #834 own that question.
- The signs of recurring menu routines come from one agent's count over two sealed
  lineages and were not rechecked. They are weak support for programs and none for a
  monitor.
- Out-of-date sentences found and not fixed here, because no change in this record owns
  their pages: `docs/design/cadence-plan.md` still describes the memory phase as not
  adopted, and ADR 009 cites a file that no longer exists. #832 owns the corrections in
  the curator session and player context designs.
- #465's description still depends on the whole of #457, as ADR 009 requires for now.
- One agent copied sealed session databases into the scratch folder to count repeated
  inputs. The lead first sealed that folder whole, then, before anything was committed,
  removed that seal and sealed only the snapshots, reports and drafts. The copies were
  deleted; the originals are untouched in their own sealed studies.

## Evidence

Sealed as `curator-path-backlog-grooming` under `.runtime/evidence/`: the before and after
snapshots of open issues, the parent and dependency graph, Project fields and card counts;
every open issue's description before the change; the five agents' reports; and the
drafted and rewritten descriptions with the list of each change and its source.
