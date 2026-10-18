---
owner: lead
status: active
review_trigger: Round 008 native findings, planner verification or publication changes
---

# Native recovery and planner verification

Round 008 source and native scenarios have passed local acceptance and independent
review; protected publication remains pending at this source checkpoint. The planner port is bounded and tested,
but no live provider or autonomous supervisor is connected. Native recovery now
works without the former Pause/Observe workaround. [Brief](../changes/008-native-recovery-planner-port.md).

## Verified source and portable behavior

The Pause repair preserves scene revision for a transport-only pause and excludes
only `paused` from cross-frame scene comparison. Same-frame metadata remains
immutable; actual same-revision scene contradictions still dispute evidence.
The new Pause regression failed before the repair. Independent review found no
material defect in the coordinated native/evidence change.

The bounded planner is injected trusted code, with immutable inputs, validated
candidate data, independent cancellation/deadlines, one physical call slot and
conservative cost accounting. Independent review found three defects: oversized
metrics escaped freeze, contradictory overrun usage released reservations, and
continuations could replace their original start evidence. Repairs and new
regressions passed independent rereview. No model provider was invoked.

The integrated common run passed **231 Python tests**, viewer regressions,
Import Linter, syntax, documentation, diagram and governance checks. Planner-only
integration passed 22 tests. Local evidence is under `.runtime/evidence/round008/`:
`pause-regression-before.txt`, `evidence-regression-after.txt`,
`planner-integrated.txt` and `integrated-common.txt`. A hosted run exposed the claimed-timeout fixture expiring before its fake bridge
claimed the key. The repair advances only the controller test clocks after claim,
retains a real watchdog, and keeps frozen/no-replay assertions. Independent review
and all 45 controller tests passed; the integrated common run again passed 231
tests. The first repair attempt failed reconciliation because only one clock moved;
that failure is retained. A later exact-head run passed on the PR event but failed
on push: the final-gate fixture missed its transient claimed file. Its replacement
uses an explicit after-claim signal and a bounded release barrier held until Pause,
with `finally` cleanup and the same no-delivery/revocation assertions. All 45
controller tests pass, and independent rereview found no weakened assertions or
remaining defects. The failed hosted log is retained; final exact-head CI and
protected publication remain pending.

## Fresh native candidate and actual gameplay

A fresh pinned build used owned workspace `/private/tmp/cdda-player-build-o15n7x9s`.
Its unsigned build binary SHA-256 is
`a25ab8acbb4a21083ab856b3b294252f95c8b29796eee2cbe541386c7440abc6`;
the signed binary used for the production-candidate probes below was
`080d021443836df01c8f770b234c8b5ca6e9305d3951c80052631904fbc2f1a4`.
`native-source-candidate.json` and `native-build-receipt.json` retain provenance.
The prior binary/build receipt remains available for rollback. Native probes use
an ordinary window and the explicit project userdir; no saves were edited.

During investigation this candidate was replaced by a separately instrumented
diagnostic build, unsigned SHA-256
`8e9c7ff4a9192b4e13ea388702ff0e7b9b84f6fbd3e507ccd6197b9c8d55aebc`,
installed SHA-256
`9da9e6e5187396a7edac299dd5d33a537195bb9256f51d98882705a38f4ed0db`.
`diagnostic/build-manifest.json` and `diagnostic/install.txt` record that transition;
receipts prefixed `diag` belong only to diagnosis. Temporary renderer logging is
outside the production diff. The diagnostics were subsequently removed and the
production source rebuilt; the final production probes below repeat the relevant acceptance.

A second diagnostic adds pixel counts before/after UI callbacks and ImGui. Its
build SHA-256 is `bc2c40780aeb60bf002b14d6b1d4c547f1912ccc73e4e215c0233ffa236c27a1`;
its installed SHA-256 is `4d3635077a88e4ba33135e455ef4e6ad91b3a4d49f21ac3b466f7338551c17c5`.
The `diagnostic/pixel-build-manifest.json` and `pixel-install.txt` receipts supersede
the first diagnostic installation only, not the production evidence above. Pixel
reads can perturb renderer timing; diagnostic success alone cannot prove a repair.

| Actual probe | Observation and evidence beneath `native/` |
| --- | --- |
| Normal play Pause | Same scene revision, distinct unpaused/paused frames; historical source retained and current evidence generation advanced (`10-normal-pause-evidence-result.json`) |
| Immediate interruption | One unpaused WAIT probe opened the real owned confirmation in 164 ms, without a preceding Pause/Observe workaround (`immediate_yes_second/result.json`) |
| Explicit YES | One answer delivered; subsequent observation reached normal play while paused (`23-explicit-yes.json`, `24-after-yes.json`) |
| Boundary changed before claim | Later attempts reached a zombie distraction prompt; recovery returned `not_applicable`, without owning or answering that unrelated prompt (`immediate_no/result.json`, `28-no-owned-prompt.json`, `immediate_no_second/result.json`) |
| Capture failure | An owned empty directory deliberately made PNG writing fail; native observation reported `frame_ok=false`, Resume and debug recovery rejected; removal restored capture (`34`–`39`, `69`–`71` named receipts) |
| Raw debug and nested load | Real tutorial terrain validation errors nested under character load; arbitrary I/C/movement rejected, one scoped continuation delivered, next error got a new identity and rejected the old request (`47`–`54`) |
| Lost replies | Labeled host-read fault injection withheld real native replies. Both current ordinary/control pending IDs remained visible and frozen (`60`–`62`). The ordinary request here was Observe, not a gameplay action. |
| Restart | Normal controller restarted paused; explicit Observe reconciled. Unknown gameplay admissions from real load/save timeouts and the delivered-but-unobserved debug result remained recorded (`63`–`65`). No automatic replay. |
| Native negative gates | Direct invalid wire envelopes under the sole controller lock rejected expired/duplicate IDs, stale session/generation/boundary/revision/frame and old boot/revoked counters (`wire-negatives/`). These are labeled wire fault probes, not public-UI success cases. |
| Save | H-world character used the normal Save-and-quit confirmation. The host wait expired, then Observe reconciled at the main menu; the unknown input admission was retained (`41`–`43`). |

These single-run timings are not a latency distribution or a universal stop bound.
The initial immediate probe found no eligible activity and sent no recovery request;
its failure is retained. The early NO attempts were replaced by unrelated danger prompts and did not
establish owned-NO behavior. The later production probes below supply that evidence.
Source/build/portable checks cannot substitute for native execution.

## Corrected interpretation and content follow-up

The initial visual reading of a raw-debug frame as blank/partial was incorrect.
Independent original-size inspection of `68-after-native-takeover.png` confirms
readable error text and Space/I/C instructions. `diagnostic/pixel-byte-audit.json`
compares the saved PNG bytes: header, field labels, filepath and instructions are
identical to the readable reference. Nonblack pixels differ from 8117 to 7909
because the error message is shorter. The renderer-target/clip hypotheses are
withdrawn; no production renderer repair is warranted by this evidence.

The mistaken interpretation led to temporary diagnostics and a stalled LLDB
attachment, whose owned processes were stopped without security changes. Those
attempts remain recorded. After removing diagnostics, the rebuilt production candidate
has unsigned SHA-256 `0405e34af99e7b60f9da67fd37e9cca8769b1d1c294eb622af80999be4854b37` and installed SHA-256
`e3c022b5da440d2e4a31fc537ea07c988c2a767bf96197b83de4c7224d47bf87`. `diagnostic/restored-receipt.json`
records source hashes and the exact restoration comparison. The final acceptance below used
this distinct candidate. This is a lesson in verifying
visual findings independently against retained artifacts before changing code.

Tutorial ID definitions exist in both pinned and installed data, with matching
hashes. Tutorial creation enables its dedicated mod, but the preserved save load
reports invalid terrain/special/trap IDs. Missing active content during load is an
inference, not a verified persisted-world diagnosis. See `tutorial-diagnosis.json`.
Errors are preserved and continued individually; future errors are not suppressed.
No valid tutorial gameplay outcome or repaired save is claimed.
[Issue #47](https://github.com/CVX-Hull/cdda-player/issues/47) owns this separate
content-load diagnosis and repair; #8 does not claim to repair game data.

## Final production scenarios

The final production binary is the restored `e3c022…47bf87` candidate identified
in full above. The Day character was saved normally. A separate **Recovery Eight**
world and **Morgan Vale** character were created through the normal CDDA UI with
default world settings and the built-in Sheltered scenario, default Survivor
abilities and random permitted starting location. No debug powers, hidden-state
inspection, save edits or validation bypasses were used. This sheltered setting
avoids the unrelated danger prompts in the older worlds; it does not establish
combat or general survival competence.

| Scenario | Actual result and retained receipt under `native/` |
| --- | --- |
| Immediate unpaused interruption, owned NO | Prompt opened in 149 ms; explicit NO delivered, then observed `activity_poll` while paused; WAIT subsequently finished naturally at 09:00 (`sheltered_owned_no/`, `restored15`–`18`) |
| Actual gameplay and recovery reply loss | A real WAIT key and explicit owned YES both executed while selected host response reads were withheld. Both pending identities remained visible and frozen. Normal service restart plus explicit Observe reconciled capacity and retained unknown histories without replay (`loss01`–`09`, `lost_gameplay_control/`, `fault_actual_wait_*`) |
| Activity finishes before claim | Labeled host publication delay let the actual thirty-minute WAIT finish after recovery admission. Native returned `not_applicable` at normal play, with no prompt/input injection (`finish-race-delay.json`, `finished_before_claim/`). This is a timing fault probe, not natural-latency measurement. |
| Ordinary input during activity | Ordinary key and Resume each returned 409 requiring a normal-play/menu boundary; one explicit recovery then opened the owned question (`final06`–`08`) |
| Graphical spectator | Lead inspected the real owned question, clicked **Yes · interrupt activity**, then **Observe**. UI showed normal play, paused, and retained unknowns (`final09`, `final-viewer-normal-paused.png`; session `20261017-214625-1f583165`) |
| WAIT backlog and Pause | After YES, one subsequent normal turn advanced exactly one second and remained normal play; Pause preserved the scene revision (`final10`–`14`). This proves only this WAIT path, not every backlog. |
| Normal save/reload | Morgan saved normally, reloaded in the same process at the saved turn with a new session, and old-session input rejected (`final16`–`20`). Day/H and Recovery Eight saves are retained. |
| Raw debug nested in real load | Tutorial load reached the real terrain error. I, C and movement rejected; one scoped Space delivered; the next error got a new identity and rejected the old request (`final21`–`29`). The raw frame is readable. |
| Capture failure | An owned empty directory made PNG writing fail. Current observation had no frame, and the previously valid frame could not authorize continuation; removing the fault restored capture (`final33`–`35`). |
| Native takeover/fallback | Native Escape invalidated prior recovery generation; old continuation rejected. One native Space advanced only to the next actual error (`final36`–`38`). Incomplete tutorial load was quit without saving. |

The capture driver first expected 409 for an empty frame string but received a
correct HTTP 400 argument rejection; a second attempt reused an exclusive receipt
filename and aborted. Both faults were removed in `finally`. The corrected probe
used the last good frame while current capture failed and received 409. Retained
receipts distinguish driver mistakes from native failures; earlier provisional
attributions were corrected against the actual JSON.

## Controlled native revocation ordering

A separate acceptance-only native build inserted one-second maximum timing
barriers before claim, before the existing final commit checks, and after commit
but before actual event delivery. Independent review verified the exact diff adds
no game-state change, bypass or replacement gate. Public recovery and public Pause
remain the input paths. Build SHA-256:
`6413bcbcbd9557825bd147ae9a4f23af9e7e13ff4676daf304f7c96fd35256eb`;
installed SHA-256:
`dc92fd08b5aeb3a430c38aa10a3eb2cfd381ddf871346764c639eaaa27594368`.

All three marker traces show controlled release, not watchdog expiry. Pause before
claim and before commit produced rejection with the same owned prompt, revision
and generation. Pause after commitment could not undo the one answer: the next
observation showed normal play and remained paused. `gate-probe/{before_claim,
before_commit,after_commit}.json` records order, public responses and resulting
native boundaries. These establish gate ordering under injected timing, not
production latency or preemption inside synchronous engine code.

The exact retained production source and binary were restored afterward;
`gate-probe/restored-receipt.json` verifies byte equality. The `final*` and `finish*`
production probes ran after that restoration. All native, fault-server and debugger
processes were then stopped; no global tooling/configuration was changed. Builds,
saves, diagnostics and unknown admissions remain owned local evidence.

## Coverage, maintenance and publication

Hook coverage is limited to the pinned engine input/activity polling and exact
owned cancellation queries, plus raw debug prompts nested under ordinary input.
Unknown/unrelated prompts remain unsupported and retain native fallback. No
universal interrupt deadline, synchronous-handler preemption, general noninterruptible
activity support, repaired tutorial content or model performance is claimed.
Production prompt timings observed here include 149 ms and the earlier 164 ms;
these are individual cases, not a distribution. Native timing instrumentation and
host response/publication faults are separate evidence lanes.

The [manifest](2026-10-17-native-recovery-planner-manifest.json) indexes retained
423 retained artifacts with hashes; the tables above identify candidate lanes. Local media are not available merely
because this report is public. Existing recovery diagrams keep the same flow and
now label the implemented public interfaces accurately. Lead inspected the rendered
recovery diagram for legibility and consistency with the current contract. The overview and runbook
state the new behavior and remaining limits. Control records retain failures and
separate portable, native and usability evidence. #9 owns possible future native
runner reuse; the one-off drivers are not a maintained regression service.

Independent native/evidence review found no blockers within this scope. Documentation
review caught a stale future-surface sentence and a manifest schema mismatch; both
were corrected. Exact-head hosted CI, protected merge, Project closure and
source-worktree cleanup remain pending at this report checkpoint.
