---
owner: lead
status: historical
kind: change
date: '2026-11-09'
scope: 'The 19 October seven-day recap video export sealed into the evidence store, and three local branches deleted, on the owner decisions of 9 November 2026 (ADR 010 follow-up, #498)'
---

# Recap video sealed and three branches deleted, 9 November 2026

[ADR 010](../decisions/010-streamlined-delivery.md)'s outcome left two items for the owner.
The owner decided both on 9 November 2026.

## The seven-day recap video

`dist/seven-day-video/` held the only copy of a captioned 60-second recap exported on
19 October 2026 from the [first supervised seven-day campaign](2026-10-19-seven-day-survival.md):
the video, its captions, a thumbnail, an export-verification file and an upload description.
No record cited it and the evidence store did not hold it. On the owner's decision it is
sealed as the `seven-day-recap-video` study, cited by this record, and the `dist/` original
was removed after every file matched the seal by hash. The recap is a summary of checkpoints,
not continuous footage or new evidence about the campaign; the campaign record stays the
authority for what happened.

## Three local branches

Three local branches held commits that existed nowhere else. On the owner's decision they
were deleted without an archive, so these commits are no longer available:

| Branch | Tip | Last commit |
| --- | --- | --- |
| `aid-zoom-view` | `70eda9a` | Add optional nearest-neighbour zoom to `player_source` (`player-source-read/2`), never merged |
| `backup/p0-453-wip` | `16cbf9e` | wip: session state directory; ADR pointer (#453), a draft that main later replaced |
| `p0-453-gate` | `dcd17b6` | wip: curator session spec (#453), a draft that main later replaced |
