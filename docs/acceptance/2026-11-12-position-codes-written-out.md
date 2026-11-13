---
owner: lead
status: historical
date: '2026-11-12'
scope: 'Keys of ADR 009, of three dated decision records and of the held-out lineages written out as what they refer to wherever a current page or code comment used them outside the page that defines them; the mapping from each key to its phrase; one data file and three unused parameters retired (#556)'
---

# Position codes written out, 12 November 2026

The [naming standard](../standards/documentation.md#names) lets a page cite a key it
defines itself and asks every other page to write what the key refers to and link the
defining page. This record lists where such keys were used outside their page, what each
was replaced with, and what was left. No identifier, stored value, schema ID, test ID or
amount changed.

## What was written out

Three kinds of key:

- **[ADR 009](../decisions/009-curated-player.md)'s keys**: its owner-direction keys
  (`D1`–`D18`), its research-area keys (`R1`–`R14`) and its numbered open owner decisions.
  The ADR keeps them, because it defines them.
- **Decision keys of three dated records**, used in
  [operator permissions](../operator-permissions.md).
- **Held-out lineage codes** (`lh1`–`lh4`) used as names in prose and comments. Each
  first use now says what the lineage is and keeps the stored identifier in code
  formatting.

Occurrences replaced, by file:

| File | Owner-direction keys | Research-area keys | Open-decision numbers | Other |
| --- | --- | --- | --- | --- |
| `docs/research-curated-programs.md` | 1 | 54 | | 2 lineage-code uses |
| `docs/research-curated-memory.md` | | 32 | 3 | |
| `docs/research.md` | | 6 | 1 | |
| `docs/research-curator-sandbox.md` | | 2 | 1 | |
| `docs/design/trace-workbench.md` | 3 | 1 | | |
| `docs/design/curator-session.md` | 3 | | 1 | |
| `docs/operations/curator-hosts.md` | | | 1 | 1 lineage-code use |
| `docs/components/observer-operations.md` | 1 | | | |
| `docs/contracts/evaluation.md` | 1 | | | |
| `docs/design/probe-protocol.md` | | | | 1 lineage-code use |
| `docs/operator-permissions.md` | | | | 4 decision keys of dated records |
| `harness/viewer/frame.py` | 2 | | | |
| `web/app/frame.js` | 2 | | | |
| `harness/curator/containers.py`, `gate.py`, `knowledge.py`, `session.py` | 1 each | | | |
| `harness/trace/sidecar.py` | 1 | | | |
| `tests/test_viewer_frame.py` | 1 | | | |
| `tools/curator_host/providers.py` | | | 1 | |
| `tools/curator_host/shadow.py` | | | 1 | 1 lineage-code use |
| `tests/test_trace_projection.py` | | | | 1 lineage-code use |

In the three research pages the section headings lost their key prefix, so their
fragments changed (for example `#r5-program-induction-and-libraries` became
`#program-induction-and-libraries`). No page linked the old fragments.

## Mapping

For a reader of older text. The phrase is the one used in current pages; code comments
use a shorter form of it. Keys not listed were not used outside the ADR.

| ADR 009 key | Written as | ADR section linked |
| --- | --- | --- |
| D6 | ADR 009's direction for a curator workbench | [Workbench](../decisions/009-curated-player.md#workbench-d6) |
| D10 | The owner's direction requiring intent and expectation emissions | [Actor emissions](../decisions/009-curated-player.md#actor-emissions-d10) |
| D14 | ADR 009's direction framing the curator as a coding agent | [The curator as a coding agent](../decisions/009-curated-player.md#the-curator-as-a-coding-agent-d14) |
| D16 | ADR 009's direction of one knowledge repository per game | [Knowledge repository](../decisions/009-curated-player.md#knowledge-repository-d16) |
| D17 | ADR 009's direction that drafts be managed containers | [Containers](../decisions/009-curated-player.md#containers-d17) |
| D18 | ADR 009's spectator direction (the spectator redesign) | [Spectator](../decisions/009-curated-player.md#spectator-d18) |
| R1 | The research area on agent memory | [Research agenda](../decisions/009-curated-player.md#research-agenda) |
| R2 | The research area on concurrent consolidation | Research agenda |
| R3 | The research area on belief under conflict | Research agenda; [Belief and disagreement](../decisions/009-curated-player.md#belief-and-disagreement) |
| R4 | The research area on ontology induction and evaluation | Research agenda; [Fitting and evaluating the ontology](../decisions/009-curated-player.md#fitting-and-evaluating-the-ontology-d4) |
| R5 | The research area on program induction and libraries | Research agenda |
| R6 | The research area on programs with model calls | Research agenda |
| R7 | The research area on supervision and interruption | Research agenda |
| R8 | The research area on novelty and anomaly detection | Research agenda |
| R9 | The research area on expectations and prediction error | Research agenda |
| R10 | The research area on offline evaluation of policies | Research agenda |
| R11 | The research area on practice environments | Research agenda |
| R12 | The research area on study design | Research agenda |
| R13 | The research area on agent workspaces and verification gates | Research agenda |
| R14 | The research area on oversight interfaces | Research agenda |
| Open decision 2 | ADR 009's owner decision on the curator's spend cap and model | [Open owner decisions](../decisions/009-curated-player.md#open-owner-decisions) |
| Open decision 4 | ADR 009's open decision on the belief model | Open owner decisions |
| Open decision 5 | ADR 009's owner decision on where the knowledge repository lives | Open owner decisions |
| Open decision 6 | ADR 009's owner decision on the sandbox mechanism | Open owner decisions |

| Key in operator permissions | Record | Written as |
| --- | --- | --- |
| Decision D2 | [Development loop](2026-11-06-development-loop.md) | The owner's decision of 5 November 2026 on the loop's new spend |
| Decision D1 | [Long-horizon arm](2026-11-07-long-horizon-382.md) | The owner's decision of 7 November 2026 on the arm's new envelope |
| Decisions E1 and F2 | [Seven-day lineage](2026-11-07-seven-day-397.md) | The owner's decisions of 7 November 2026: a $150 envelope for one lineage, then its raise to $300 after admission 4 |

| Lineage code | Written as |
| --- | --- |
| `lh1`–`lh3` | #382's three held-out lineages, stored as `lh1`–`lh3` |
| `lh4` | The fourth held-out lineage (#522), stored as `lh4` |

## Two leftovers retired

- **The inter-rater matching file.** `data/evaluation/probes/inter-rater-matching.json`
  had no code or test reader; only the
  [probe baseline record](2026-11-08-probe-baseline-449.md) used it. It moved unchanged
  to [that record's assets](assets/probe-baseline-449/inter-rater-matching.json), and the
  record's link points there.
- **Three unused parameters.** `run_one` in `tools/curator_host/shadow.py` took
  `memory_until`, `expected_brief_sha256` and `expected_trace_manifest_sha256`, which no
  caller or test had passed since the study tooling was retired. They were removed.
  `run_session` in `harness/curator/session.py` lost `memory_until` for the same reason.

## Left, and why

- **Two notes in tracked data** still carry an ADR 009 key.
  `data/evaluation/probes/397/episodes.json` says "ADR 009 D18" in a `note` that the
  spectator frame serves. `data/curator/shadow-arms.json` says "ADR 009 open decision 2"
  in a `note`, and the curator memory study's frozen arms file records that file's hash.
  Both are data values, so they were reported to the lead and not edited.
- **Historical pages** keep the labels of their time: the dated records, the change
  briefs, ADR 007, ADR 010, the two retired study protocols and the snapshot-diff cost
  measurement.
- **Stored identifiers** stay: lineage and run names in tests and recorded data, the
  example label in `schemas/dev-run.schema.json`, and the `#running-lh4` fragment of a
  historical page.
- **A page's own keys** stay: the research pages' source and observation lists. The
  curator sandbox page uses `L` keys for two of its own lists (local observations and
  low-severity review findings); that is inside one page and was left.
- **ADR 009's section fragments** such as `#spectator-d18` still contain a key, because
  the ADR's headings do. They are link destinations and the ADR was not edited.
- **Parameters that still have a user or lie outside this change.** `SessionConfig`
  keeps its two `expected_…` fields, which `tests/test_curator_session.py` exercises.
  `project` in `harness/trace/projection.py` keeps `memory_until`, which now has no
  caller; removing it is the lead's call.
