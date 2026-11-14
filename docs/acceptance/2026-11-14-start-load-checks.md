---
owner: lead
status: historical
kind: run
date: '2026-11-14'
scope: 'Load checks of the reusable starts (#388) through the campaign custodian, approved by the owner on 13 November 2026 ("I approve additional starts"): each start of the seven-day lineage''s final save loaded once with a minimal one-actor route, and fresh starts made for the withholding pilot. $0.095 of player play'
---

# Load checks of the reusable starts (#388)

## At a glance

- **Question.** Does each reusable start, a hash-verified copy of the seven-day lineage's
  final saved game, load in the game to its recorded survivor and time?
- **Result.** Yes. The six starts `seven-day-end-01`, `-02`, `-04`, `-05`, `-06` and
  `-07` (which replaced `-03`) each loaded **Morgan Hale, Spring day 63, 7:43:20 AM**, in
  the world Whitethorn (named in five players' reports, and in `-02`'s load-menu frame),
  the survivor and world of the [seven-day lineage](2026-11-07-seven-day-397.md). The
  lead checked the loaded frame of the first by eye.
- **The save's moment.** 7:43:20 AM is about four game minutes before the lineage's
  recorded death at 7:47 AM (it caught fire starting a craft beside a fuelled fire). Every
  start begins there, which the withholding pilot (#619) needs to know.
- **One invalid start.** `seven-day-end-03`'s run stopped before any play: the custodian
  could not bind its loopback port, still held by the previous run (`OSError: [Errno 48]
  Address already in use`); \$0. It was reported and replaced once by `seven-day-end-07`,
  applying by analogy the protocol's rule for an invalid start
  ([memory screen protocol](../design/memory-screen-protocol.md)), and later packages
  chose a free port.
- **Fresh starts.** A check uses a start up, so six new starts, `seven-day-end-08` to
  `-13`, were made from the same sealed save for the pilot.
- **Spend.** \$0.0949 of player play in all, from the seven sealed receipts. Like the
  spend-limit check, these are diagnostic qualification packages, not study admissions,
  so they have no run-ledger rows; the receipts in `start-load-checks` are the numeric
  record.
- **Not known.** Whether the fresh starts `-08` to `-13` load: loading uses a start up,
  so they rest on being byte-identical to six copies that did.
- **Owner decisions needed.** None.

## Method

- **Bridge** rebuilt at main `77758ff1` with `tools/build_computer.py` (`bridge.dylib`
  sha256 `1541cc4d…`), since the native source had changed since the last build.
- **Packages** (`campaign-run/7`, one per start, built by one script): the route of the
  spend-limit run (`openai/gpt-6.1-terra`, pinned provider) as `player-host/5`, with a
  reduced image context (8 images in blocks of 4), 12 requests, \$0.60 limit, finish
  reserve \$0.4096, one host, an inactive recall block; empty delivered knowledge
  (`tools/knowledge_export.py --empty`); the current player guide as context; the prompt:
  load the existing saved game through the ordinary menus, read the survivor's name and
  the in-game date and time, then take no action and do not save. Each package passed
  `tools.campaign_package` preflight before launch.
- **Each check**: `tools.starts install`, launch through `tools.campaign_supervision`,
  read the receipt and the player's final message, then `tools.starts dispose --seal`. The
  original userdir was archived before the first install
  (`.runtime/archive/userdir-20261114T034511439631Z`) and restored after the last.
- **Start identity.** Each run used a start whose manifest hash the start's sealed study
  records (`start-load-check-0N` in the evidence index); the copied lineage `397` is no
  longer held out, as the start procedure says of any run that uses a start.

## Result

In run order; attempts and spend from each sealed `receipt.json`.

| Start | Outcome | Attempts | Spend | Reported by the player |
| --- | --- | ---: | ---: | --- |
| `seven-day-end-01` | completed | 7 | \$0.0161 | Morgan Hale, Whitethorn, Spring day 63, 7:43:20 AM |
| `seven-day-end-02` | completed | 7 | \$0.0161 | Morgan Hale, Spring day 63, 7:43:20 AM (Whitethorn in its load-menu frame) |
| `seven-day-end-03` | incomplete: port in use, no play | 0 | \$0 | none |
| `seven-day-end-07` | completed | 7 | \$0.0161 | Morgan Hale, Whitethorn, Spring day 63, 7:43:20 AM |
| `seven-day-end-04` | completed | 6 | \$0.0146 | the same |
| `seven-day-end-05` | completed | 7 | \$0.0160 | the same |
| `seven-day-end-06` | completed | 7 | \$0.0159 | the same |

The saved-game files are identical across the seven working copies after their runs:
no check saved the game.

## Deviations

- **The goal asked for each of the six original starts**; `-03` could not be loaded and
  its replacement `-07` was, applying the protocol's replace-once rule by analogy.
- **The starts the pilot plays (`-08` to `-13`) are not themselves loaded**: loading uses a
  start up. They are byte-identical, hash-verified copies of the save six copies of which
  loaded here.

## Removed after sealing

- The seven package directories under `.runtime/computer-sessions/load-check-*` (253
  files), each matched to `start-load-checks` by path and hash.
- The userdir archive `.runtime/archive/userdir-20261114T034511439631Z`, after the
  restored `.runtime/user/` matched it file for file (526 files).

## Evidence

Sealed: `start-load-checks` (the seven packages, 253 files) and one study per disposed
start, `start-load-check-01` to `-07` (each start's working copy after its run), in the
[evidence index](../../data/evidence/index.json).
