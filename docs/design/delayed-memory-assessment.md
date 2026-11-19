---
owner: lead
status: proposed
date: '2026-11-18'
scope: 'CDDA development and experimental assessment of episode memory across natural activity and context boundaries'
review_trigger: Context coverage, decision opportunity, scoring or price changes
---

# Assessing memory during CDDA play

## At a glance

Test whether episode memory helps the player make a consequential choice after
its ordinary context has stopped supplying a useful world-specific fact. Start
by auditing retained decision packets. Replay eligible packets with the current
and a smaller context. Where existing evidence cannot supply eligible packets,
acquire one fresh naturally played lineage through two waking periods, with
work after each wake. Aim for two completed development lineages in distinct
start profiles, with one conditional fresh start to address an observed
coverage gap. Use those outcomes to size a matched live comparison.
Episode memory means a source-linked readout from earlier play in that world.
The [research proposal](structured-recurrence-research.md) owns the eventual
comparison of editable memory, fixed recurrence and episodic replay. This design
proposes the opportunities, horizons and context conditions that make that
comparison answerable. Each paid acquisition, replay or live comparison needs
its own frozen package and numerical owner envelope before dispatch.
[Gameplay permissions](../operator-permissions.md#finite-gameplay-budget-delegation)

## What the runs say about pacing and context

- #767 obtained three same-survivor reloads across two fresh Evacuee
  starts. Early voluntary saves, water availability and active threats
  limited play to 1h 12m 44s and 11m 39s in game. Neither world reached
  a natural wake. The final second-world Save showed the clock without
  a co-timed named view, and pursuit displaced the later objective.
  [Targeted capture](../acceptance/2026-11-18-targeted-tool-memory-767.md)
- Townsend reached a natural wake at 21h 38m 52s and two wakes by
  44h 22m 15s across three admissions and about 81 custody minutes.
  The swamp route choice produced food after the first wake, with the
  relevant earlier fact in the ordinary handoff. About 42.4 game hours
  were attributed to long activities. Provider-reported player input
  peaked at 136,910 tokens in one slot. This gives a useful reference
  for pacing and ordinary cue redundancy.
  [Townsend record](../acceptance/2026-11-18-wilderness-delayed-memory-762.md)
- Scipio reached 7h 50m 22s in about 76 minutes of total custody. Two waits
  supplied five game hours, and one digging-stick craft added about 87 minutes.
  The reload actor made a real roof-water decision at roughly 5h 18m fact age.
  Its intact handoff still stated the fact. The run stopped before sleep and a
  later waking decision, and its final living view lacked the survivor name.
  [Scipio record](../acceptance/2026-11-18-evacuee-delayed-decision-759.md)
- Two older viable lineages reached 24–25 game hours across two or three
  admissions. One slow lineage got only about 32 game minutes. Whitethorn
  reached 47.79 game hours across seven admissions and about 4.3 wall hours.
  Two of its admissions advanced under 1.4 game hours each despite recording over
  240 decisions each. Earlier routes and operating conditions differ. These are
  reasons to budget an additional serial checkpoint and measure actual pace.
  [Day-scale run](../acceptance/2026-11-07-long-horizon-382.md),
  [Whitethorn run](../acceptance/2026-11-07-seven-day-397.md)
- On the frozen Scipio route the configured player window was 262,144 tokens,
  with a 16,384-token output limit and a 32,768-token context warning reserve.
  The host kept up to 39 images, dropping older pixels in blocks of 20 while
  preserving text, tool history and omission markers. In the sealed reload
  `host.jsonl`, `context-image-projection` first dropped pixels at request 41.
  `context-estimate` peaked at about 135,000 tokens at request 242. These are
  host configuration and estimates. The run ended on time with room in the
  configured window. A fresh actor changed the transcript, and its full
  handoff still carried the tank fact. A fact can also return through a source
  read or curator reminder. [Host context](../contracts/player-host.md#context-manifest),
  [Sealed evidence index](../../data/evidence/index.json)
- In one retained lineage, supplying an earlier rod observation changed a
  recipe-search proposal into a targeted location check at roughly 22h. Food
  choices matched when the current view answered the question. This shows why
  both useful gaps and cases with an ordinary answer belong in the test.
  [Paired cue probe](../acceptance/2026-11-18-delayed-observation-cueing-755.md)

## Start portfolio

The earlier [CDDA scope decision](../decisions/owner-decisions.md) directs this
study toward diverse genuine starts within CDDA. The [portfolio design](structured-recurrence-research.md#diversity-is-in-situations-and-histories)
and [preparation worksheet](../../data/recurrence-research/spec.json) define
three development profiles. They vary which earlier observation could matter
to the player.

| Development profile | Decision to look for in normal play |
| --- | --- |
| Sheltered with visibly limited supplies | Return to a stockpile or finish a task after an intervening activity. Scipio is a reference for setup, continuity and ordinary-context redundancy. |
| Exposed and unfamiliar surroundings | Revisit a place, choose between routes, or verify an earlier resource observation after travelling elsewhere. |
| Different visible capabilities or equipment | Recheck whether earlier advice or a planned method still applies given the survivor's visible tools, skills or condition. |

Bowdle and Nancy were independent fresh worlds. Both offered similar early
shelter and food choices. The earlier preparation also found two saved payload
groups across 77 manifests in one related source family. Independent worlds
support replication within a profile. Distinct situations expose different
memory demands. Hash-verified copies supply matched comparisons within a world.
[Fresh-start progress](../acceptance/2026-11-17-fresh-evacuee-progress-751.md),
[Source inventory](../acceptance/2026-11-16-cdda-recurrence-preparation.md)

Use retained shelter evidence to dry-check capture. For the first new
acquisition, stage a fresh Safe Place / Farm candidate on ordinary world
rules. The installed scenario lists Farm as an allowed start. Verify it in
the rendered setup. The intended contrast is a sheltered rural location
with plausible supply, unfinished-work and return choices. Actual resources
and nearby threats are learned through play. For independent replication,
prefer a fresh Wilderness / Campground world with the same model and
capture protocol. Its exposed start supports navigation and alternate-source
choices, and Townsend established that the profile can reach two natural
wakes. Both worlds start with empty episode state. Keep failed starts as
assigned feasibility outcomes.

Plan for **two completed worlds from up to three fresh starts**, priced
and run serially. Stage the Farm first. Use its settled evidence to
confirm the protocol before dispatching the fresh Campground contrast.
Retain the third overnight block as contingency. Each start uses the
same finite per-world limits, with up to eight custody hours plus
between-slot review. Two completed worlds are a feasibility target.

| Observation during acquisition or after the first two starts | Use the remaining time or start for |
| --- | --- |
| Named checkpoint, visible progress and a concrete older fact still relevant to a feasible choice | Continue that world under its remaining slots. Use the third game day, up to 72 hours from entry, only when the recorded choice can occur there. |
| One profile ended in an early gameplay loss before it could yield a later choice, and capture and ending worked | Use the third fresh start once in the missing profile. Preserve the failed assignment. |
| Both worlds reached waking endpoints, but the observed choices omit a specific decision family | Use the third start only for a predeclared contrast with a concrete opportunity, such as a different starting capability for an unfinished tool task. Verify the setup and keep that world in development. |
| Capture, accounting or continuity failed in a way likely to recur | Repair and verify that failure offline before dispatching the next start. |
| Both worlds yielded scoreable choices, and the facts remained in ordinary context | Close the acquisition unless a specific new decision family is missing. Test the retained packets at the smaller budget and use ordinary-cue cases as controls. |

For each assignment record whether it reached a first wake, a second
wake, a scoreable later choice and a gap under the declared context.
Count these at the world level alongside the packet count. Reloads and
multiple choices from one survivor give richer within-world evidence.
A deciding comparison needs independent reserved worlds, with the number
set from observed feasibility, paired outcome variability and the
declared practical effect. A three-day or longer follow-up earns its
time by targeting an older fact that naturally becomes useful again,
such as a return after relocation or a deferred repair after finding
a missing tool. The current pilot seeks earlier evidence of that kind.

After feasibility, the broader coverage target also considers changed
environmental conditions, an established survivor or base, and a later return
or relocation. Acquire those states through ordinary play. A later state in
the same world contributes history and stays in its original lineage. Give each
fresh world an empty episode store. Test transfer of the frozen representation
or reusable rules while learning that world's locations and supplies through
play. Split by whole world before opening the test histories. The earlier
six-profile, twelve-source target is a coverage proposal. Size a deciding
comparison from the pilot and the cost of the available independent sources.

## What to capture and when

Enroll the first opportunities that meet a frozen pre-action rule for each
family. The player chooses its objective and actions. For retained traces,
inspectors judge eligibility from the earlier fact, the ongoing objective,
the current scene and feasible alternatives with the actual choice and result
still sealed. Keep enrolled packets with unknown effects. Useful
examples include the location of a supply the player left behind, the next
dependency in an unfinished job, or an earlier resource or route condition
that calls for a recheck. Specific world facts come from normal play. A target
choice needs a real alternative, such as broad search, another source, a
low-cost verification or a viable alternate task. A stale case requires visible
evidence of change or a genuine reason to doubt continued applicability.

| Horizon | What would make it informative |
| --- | --- |
| About 30–90 game minutes | A useful activity switch and a return to a task or resource. Include ordinary-context controls and measure which pixels and text remain. |
| First natural wake, budget roughly 18–36 game hours from fresh entry | After ordinary rest, seek a consequential choice tied to an earlier observation roughly 8–24 game hours old. Include a later choice across a real actor or Save/reload boundary where ordinary play supplies one. |
| Second natural wake and ensuing work, plan 48–60 game hours from entry | Seek a decision using a roughly 24–48-hour-old fact after intervening work. Capture the actual age, choice and effect. Allow up to 72 game hours when a specific prospectively recorded issue remains actionable. |

At a candidate, retain the original operation, scene and clock; the ongoing
objective and intervening activities; the later pre-action frame, claim age and
permitted context; and the feasible alternatives. Retain the verified game
effect and name the living survivor close to that effect. Ask the player in the
common brief to capture identity and time at a natural progress checkpoint
and leave enough ordinary work time for an appropriate Save before the ending
reserve. The reserved finish-up can still end without a Save. Record
wall minutes, elapsed game time, time in long actions, consequential choices
and observation counts separately. An uninterrupted sleep, wait, craft, travel
command or menu search can advance time or effort substantially. Count its
distinct decisions and visible effects on their own evidence.

Replay the actual cutoff manifests using
[`request_context`](../../harness/evaluation/core/context.py). Inspect matched
payload text, sent pixels, ordinary report and journal/source reads, static
knowledge and prior reminder deliveries. Audit which part carries the fact.
Record two things at each cutoff. Was the fact already sent in ordinary context?
Could the player recover it through an available ordinary action? An omission
marker with a callable source is often a cheap lookup. A fresh trip or search
can have higher cost. Mark the observed access path as explicit lookup, fresh
search or re-observation, no visible feasible path, or unknown. A fact already
sent is a control even if it could also be recovered a different way.
Digests establish identity of retained content. Where the relevant contents
cannot be recovered, exposure stays unknown. A historical prefix can form a
labelled reconstruction for pilot work. A faithful sent-context comparison
requires inspectable matched inputs. If needed, stage a small research-only
capture of the selected cutoff parts, with the same private evidence retention
as the game frames. Preserve the whole ordinary handoff.

## Comparison sequence

### Calibrate on retained play, then replay paired choices

Use #759, #755, #757 and the day-scale reports as development evidence. At
$0 new provider spend, build and blind a few cutoff packets with the existing
evaluator and [prefix preparation](../acceptance/2026-11-16-cdda-recurrence-preparation.md).
Include a likely gap, a redundancy control and a stale or unknown control.
Make claims about absence only for inspectable inputs. Test matching, packer
headroom and effect labels offline. The existing feasibility review and Scipio
found no verified natural context gap with a scoreable effect. A reconstructed
compact packet can test the apparatus. If the audit cannot find an inspectable
eligible gap for faithful replay in a declared context condition, prioritize
prospective capture and the waking-period acquisition over more cueing calls.
Dry-check that the selected capture can recover the relevant cutoff parts
before pricing that acquisition. Keep the reserved source worlds closed during
protocol development. [Retained feasibility](../acceptance/2026-11-18-delayed-decision-feasibility-757.md)

The first priced replay uses a small crossed comparison on the same decision
packets. It asks for a proposed next choice and verification plan. Replay
dispatches no player tools. Both columns can propose the same feasible source
lookups and game rechecks. Score those as ordinary alternatives. A valid cheap
lookup supplies an efficiency question even if the old pixels are unavailable
in the sent request. The full row tests marginal value under normal context.
The smaller row tests decision quality at a smaller budget.

| Common context | Ordinary player only | Ordinary player plus episode memory |
| --- | --- | --- |
| Current context rules and full common history available at the cutoff | Measures what the current player can do with the ordinary carriers. | Estimates added value under current context. |
| 64k-token total input target for replay | Measures the effect of retaining fewer old turns. | Estimates how much quality the extra memory recovers at that context size. |

The 64k figure is an initial input-budget target, chosen to be meaningfully
below Scipio's late estimates. Calibrate it on retained packets before freezing
it. Budget text, tools and images and reserve output separately. Keep the same
model, effort, guide, tools, ongoing objective, intact handoff, actor state and
current view. Pack the newest complete turns that fit, including paired calls
and results, under a deterministic rule. Keep ordinary omission references and
the same pixel projection policy. If protected material cannot fit, record the
packet as infeasible at that size. Keep the common packet byte-identical within
a context row. Reserve the same optional readout space in both columns before
packing. A 65,536-token budget with a 2,048-token reserve leaves at most 63,488
for common parts, including measured framing overhead. Keep a full-history
cutoff only if the same readout fits without changing the ordinary history.
The memory updater and reader see only authorized pre-cutoff material. They
choose the readout without the label, a handpicked answer or later frames. All
ordinary knowledge and recorded deliveries selected for a cutoff are identical
in both columns. Record actual input and output usage, cache reads and writes,
latency and returned cost separately.

Freeze interleaved order, repeats, scoring and exposure conditions before calls.
Inspect
one end-to-end unit before proceeding. Budget up to six development packets
with two samples per cell, or at most 48 player responses, plus a separately
bounded updater and reader allowance. Count every assigned cell. Samples and
windows remain nested within their source worlds. A grounded targeted check
and an equally effective alternative can both score well. Score their
feasibility from the packet. A recorded later effect supports the executed
branch only. Reward justified stale-state verification and record unsupported
certainty, needless backtracking and harmful reliance on stale facts.

Compare smaller context plus memory with the current ordinary player against
a frozen acceptable loss in decision quality and a practical cost or latency
gain. That contrast supports a context-efficiency follow-up. A benefit
confined to the smaller row supports the smaller-context condition. The
replay result concerns proposed decisions. For a representation claim,
compare the selected episode-memory policy with matched episodic retrieval and
fixed recurrence using the [parent design](structured-recurrence-research.md).

### Acquire through two wakes in one continuous world

Price **one fresh development world with up to six serial admissions**.
Plan one start and up to three normal reloads, with up to two contingent
reloads. Size the proposed work under the approved dollar envelope and
use provider-reported costs under the [existing admission rule](../operator-permissions.md#finite-gameplay-budget-delegation).
An incomplete trace keeps its separate recorded admission bound.
For time planning, the prior slots allowed 80 custody minutes and
70 actor minutes including ten for the endpoint and ending. At that
size four slots allow 5h 20m of custody and six allow eight hours.
Schedule one lineage per overnight block with separate time for
between-slot review. Townsend reached nearly two
game days in roughly 81 custody minutes. Whitethorn reached about 46.3
game hours after six slots and ended at 47.79 hours with a death in the
seventh, after about 4.3 wall hours. Six slots are a finite feasibility
allowance and may end before the target.

Estimate attempts to validate context, capture and ending headroom. Freeze
the dollar limit and operational capacities in each package, then record its
observed attempts, provider subtotal, unpriced requests and ending reason.
The [budget-led campaign contract](../operations/campaign-run.md#spend-limit)
and [owner decision](../decisions/owner-decisions.md#in-force) govern the final
package freeze.

The common brief gives the player an ongoing objective from the outset.
Establish a sustainable place to work and sleep, pursue an ordinary
project or replenishment need, and work through two natural wakes when
feasible. A routine checkpoint or one completed chore counts as interim
progress. The player chooses all projects, routes and actions and can end
for survival or inability to continue. A useful endpoint after a wake
includes a genuine choice and its visible consequence. Track settled
needs, work deferred and resumed, and the feasible alternatives when
judging progress between slots. Before either contingent slot, record a
verified named Save, visible progress toward the next wake or toward
resolving an earlier observation, and a specific feasible choice or
remaining task within the slot allocation. For example, a first wake
followed by work on a known supply problem supports investigating it
after the next wake. Record repeated threat response or menu work with
no feasible recovery or task path as no opportunity or inability to
continue, according to the visible outcome.

Freeze the initial manifest and a hashed conditional reload recipe. Each
reload binds a new manifest to the actual closed save, userdir and supported
journal. Preserve the full ordinary report when supplied and record its absence
when missing. Validate the manifest before dispatch against the original lineage
and per-slot limits. Admit a reload only after a verified ordinary Save to title,
a separate Quit with independently verified normal native exit before forced
cleanup, released custody, a reconciled ledger and a feasible task or opportunity
within the next slot.

Use that evidence rule in the frozen reload recipe and player brief. For an
uncertain Quit, collect the result on the original operation ID and preserve its
delivery status and the driver disposition. Input stays fenced and the action is
never resent. A second identical read of the same terminal result is observational
and leaves reload eligibility unchanged. Conflicting results leave delivery
unknown. If the conflict prevents verification of any required reload evidence,
withhold the reload. Use the independent Save, exit, custody and accounting
evidence to decide eligibility.

After dispatch, verify the visible world, survivor and clock at Load before
meaningful play. Capture the name and clock close to the effect for scoring, and
at the saved checkpoint for continuity.
The feasibility endpoint is two natural wakes, meaningful work after each,
and a later consequential choice with a visibly scored effect and named
living checkpoint. Ordinary cues can remain present. The 48–60 hours size
the expected span. An endpoint reached earlier can close the world. Beyond
60 hours continue only for the documented candidate, with an ending at
72 hours or an earlier finite stop. If an ordinary activity crosses the
game-time limit, record the actual clock and begin ending at the next
safe opportunity within the original time, budget and mechanical limits. Record
death, a lost checkpoint, no opportunity, unknown exposure and time
exhaustion as assigned results. Keep one writer and one native game lane.

Use ordinary context and delivery settings in acquisition. Retain the actor's
own report across reloads. Aim to retain three to five decision packets per
world, spanning ordinary controls, a post-wake choice and any older or
changed-state candidate. Classify each packet by opportunity, fact age,
ordinary sent exposure, ordinary lookup or fresh search, effect and named
living evidence. A delayed decision whose answer appears in the handoff
is an ordinary-context control. Follow the start portfolio after each
settled world. A repeatable capture, continuity or ending failure needs
offline repair before further dispatch. Early gameplay losses remain
assigned results and inform the choice of contingency start.

Before paying for the crossed replay, use retained traces to dry-check exact
cutoff reconstruction, the 64k packer and blind before/effect scoring.
Retain an ordinary-context redundancy control and an actionable gap under
the question's declared context condition. Tag a gap introduced by smaller
context as a context-efficiency case. If the fact remains ordinarily
available under both context budgets, keep the packet as a control and
reassess the proposed comparison before further acquisition. Mark exposure
or ordinary access unknown when the corresponding evidence is missing.
Two independent worlds with scoreable cases support a development pilot.
That milestone tests the delayed-memory procedure. The parent proposal
retains its separate multi-profile, three-arm procedure. Size a deciding
comparison later from paired, whole-world variability and feasible costs.

### Confirm on independent live pairs

Seek a current-context live pair only after the development profiles
show prospectively enrolled, scoreable opportunities with an actionable
gap under ordinary current context. Gaps that appear only with the 64k
budget support the smaller-context efficiency question. Assign held-out
worlds by profile before opening them. Acquire each starting checkpoint through
normal play at a safe point before any assigned target choice or outcome. Use
the first qualifying checkpoint under the frozen selection rule. Freeze the treatment
readout from the shared authorized pre-save prefix. Pair the conditions on
verified save copies and separate verified copies of the same supported closed
journal, as in Scipio's continuation. Preserve the intact shared handoff,
starting source access and standard knowledge in both arms. Verify that both
copies can read the same retained sources with ordinary tools. A carried ID
supplies a read only where supported, and permissions for new input come from
the current session. Use supported
between-admission publication for the readout and verify the actual delivered
change. This first live comparison needs a delivery contract that permits the
study treatment while preserving the normal carriers. Within-admission
adaptive delivery is a separate comparison through [#664](https://github.com/CVX-Hull/enactive/issues/664).

Counterbalance execution order. Audit the ordinary post-Load view and lookup
availability again. A fact that reappears before action is a control and
its trial remains assigned. Post-treatment progress never determines which
assigned trials enter the primary analysis. The first live pair uses current
context rules. A later smaller-context efficiency test needs its own frozen
live condition and a full-context reference. The player uses the same ordinary
goal, controls and source access in both arms. Score one preregistered visible
task-progress-and-alive
predicate per world per arm at the finite endpoint. Use the same rule for
alternate successful actions and log steps to re-find, justified checks,
verified effects, resource use, inability to act and stop reason as diagnostics.
Judge outcomes blind to the memory treatment and resolve scoring reliability
with [outcome qualification #681](https://github.com/CVX-Hull/enactive/issues/681).
Count all assigned attempts. Extra windows, repeats and copies stay within the
same lineage. Use world-paired uncertainty and the parent design's sizing
simulation before making a decision from live differences. Freeze a useful
effect threshold and a complete cost estimate with the analysis. An affordable
comparison may be exploratory.

The cutoff and blinding checks address R-FALSE-CLAIM with a small review per
selected packet. The first-unit inspection and finite acquisition address
R-STUDY-OVERRUN using existing controls and one serial development lineage.
Reuse the [run ledger](../../data/evaluation/runs.jsonl) and retained evidence
workflow. Price acquisition, all arms, memory update and retrieval, scoring,
retry, ending and capture overhead from measured traces and the selected rates.
Record OpenRouter-returned charges and count unpriced attempts separately.
Keep the design, acquisition and comparison under the existing
[#666 outcome](https://github.com/CVX-Hull/enactive/issues/666).
