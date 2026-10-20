---
owner: lead
status: historical
date: 2026-10-20
scope: Registered owned launch source composition and absolute-deadline passive observation; no real game launched
---

# Registered launch without identity adoption

The mission runtime now implements lifecycle `launch` through the existing fixed
NativeProcess adapter. It accepts only a source-free root and the admission's
world/character and binary hash. This source increment precedes creation, identity,
charged Resume, save/reload and independent gameplay; it does not complete #155,
#144 or seven-day readiness. [Protocol](../protocol.md#integrated-mission-lifecycle)
owns current behavior; the [earlier ingress report](2026-10-20-mission-ingress.md)
retains the previous checkpoint's scope.

## Qualified source behavior

- Preparation, existing-process guard, exec and readiness share the original
  root/mission wall deadline and preserve the cleanup reserve. Process launch
  consumes no primitive game input and never assumes menu game time is zero.
- NativeProcess receives a required cancellation callback. Checks before/after
  preparation and after committed spawn preserve the handle even if Pause or a
  deadline arrives during exec. No signal, arbitrary script/path or PID adoption
  is exposed. A live or unverified owned launch cannot silently be replaced.
- Runtime requires paused empty host writers/native inboxes, unchanged actor/epoch,
  controller boot and operator counter, a retained running child, and a fresh
  paused untouched MAIN_MENU with an actual frame and empty error. An unrelated
  normal scene, human takeover or stale/error-bearing response cannot establish
  readiness. The menu source is passive: no identity, normal facts, clock anchor,
  map, input binding, lease or Resume follows.
- Trusted passive Observe carries the absolute deadline through bounded command
  queueing and native publication. It cannot start a new relative timeout after
  the root expires. Public JSON accepts no callback or absolute-deadline authority.
- Cached status exposes last sampled process facts, explicitly without restoring a
  handle. Shutdown journals custody without killing the child. Reopening the same
  admission conservatively marks prior attempted/uncertain launches unavailable;
  immutable SQLite request history never acts as an outbox. Process absence/exit
  code alone cannot resolve normal save/exit, and later exit handling remains pending.

## Verification and limits

Common checks passed821 Python tests plus viewer, Ruff, four dependency contracts,
Python/JavaScript syntax, document links/stewardship, governance and pinned diagram
receipts. Thirteen new launch-composition cases use an explicitly named fake process
boundary and real temporary file transport. They include custody after Pause/timeout,
unrelated normal play, stale/error menus, live-child replacement, changed admission/
binary, prepared-launch crash/reopen, no replay and zero Resume/action/key publication.
Process tests migrate every launch caller to required cancellation. Controller tests
check bounded queue refusal, no post-deadline Observe publication and native request
deadline limits, alongside existing mission/Resume queue/deadline regressions.

Independent review found two real defects: an error-bearing menu could count as ready,
and readiness Observe used only a relative timeout after queueing. The first new
regression failed the old source; both defects were repaired and independently
retested. Stale native evidence already failed retention, and now rejects before
readiness publication as well. Earlier fixture failures are retained: shared schema
already rejected borrowed launch authority, and the retired unsupported-launch test
needed to exercise an actually unsupported, fully bound load request. Production
validation was not relaxed to pass those tests.

The reviewer independently passed47 launch/process/deadline tests and cleared this
bounded source slice. There was no real native launch, creation, load, save, game
input, model run or autonomy result. The installed wire4 binary/patch is unchanged;
its earlier menu-only graphical probe remains separately scoped. Registered normal
exit and recovery of unavailable custody still require implementation; no forceful
cleanup fallback is granted by this report.
