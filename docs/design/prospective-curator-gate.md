---
owner: lead
status: proposed
scope: 'Unbuilt proposal for publishing curator knowledge only after checks on evidence captured later; the curator contract governs current publication'
review_trigger: An owner decision on the test oracle or utility policy, a change to gate checks or session exposure, or a prospective verification producer is built
---

# Prospective curator gate

## At a glance

- **Question.** Should the gate check a curator submission against evidence captured
  after the submission was frozen, before publishing it?
- **Proposal.** A coordinator freezes each candidate, waits for an eligible later
  admission, and publishes only when supported tests and a frozen utility policy pass.
- **Current behavior.** None of this is built. The [curator contract](../contracts/curator.md#gate-v0)
  owns the structural checks that publish knowledge today, with no pending state.
- **Unknown.** No executable oracle for the truth or usefulness of a fact exists. How
  one pending candidate at a time would fit the
  [live runner](../components/curator.md#runner-windows), which starts sessions during
  play, is not designed.
- **Decisions needed.** An independent test oracle, a utility policy, and a coordinator
  for later evidence.

This proposal adds source-separated verification to the
[knowledge store and gate contract (#457)](https://github.com/CVX-Hull/enactive/issues/457).
The [gate-gaming research](../research-gate-gaming.md) covers outside evidence, and the
[curated-player decision record](../decisions/009-curated-player.md#fitting-and-evaluating-the-ontology-d4)
gives the rationale.

## Evidence identity and exposure

A session pins a knowledge version, trace-manifest hash and brief hash, reads the entire
published store, and receives open and stale drafts. Its brief includes recent gate
diagnostics, and a restricted window keeps the actor's prompt and guide. The step bound
alone is therefore not the session's information boundary. A
[coverage stamp](../contracts/curator.md#coverage-stamp-curator-coverage2) records a last
step or whole-admission names, not everything the curator has been shown. Trace later
than a base version may already have reached the curator in a window, draft, published
record or diagnostic.

The proposed trusted coordinator freezes each candidate **after collection** and before
it selects verification evidence. Its receipt binds:

- **Origin.** The repository or fork identity (game, and study, arm and lineage where
  applicable), base tag and content identity, source session, submitted bytes and
  candidate digest.
- **Exposure.** The files offered to that curator: the narrowed trace manifest and
  hashes, knowledge digest and version, prompt, guide, brief, drafts and prior
  diagnostics.
- **Plan.** A frozen gate-owned test plan with its targets, sources, resource limit and
  stop boundary. The candidate cannot nominate its own favorable future cohort.
- **Frontier.** The acquisition frontier at collection, and the original session,
  operation and source IDs and hashes of later evidence. Filenames, copied directories,
  admission names or a greater step number do not prove capture order or independence.

Exposure means bytes made available, not a claim about which files a model read. It
covers all prior controlled exposures on that repository branch, including aborted
sessions and unpublished drafts. Unknown exposure or capture provenance makes a cohort
ineligible. This bounds controlled input leakage; it cannot show the absence of model
prior knowledge or of guessed answers. Source IDs with their original operations
identify observations: identical image bytes can be a later re-observation, and they
establish neither new information nor an independent world.

The first design admits only **new captures after candidate freeze**, from an
independently approved later admission on the same permitted fork or lineage. An omitted
suffix of an already sealed admission is development holdback. The proposal permits no
cross-world promotion, arm mixing or new gameplay. A cohort stays outside curator
workspaces until its verdict is terminal, and a cohort exposed through raw trace,
derived knowledge or feedback is not fresh evidence for a revised candidate.

## Lifecycle without a session deadlock

The proposal extends session and submission records and the gate journal together. Its
`pending` and `deferred` states need a coordinated contract revision. The minimum
coordinator handles one frozen candidate per repository, with one writer. It closes the
proposing session and releases its lock while verification is pending. A candidate is
**settled or explicitly deferred before another curator session**; no lock is held while
waiting for future play.

| State or event | Proposed effect |
| --- | --- |
| Collection or structural refusal | Retain the submission and a precise structural diagnostic; publish nothing. |
| Plan missing or unsupported | Terminal `deferred` that names the missing oracle, input or policy. Structural acceptance never stands in for semantic acceptance. |
| Eligible candidate, no later trace yet | `pending`. The published base stays, no draft is promoted, and the candidate is not delivered. |
| Approved next admission | The player uses published knowledge only. Existing run authority and budget govern capture; the pending candidate grants neither. |
| Later source ready | Verify receipt, exposure and order, and evaluate before another curator sees the cohort. Candidate and plan stay fixed. |
| Unknown result, absent opportunity or breached limit | Defer at the frozen boundary, with no acceptance and no claimed negative utility. No retry for a favorable score. |
| Known failure or non-improvement | Reject with the rule category, not a claim of universal falsity. |
| Supported tests and utility policy pass | Recheck the base under the writer lock, publish atomically and promote drafts. |
| Any intervening publication or restore | Reject as stale. No automatic rebase and no reuse of the cohort. |
| No admissible source by the boundary, or a session is needed first | Terminal defer with the source gap. Retain the candidate, then allow the next session. |

Semantic feedback is limited to terminal status and coarse rule categories. The next
brief receives no hidden queries, expected answers, source excerpts or evaluator labels.
Acceptance itself leaks information; fresh cohorts and exposure accounting limit adaptive
reuse without preventing all inference. An operator may inspect retained evidence on the
separate read-only surface, whose contents do not enter a brief.

## Test, oracle and utility boundary

| Proposed check | Source and limit | Recommendation |
| --- | --- | --- |
| Shape, scope, stale base, citations, links and types | Current structural gate and immutable source identities | Reuse. These establish structure and provenance, not factual truth. |
| Capture order, exposure, cohort freshness and writer transitions | The receipts and coordinator above | Testable once built. Current coverage stamps alone are insufficient. |
| Retrieval misses, re-observation truth and wrong merges | A defined proposition, opportunity, scope and horizon, and an independent answer from visible observations | Deferred: no such oracle exists. A hint, citation, read or curator assertion is not its own truth label. |
| Retrieval comparison | A common query set and expected answers fixed independently of the edit | Deferred. Existing reads were selected under the base store, so replaying them does not measure the candidate. |
| Compression, type agreement and churn | A fixed counting scheme or classification procedure with its price | Descriptive diagnostics. Fewer bytes or more agreement do not prove correctness or benefit. |
| Program replay, predicates and disable | The interfaces in the [consumer matrix](#shared-consumer-and-verification-matrix) | Outside the knowledge gate, which validates data. |

A test plan binds the base and candidate comparison, the visible source and origin of
answers, eligible opportunities, unknown rules, scoring and complexity convention,
acceptance rule, price and finite stop **before** its cohort is viewed. Base and
candidate receive the same information and evaluation resources. Undefined support
yields unknown or defer, not a zero score or a pass. A fallible semantic assessor would
be a separately specified playing-system component with its own errors and price, not a
route from offline judges into the curator.

The gate computes any supported comparison. The proposing curator cannot edit the plan,
expected answers or pass criterion. It may add its own tests, such as one for a
retrieval miss it finds in the trace, but may not edit the gate's checks, and deleting a
test needs a stated reason that the gate reports. Curator self-tests remain untrusted
inputs. An unspecified “utility minus complexity” formula does not become an arbitrary
threshold, and no utility-based publication is recommended until a concrete finite plan
meets these requirements. [Approval for paid checks](../operator-permissions.md) is
separate from this proposal.

## Shared consumer and verification matrix

| Surface | Requirement for prospective verification |
| --- | --- |
| Gate, repository and session | Record the frozen candidate, test plan, eligible cohort and terminal verdict in coordinated contracts. Reuse structural and interruption checks. |
| Shadow runner, curator runner and boundary grooming | Keep submission rejection distinct from unresolved and pending outcomes. |
| Projection and window | Record acquisition and exposure separately from coverage. Keep the trace reader independent of evaluation. |
| Export, player host and recall | Keep pending knowledge out of delivery. Distinguish publication, selection, delivery, read, observed effect and confirmation time. |
| [Spectator knowledge view (#464)](https://github.com/CVX-Hull/enactive/issues/464) | Read candidate, base, target and result identities and terminal reasons from producers. Extend the [recorded knowledge projection](../contracts/spectator-view.md#recorded-knowledge-and-public-reports) and show missing evidence. |
| Historical and research readers | Keep version-qualified identity and observation age. Gate diagnostics supply no judge labels or calibration. |
| Programs | [Passive execution (#465)](https://github.com/CVX-Hull/enactive/issues/465) uses the gate and store interface. Disable needs gate-owned eligibility and [active stop (#467)](https://github.com/CVX-Hull/enactive/issues/467). [Monitoring (#468)](https://github.com/CVX-Hull/enactive/issues/468) and [fitting (#469)](https://github.com/CVX-Hull/enactive/issues/469) need runner-supported tests. The [programs proposal](programs-and-monitor.md) assigns interfaces. |

Live prospective verification needs approved acquisition of later sources, custody of
cohorts and exposure, a finite pending expiry and a delivery-version handoff
([live curator integration and delivery, #664](https://github.com/CVX-Hull/enactive/issues/664)).

## Contract cases

| Case | Proposed result |
| --- | --- |
| No later trace | Pending only under a concrete plan and bound; terminal defer otherwise. No new game call. |
| “Later” source already offered, copied or renamed | Ineligible. Exposure and original acquisition identity win over version, name or step. |
| Delayed evidence and the next session | Release the writer lock; settle or defer before another curator sees the cohort. |
| Stale base or concurrent restore | Reject and propose again against the new base. No rebase or cohort reuse. |
| Malformed or unsupported test or utility input | Structural rejection or an explicit unsupported-plan defer. Submitted tests are never executed. |
| Unknown semantic answer or no opportunity | Defer with the semantic or coverage gap. |
| Accepted prospective publication | Requires supported frozen tests and utility, an eligible cohort and a final base check. |
| Rejected submission | No knowledge change or draft promotion. Retain bounded diagnostics without hidden answers. |
| Restore, then a new proposal | The new tag holds the old snapshot with its old observation ages, and historical IDs stay reserved. An old-base proposal is stale. |

These cases bound source leakage, false freshness and loss of versioned knowledge.
