---
owner: lead
review_trigger: Finite-test watch policy, target binding, process ownership or acknowledgement changes
status: active
---

# Supervise a finite development test

The [test supervisor](../../tools/campaign_supervision.py) wraps the maintained
[campaign custodian](campaign-run.md). It belongs to test operation, outside the
player context. The independent guardian owns the original custody deadline, Pause
receipt and owned wrapper cleanup; the existing custodian owns native input,
original allowances and native/host cleanup. The gateway serves the page, relays
passive status and source reads, forwards bounded viewer reads and verified Pause, and
never actor tools. A separate read-only viewer runs outside supervision.

Every launch selects one attention policy, recorded in `watch-start.json`:

| Policy | Use | Stop rule added to custody, Pause and uncertain-delivery stops |
| --- | --- | --- |
| `best-effort` | Development runs (owner decision D1, [#369](https://github.com/CVX-Hull/enactive/issues/369), 5 November 2026) | None. The gateway offers no operator check. An unnoticed bad loop or death can continue until the original finite limits end the run; the lead cancels on first observed death or replacement. |
| `required` | A frozen test that explicitly requires continuous attention | No completed operator check within 45 seconds stops the run. |

The custody deadline is the independent outer timeout in both policies: the
guardian terminates the custodian at the original `wall_seconds` bound, whatever
the operator conversation is doing. Neither policy generates acknowledgements
automatically.

This is a Mac finite-test helper. Source delivery grants no gameplay/provider
spending or new admission. General unattended operation remains unqualified.

## Freeze, launch and inspect

1. Prepare the exact clean source and fresh `campaign-run/5` package through the
   [campaign procedure](campaign-run.md). Resolve scope, spending, original
   resources, ending reserves and stop rules before admission. Preserve original
   saves and failed chains; old experiment launchers stay historical evidence.
2. Supply the selected route's credential: export its environment variable, or
   map it to your own keychain item in the git-ignored `.runtime/credentials.json`
   ([setup](../setup.md#install-the-generic-gameplay-host)). The supervisor reads a mapped
   item with `security find-generic-password` only when the variable is unset,
   and passes the value only to the custodian; gateway and keep-awake children
   receive executable lookup and locale. No global permission entry is installed.
3. Invoke from the selected checkout through engineering command permissions:

   ```sh
   .venv/bin/python -m tools.campaign_supervision --attention best-effort --run .runtime/computer-sessions/SELECTED
   ```

   Use `--attention required` only when the frozen test requires the 45-second
   policy; step 5 then applies. Add `--runs DIR` to let the viewer list archived run
   directories beside the live run.

4. Under either policy, open the exact printed gateway URL to observe play and reach
   Pause. Under `best-effort` the page shows no check button and the gateway refuses
   check records, so an optional check can never stop a healthy run. The supervisor
   starts the viewer as an unsupervised child on a free loopback port; if the page shows
   **viewer unavailable**, play, checks, the frame and Pause are unaffected, and the
   cause is in the run directory's `viewer-stderr.txt`. Its exit is never a stop.
5. Under `required`, inspect the current session,
   status and decoded source in the check panel, then click **Record operator check**. Confirm the
   accepted number. Target one completed check every15 seconds. The first must
   finish strictly before readiness plus45 seconds; each later completion must
   precede the prior accepted observation plus45 seconds and the original custody
   cutoff. Equality is too late. A failed or unconfirmed guardian acknowledgement
   does not renew it. Missing browser confirmation is unknown: the guardian may
   already have accepted the check. Use Pause when control is uncertain.
6. Use the same page's **Pause** for immediate control and choose its reason (loop,
   fault, spend or other). The page asks for a reason, but the gateway never refuses a
   stop over one: it stops first, then records the reason as given, or `unspecified`
   when it is missing or unknown. It forwards an empty Pause to the custodian and
   records the reason in `watch-terminal.json`; Pause never waits for the viewer. No
   check renews after Pause. Refreshing the page cannot resume or reopen a
   stopped/partial package.

The button requires a trusted explicit click, a visible check panel, decoded in-viewport
pixels and current displayed status, all taken from the custodian's status and source
reads, never from the viewer. The gateway checks session, source/digest,
increasing sequence and displayed-status age within12 seconds, then waits for
the guardian's exact confirmation. This checks displayed retained evidence;
human attention, physical paint, continuous capture and useful game effects
remain separate. Repeated or older retained pixels do not become new captures.

## Failure and owned cleanup

The guardian performs no HTTP work. Blocked source reads, delayed checks and
partial confirmation cannot suspend its deadlines. Renewal uses actual
confirmation completion; checks racing with Pause are rolled back. Original
custody also bounds terminal coverage. The receipt's wall-clock end is mapped
onto the monotonic clock from readiness, so "terminal after the last accepted
check" allows less than `CLOCK_MAPPING_TOLERANCE` (0.25 s, the same bound the
check-row mapping uses) for drift or steps between the clocks; the custody and
watch deadlines stay strict. Incomplete startup JSON is retried under
the original clocks because producers expose the pathname before buffered close;
complete invalid marker objects fail.

The expected Pause receiver comes from the newly created custodian handle, not
retained process JSON. On the supported Mac deployment, the gateway verifies the
connected loopback socket against that receiver before posting Pause. An
uncertain receiver gets no POST; renewal stops and owned cleanup proceeds.
This does not qualify another OS or hostile-process isolation.

On stop, signal, startup or supervision failure, custodian/gateway termination
is requested before bounded waits. Every launched child, including the viewer and Mac
`caffeinate`, receives an explicit cleanup result. A viewer that exits early or cannot
start is recorded but is not supervision loss, and never fails startup. The shared group helper acts
only on groups created by those exact launches. Keep-awake is process-scoped.
Cleanup errors stay visible; arbitrary OS hangs, abrupt supervisor death and
native application responsiveness remain limits.

Generic stopping needs no Save, model reply or normal native exit. The player
chooses ordinary actions. Persistence, native exit, host settlement, supervision
coverage and owned absence stay distinct. Fencing inputs does not pause a live
game's clock. Apply save/reload/exit criteria in their separately frozen lane.

## Retained artifacts and assurance

| Artifact | Current version and meaning |
| --- | --- |
| `watch-start.json` | `campaign-watch-start/3`; exclusive reservation before children, binding session/source, manifest SHA256, wall/monotonic start, `attention`, `watch_seconds` (45 for `required`, null for `best-effort`) and the planned `viewer_port`, which the gateway must match. Prior/partial markers refuse; never delete to rearm. |
| `watch-attempts.jsonl` | `campaign-watch-attempt/1`; source/digest, sequence, observation/start/recorded clocks and active/ending phase. Observation/guardian values are monotonic seconds derived from original wall timing; the shared-clock relationship is checked, not assumed exact. |
| `watch-terminal.json` | `campaign-watch-terminal/3`; attention policy, accepted checks/completion/prior-observation clocks, raced checks, reason, `pause_reason` (`loop`, `fault`, `spend`, `other` or `unspecified`; null when the owner did not press Pause), exact children (the viewer with its pid, port and `supervised: false`, or its launch error), bounded cleanup and custodian disposition as separate facts. |
| `viewer-stdout.txt`, `viewer-stderr.txt` | The viewer's own output, created exclusively by the supervisor; diagnostics only. |

Current `computer-start/1`, `computer-ready/1` and `campaign-receipt/3` must match
the fresh owned custodian/session/source and chronology. Under `required`, a missing
first check or late terminal coverage cannot certify supervision; under either policy,
a terminal receipt after the custody deadline, substituted receipt/manifest or unresolved cleanup cannot
certify supervision success. No wrapper receipt accepts gameplay or restores
custody.

[Guard/process tests](../../tests/test_campaign_supervision.py),
[local HTTP/socket tests](../../tests/test_campaign_watch.py) and
[UI behavior tests](../../tests/test_campaign_watch.cjs) exercise maintained code.
Fixtures establish protocol behavior, not native game effects, human takeover,
model competence or real timing. Retain failures before temporary-test pruning;
use a fresh owned directory. Actual use remains a separately frozen lane.

The engineering lead owns maintenance. Replace this helper when the
custodian/observer supplies the same independent verified-check deadline and owned
cleanup, or retire it when the finite-test watch policy is explicitly retired.

[Operations index](../runbook.md).
