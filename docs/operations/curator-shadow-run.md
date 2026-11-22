---
owner: lead
status: active
review_trigger: The shadow runner's command, inputs, caps or output change
---

# Run a curator shadow session

Use this procedure to run the Pi curator host on sealed traces and read its summaries.
The [curator host reference](curator-hosts.md#pi-curator-host-the-shadow-session-host)
covers installation, route configuration, proxy accounting and shutdown. The
[curator contract](../contracts/curator.md) owns sessions, the gate and publication.

```sh
.venv/bin/python -m tools.curator_host.shadow --arm terra|opus --lineage 397|372 [--sessions NAME…] --cap-usd N --out .runtime/curator-shadow/RUN
```

## Inputs

- **Key.** The runner reads `OPENROUTER_API_KEY` or the project credential mapped by the
  selected runtime's ignored `credentials.json`, and fails if neither resolves.
  `--upstream` accepts only OpenRouter or a local http origin.
- **Sessions.** It selects only the sampled sessions: 397 has `sd1a1`–`sd1a7`; 372 has
  `aidB3 ceil09 ceil07 ceil05 aidB9 aidA5`, in that order. It refuses the four held-out
  lineages, stored as `lh1`–`lh4`, and any other name.
- **Memory.** A 372 run gets its own sealed memory store. The 397 lineage store is not
  passed, because it would carry later admissions into earlier sessions.

## Sessions and caps

Each session is one `run_session` against
`.runtime/knowledge/shadow-454/<out name>/<arm>/<lineage>/` (game `cdda`), with its own
proxy and token. The proxy cap is what the whole-run cap leaves, or `--session-cap-usd`
if that is smaller.

The run stops when:

- the cap is reached, or a session reaches its own cap;
- the proxy revokes or records a breach, or accounting remains unsettled after shutdown;
- host cleanup is unconfirmed;
- a gate result is unknown or unsupported;
- with `--stop-on-abort`, any other session is not sealed;
- with `--stop-on-reject`, the gate rejects a session's submission, since that loses the
  session's facts (`stopped: submission-rejected`).

Nothing retries.

### Several invocations under one stop

The cap flags hold per invocation, and `--session-cap-usd` must be positive. A step that
takes several invocations (a re-run, then the sessions still to run) passes as
`--cap-usd` the step's stop minus the spend of its earlier invocations, which is the
`total_cost_usd` of each run summary.

## Windows

A window is one actor's steps `first` to `last`
([window rules](../contracts/curator.md#windows-of-decisions)). Windows replace
`--sessions`, and each runs one session, in the order given, from the store the previous
one left.

| Option | Meaning |
| --- | --- |
| `--windows-file FILE` | A JSON list of `{session, actor, first, last}` |
| `--window-plan SESSION ACTOR START SIZE COUNT` | The same list as COUNT consecutive windows of SIZE steps |

- A window is labelled `<session>-<actor>-<first>-<last>` and never reads the sealed
  memory store. The refusals above apply to the session it names.
- The run summary records `windows` and `windows_sha256` (of their canonical JSON).

## Re-run a session that reached its cap

A session that reaches its cap is recorded (`stopped_by_cap`). To run that one session
once more:

1. Pass `--double-session-cap` with `--session-cap-usd` and exactly one named session or
   window. The session gets twice the cap.
2. Pass `--knowledge-root DIR`, the earlier run's `knowledge_root`, to continue its
   repository. The re-run, or the windows still to run, then starts from the store as it
   stood. The repository must lie under `<runtime>/knowledge/` after links and `..` are
   resolved, and its path must end in the run's `<arm>/<lineage>`.

The run summary records `published_before_run`, `session_cap_doubled` and
`knowledge_root`.

## Grooming

`--groom` runs a grooming session after each whole admission that publishes, on the same
repository and under the same caps. It does not combine with windows or with
`--double-session-cap`.

A re-run is of one session only, so an admission is not paid for twice:

- Re-run an admission without `--groom`.
- Re-run a grooming session with `--groom-only`. It needs `--knowledge-root` and exactly
  one named admission, which is already the repository's last admission.

## Output

Summaries are `curator-shadow/2`. A run writes `<out>/summary.json`. Each session writes
`<out>/<lineage>/<session>/summary.json` and its `proxy-ledger.jsonl`.

**A session summary** holds:

- `session_kind` (`admission` or `grooming`), the trace session read and the `coverage`
  stamp;
- wall seconds, host start to first model request, first-request prompt tokens and tokens
  by kind;
- requests, tool calls, submissions, verdicts with diagnostics, drafts and the record
  path;
- proxy-settled cost, `cap_usd` and `stopped_by_cap`;
- the `proxy` object, with `charged_usd`, `max_reserved_usd`, `revoked` and breaches.

Counts cover published and rejected submissions only. Restore and unchanged events are
distinct.

**A run summary** lists each session with its kind, published versions before and after,
`ledger_charged_usd`, `wall_seconds`, `stopped_by_cap` and `cap_usd`. It also records
`groom`, `groom_only` and `grooming_skipped` (an admission that published nothing is not
groomed), and counts every session in `sessions_run`. It is `complete` when every planned
admission ran, or with `--groom-only` the grooming session, and nothing stopped the run.

**The prompt is recorded.** `prompt_sha256` (of `prompt.md`) is in the run summary's
`host` and in each session manifest's `pinned.host`. A grooming session also pins
`grooming_sha256`.
