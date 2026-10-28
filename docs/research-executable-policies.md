---
owner: lead
review_trigger: Executable learning design, relevant new evidence, or a learning/responsiveness claim
status: active
---

# Player-authored executable policies

Research cutoff: **2026-10-23**. This is a research synthesis and proposed
direction, not an implemented execution contract or a passing gameplay result.
The question is whether the player can discover, write, test and revise scripts,
decision trees and strategies over ordinary visible observations and atomic
inputs, amortizing reasoning without losing organic adaptation.

This review assessed the advisory Procedure/2 source baseline. The subsequent
[execution slice](changes/061-player-program-execution.md) owns the current
Procedure/3 candidate, runtime choice, bounded visible-data view, source checks
and remaining qualification. The research below is not evidence that this new
candidate has organically learned, improved total cadence or completed a campaign.

## Finding and current gap

**Support player-authored, observation-conditioned executable routines alongside
ordinary model-driven exploration.** Do not restrict learning to prose, require
the lead to implement each discovered behavior, or replace exploration with a
fixed menu catalogue. Code, small trees, state machines and natural-language
strategies can coexist; no single representation is established as best.

The assessed Procedure/2 baseline contained advisory descriptions, not evaluated
code; its runtime recorded selection/outcomes without executing those steps.
That historical gap motivated the subsequent Procedure/3 execution slice.
The [current component view](components/memory-learning.md) owns implemented
bounded program support. The [October24 follow-up](research-multirate-agents.md)
assesses current program coverage and asynchronous learning; it does not infer
cadence or causal benefit from execution support.

[Diagnostic017](acceptance/2026-10-23-luna-responsiveness-seventeenth-attempt.md)
is motivating evidence: six completed navigation goals each moved one tile;
the wield-menu capture-to-effect interval was81.843s, including draft/scope errors.
No procedure was authored or used. Improving argument errors alone cannot
establish the requested autonomous learning or useful execution cadence.

## Search and reading scope

Three independent read-only lanes covered executable-skill research, contrary
evaluation evidence, and the repository boundary. Initial2026/2025 queries used
problems—online executable skill discovery, generated policies, changing GUI
conditions and continual learning—rather than a seed list of familiar systems.
Dedicated30-,14- and7-day discovery passes found additional October work; older
references were followed afterward. Primary arXiv texts, conference proceedings,
author projects and official implementation documentation were inspected.

Downloaded primary PDFs, manifests and layout-text extracts are retained under
`.runtime/research/2026-10-23-executable-policies/`; HTML methods/results were used
to check important claims. Extraction used the existing skill's tools and available
pdftotext, without installing dependencies. Layout text is not reliable evidence
for reconstructing equations/tables. The table below names the relevant read
sections; no entry is an assertion of independently replicated SOTA.

Dates come from primary version histories. Aggregator update dates did not prove
paper revisions: RAX and MetaSkill expose v1 dated October15 and17 respectively;
SkillNEO exposes v2 dated October20. Research remains a search sample, not an
exhaustive claim about everything published before the cutoff.

## Primary evidence and limitations

All October entries below are treated as recent preprint evidence.

| Source / read scope | Evidence relevant to Enactive | Limitation / consequence |
| --- | --- | --- |
| [RAX](https://arxiv.org/html/2610.22496v1), Oct15; §§3–5,10 and real-robot appendix | Agents explore, compile observation-driven control programs, compose prior skills and evaluate frozen routines on unseen scenes. This directly supports studying executable procedural learning rather than prose-only recall. | Robot backends supply rich sensing/control helpers and scoring; RGB-only performance is materially weaker, and some physical runs include operator assistance. It does not establish raw keyboard/mouse CDDA competence. Transfer the experiment/compile/revise loop, not reported robot success rates. |
| [MetaSkill](https://arxiv.org/html/2610.24723v1), Oct17; §§3–7 | Makes persistent dependencies and predecessor-output bindings executable while leaving substantive judgments inside skills. Audited traces conform to declared coordination. | Twenty artifact tasks, supplied component skills and a shared frozen plan; most quality-preference intervals include parity. No online game-policy discovery or reactive-loop evaluation. Formalize observable bookkeeping without pretending open semantics are solved. |
| [Procedural Exposure Bias](https://arxiv.org/html/2610.26062v1), Oct19; §§2–5, appendix A.5 | Controlled repetition can favor an action even when its current relevance is unchanged; representation affects this bias. | It does not compare executable policies against prose policies or prove that image-rendered memory solves learning. Keep retrieved context relevant and bounded; repeated procedure text is neither evidence of applicability nor a reason to act. |
| [AtomSearch](https://arxiv.org/html/2610.19951v1), Oct14; §§3–5 | Evidence-linked local edits, outcome memory and short lookahead preserve useful paths through locally weaker revisions. Repairs and regressions are tracked separately. | Additional offline evaluations, finite validation and stochastic outcomes; studies instruction optimization, not our live controller. It supports non-myopic candidate development, not guaranteed convergence or installing tree search by default. |
| [SkillNEO](https://arxiv.org/html/2610.20926v2), Oct14 / Oct20 revision; methods, experiments, limitations | Separates the deployed incumbent from candidates allowed further development; a weak immediate result need not destroy a promising revision path. | Development/final evaluation use the same task instances, one developer model and incompletely isolated component effects. Retain candidates without equating development progress with unseen-task improvement. |
| [SEAR](https://arxiv.org/html/2610.18792v1), Oct13; §§2–5, A.7–A.9 | Compares code-as-policy, live model control and training; matched no-library/restart controls distinguish retained experience from extra attempts. Code libraries can help or hurt. One learned success detector propagated systematic false positives across later sessions. | Simulation has richer tools and explicit judges; physical samples are small and transfers weaken away from practice. Generated detectors are fallible learned artifacts too; their verdict cannot be their only assessment evidence. |
| [Agent Plasticity](https://arxiv.org/html/2610.08902v1), Oct6; §§2–4, game/failure appendices | Fixed models retain executable tools, strategies and memory across fresh contexts; evaluates held-out outcomes and acquisition cost. Distinguishes missing, available-but-unused and used-but-failed artifacts. | Improvement is model/task dependent and non-monotone; reuse is not causal proof of benefit. Diagnose discovery, retrieval, application and routine quality separately. |
| [SkillScriptBench](https://arxiv.org/html/2610.04008v1), Oct2; §§2–4, A.7, limitations | Separately tests documentation repair, script repair and preservation of working behavior. Generated revisions can repair one case while regressing others. | Mostly Python with constructed faults; long-horizon game reliability untested. Maintain readable applicability/instructions with executable revisions and check prior successes as well as the new counterexample. |
| [Compiled Agency](https://arxiv.org/html/2609.18996v2), Sep26 revision; §§2–9 | Agents develop standalone controllers that run without model calls; held-out replay distinguishes the shipped policy from development claims. Documents stale validation and optimistic conclusions. | Game descriptions/APIs and development access differ from visible-only play; no blanket CDDA transfer. Autonomous experiment design is itself something to evaluate. |

Two useful cross-checks: [CodeHack](https://arxiv.org/html/2609.31076v1),
§§2–5 and appendix A, supports mixed code skills plus primitive fallback but uses
a human-designed NetHack library; it is not evidence that an agent discovered
those skills. [SkillComposer](https://arxiv.org/html/2608.14944v1), §§III–V,
uses existing Stitch library learning to compress repeated accepted programs;
compression does not by itself establish closed-loop behavior or transfer.
These were already conceptually relevant to our earlier tiered design.

Earlier [SkillWeaver](https://arxiv.org/html/2504.07079v1), §§2–4 and appendix D.2,
demonstrates synthesized executable web APIs but reports routines that evade an
exception-based verifier without doing the task. [WebXSkill](https://arxiv.org/html/2604.13318v1),
§§3–5, combines executable actions and step guidance for adaptive use; its DOM/
site assumptions do not transfer automatically. These are foundations and
implementation references, not substitutes for the fresh October search.

## Evidence matrix and project judgment

| Claim | Support / contrary evidence | Assessment for this project |
| --- | --- | --- |
| Fewer model calls through local programs can accelerate repeated work | RAX, SEAR, Compiled Agency; perception, recovery and learning costs remain | Strong reason to build a measured thin execution path; actual CDDA latency benefit unqualified. |
| Executable memory necessarily improves play | SEAR/Plasticity show negative transfer and used-yet-failed routines | Reject. Treat applicability and usefulness as hypotheses, not effects of compilation. |
| Learning must improve at each revision | AtomSearch/SkillNEO retain useful non-incumbent paths | Reject. Separate experiment eligibility from currently preferred deployment; bound exploration costs. |
| Every expectation must be engineered in advance | Programs can learn checks; MetaSkill separates mechanical relations from judgments | Reject. Keep stable input/accounting contracts, learned world hypotheses and semantic judgment distinct. |
| A successful script proves generality | CodeHack has authored domain knowledge; robot/web APIs differ; transfer declines | Reject. Test distinct situations, changed interfaces and fresh contexts, preserving failures. |
| More procedural context is automatically better | PEB and library failures | Reject. Reveal a small relevant description and invalidators first; retrieve code/details only when needed. |

The recommendation below is **our engineering inference**, not a demonstrated
CDDA result or a promise that learning eventually converges. In a changing,
partially observed world, revision and retirement remain necessary indefinitely.

## Proposed responsibility split

The stable platform exposes current visible observations and ordinary key/text/
click actions through the existing writer. It handles IDs, selected-source
binding, receipts, clocks, cancellation and original resource accounting.
The player authors strategies, conditions, branches, loops, parameters and
fallible outcome detectors. The platform must not require a CDDA-specific
engineering handler for each new menu or learned behavior.

A routine runs locally against fresh observations, without an LLM turn at each
primitive. Known conditions and ordinary calculations use code; semantic novelty,
uncertain applicability and strategy changes can request model interpretation.
The routine may return control for organic ordinary-input exploration. A missing
learned branch is not itself a transport failure or permanent mission revocation.
Unknown delivery still uses original-operation collection, never input replay.
Do not make every pixel change require a model verdict, or treat a learned
success predicate as unquestionable world truth.

The deciding player remains accountable for its current task. An asynchronous
learner can propose/revise routines from existing trajectories while useful
authorized execution continues. Software records invocation, branch decisions,
observations, effects, time, failure and revision lineage. Models supply semantic
explanations only where needed; they need not narrate every key or report data
already in receipts. Advice pending must not force a model poll or lead wakeup.

Distinguish **stable execution substrate** from **evolving player artifacts**.
A prospective adaptation policy can allow player-created program revisions
during play while substrate, capabilities and original limits remain fixed.
Pin the version used by a running instance; later advice can affect a subsequent
selection or explicit player replan. This needs one reviewed substrate contract,
not a PR, human approval or independent model approval for each learned routine.
Current Procedure/3 admissions provide bounded executable artifact evolution
under their frozen policy. That is substrate support, not proof of general
learning benefit or sufficient routine coverage.

## Representation, reuse and maintenance

Do not begin by inventing a policy language, new planner, memory database,
revision-control system or universal behavior-tree framework. A small program
can express a decision tree or state machine. Evaluate the existing language/
runtime facilities against source-only observations, interruption, bounded local
computation, model authoring ergonomics and actual overhead before adding one.
Keep game input serialized by the current writer, even if analysis is parallel.

If reactive tree composition earns its cost, existing
[py_trees](https://py-trees.readthedocs.io/en/devel/composites.html) provides
selectors/sequences and inspectable execution. Memory modes can skip earlier
conditions; invariant platform checks must remain outside learned control flow.
It is not an isolation runtime. For executable code isolation, evaluate mature
capability-limited embeddings rather than treating restricted Python builtins or
a virtual environment as isolation. [Wasmtime security](https://docs.wasmtime.dev/security.html)
and [interruption](https://docs.wasmtime.dev/examples-interrupting-wasm.html)
illustrate existing capability and compute-limit facilities; this is a candidate,
not a selected dependency or justification for a large runtime project.

Keep executable artifact bytes and revision identity in the existing owned
artifact/history facilities, with memory indexing purpose, parameters,
applicability, invalidators, source episodes and observed outcomes. Git owns
engineering source history; do not rebuild Git in campaign memory. The subsequent
execution slice selected the bounded V8 embedding and current Procedure/3 storage;
its component/protocol own those choices. Progressive context supplies summaries
first; the model does not need source hashes, full scripts or traces on every
invocation.

Maintain fallible selectors/detectors with their routines. Retain contrary
episodes and prior working behavior. Distinguish absent knowledge, missed
retrieval, wrong applicability and used-but-failed execution. Automatic tests of
syntax/types/accounting are inexpensive entry checks, not semantic certification.
Ordinary experimentation under finite authority should not wait for a global
confidence score or bureaucracy. Broader reuse claims require distinct-situation
evidence and assessment beyond the routine's own success declaration.

## Crosswalk and next delivery

| Existing authority | Retain / change needed |
| --- | --- |
| [Tiered gameplay](research-tiered-gameplay.md) and [responsive gameplay](research-responsive-gameplay.md) | Retain mixed primitives/skills, empirical tier choice and useful latency. Extend beyond authored executors toward player-authored programs. |
| [Memory architecture](research-memory-architecture.md) and [procedure design](design/procedure-learning.md) | Retain evidence, immutable revisions and the distinction between advisory meaning and execution authority. Earlier offline-only boundaries are historical; current Procedure/3 admissions explicitly govern bounded artifact evolution. |
| [Learning research](research-memory-learning.md) and [representations](research-memory-representations.md) | Retain source-linked hypotheses and counterexamples. Add executable artifacts without equating storage, reuse or detector agreement with learning benefit. |
| [Protocol](contracts/procedure-programs.md#ordinary-discovery-and-procedure-data), [architecture](architecture.md) | Keep one writer, original uncertainty, ordinary fallback and current authority. The implemented Procedure/3 runner closes the advisory-baseline execution gap; actual acquisition, useful coverage and cadence remain distinct acceptance. |
| [S-ARCH/S-CODE](engineering.md), [control map](controls.md) | Review the stable boundary and reuse once; automatic runtime/accounting controls operate thereafter. Actual learning, changed-condition recovery and cadence require gameplay evidence. |

GitHub owns the action items: **#177** executable representation, runtime/reuse
spike, adoption and revision; **#176** generic primitive API and organic fallback;
**#178** asynchronous synthesis and automatic feedback; **#164** total learning/
execution cost, useful progress and tails; **#191** game-family observation/input
boundary. Parent **#136** and fresh campaign **#145** retain the combined outcome.

The next coherent implementation should connect one player-authored routine from
discovery through local branching execution, changed-condition correction and
fresh-context reuse, with background proposal work and normal lifecycle. The
player chooses the routine; the lead does not script a winning trace. Compare
useful task progress, failures, recovery and whole model/tool/display latency
against ordinary interaction, including failed learning attempts and compilation
cost. Trace inspection can test flow on retained observations but cannot prove
the counterfactual outcome of an action never taken. Wider independent learning
and the genuinely fresh seven-day campaign remain acceptance, not a prerequisite
to let a candidate routine try ordinary inputs.
