---
owner: lead
status: historical
date: '2026-10-22'
scope: Dated candidate observations and qualification limits; not current instructions
  or live work status
---

# Independent seven-day attempt010: normally stopped partial run

## Outcome

Morgan survived **3,849 of the required 604,800 game seconds** in the fresh world
EnactiveSevenDayTen. No daily milestone or midpoint save/new-child/reload was
completed. The engineering lead ended the attempt after the user rejected its
pace. The player completed normal save, owned exit and `NormalFinish` with
disposition `stopped`; this is neither seven-day acceptance nor a resource-exhaustion
failure. The original full outcome remains open in
[#145](https://github.com/CVX-Hull/enactive/issues/145).

The run stayed frozen on source `77d02fa02ccd2dcc923517683dd330425718d2ec` and native
SHA-256 `40acb88b75cabf50a1b8a1134336c210d3f20503dcedd910fa2463019bdbcd56`.
All fourteen original setup/request/external pins recompute correctly. The source's
[exact CI failed](https://github.com/CVX-Hull/enactive/actions/runs/39870566385)
on the retained cached-Pause-source assertion. The independently reviewed isolated
repair passed its own CI, but was not applied during play. Source integration
started only after the complete run, all actual actors and owned processes ended.

## What the closed evidence establishes

| Original requirement | Actual disposition |
| --- | --- |
| Genuinely fresh default character | New Evacuee/Survivor world with random starting location; Morgan adopted by `sd010-create-adopt`, initial turn5212800 |
| Seven elapsed days | Incomplete: final normal source `860f04636909e22a664ab7daa7d7fc5d5591a3b4a4fd8d6b884cd80bbe1dbb48` is turn5216649, showing09:04:09 versus08:00 initially |
| Meaningful survival decisions | Bounded food pickup, travel/threat decisions, trading, clothing, shelter return and warming; final comfortable/full-health scene. Sustainable water, house arrival and multi-day needs maintenance unproved |
| Scoped memory/procedure use | Seven pinned learning006 procedure PNGs actually presented. `sd010-procedure-ration-pickup-002` selects `dl006-stocked-locker-v2` narrowly for cupboard pickup/count/verification; child `sd010-procedure-one-confirm` retains the inherited use ID. No newly adopted procedure revision or causal learning benefit |
| Actual clean successor | Registered `sd010-clean-handoff-002`; genuinely separate successor context presented ten campaign and seven procedure PNGs, then `sd010-s1-claim-001` and separate charged `sd010-s1-readmit-001`. Substantive scouting/trading/clothing/warming follows. Presentation is not proof of attention |
| Midpoint save/reload | Not exercised; the final save cannot substitute for midpoint new-child/exact reload |
| Useful play during bounded advice | Shelter entry `sd010-s1-shelter-enter-001` overlaps an actual claimed advisory job; later player dispositions retained. Coverage is incomplete, not continuous oversight or demonstrated advice benefit |
| Final normal lifecycle | SavedCheckpoint `sd010-s1-late-save-transition-record-001`, OwnedNormalExit `sd010-s1-late-exit-yes-001`, and stopped Finish `sd010-s1-late-stopped-finish-001`; completed Work is null |
| Independence | Actor-owned MCP inputs, current-source records, clean-context handoff and unchanged pins support procedural separation. No observed alternate executor, live patch or save editing. Lead supplied engineering/admission/closure, not recorded ordinary inputs. Encrypted lead-message bodies in actor exports prevent independent verification of every message's wording; no security-isolation or mental-attention claim |
| Original accounting and ending reserve | All costs, failures and unknown ACKs retained; original deadline1792797443.761788 unchanged. No extension or failed-authority renewal |

Independent review checked the original frozen profile, raw SQLite rows,
actor/output images, journal and selected real source PNGs, rather than accepting
actor summaries. All ten campaign and seven procedure images in the successor
handoff, seven original procedure images and 38 advisory images matched their
original byte hashes. Four unfinished Work records remain; stored Work does not
prove objective completion.

## Costs, uncertainty and coverage

| Measure | Retained total |
| --- | --- |
| Requests | 302:264 partial,30 completed,6 blocked,2 unknown |
| Charged primitive mappings | 565:562 returned,3 unknown |
| Requests with zero / one / multiple mappings | 42 /188 /72; not model-call or useful-action counts |
| Canonical PNG archive | 1,422 files /169,952,845 bytes |
| Mission Start to Finish's stored last_wall | 5,528.325 seconds; includes setup, play, handoff, ending and waits |
| Start to controller-close last_wall | 5,684.544 seconds; shutdown advanced only last_wall by156.219s |
| Advisory work | 34 completed jobs,2,040 charged seconds of3,600; all accepted within original windows |

Three primitive ACKs remain unknown: `sd010-menu-019`,
`sd010-s1-late-save-yes-001` and `sd010-s1-late-exit-yes-001`. Their
`native_ack:null` remains unchanged. Creation/save have explicit lifecycle-effect
reconciliation; exit has the owned process-return proof. All unresolved effects,
unreconciled counts and native/control pending slots are zero at Finish. An
observed effect does not rewrite a lost ACK as returned.

Completed advisory coverage ends at request sequence294 and memory654; advice034
omits72 sources. One subsequent zero-charge unreviewed job covers294–297/memory655,
and closure requests are outside completed coverage. The phone-flashlight candidate
was proposed but not adopted as a new procedure; later trade invalidated its
carried-phone precondition. A rejected post-completion correction and original
pending-result collection remain recorded. No complete-trajectory coverage claim.

## Responsiveness findings and next work

The original activated player made122 MCP calls; adjacent nonoverlapping call
gaps were6.665s median,18.091s nearest-rank p95 and117.428s maximum. Successor
activated-role tool durations were3.376s median,10.043s p95 and15.295s maximum;
its inter-call gaps were8.595s median,27.770s p95 and151.170s maximum. Gaps include
reasoning, other work, scheduling and transport, not isolated inference. These
measurements do not qualify acceptable useful-progress cadence.

Response counters reconcile per response, turn and thread, including final output.
Activated original/successor/adviser turns respectively record30,978,978 /
62,811,043 /59,766,713 total tokens, including repeated context, tools and reporting.
They are not unique context size, isolated inference, billing or a model comparison.
Preflight totals remain separate in private measurement evidence. Roles overlap;
their durations must not be added as elapsed wall time.

An early event-log audit inferred model-visible nested result duplication. That
inference is retracted: persisted MCP event envelopes differ from forwarded model
output. The [responsive-player brief](../changes/060-responsive-player.md) records
the corrected observation layers and direct-result redundancy. Compact decision
presentation, automatic plumbing, bounded working context and useful closed-loop
execution remain the relevant engineering work. Longer condition-based advisory
waiting can reduce idle model round trips, but does not eliminate them. Neither
an offline byte reduction nor smaller model name establishes responsive play.

The next short configuration trial uses the user's selected Luna/low profile;
its exact source, host, finite resources and numerical cadence/quality criteria
must be frozen before play. A long campaign follows demonstrated responsiveness;
none of these new criteria retroactively changes010's frozen acceptance.

## Closure and retention

Original player, successor and adviser are actually FINAL with all tool calls
terminal. NativePID20540 exited0 through the registered normal flow. Controller
session74966/PID18430 then exited0; both exact PIDs and port8766 listener are absent.
Before/after SQLite copies have identical requests, primitives, memory,
reservations, advisory jobs and commands; only metadata last_wall advances.
The closed journal preserves its original4,469-line prefix plus two shutdown events.

Under standing user-directed stale-world cleanup, all51 save files were archived
and member-hash verified before retiring the closed world from the active menu.
Archive SHA-256:
`ee063070b549afa49a2bedbc6a71b7ba90078053d42529b164ff50cc70bff8be`.
All191 files in the three retained worlds are unchanged. No save contents were
edited or used to manufacture a game outcome.

Private evidence is retained under
`.runtime/campaigns/independent-seven-day-010/closed-evidence/`: original receipts,
actor traces/hashes, SQLite backups, journal snapshots, final source, closure
verification and save-retirement manifest/archive. Canonical source PNGs remain
in the mission evidence directory. Raw hosts, credentials and saves stay out of
Git. Source tests, actual gameplay, responsive configuration admission and
protected publication retain their separate gates.
