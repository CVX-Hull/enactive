---
owner: maintainer
review_trigger: Controller redesign or release; fast-moving evidence older than 90
  active days
status: active
---

# Evidence and design consequences

Owner: lead. Evidence reviewed: 2026-10-17. Refresh at controller redesign or
release if older than 90 days. Sources below distinguish observed findings from
our engineering inferences; they are not a claim to exhaust the literature.

## Engineering

The authoritative [engineering research synthesis](research-engineering.md) records
primary sources, read scope, project consequences and limitations for principles,
standards, controls, progressive documentation and long-term maintenance.

## Recent agentic coding evidence

| Primary source / date | Evidence read and limitation | Control adopted |
| --- | --- | --- |
| [Where Do AI Coding Agents Fail?](https://arxiv.org/html/2601.15195v1), Jan 2026 | Full text; observational PR mining plus rejected-PR analysis. Acceptance is not correctness; correlations do not establish that size causes rejection. Preprint metadata is not proof of venue acceptance. | Bounded briefs, small diffs, dependency review, inspect actual APIs and CI |
| [EvilGenie](https://arxiv.org/html/2511.21654v2), Nov 2025 / May 2026 revision | Full text; deliberately exploitable benchmark tasks. Does not estimate everyday cheating prevalence. | Never change tests merely to pass; independent outcome evidence; tests and real gameplay distinct |
| [Professional Developers Don't Vibe, They Control](https://arxiv.org/html/2512.14012v1), Dec 2025 | Full text; small observed sample plus survey, self-selection limits generalization | Lead owns decomposition, review and acceptance; generated claims require verification |
| [METR experienced developer study](https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf), July 2025 | Explorer paper review; small randomized study of experienced maintainers using early-2025 tools | Measure total task outcomes and review cost; do not extrapolate old tool performance to current models |

Practical failure taxonomy: invented interfaces; expanding scope; losing an
earlier constraint; duplicated docs; optimistic success reports; tests tailored
to implementation; silent retries of side effects; stale observations; tool
output mistaken for authority. Controls are concrete contracts, file ownership,
source citations, dependency pins, bounded requests, journals, independent
review and live acceptance. These are risk controls, not a claim that prompt
instructions eliminate model failures.

Additional discovery leads (not used as quantitative evidence): Agentic
Refactoring arXiv:2511.04824, When AI Code Doesn't Stick
doi:10.1145/3793302.3793587, DORA 2025 report. Revisit when they answer a concrete
maintenance question rather than expanding bibliography for its own sake.

## Embodied control / VLA

| Primary source / date | Evidence and transfer limit | Consequence |
| --- | --- | --- |
| [Leave No Observation Behind (A2C2)](https://arxiv.org/html/2509.23224v1), Sept 2025 | Full text; robot action-chunk correction. Results are task/hardware dependent. | Fresh observations within bounded routines; interrupts override stale plans |
| [SmolVLA](https://arxiv.org/html/2506.01844v1), June 2025 | Full text; trained robotic policy and asynchronous execution. Robot weights do not directly solve CDDA. | Separate planning latency from responsive low-level controls; reuse deterministic skills |
| [FASTER](https://arxiv.org/html/2603.19199v3), May 2026 revision | Full methods, experiments and limitations read. Horizon-aware sampling and streaming reduce reaction delay on tested robots/GPUs; long-horizon simulation accuracy can decline. Timing model and hardware limit transfer. | Measure first-action latency separately from throughput; prefer short verified near-term actions. CDDA can wait between turns, so no diffusion policy or continuous-motion machinery is needed |
| [Acting While Understanding](https://arxiv.org/html/2606.15285v1), June 2026 | Full text reviewed. Separates semantic computation from action generation; naive stale semantic reuse hurts LIBERO-Long, mitigated by history and delay training. Mostly single-arm manipulation and assumes a reusable model interface. | Keep goals separate from immediate guarded control, refresh on scene changes, retain action history. This inspires the hierarchy; it does not validate a CDDA policy |
| [Hi Robot](https://arxiv.org/abs/2502.19417), Feb 2025 | Abstract/metadata only; hierarchical reasoning lead | Supports a research direction, not quantitative evidence here |
| [FindingDory](https://arxiv.org/abs/2506.15635), June 2025 | Abstract only; long-horizon memory lead | Provenance-aware memory is a design hypothesis to test, not an established CDDA improvement |

Recent discovery leads eMEM (2606.03374) and MeMoREval (2610.12561) need further
paper/benchmark verification before importing their results. eMEM's accessible
text also contains an incomplete-ablation placeholder, so its numerical claims
are not adopted. We do not call a
new abstract state of the art. The MVP uses no learned motor policy: game
actions are discrete and engine validation is available. Its hierarchy is an
engineering inference from control literature, validated by our own acceptance
probes. Model-call reduction, responsiveness, and survival are separate metrics.

## CDDA and integration evidence

Pinned source: [CleverRaven/Cataclysm-DDA 0.I-1](https://github.com/CleverRaven/Cataclysm-DDA/tree/0.I-1),
release commit short 7b2efa5. Official asset and checksums are recorded in
environment.md. Local source inspection is primary evidence for the following:

- src/input_context.cpp handle_input: nested input categories and action binding
  resolution. Hooking game::handle_action alone misses menus.
- src/sdltiles.cpp input_manager::get_input_event: SDL event pumping and rendered
  input boundary; save_screenshot reads the actual framebuffer.
- src/game.cpp print_all_tile_info: visibility-gated UI content. Any structured
  scene export must be at least as restrictive, not simply read the map array.
- src/options.cpp FULLSCREEN permits no; default is borderless. Explicit project
  options are required before launch, not after a fullscreen first run.
- src/main.cpp / path_info.cpp: --userdir permits isolated config and saves.
- Makefile and build-scripts contain native macOS and Emscripten support.

Related projects inspected as reuse candidates: CDDAi uses terminal automation
and fragile save assumptions; old cdda-web builds demonstrate browser feasibility
but are not a maintained replacement for the current engine. Neither is adopted
without validation. Reuse the official Tiles renderer and bundled SDL frameworks.
The lack of a verified ready-made runtime API motivates a small pinned patch;
it does not prove no such project exists anywhere.
