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

### Generality and the Bitter Lesson

Targeted cross-check on 2026-10-21: Richard Sutton's 2019
[The Bitter Lesson](http://www.incompleteideas.net/IncIdeas/BitterLesson.html),
both pages read from the [university-hosted copy](https://www.cs.utexas.edu/~eunsol/courses/data/bitter_lesson.pdf)
after the original site failed to load. Sutton argues from historical AI examples
for methods that benefit from growing computation, especially search and learning,
and cautions against substituting researchers' domain knowledge for discovery.
This is an influential argument, not a CDDA experiment, a current model benchmark
or proof that any proposed memory architecture learns effectively.

Our application is P-GENERALITY, enforced through S-ARCH/S-CODE and the existing
C-REVIEW/C-PORTABLE lanes. Preserve ordinary visible input as the foundation;
semantic shortcuts and procedure memory remain scoped, revisable aids. A new or
changed menu should not require adding a handler merely to let the player try a
key. Separate transport/ownership/delivery invariants from fallible interpretations
of game behavior. Evaluate unseen interface variants and behavior that changes
after earlier success, without changing the player substrate for each variant.
Retain attempts, current observations and explicit uncertainty automatically so
the player and advisory path can revise their hypotheses. No additional model,
training service or framework follows automatically from the essay.

The [organic-discovery crosswalk](design/organic-discovery.md#cross-check-against-prior-work),
[mixed-input design](design/mixed-input.md) and
[procedure/reflection boundary](design/procedure-learning.md) already point in
this direction. Actual campaign002 shows a gap between that intent and execution:
a zero-input representation error revoked ordinary input. #190 fixes that known
case; #176 owns the broader whole-loop qualification. Changed labels/layouts or
behavior after an arbitrary f(T) are nonstationary conditions, not permission to
reuse stale coordinates or silently replay an uncertain input. Neither passing
finite perturbation tests nor one seven-day campaign guarantees success against
an unrestricted adversary. Further concrete gaps belong in the existing backlog.

The [October 19 architecture assessment](research-memory-architecture.md) checks the
implemented paths against the actual seven-day run and revisits recent primary
memory evidence. It proposes player-owned mission integration, durable campaign
views and semantic revision; it does not change current execution authority.

The [cross-disciplinary representation study](research-memory-representations.md)
compares mathematical, database, control and statistical views of memory. Its
[simulation protocol](design/memory-study-protocol.md) was independently reviewed
before implementation, with documented clarifications frozen before final
collection. The [results and reproduction](acceptance/2026-10-18-memory-representations.md)
support a simple replay/query design basis and a bounded visible-trace benchmark;
they do not establish native efficacy or select a new live memory architecture.

The [memory and continuous-learning review](research-memory-learning.md) covers
episode memory, revisable beliefs, retrieval, forgetting, evaluated improvement
and mathematical foundations through 2026-10-18, including October 14–15
preprints. It is a discussion proposal; current task memory and action authority
remain defined by the protocol.

The [tiered-gameplay research proposal](research-tiered-gameplay.md) reviews
hierarchical execution, routing, memory and recovery through 2026-10-17, including
October revisions. It is a discussion proposal, not current runtime behavior.

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

## Reuse candidates rechecked — 2026-10-17

The earlier bare names did not preserve enough provenance to identify precisely
what was inspected. This comparison replaces that claim with newly checked public
repositories at exact revisions; it does not retroactively identify the earlier
unnamed sources. Commit dates below come from GitHub commit metadata.

| Candidate / inspected revision | Primary evidence read | Consequence and limit |
| --- | --- | --- |
| [rekon307/CDDAi, 8561510](https://github.com/rekon307/CDDAi/tree/85615103d7b43fec5d04a33ac01828c1bc97dba2), 2026-01-04 | [Terminal controller](https://github.com/rekon307/CDDAi/blob/85615103d7b43fec5d04a33ac01828c1bc97dba2/src/cddai/execution/terminal_controller.py) uses pexpect, a 24×80 terminal and key sequences. [JSON reader](https://github.com/rekon307/CDDAi/blob/85615103d7b43fec5d04a33ac01828c1bc97dba2/src/cddai/perception/json_reader.py) parses save JSON and chooses the newest matching save; missing fields receive defaults. | These are concrete terminal/save dependencies, not measured failure rates. Adopting this perception path would conflict with our rendered, player-visible observation contract. It is a design reference, not a ready replacement. |
| [yellowgg2/cdda-web, 7c7444b](https://github.com/yellowgg2/cdda-web/tree/7c7444bb004b58f9078b13a818ad3221f4c0c3bd), 2022-12-13 | Pinned README describes an Emscripten/WebAssembly port based on 0.F-3 and its build commands. | Establishes historical browser feasibility; does not establish compatibility or maintenance for our pinned 0.I-1 engine. |
| [nornagon/play-cdda, 706f481](https://github.com/nornagon/play-cdda/tree/706f481ffa81141766e1c039bf2085ead889d85d), 2026-10-09 | Pinned README describes stable/prerelease/experimental channels, immutable bundles, atomic channel updates, Emscripten 6.0.8, SDL2-era stable patches and SDL3 experimental builds. | A recently updated browser-delivery candidate; it must not be called abandoned. The README documents publishing, not our observation/command-authority API. No local browser build or comparative benchmark was executed. |

Reassessment: native remains the implemented choice for a single visible local
game with validated input/observation/recovery boundaries. Browser delivery is a
credible alternative, not an obsolete curiosity. Revisit it for browser-first
sharing, multi-host deployment or excessive native patch cost, and directly test
input authority, persistence, setup, rendering and upgrade burden before choosing.
This is a requirements and integration-cost inference, not measured native speed
superiority. The [platform decision](decisions/001-native-platform.md) records the
broader alternatives. Reusing official Tiles/SDL and established controls avoids
building a new renderer or general policy engine; our bounded bridge fills the
verified integration gap, without claiming no reusable API exists anywhere.
