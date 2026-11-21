---
owner: lead
status: active
review_trigger: The shadow runner's command, inputs, caps or output change
---

# Run a curator shadow session

Use this procedure to run the Pi curator host on sealed traces and read its summaries.
The [curator host reference](curator-hosts.md#pi-curator-host-the-shadow-session-host)
covers installation, route configuration, proxy accounting and shutdown.

**The shadow runner.**
`.venv/bin/python -m tools.curator_host.shadow --arm terra|opus --lineage 397|372 [--sessions NAME…] --cap-usd N --out .runtime/curator-shadow/RUN`.
- **Input.** It reads `OPENROUTER_API_KEY` or the project credential mapped by the selected
  runtime's ignored `credentials.json`, and fails if neither resolves. `--upstream`
  accepts only OpenRouter or a local http origin. It selects only the sampled sessions (397:
  `sd1a1`–`sd1a7`; 372: `aidB3 ceil09 ceil07 ceil05 aidB9 aidA5`, in that order) and refuses
  the four held-out lineages, stored as `lh1`–`lh4`, and any other name. A 372 run gets its own sealed memory store; the 397 lineage
  store is not passed, because it would carry later admissions into earlier sessions.
- **Run.** One `run_session` per session against `.runtime/knowledge/shadow-454/<out name>/<arm>/<lineage>/`
  (game `cdda`). Each session has its own proxy and token, sized to what the whole-run cap leaves
  (or `--session-cap-usd`). The run stops when the cap is reached, the proxy revokes or records
  a breach, accounting remains unsettled after shutdown, or host cleanup is unconfirmed.
  `--stop-on-abort` additionally
  stops on other non-sealed sessions.
- **Windows.** `--windows-file FILE` (a JSON list of `{session, actor, first, last}`) or
  `--window-plan SESSION ACTOR START SIZE COUNT` (the same list as COUNT consecutive windows) runs one
  session per window, in the order given, against one repository, each starting from the store the
  previous one left; it replaces `--sessions`. A window is one actor's steps `first` to `last`
  ([the design](../design/curator-session.md#windows-of-decisions-and-the-coverage-stamp)); a unit is
  labelled `<session>-<actor>-<first>-<last>`, and a window never reads the sealed memory store. The same
  refusals apply to the session each window names. The run summary records `windows` and
  `windows_sha256` (of their canonical JSON), and per session the proxy ledger's `charged_usd` and
  `max_reserved_usd`, `wall_seconds`, `stopped_by_cap`, `cap_usd` and the `coverage` stamp.
- **A session that reaches its cap** is recorded (`stopped_by_cap`) and stops the run. Nothing retries.
  `--double-session-cap` (with `--session-cap-usd`, and exactly one named session or window) runs that
  one session once more at twice the cap; `--knowledge-root DIR` (an earlier run's `knowledge_root`,
  inside `<runtime>/knowledge/`) continues its repository instead of a fresh one, so the re-run or the
  windows still to run start from the store as it stood. The summary records
  `published_before_run`, `session_cap_doubled` and `knowledge_root`. The repository must lie
  under `<runtime>/knowledge/` (after links and `..` are resolved) and be of the same arm and
  lineage as the run (its path ends `<arm>/<lineage>`). With grooming, the re-run is of one
  session only: an admission is re-run without `--groom`, and a grooming session with
  `--groom-only` (exactly one named admission, already the repository's last admission, in
  `--knowledge-root`), so the admission is not paid for twice; `--groom` and
  `--double-session-cap` together are refused.
- **The cap flags hold per invocation.** `--cap-usd` limits one invocation, and `--session-cap-usd`
  must be positive. A step that takes several invocations (a re-run, then the sessions still to
  run) passes `--cap-usd` as the step's stop minus the proxy ledger's total so far across its
  earlier invocations (the `total_cost_usd` of each run summary), not the full stop.
- **`--stop-on-reject`** stops the run when the gate rejects a session's submission, since a
  rejected submission loses that session's facts (`stopped: submission-rejected`).
- **The prompt is recorded.** `prompt_sha256` (of `prompt.md`) is in the run summary's `host`
  and in each session manifest's `pinned.host`. A grooming session additionally pins
  `grooming_sha256` in its manifest.
- **Output.** `curator-shadow/2` summaries: one per session (`<out>/<lineage>/<session>/summary.json`
  and its `proxy-ledger.jsonl`) and one per run (`<out>/summary.json`). A session summary holds
  wall seconds, host start to first model request, first-request prompt tokens, tokens by kind,
  proxy-settled cost, requests, tool calls, submissions, verdicts with diagnostics, drafts, the
  record path, the proxy's `revoked` and breaches, and whether the cap stopped it, its
  `session_kind` (`admission` or `grooming`) and the trace session it read. Counts cover published
  and rejected submissions only; restore and unchanged events are distinct, and an unknown or
  unsupported result stops the screen as unresolved. The run summary
  lists each session with its kind and published versions before and after, records `groom`,
  `groom_only` and `grooming_skipped` (an admission that published nothing is not groomed),
  counts every session in `sessions_run`, and is `complete` when every planned admission (or,
  with `--groom-only`, the grooming session) ran.
