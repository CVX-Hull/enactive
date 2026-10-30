---
owner: lead
review_trigger: Spatial context/presentation changes, new contrary evidence or model/vision changes
status: active
---

# Spatial grounding, visual inspection and working state

Research cutoff: **30 October 2026**. This focused review informs
[#300](https://github.com/CVX-Hull/enactive/issues/300). It extends the
[context review](research-context-engineering.md), whose earlier source-bound
measurements are historical. Research is evidence for a candidate, not a guarantee
of better CDDA play or an instruction to add another model/service.

## Decision and scope

The local distinction matters: **recognizing a figure, tracking it across images,
and interpreting movement in a reference frame are different problems**. #298's
organic play and #300's retained diagnostic expose more than poor legibility.
Both diagnostic answers to one sequence treated a screen-centered avatar as not
travelling despite landmark-relative movement. Other answers misidentified a
figure or missed an explicit player-tile cue. Clinically directed questions mostly
preserved local-search limits; that does not establish organic calibration.

The first experiment tested a compact **player-owned spatial-state frame and
worked transition example** using the existing guide/context mechanism. Separate
inspection focus, actor identity support, landmark-relative position, established
effect and remaining uncertainty. A historical example demonstrates how display
position can stay fixed while landmark-relative position changes. It supplies no
current-world facts or prescribed action. Existing Work records remain optional;
no per-key narration, automatic state inference, critic or input gate is added.
This was our engineering hypothesis, not a reproduction of a paper's method.
The [retained assessment and organic play](acceptance/2026-10-30-spatial-grounding.md)
did not establish the proposed repair: the original frame error persisted, reserved
answers overstated displacement, and live play again made false outside claims.
The candidate was rejected and removed from current guidance. Research justified
testing a hypothesis; it did not predict its success.

The previously proposed optional crop/magnification API remains **unimplemented
and deferred**. It may be useful for a demonstrably unreadable detail, but the
current dominant transition error is not evidence of insufficient image resolution.
The same LLM would choose the crop, so erroneous region selection remains possible.
No second prototype is selected. Existing exact images, source recall and player
program views remain available.

## Method and access limits

Searches prioritized 2026/2025, then foundations, across arXiv, ACL Anthology,
CVF proceedings, publisher papers and official research pages/implementations.
The earlier context review supplies survey/foundational interface background.
Three independent read-only sweeps here covered spatial dynamics, visual inspection
and working-state/uncertainty. The lead checked decisive primary methods, experiments,
negative results and transfer assumptions. Abstract/project-page-only leads are
excluded from the main evidential claims; multiple versions of one paper are not
independent evidence. No exhaustive review, benchmark replication or SOTA ranking
is claimed.

Ten primary PDFs/HTMLs and extraction manifests are retained project-locally under
ignored `.runtime/iteration300/research/`. Extraction used installed `pdftotext`
and HTML fallback; tables/equations are flattened. The judgments below concern
methods and qualitative limits, not unverified table arithmetic. Full texts are
not republished, and the complete corpus may be unavailable in a fresh checkout.
The exact deployed checkpoint, tiled game graphics and screenshot/action interface
were not tested by these papers.

## Evidence and transfer

“Read” below means the named methods/evidence/limitations sections, rather than an
abstract or every appendix. Conference papers, publisher articles and recent
preprints carry different weight. Benchmark gains are not expected project gains.

| Primary source / reading scope | What it establishes, and what does not transfer |
| --- | --- |
| [CameraVLM: When Left Is Right?](https://arxiv.org/html/2610.17242v1), Chong Cheng et al., Oct2026 preprint; §3, §4 and limitations | Separates camera, subject/background flow and the query's reference frame. Follow shots can preserve subject screen position while the camera moves. Its improvement requires pose/flow supervision and model training; it is not a prompt-only fix. Borrow the diagnostic distinction, not its architecture or scores. |
| [CaMo](https://arxiv.org/html/2605.20165v1), Hsiang-Wei Huang et al., May2026 preprint; §§4–5, appendices G/H | Camera-motion narratives reveal weaknesses obscured by direct spatial QA. Evaluation uses a proxy reasoner and video segments; its remedy fine-tunes a VLM. Narrative QA does not establish precise geometry, global mapping or game-action competence. Faithful state evidence is worth testing separately from answer accuracy. |
| [Thinking in Space](https://arxiv.org/abs/2412.14171), Jihan Yang et al., CVPR2025 / July2025 v2; spatial-error, prompting and cognitive-map experiments | Separates relational reasoning and reference-frame transformation failures; generic longer reasoning and map prompting do not uniformly help. Indoor videos and annotated geometry differ from game screenshots. Do not assume more narration, a larger map or a generic reflection loop supplies the missing ability. |
| [Thinking outside the frame](https://doi.org/10.1007/s44267-026-00126-0), Yan Ke et al., *Visual Intelligence*, Aug2026; §§3–4 and discussion | Explicit entity/anchor identification and viewpoint-aware correction improve tested spatial QA relative to generic refinement. The method has generation/critique/refinement stages and uses model judging with a partial human audit; compactness/completeness tradeoffs vary by model. Borrow explicit reference framing as an untested low-cost hypothesis, not a mandatory critic or proven game remedy. |
| [RegionFocus](https://openaccess.thecvf.com/content/ICCV2025/html/Luo_Visual_Test-time_Scaling_for_GUI_Agent_Grounding_ICCV_2025_paper.html), Tiange Luo et al., ICCV2025; method, §4.3 and failure/runtime analysis | Focused regions and visual action landmarks help tested GUI grounding, but multiple proposals/aggregation add inference burden. Directly predicted regions underperform its fixed-box variant; off-screen targets and wrong focal points remain failures. A simple optional crop is not the same method, and GUI target localization does not establish avatar identity or world-motion reasoning. |
| [UI-Zoomer](https://arxiv.org/abs/2604.14113), Tang et al., Apr2026 preprint; §3 and experiments/ablations | Adaptive zoom combines multiple sampled boxes with token confidence; unconditional zoom can reduce accuracy and increase runtime. Those signals are not equivalent to the player's verbal confidence. This does not justify automatic cropping, numeric confidence thresholds or extra inference on every game action. |
| [Active-Look](https://aclanthology.org/2026.findings-acl.745.pdf), Yubo Jiang et al., Findings ACL2026; §§4–6 and limitations | Controlled tests expose local-detail/global-context tradeoffs and over-trust in mislocalized regions. Its system uses external grounding experts; its budget counts visual tokens rather than full system latency. Use the negative cases when evaluating presentation. Do not import detector-selected game semantics or claim that model-selected crops remove proposal errors. |
| [The Illusion of Visual Tool-Use](https://aclanthology.org/2026.findings-emnlp.728/), Zhiheng Wang et al., Findings EMNLP2026; §§3–5 and limitations | Separates calls with little observation-mediated effect from useful evidence used under poor call scheduling. Aggregate tool gains need not imply individual views helped. Its fine-grained audit requires counterfactual observations and model probabilities; ordinary API traces cannot reproduce that causal measurement. Tool use, source availability and correct output remain distinct evidence. |
| [FlashAdventure](https://aclanthology.org/2025.emnlp-main.1192/), Jaewoo Ahn et al., EMNLP2025; COAST method, failure analysis and limitations | Clue/observation tracking helps some planning and delayed-use tasks but does not fix the same backbone's perceptual failures. Evaluation uses manual milestones and an interacting verifier, with genre limits. Small clues fitting context did not require compaction in that study. Borrow observation-versus-belief/task distinctions, not its agents, oracle hints or claimed universal memory benefit. |

R-VLM's [two-stage GUI grounding study](https://aclanthology.org/2025.findings-acl.501.pdf)
was also checked for its additional-stage latency/recall limits. Newer leads
AdaGround, InnerZoom and broader abstention studies were screened by the sweeps;
they are not prerequisites or adopted methods. Token-probability verification,
model-internal training, generated tool tasks and self-reported uncertainty have
different assumptions. No quantitative confidence calibration is inferred here.

## Comparison of candidate approaches

| Approach | Evidence / fit | #300 disposition |
| --- | --- | --- |
| Explicit actor/focus/landmark/effect state and one worked reference-frame example | Directly targets the repeated local error; related spatial work supported investigating reference/entity distinctions. Local assessment and live play did not establish benefit. | Tested once and rejected; current guide restored. Exact candidate/failures retained in the linked report. |
| Optional crop/magnification | Plausible for small visible detail; may lose relationships, select the wrong region and add inference. No direct evidence it repairs the observed transition error. | Defer before implementation; revisit only with a concrete legibility question. |
| Automatic grid, segmentation, tracking or camera/pose model | May expose different cues, but introduces representations/dependencies and often trained or external semantics. | No current demonstrated need; no semantic detector in computer authority. |
| Larger history, mandatory summaries, self-critic or map service | Existing context research and current spatial papers contain mixed/negative results; each adds latency or distortion risk. | Not a default remedy. Existing source/memory/program facilities already cover optional access. |
| Changing model/effort/provider | Capability and serving can matter, but the local diagnostic does not isolate them. | Keep the selected model/effort fixed for this candidate; use fresh fast-route eligibility and retain unmatched-route limits. |

## Evaluation consequences

Freeze the source-backed demonstration and context before assessment examples or
outputs are opened for tuning. Discovery examples may inform it; report that exposure
and same-episode correlation. Evaluate supported facts, appropriate uncertainty,
unsupported assertions and missing decisive evidence separately. Retained source QA
is a local probe, not independent gameplay or attention evidence.

The candidate should correct the screen-versus-landmark mistake when relevant
before/after evidence exists, while avoiding invented movement when only one image
or genuinely unchanged evidence is available. Entity identification, moving anchors,
rotation/scale changes and unavailable evidence may still require uncertainty.
Do not force a frame calculation where its assumptions are missing.

Then assess substantive useful play and continuation, including interpretation
errors, failed/canceled work, note/recall preparation and ending. The player chooses
all actions and optional records. No per-key state ritual, fixed route, planted
mistake, human-corrected live belief or new semantic eligibility check is introduced.
A fluent state description or teacher-example repetition does not earn readiness.

Retain original request/tool/native/DOM/cache diagnostics and their populations,
but judge apparent time to supported useful effects. Extra model turns, omitted
information and unsafe certainty can outweigh fewer tokens or sharper pictures.
Do not corrupt live game observations to reproduce a paper's causal audit; ordinary
traces alone leave causal use unknown. Independent review, actual Save/persistence
limits, protected delivery and cleanup remain in the selected issue/workflow.

If the candidate fails, retain the failure and adopt/reject/rescope explicitly.
This review grants neither a new resource ceiling nor parent cadence, learning,
survival or portability qualification.
