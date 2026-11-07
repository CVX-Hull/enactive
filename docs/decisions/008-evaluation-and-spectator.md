---
owner: lead
review_trigger: Evaluator placement, the evaluation-record or spectator-view contracts, an adopted dependency, or a second game binding
status: historical
date: '2026-11-07'
scope: Accepted direction for the run evaluator, its game binding and the redesigned spectator (#383); not delivered runtime support
---

# ADR 008 — Offline evaluator, game binding and a split spectator

The owner selected this direction on 6 November 2026 in
[#383](https://github.com/CVX-Hull/enactive/issues/383). It changes four existing
constraints, named below. It does not change the computer-control boundary of
[ADR006](006-computer-control-boundary.md): the harness still exposes basic
observation and control only, and nothing here gates input.

## Context

The [development loop](../development-runs.md) measured run outcomes by hand from
frames. A read-only retrospective of its 30 runs (#383) found four problems:
- Most game time came from single long activities.
- The survival gate could not separate arms at the run counts we can afford.
- The player's intent and its component use (memory, programs, handoff) were
  invisible.
- Cost was dominated by cache rewrites after image eviction.

The long-horizon arm ([#382](https://github.com/CVX-Hull/enactive/issues/382)) needs
game time, continuity and needs read automatically across chained admissions. It
also needs a spectator that shows them while the run moves. That is the demonstrated
gap that [research-context-engineering](../research-context-engineering.md) requires
before telemetry tooling is added.

## Decision

1. **Evaluator.** An offline evaluator derives interpretive records from a run's
   recorded data:
   - the computer session store;
   - the host traces;
   - the player memory store;
   - the original frames.

   It is exposed as `tools/evaluate.py` subcommands. Its package is
   `harness/evaluation`, outside `harness/computer` and `harness/player`.
2. **Two layers.** A game-neutral **core** owns:
   - the record envelope, three clocks, provenance, confidence and abstention;
   - metric definitions;
   - survival statistics;
   - lineage stitching across chained admissions.

   A **CDDA binding** owns:
   - the screen readers;
   - the milestone ladder;
   - the long-activity threshold;
   - the vocabulary.

   The core imports no binding code. The binding interface is only what CDDA needs.
   It becomes a formal protocol when a representative second game is named, as ADR006
   already requires before any portability claim.
3. **Records are versioned and additive.**
   - Each evaluation writes a new [`evaluation-record/1`](../contracts/evaluation.md)
     store, keyed by run and by core and binding versions.
   - Hand-scored rows in the development-run tables are never rewritten.
   - Re-scoring a run under a new version adds a store beside the old one.
   - The derived store is regenerable, so a version change re-scores the archive
     instead of keeping two formats.
4. **Nothing reaches the player.** Evaluator output enters no player context, memory,
   prompt, guide or tool result, and it gates no input. Import-linter contracts forbid
   the player, player adapters and computer packages from importing
   `harness.evaluation`.
5. **The spectator is split in two.**
   - **Control path.** The supervised gateway keeps Pause and the attention checks
     with their current independence and safety checks. It also serves the page's
     origin and static files. Its exit still ends supervision, so it stays minimal.
   - **Viewer.** A separate read-only process outside supervision runs the evaluator
     incrementally over the live run's records and serves the
     [`spectator-view/1`](../contracts/evaluation.md#spectator-view) API. The gateway
     forwards view requests with a short timeout and a size cap.
   - **Failure.** A viewer failure shows "viewer unavailable" on the page. It never
     ends, pauses or gates a run, and Pause never depends on it.
6. **The old spectator paths are removed together**, per S-MIGRATION:
   - the Watch/Timeline/Analysis page;
   - the activity projection;
   - the recorded investigation export and its contract.

   The redesigned page is built only after the owner approves the UX design.
7. **Adopt, don't reinvent.** Each capability was assessed on fit, license,
   maintenance, security, offline use and size. The adopted set is below. Custom code
   is limited to the recorded gaps.

## Dependency assessment

Library facts were read from npm, PyPI and project repositories on 6 November 2026.
Every adopted package is pinned, installed project-locally and recorded with its
license.

| Capability | Adopted | Considered and not adopted | Reason |
| --- | --- | --- | --- |
| UI components | **Preact + htm**, vendored ES modules, no build step | Vanilla JS; Lit (Shadow DOM complicates browser tests); Svelte, React + Vite, Solid (build chain); Panel, Dash, Streamlit, NiceGUI, Shiny (heavy server models that still need custom JS for the timeline) | Small (MIT/Apache-2.0), no build tooling for one maintainer, ordinary DOM for browser tests |
| Charts and timeline | **Apache ECharts** (Apache-2.0), vendored | uPlot plus a custom canvas timeline; Observable Plot; Vega-Lite; Chart.js; vis-timeline; Plotly | One library covers lane timelines (custom series), zoom and brushing, step curves with bands, sparklines and an accessibility description, so no timeline renderer is written. The mockup prototyped the timeline and survival curves with it. |
| Viewer server | **Starlette + uvicorn** (BSD-3), pinned directly | stdlib `http.server` with hand-written server-sent events; sse-starlette | Already present transitively; static files, streaming and a test client built in |
| Survival statistics | **numpy + scipy** (BSD) | lifelines (pulls pandas, matplotlib, autograd); statsmodels (adds pandas); scikit-survival (GPL-3.0) | `scipy.stats.ecdf` with censored data, `logrank` and `bootstrap`. Restricted mean survival time is about ten lines (the integral of the Kaplan–Meier step function), checked once against lifelines in a throwaway environment. |
| Storage | **SQLite** (stdlib) | DuckDB, pyarrow, Polars, pandas | About two million rows at the expected scale; the project already relies on SQLite transactions |
| Screen reading | **Glyph atlas on Pillow** (custom, recorded gap) | OpenCV matchTemplate; Apple Vision through pyobjc; RapidOCR; Tesseract (system binary); EasyOCR | A fixed bitmap font makes exact glyph lookup lossless and deterministic at about 1 ms per line. Neural OCR is tuned for scene text, is not deterministic across OS versions and costs tens of milliseconds. Colour bars need pixel classes, which OCR does not provide. The atlas is data, so another game re-learns it. |
| Trace browsing | **None**; the spectator timeline shows requests and tools | Phoenix (Elastic-2.0, 53 dependencies, analytics on by default); Langfuse; Inspect view; MLflow; Weave; Jaeger; Perfetto UI; otel-desktop-viewer; Docent | No tool renders frames or game lanes. A Chrome trace-event export for Perfetto stays an optional later addition. |

Custom scope and retirement triggers:
- **Glyph reader.**
  - Replace it if a game binding needs free text the atlas cannot cover.
  - Then evaluate Apple Vision as an atlas-miss fallback.
- **Restricted mean.**
  - Replace it if scipy gains the function.
- **Viewer proxy in the gateway.**
  - Bounded forwarding only.
  - Remove it if the viewer moves to the gateway's origin some other way.

## Constraints this changes

| Constraint | Change |
| --- | --- |
| ADR006: "no new per-action critic, approval, scheduler or separate metrics service" | A separate read-only viewer process and an offline evaluator are added. They are not a per-action critic, approve nothing and schedule nothing. They read records after the fact and gate no input. |
| [Observer operations](../components/observer-operations.md): "No collector, automatic diagnosis, annotation store or game semantics is added" | The viewer adds interpretive game readings and display-only alerts, each labelled with its source and confidence. There is still no annotation store: labels are deferred. |
| `tools/evaluate.py`: "no gameplay verdict" | Evaluator subcommands produce interpretive records and metrics. They still accept no run or claim. Acceptance stays with frames, review and the issue's decision rule. |
| [Research context](../research-context-engineering.md): "no separate telemetry framework without a demonstrated gap" | The gap is demonstrated in #383. The framework is a package and subcommands over existing records, not a telemetry pipeline or a new store of raw events. |

## Consequences and limits

- Game-specific interpretation now exists outside the playing system for evaluation
  only. It is fallible, versioned and validated on held-out frames before its numbers
  are used.
- The binding validation is CDDA on one Mac. It is not a portability claim.
- The viewer adds a second local process during supervised runs. Its failure is
  isolated by design and tested by stopping it during a replay.
- Deferred until after #382, each in its own issue:
  - intent visibility;
  - a label store;
  - model judges;
  - a cross-run memory channel;
  - a scenario bank.
- Revisit when:
  - a second game is named;
  - an adopted dependency is abandoned or relicensed;
  - the viewer's isolation is shown to fail;
  - evaluator readings disagree with held-out labels beyond the contract's accuracy floors.
