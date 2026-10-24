---
owner: lead
status: historical
date: '2026-10-24'
scope: Design and development record preserved on this date; current architecture/protocol
  and GitHub own behavior and remaining work
---

# Prepare the exact recorder allowance before Codex restart

The user requested a narrow project-scoped allow rule at the next paused gameplay
checkpoint. The current recorder's loopback command otherwise requests automatic
review on each call. Existing direct CLI rules do not match its wrapper. The
allowance is process permission only; native authority and campaign guards remain.

## Scope and alternatives

Add one rule in `.codex/rules/gameplay.rules` for this exact argument prefix:

```text
.venv/bin/python .runtime/campaigns/seven-day-campaign-005/preparation/capture.py lead|player
```

The actor position is a finite union, not a literal pipe or shell command. The
reason and ordinary command follow as arguments parsed by the existing recorder.
Use direct literal calls; returned JSON can be interpreted by the orchestration
tool. Shell scripts/redirection/heredocs do not inherit this allowance. No global
rules/configuration, Python-wide prefix, future-study wildcard, server launch,
GitHub command, native code, recorder code or permission profile is changed.

Reuse Codex's existing Starlark prefix rules, inline positive/negative cases and
`codex execpolicy check`; no custom policy parser or new library. Broad Full Access
would remove more of the sandbox boundary than this task needs. A new generic
campaign command/service is unnecessary for this scoped allowance.

Rules do not pin source bytes, enforce cwd or isolate actors. Use only the trusted
reviewed checkout. Recorder005 retains hash
`0b31b2e79f52c8194744b08a2788b7d61ff6fb03214e73d898c7f1f61bd6e227`;
its current admission/source/native/actor/time/input/frame checks remain. Lead
owns review and retirement when005 closes or the recorder changes. A new study
path requires review; never expand this prefix just to bypass an actual denial.

## Paused checkpoint and restart handoff

Protected PR117 accepted source dffc6dda029861273346926109d68643e2fe376c,
exact39181924309/39181942569 and merged-main39182126034. Actual005 load/identity,
player inventory and frames retained in `.runtime/campaigns/seven-day-campaign-005/`.
Player Pause19/status20 relinquished authority; lead Observe21/status22 confirmed
supported paused STRING_INPUT, no activity and empty live request/control/lease.
No recipe started or new game time advanced. This is a user-requested checkpoint,
not an unsupported-state failure or survival success.

Totals285whole/260day1/97lifecycle inputs,3816.986843seconds shared lifecycle;
72current-v3 plus one archived-v2 gameplay unknown and two control unknowns.
Latest supported normal5212919 / Spring61 08:01:59,119seconds from originalT0.
Original whole3813670.588570708 and day3823241.166884125 clocks continue without
reset. The owned controller42335 exited0 normally; native59507 remains paused.
Admission is `paused-for-user-requested-permission-setup`, so the recorder refuses
further contact. The permission/docs work ends its old source freeze explicitly;
it does not grant an automatic source rebind, resumed actor or renewed allowance.

Verify the reviewed source publication, exact/main CI and offline rule cases before
advising restart. Reopen this project after restarting Codex. Its project config
must be trusted for rules to load; no explicit user-config trust entry was found,
and no global file was changed. Activation is unverified until after restart.
Then inspect effective policy, a harmless command and current paused game state.
User-authorized resumption needs a prospective source/hash/remaining-budget review
before any new assignment; retain all original receipts, clocks and unknowns.

## Verification and limits

Inline examples cover allowed lead/player calls and nonmatching Python `-c`,
other helper paths/actors, setup/server, shell and GitHub commands. Run the mature
checker against representative positive/negative command token lists and inspect
its decision/matching rules. `allow` proves a rule decision, not live activation,
filesystem confinement, engine delivery or survival. Existing common checks and
independent review remain required for publication; no policy CLI validation in
portable CI is claimed. No game input is part of the rule check.

[Operator permissions](../operator-permissions.md) owns the lasting procedure.
[Official rules documentation](https://learn.chatgpt.com/docs/agent-configuration/rules)
requires trusted configuration/startup; [Auto-review guidance](https://learn.chatgpt.com/docs/sandboxing/auto-review#reduce-review-volume-without-weakening-security)
recommends narrow prefixes rather than broad interpreter allowances.
