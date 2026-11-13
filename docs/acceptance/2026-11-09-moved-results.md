---
owner: lead
status: historical
kind: change
date: '2026-11-09'
scope: 'Results and incident observations that current pages held until 9 November 2026 and no other record holds, moved here unchanged when ADR 010 kept current pages free of dated results'
---

# Results moved from current pages

[ADR 010](../decisions/010-streamlined-delivery.md) keeps dated results out of current
pages. No other dated record, research page or data file held the passages below, so they
are kept here, as the pages stated them. Each section names the page that now links here.
An earlier set is in [moved measurements](2026-11-08-moved-measurements.md).

## Development runs: the earlier multi-day survival

From [development runs](../development-runs.md).

The only multi-day survival (19 October) used a frontier coding agent with a game-aware
harness, and every later run changed both the model class and the boundary.

## Trace workbench: evidence reader

From [the trace workbench design](../design/trace-workbench.md).

On the sealed #397 store it read 11 records, 0 programs and 61 sources.

## Coding agent hosts: the #383 observation

From [coding-agent hosts](../operations/coding-agents.md).

In #383, observed: a `/goal` stop check re-ran each time a turn ended while CI was pending,
re-prompting the session every few seconds. In the desktop app, Auto-fix woke the session on
CI failures, conflicts and review comments but not on a pass, so a pass relies on the watch
or pinned auto-merge.

## P1 study: clusters in the #397 sample

From [the P1 study](../design/p1-study.md). In #397's sample, 17 informative probes formed 12
clusters.

## Curator hosts: binary sizes

From [curator hosts](../operations/curator-hosts.md). `claude` (307 MB) under
`~/.local/share/claude/versions/` and `codex` (235 MB) under the Homebrew Caskroom.
