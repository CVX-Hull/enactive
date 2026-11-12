---
owner: maintainer
review_trigger: Changes to this standard, its controls or engineering constraints
status: active
---

# Authority and reading order

The [overview](../overview.md) is the user's starting point and AGENTS.md routes agents
to the relevant current material. Which document owns which kind of fact is stated once,
in the [documentation map](../documentation.md#one-authoritative-home-per-kind-of-fact).
A discrepancy is a defect to resolve, not permission to silently pick a convenient
source. User instructions take precedence. Proposed/superseded records cannot
silently change current contracts. Link to authoritative facts instead of copying
full contracts, procedures or delegation rules into multiple documents.

Principles explain the desired qualities and tradeoffs. Policies are decision rules
about when and by whom work proceeds; they live here and in project management.
Standards specify required properties; contracts/design apply them at a boundary;
controls provide prevention, detection, review or recovery; evidence records what
actually happened. These are related responsibilities, not six mandatory documents
per change. [Engineering](../engineering.md) lists each standard with the risks it
addresses. [Documentation organization](../documentation.md) defines artifact
roles and their lifecycle.

## Control review

The [risk register](../risks.md) owns the risks the project defends against, judged in
the charter's [scope of use](../charter.md#scope-of-use-and-what-is-guaranteed). The
[controls page](../controls.md) owns what is done about each one.

**A control needs a risk and a mechanism.** A control is anything kept to stop a
failure: a test, a check, a continuous-integration step, a runtime guard, a review, a
rule in a standard or a step in a procedure. Before one is added or widened, its author
states three things in the change that adds it:

1. the risk in the register it serves. If no listed risk fits, the register changes
   first, with a failure scenario that can realistically happen in the scope of use;
2. how it reduces that risk: what it would catch or prevent, and why that is plausible;
3. what it costs each time it runs or is followed, and why that is less than the risk.

A control that fits an existing row of the controls page is covered by that row. A new
kind of control gets a row. Review rejects a control that cannot state all three, and a
control that defends something the register lists as out of scope. More checking is not
safer by default: each control is paid for on every change.

**The register is pruned on events, not on a calendar.** Reconsider a control, and the
risk it cites, when:

- it fails, is bypassed, or costs more than its row says;
- it has blocked work without preventing a defect;
- the boundary it guards changes;
- the charter's scope of use changes;
- the work it protected is finished, as when a study closes and its tooling and tests
  have nothing left to protect.

Do this in the issue or pull request that meets the trigger. Keep, narrow, replace or
remove the control from that evidence, and change the register, the controls page and
the standards that name the control together. A control whose risk has recorded failure
evidence is removed only when something cheaper covers the same failure.
Revisit custom tools and previously rejected reuse options on changed needs, upstream
support, repeated defects or excessive upkeep, rather than accumulating controls.

`tools/documents.py` fails a control row that names no risk and a risk ID that the
register does not define. That keeps the two pages from drifting apart
([R-STALE-DOCS](../risks.md#development-risks)) and costs seconds. It cannot judge
whether a risk is real or a mechanism works; that is the reviewer's job
([R-CONTROL-BLOAT](../risks.md#development-risks)). A Low risk may have no control.
Keep three facts distinct: a control exists; it was exercised with a result, recorded
in the dated record or PR that ran it; its effectiveness was assessed. A failure stays
in history after repair; actual affected failures or evidence gaps stop the affected work.
An exception issue identifies scope, owner, expiry, reason and mitigation; it
does not silently suppress a failed mechanical gate or override user constraints.

## Change and review cadence

Define outcome/failure conditions → inspect real interfaces → brief/design where
needed → implement a cohesive slice → run relevant checks → review risk and
semantic drift → inspect staged candidate → checkpoint with honest scope.
The fast development-checkpoint command is `python tools/check.py --fast`, with
applicable focused behavior tests chosen by the lead. The default common command
`python tools/check.py` remains full. The [protected CI profile policy](../workflows/ci-profiles.md#protected-ci-profiles)
owns eligibility and evidence reuse; [development-first delivery](../workflows/development.md#development-first-delivery)
owns sequencing and escalation. Setup owns commands and environment requirements.
Only a successful full profile establishes a full portable pass; fast, editorial
and selected smoke results must state their narrower executed and unrun lanes.

On behavior changes, update contract, tests, guide and overview as applicable.
On failure, classify transport/perception/decision/engine/process, preserve
provenance, and add a reusable regression or adjust a rule when justified.
Review dependency pins and external documentation when resuming after a pause, and
when an upstream change breaks setup or a run. Do not optimize document count, lines of
code or test count as substitutes for quality. The research basis and evidence limits
are in [engineering research](../research-engineering.md).

[Standards index](../engineering.md).
