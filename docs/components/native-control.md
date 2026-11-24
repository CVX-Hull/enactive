---
owner: lead
review_trigger: Native observation, input delivery, mechanical custody or stop changes
status: active
---

# Native control and visible observation

The [computer package](../../harness/computer/) owns mechanical custody and basic
input. It has no game/player/tooling imports. [Exact contract](../contracts/computer-control.md)
and [architecture](../architecture.md) define the boundary; CDDA preparation stays
outside it. The current adapter targets macOS SDL; a second game is unqualified.

## Internal responsibilities

| Part | Owned state / failure responsibility |
| --- | --- |
| [Launch](../../harness/computer/launch.py) | Exact native process/group, exclusive one-shot marker, inherited shared-lock descriptor and socketpair; no PID adoption or global process scan. |
| [Native adapter](../../harness/computer/native/bridge.mm) | Actual default-renderer capture, basic SDL events, real-input precedence, mechanical geometry and nonblocking bounded packet work. |
| [Channel](../../harness/computer/channel.py) | Socket framing and bounded receipt/state slots; independent permanent stop path; no receive-thread file/DB writes. |
| [Runtime](../../harness/computer/runtime.py) | One serialized writer, actor capabilities, original IDs/deadlines/capacities, issued sources and exact result collection. |
| [Store](../../harness/computer/store.py) | Fresh `computer-session/1` SQLite operations/source provenance; cannot reconstruct runtime custody. |

The native adapter validates the exact inherited shared-lock descriptor/file
identity and retains its reference for the native lifetime. Descriptor closure,
not `LOCK_UN`, releases an owned reference. Native sets inherited descriptors
close-on-exec. The host/MCP receives no native descriptors; only the provider host receives its selected key, while MCP/native receive none.

Native callbacks perform bounded nonblocking socket work and never publish files
or SQLite. The custodian publishes image bytes/records outside the game thread.
One pending packet and a separate Pause receipt preserve original terminal results
under backpressure. This bounds bridge publication coupling; it does not cover
upstream save I/O, PNG CPU or arbitrary OS hangs.

## Pause, unknown effects and restart

Pause latches before executor/DB waits and sends through a separate bounded path;
if framing cannot complete, write-side shutdown signals EOF. Native neutralizes
only owned presses and retains the original receipt before the separate Pause
receipt. Report stop-requested separately from native-confirmed Pause.

Partial/unknown input permanently stops new input. Preserve original IDs and
collect late results; never replay/rearm. Capture equality/age and game phase do
not gate keys/text. Clicks require issued source geometry. Real native input
precedes synthetic events and fences automation without discarding human input.
Restart reads no old inbox and reconstructs no authority.

### Stop, collection and recovery views

These two diagrams are current. Boxes are logical states, not processes; labelled
arrows are the transitions or reads the
[contract](../contracts/computer-control.md#computer-operations-and-custody) allows.
The paragraph under each diagram is its text equivalent, and the numbered list after
them gives the operator's steps.

```mermaid
flowchart TB
  accTitle: Current original request collection
  accDescr: The client assigns the request ID before sending. Complete local refusal proves no submission only when established. Admitted or uncertain work retains original collection without replay. Partial or unknown physical delivery permanently stops new input. Read results never renew custody.
  P["Player chooses basic control or player service"] --> I["Client assigns original operation ID"]
  I --> W["One current authenticated ingress"]
  W -->|"Verified no submission"| R["Inspect refusal<br/>New explicit corrected choice allowed"]
  R --> P
  W -->|"Admitted or uncertain"| C["Collect exact original computer_result<br/>or player_result"]
  I -->|"Lost response"| C
  C -->|"Original receipts and sources"| E["Interpret actual effect<br/>No replay or success inference"]
  C -->|"Partial or unknown input"| S["Permanent input stop"]
```

Current. “How is one submitted request collected, and when may the player submit a corrected replacement?”
Only a verified complete local refusal permits a new corrected choice; admitted or
uncertain work is collected under its original ID, and partial or unknown input
stops input permanently. A lost response is collected under the same ID. After
collection the player interprets the actual effect before its next choice, unless
input stopped.

```mermaid
flowchart TB
  accTitle: Current permanent stop and original collection
  accDescr: There is no Resume or phase-based recovery. User Pause, native takeover or uncertain input permanently fences automation. Original results remain collectable without replay. Native manual recovery and exact owned cleanup do not restore authority or certify a save.
  A["Active mechanical custody"] -->|"User Pause or native takeover"| S["Permanent input stop"]
  A -->|"Partial or unknown input"| S
  S -->|"Read exact original ID"| C["Collect receipts and retain uncertainty<br/>Never replay or renew limits"]
  S -->|"Operator chooses"| N["Ordinary native recovery<br/>Save or quit through visible controls"]
  C --> E["Exact owned cleanup<br/>Normal exit distinct from forced signals"]
  N --> E
  E -->|"Separate explicit admission only"| F["Fresh coherent session<br/>No authority restored from history"]
```

Current. “What happens after Pause, takeover or uncertain input?” Automation stays
fenced, original receipts are collected without replay or renewed limits, and any
further play needs separate explicit admission of a fresh session. The operator may
instead recover through ordinary native controls; both paths end in exact owned
cleanup, with normal exit kept distinct from forced signals.

#### What may an operator do by hand after a permanent stop?

This expands the operator branch of the recovery diagram above.

1. Pause is independent and permanent: no further automation runs, and the original
   receipts are retained. It cannot undo events already delivered or cancel every game
   activity.
2. Use the game's ordinary native controls, interpreting the screen and interrupting an
   activity if needed. The harness supplies no activity, menu or debug recovery handler.
3. Observe the actual effects, and record the intervention and its uncertainty.
4. Save or exit if appropriate. The harness certifies neither the recovery nor a save,
   and reports no success for either.
5. Finish with exact owned cleanup and evidence that the owned processes are absent.

See [Pause procedure](../operations/pause-timeout.md#operator-recovery).

## Portability and verification

The SDL2 adapter maps uppercase ASCII letters and shifted US-ANSI punctuation
to their base keycode and host-layout scancode with left Shift (scancodes follow
the active host keyboard layout, and the compiled key-mapping check assumes a
US-ANSI layout). An explicit `SHIFT` and an implied Shift share one modifier press
and release. When SDL text input is active and neither Ctrl nor Alt is held,
printable keys also emit text, shifting letters and US-ANSI base symbols
consistently when Shift is held. Named keys (`ESC`, `ENTER`, `SPACE`, etc.)
deliver their keycode and scancode in either text input mode and generate no text
event.

Actual PNG and mechanical geometry are the whole observation port. Save/load,
identity, menus, activities and objective meaning belong to the player. The
[prepared application](../../harness/prepared_app.py) and
[preparation tool](../../tools/prepare_game.py) select ordinary CDDA options
before a run; the computer adapter does not override game settings.

## Assurance and evidence

Protocol, wire, channel and runtime tests assert ingress, original expiry and
capacity, packet backpressure, stop and uncertainty. Compiled checks exercise actual
SDL and inherited descriptors. Two short fixture runs compare the keycode,
scancode, modifiers and text in both text input modes to catch
input regressions ([R-REGRESSION](../risks.md#development-risks)).
Portable doubles cannot replace these checks or actual CDDA qualification.

The [native procedure](../operations/native-acceptance.md) owns actual control,
useful play, save/new-child reload and normal exit evidence. The [production report](../acceptance/2026-10-29-computer-control.md)
retains scoped actual outcomes. Geometry/resize, Unicode/IME, actual-human takeover and
second-game qualification remain explicit limits.
