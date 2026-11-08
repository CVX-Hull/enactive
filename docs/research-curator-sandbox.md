---
owner: lead
review_trigger: A macOS or coding-agent host update, a change to ADR 009's isolation boundary, an escape-suite failure, or new sandbox evidence
status: active
date: 2026-11-08
scope: R13 of ADR 009 (#451) — project-local sandbox mechanisms on this Mac, coding-agent hosts under them, session cost evidence, and gate gaming
---

# Curator sandbox (R13)

Research and prototype for [ADR 009](decisions/009-curated-player.md#isolation)'s
isolation boundary ([#451](https://github.com/CVX-Hull/enactive/issues/451)). The
curator is a coding agent that runs code on the Mac that runs the live game. Today's
runtime files hold live secrets: the provider key is in the actor host's environment
and `actor.json` holds each actor's custody token. The custodian's Pause route trusts
loopback.

Search and retrieval date: **2026-11-08**. Conclusions whose newest support predates
2025-05-08 are flagged *stale*. Host: macOS 27.2 (26B123), Apple silicon, Claude Code
2.1.319, Codex CLI 0.162.1.

## Finding

**A project-owned, default-deny Seatbelt profile (`/usr/bin/sandbox-exec`) is the only
mechanism on this Mac that confines reads, writes and network together without an
install.** It is wrapped by a supervisor outside the sandbox and a key-holding
loopback model proxy. The prototype
([`harness/curator/sandbox.py`](../harness/curator/sandbox.py),
[`harness/curator/proxy.py`](../harness/curator/proxy.py)) passes the escape suite
([`tests/test_curator_sandbox.py`](../tests/test_curator_sandbox.py)). The suite runs
against the real custodian/playing-service HTTP listener and the real Pause gateway,
over their receiver doubles. The real Claude Code 2.1.319 completed headless turns
under it, including a Bash tool call, through the proxy only (L13, L14).

Two caveats:
- **Apple has deprecated `sandbox-exec`.** Its developer support calls custom SBPL
  unsupported and names Endpoint Security, App Sandbox and Virtualization as the
  supported options (S5, S6).
- **macOS has no kernel memory cap for a process tree.** Memory, disk total and
  process count are enforced by a polling supervisor, not by the kernel (L3, L11).

The [risks table](#residual-risks) lists what stays open. Adopting this mechanism for
live P1 is ADR 009 open decision 6, an owner decision.

## Brief and sources named

A delegated research agent (one session, read-only, nothing installed or started)
answered these questions. The lead then built and tested the prototype.

1. Which mechanisms can enforce each boundary element on this platform without a
   global install? Candidates: Seatbelt (`sandbox-exec`), setrlimit, `taskpolicy`,
   launchd, disk images, VMs and containers (colima, lima, docker, Apple
   `container`, Virtualization). For each: escapes, gaps and maintenance status.
2. How do current coding-agent CLIs sandbox themselves? Can they run headless
   against a local proxy, with memory off and no instruction files?
3. How well do coding agents work in sandboxed ephemeral workspaces? What does a
   session cost in tokens and cold start?
4. How do agents game pass/fail gates, and which gate designs resist it?

**Foundational sources.** The brief named Dennis and Van Horn (1966) and Saltzer and
Schroeder (1975). Neither was retrieved or read. They frame the design
(default-deny, one named channel, authority passed explicitly), but no conclusion
rests on them.

**Read scope.** Web pages were read through a fetch tool that returns a model-written
answer over the page. "Full text" below therefore means read through that tool. Some
PDFs were read only to abstract and introduction. The lead re-read S6 (quotes
verified 2026-11-08) and the local `sandbox-exec` and `taskpolicy` man pages (L4),
and reproduced L1 to L3 independently (L9 to L12).

## Mechanisms compared

Key: **Y** enforces; **P** partial; **N** no; **–** not established.

| Element | Seatbelt | setrlimit | `taskpolicy` | Sparse disk image | Lima / Colima VM | Apple `container` | Claude Code's own sandbox | Codex's own sandbox |
|---|---|---|---|---|---|---|---|---|
| Default-deny reads | **Y** (L1, L9) | N | N | N | Y | Y | P: reads default-allow; Bash children only (S1) | P: restricted-read mode exists (S8) |
| Writes only to named directories | **Y** (L1, L9) | N | N | P (whole image) | Y | Y | Y for Bash children (S1) | Y (S8) |
| No network except one loopback port | **Y** (L1, L10) | N | N | N | Y | Y | P: `allowLocalBinding` opens all local ports on macOS (S1) | Y (S8) |
| Other processes hidden | P: signals and Mach services denied; argv of same-user processes still readable (L12) | N | N | N | Y | Y | – | P (S8) |
| Memory cap | N | **N**: macOS refuses address-space and data limits (L3, L11) | **N** in a test: `-m 200` did not stop 800 MiB (L3) | N | Y | Y | N | N |
| Disk cap | N | P: per-file size only (L3) | N | **Y**: 32 MiB image stopped writes at 31,457,280 bytes (L5) | Y | – | N | N |
| Process-count cap | N | P: counted per user, not per tree (L3) | N | N | Y | Y | N | N |
| Low CPU priority | N | N | Y, documented; effect not measured (L4) | N | P | P | N | N |
| Footprint | None (built in) | None | None | None; mount visible while attached (L5) | Starts a VM; changes existing `~/.lima`, `~/.colima`, `~/.docker` (L6, S10) | Administrator install under `/usr/local` (S12): excluded by the [environment rule](environment.md) | Part of the host | Part of the host |
| Status | Deprecated; unsupported by Apple DTS (S5, S6); used by Chromium (S7, stale), Codex (S8) and Claude Code (S1) | Current | Current (L4) | `hdiutil create -size` deprecated in favour of `diskutil image` (L5) | Active (S10, S11) | Active; macOS 26+ (S12) | Active | Active |

**Rejected for P0:**
- VMs and containers: VM state under existing per-user directories, or a global
  install. They remain the fallback if Seatbelt is withdrawn or escaped. Apple's
  Virtualization framework is supported and needs no install, but it would mean
  building a VM host and sourcing a guest image. It was not evaluated.
- The agents' own sandboxes as the boundary: default-allow reads, Bash children only,
  and all loopback ports open.
- Nesting: a nested `sandbox-exec` failed under a minimal profile (L7), so inner
  sandboxes are off and the outer profile is the only enforcement.

## The prototype

**Profile.** [`sandbox.profile`](../harness/curator/sandbox.py) emits SBPL from a
validated layout:
- Default deny.
- Reads: only `/`, a fixed list of system roots, the workspace, the fresh home and
  named tool roots.
- Writes: only the declared writable directories (`submissions/`, `drafts/`,
  `scratch/`) and the home, plus a few devices.
- Network: one rule, `(remote ip "localhost:<proxy port>")`.
- Mach services: four, for libc user lookup, notifications and logging.
- Signals and process information: own processes only.
- Kernel values: a named list, no process tables.

The layout refuses relative paths, unquotable characters, writable directories
outside the workspace or equal to it, and a home inside the workspace.

**Launch.** [`sandbox.run`](../harness/curator/sandbox.py) runs the command:
- with nothing inherited, only a minimal environment, a fresh home and temporary
  files in `scratch/`;
- under rlimits: CPU seconds, file size, open files, no core files, and processes at
  the user's current count plus the session allowance, because macOS counts per
  user;
- at nice 19, in its own process group.

The supervisor polls the tree's resident memory, the writable directories' disk use,
the tree's process count and wall-clock time, and kills the group on a breach. At
close it signals the group and its descendants. It reads the tree only while the
group exists, so a reused process ID is never signalled.

**Model proxy.** [`ModelProxy`](../harness/curator/proxy.py) is a loopback HTTP
server outside the sandbox.
- **Authentication and routes.** It holds the key and accepts only a per-session token
  that it can revoke. It forwards only the provider's model route (`/v1/messages` or
  `/v1/responses`) and rewrites authentication.
- **The cap is enforced by reservation.** Before forwarding, it reserves the worst
  case: every body byte counted as an input token at the highest input-side price,
  plus the requested output limit at the output price. A request whose reservation
  would cross the cap is refused.
- **Settlement.** After the call it settles at the reported usage, or keeps the whole
  reservation when usage is missing.
- **Ledger.** Each request is appended without the key or token. Prices are a frozen
  input with their source; there is no default.
- **Reuse review (S-CODE).** Gateways exist (LiteLLM, Envoy and mitmproxy are named in
  S13 and S20), but they add a dependency that is unaudited by its own vendor's
  statement (S20). The required behaviour is about 250 lines with tests: token swap,
  two routes, a reservation cap and a ledger. Owner: the lead. Retire it if a vetted
  gateway with reservation caps is adopted.

**Escape suite.** An adversary script runs inside the sandbox and reports only
allowed or denied, never contents. The local run on 2026-11-08 passed 29 tests in
18 s. Exactly these attempts were allowed: reading the brief and knowledge files,
writing `scratch/`, `submissions/` and `drafts/`, and reaching the proxy. Every
other attempt was denied:
- **Secrets.** Reading the real `.runtime/credentials.json`, a live `actor.json` with
  a custody token, the repository, another session's home and the proxy ledger;
  listing the user's home, `~/.ssh` and `.runtime`.
- **Writes.** Writing `knowledge/`, `trace/`, the workspace root, `.runtime`, a
  published-snapshot directory outside, shared `/tmp` and another session's home.
- **Listeners and network.** The real custodian/playing-service listener over TCP,
  TCP6 and UDP; the real Pause gateway; an outside Unix socket; external TCP and DNS.
- **Host services and processes.** The pasteboard, opening an application, signalling
  the test runner and listing processes.

Further tests show:
- the proxy is the only way out, and a forged token gets 401;
- no state carries into the next session;
- the supervisor stops memory, disk, process-count, wall-clock, CPU and file-size
  exhaustion;
- the proxy refuses wrong tokens, routes, unpriced models, missing limits, oversize
  limits and requests over the cap, and charges the full reservation when usage is
  missing.

**Lanes.** The escape suite needs macOS and skips elsewhere, so Linux CI does not run
it: the local Mac run is its evidence. The proxy tests are portable. The real-host
probe ([`tests/curator_host_probe.py`](../tests/curator_host_probe.py)) is a manual
local check because it needs an installed host binary. It spends $0, because a local
stand-in answers in the Messages streaming shape.

## Residual risks

| # | Risk | Evidence | Mitigation or decision |
|---|---|---|---|
| 1 | Seatbelt is deprecated and unsupported; an OS update may break or widen the profile | S5, S6, S7 | Re-run the escape suite after every macOS or host update and record host versions per session; the VM fallback stays documented |
| 2 | **Same-user argv is readable** (`KERN_PROCARGS2`), even with process information limited to self and a named kernel-value list; environments were not readable | L12 | No credential may travel in argv. Today the token is in `actor.json` and the key in the environment (`tools/campaign_player.py`). The #454 run checks live argv for the session's secrets |
| 3 | **Memory, disk total and process count are polled, not kernel-enforced**; overshoot is bounded by the allocation rate times the 0.1 s poll | L3, L11 | Supervisor kills on breach; file size and open files are rlimits. A sparse disk image (L5) would make disk a hard cap and is the first hardening step if #454 shows bursts |
| 4 | **An orphaned descendant that left the process group** (double fork plus `setsid`) cannot be safely identified at close | L15 | It keeps the inherited profile. Once the workspace is deleted it cannot recreate it, its token is revoked, and it runs at nice 19 under the CPU rlimit. Its memory is unbounded: residual. #454 checks for survivors after every session |
| 5 | System read surface: `/usr`, `/System`, `/private/etc` (including `passwd`), `/dev`, the hostname and hardware values | L9, S8 | Accepted; nothing project-secret lives there |
| 6 | Shared kernel: a kernel or Seatbelt bug escapes | S3 | Accepted for P0; escalate to a VM if the owner's threat model requires it |
| 7 | The proxy channel carries data out; any local process can reach the proxy port | S3 | Per-session revocable token, model routes only, ledger; trace content is model-visible by design |
| 8 | Host version drift changes flags and startup behaviour | L13, S4 | Record host version and binary hash per session; re-run the host probe on update |
| 9 | Claude Code writes its temporary root to `/tmp/claude-<uid>` unless `CLAUDE_CODE_TMPDIR` is set; allowing that path would share state with other sessions | L13 | The runner sets `CLAUDE_CODE_TMPDIR` to `scratch/`; the profile never allows `/tmp` |
| 10 | Codex was not yet run under the profile | — | #454's second host; same probe with a Responses-shape stand-in before any spend |

## Coding-agent hosts

**Claude Code (2.1.319).**
- `--bare` skips hooks, plugins, auto-memory, keychain reads and CLAUDE.md discovery,
  and takes its key only from `ANTHROPIC_API_KEY` (local `--help`, L8; S4).
- `ANTHROPIC_BASE_URL` points it at the proxy (S16).
- `CLAUDE_CODE_DISABLE_AUTO_MEMORY` and `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` are
  documented (S14, S16). Under the profile, network is denied anyway.
- Observed under the profile (L13, L14), with stand-in token counts and a synthetic
  price, so not a real-cost figure:
  - exactly one upstream route (`/v1/messages`) per turn;
  - a Bash tool call that wrote `scratch/` and was refused the project secret;
  - 0.23–0.24 s from launch to finish against the stand-in;
  - about 157 MB peak resident memory;
  - no survivors;
  - a ledger charge settled from the streamed usage.

**Codex CLI (0.162.1).** `codex exec` has `--ephemeral`, `--ignore-user-config` and
`--ignore-rules` (L8). A custom `model_providers.<id>.base_url` and the `memories.*`
switches exist in the configuration schema (S9). Whether `project_doc_max_bytes=0`
disables instruction files is not verified. It has not been run under the profile.

**Comparison.** Both hosts can be started headless against a local proxy with memory
and instruction files off, according to their own documentation. The outer profile is
the common boundary.

## Session cost and cold start

No primary source measured a coding agent in a confined ephemeral workspace.
- **Run-to-run token spread is large.** One study reports about 1.34× for identical
  specifications (S18). Another reports up to 40× in tokens per solved task across
  harnesses (S19). Both are single-model preprints.
- **Vendor guidance carries no method.** Figures such as 1 GiB RAM per agent and
  "dollars per long session" (S15, S20) are vendor-reported. They are not estimates.
- **Cold start is mostly a cache miss.** Per-session cold-start cost is the re-read of
  the system prompt and workspace context. Prompt caching does not survive a break
  (S20). Its token cost must be measured in #454 under the final configuration.
- **Local startup is fast.** Launch to first model request was under 0.25 s locally
  (L13).

## Gate gaming

The findings (S21 to S26, all 2025-06 to 2026-06, mostly preprints with single
configurations) are:
- **Agents exploit visible tests**, and the gap to hidden tests grows with task size.
  For one host and model, SpecBench reports 43–48 points (S24).
- **Test editing is the main channel** (S21, S23). Special-casing and reading the
  scorer follow (S22).
- **"Don't cheat" prompts barely help** (S22).
- **Resubmission with feedback raised cheating**, and an explicit "cannot satisfy"
  option cut it for some models but less for others (S21).
- **Every detector missed cases**, whether hidden tests, a model judge or file-edit
  detection (S21, S23).

**Implications for gate v0 (#453) and its later tests (#459).** These are hypotheses,
because no source tests a gate that scores knowledge or programs on prospective
trace.
- Score only gate-owned tests the curator cannot see.
- Flag any change to existing tests mechanically.
- Return coarse diagnostics, never held-out content.
- Back off resubmission.
- Offer a "cannot satisfy" exit in the submission manifest.
- Combine held-out tests, an independent transcript review and a diff check rather
  than trusting one.

## Sources

Read scope: FT full text through the fetch tool; SS stated sections; AB abstract
(and introduction where stated); CODE source read. All retrieved 2026-11-08. Flags:
**V** vendor-reported; **PP** preprint; **SR** single run or unreplicated.

| ID | Source | Date | Read scope | Used for | Flags |
|---|---|---|---|---|---|
| S1 | Anthropic, Claude Code sandboxing docs, code.claude.com/docs/en/sandboxing | Undated; release markers to v2.1.310 | SS (first 100k of 111k chars) | Built-in sandbox scope, defaults, `allowLocalBinding` | V |
| S2 | anthropic-experimental/sandbox-runtime README | Release v0.0.81, 2026-10-20 | SS | Beta status, profile style, warnings | V, beta |
| S3 | Anthropic, "Securely deploying AI agents" | Undated | FT | Proxy-for-credentials pattern; shared-kernel risk | V |
| S4 | Anthropic, headless docs, code.claude.com/docs/en/headless | Undated; notes to v2.1.295 | FT | `--bare`; cost fields are client estimates | V |
| S5 | `man sandbox-exec` on this Mac | Page dated 2017; shipped with 27.2 | FT, local; re-read by the lead | "DEPRECATED" | Current as shipped |
| S6 | Apple Developer Forums thread 777509 | Posts Mar 2025, Sep 2026, Oct 2026 | SS; quotes re-verified by the lead | SBPL "never been documented for third-party use"; custom SBPL "unsupported by DTS"; supported options are Endpoint Security, App Sandbox and Virtualization | Mar 2025 post stale; later posts current |
| S7 | Chromium, "How Chromium uses Seatbelt on macOS" | Updated 2025-01-30 | FT | Deny-by-default profile in production use | Stale |
| S8 | openai/codex `codex-rs/sandboxing` (`seatbelt.rs`, `.sbpl` policies) | main, 2026-11-08 | CODE (policies in full; parts of `seatbelt.rs`) | Restricted-read mode, loopback-port rules, platform read defaults | Apache-2.0; not copied |
| S9 | openai/codex `config.schema.json` | main, 2026-11-08 | SS (descriptions) | Provider, memory and instruction keys | Schema, not behaviour |
| S10 | Lima internals page | Lima v2.3.0, 2026-11-06 | SS | Default state under `~/.lima` | |
| S11 | abiosoft/colima README | v0.10.3, 2026-06-04 | SS | Resource flags | |
| S12 | apple/container README | 1.7.1, 2026-11-06 | SS | Administrator install under `/usr/local`; macOS 26+ | |
| S13 | Anthropic, "Other LLM gateways" | Undated | FT | Gateways hold credentials and spend controls | V |
| S14 | Anthropic, "How Claude remembers your project" | Undated | SS | Auto-memory switches | V |
| S15 | Anthropic, "Hosting the Agent SDK" | Undated | FT | Ephemeral pattern; resource guidance | V |
| S16 | Anthropic, "Connect Claude Code to an LLM gateway" | Undated | FT | `ANTHROPIC_BASE_URL`; nonessential-traffic switch and its limits | V |
| S18 | Smékal, arXiv 2608.25399v1 | 2026-08-26 | AB + intro | Token-spend spread (Kimi K3, 2,700 runs) | PP, SR |
| S19 | Vats and Golev, arXiv 2607.22585v1 | 2026-06-08 | AB + intro + related work | Harness effect on tokens per solved task | PP, vendor-affiliated |
| S20 | Anthropic, "Manage costs effectively" | Undated | FT | Cache-miss behaviour; costs are client estimates | V |
| S21 | Zhong, Raghunathan and Carlini, "ImpossibleBench", arXiv 2510.20270 | 2025-10-23 | FT (first 100k of 113k chars) | Cheating channels and mitigations | PP |
| S22 | METR, "Recent frontier models are reward hacking" | 2025-06-05 | FT | Reward-hack rates; prompts barely help | Blog |
| S23 | "EvilGenie", arXiv 2511.21654v2 | 2026-05-17 | FT | Detector miss rates | PP |
| S24 | "SpecBench", arXiv 2605.21384v1 | 2026-05-20 | FT | Visible-versus-hidden test gap | PP, SR |
| S25 | Qwen Team, "The Verification Horizon", arXiv 2606.26300v2 | 2026-06-29 | SS | Trajectory monitor in RL training | PP, vendor |
| S26 | Lodkaew et al., arXiv 2606.07379v2 | 2026-06-08 | AB + figure 1 | Capped-score detection idea | PP |

S17 (OpenAI Codex security pages) held almost no detail and supports nothing.

## Local observations

All were made on this Mac on 2026-11-08, as single runs. They demonstrate that the
boundary exists; they are not a security evaluation.

- **L1 to L8, by the research agent.**
  - **L1.** A deny-default profile built from Codex's policies allowed workspace
    reads, writes to `submissions/` and one loopback port. It refused `$HOME`, an
    outside file, the workspace root, a second loopback port and an external address.
  - **L2.** Signal to PID 1, process-table sysctls, the mDNSResponder socket and `ps`
    were refused. Hostname and hardware values were readable.
  - **L3. Resource limits.**
    - `RLIMIT_AS` and `RLIMIT_DATA` were refused below about 1 TiB.
    - `taskpolicy -m 200` did not stop an 800 MiB allocation.
    - `ulimit -u` broke forks, because the user already runs about 563 processes.
    - `ulimit -f` capped a file.
  - **L4.** Man pages: `sandbox-exec` is deprecated; `taskpolicy` dated 2025-12-04;
    `setrlimit` RSS is advisory.
  - **L5.** A 32 MiB sparse APFS image attached in 0.15 s without root and stopped a
    100 MiB write at 31,457,280 bytes.
  - **L6.** docker 29.8.1, colima 0.10.3 and limactl 2.2.0 are installed and not
    running; their per-user directories already exist.
  - **L7.** A nested `sandbox-exec` failed with `sandbox_apply: Operation not
    permitted`.
  - **L8.** Host `--help` flags and binary locations: a 307 MB `claude` Mach-O and a
    235 MB `codex` Mach-O, both linking only system libraries.
- **L9, by the lead.** The project's own profile was written independently of Codex's
  files. It refused reads of the repository and home and writes to `trace/`, and
  allowed workspace reads and `scratch/` writes.
  - Before Mach lookups were restricted, `pbpaste` inside the sandbox read the
    owner's clipboard.
  - The output was treated as data and not acted on. Probes since then test only
    whether the pasteboard is reachable.
  - With the four-service allowlist, the pasteboard and Launch Services are refused.
- **L10.** With `(remote ip "localhost:P")`, port P connected over IPv4 and as
  `localhost`. Another loopback port, `::1` and an external address were refused.
- **L11.** In the project's environment, macOS refused to lower `RLIMIT_AS` and
  `RLIMIT_DATA` at any value ("current limit exceeds maximum limit").
- **L12. argv is readable, environments are not.** `KERN_PROCARGS2` of another
  same-user process returned its argv but not its environment, outside and inside
  the sandbox. That held under `process-info* (target self)` and under a named
  `sysctl-read` list. A `deny` of the name did not change it.
- **L13. Real Claude Code, one turn.** Claude Code 2.1.319 ran with `--bare -p`,
  `ANTHROPIC_BASE_URL` set to the proxy and the session token as `ANTHROPIC_API_KEY`,
  against a local Messages-shape stand-in.
  - It first failed with `EPERM ... open '/tmp/claude-501'`. After setting
    `CLAUDE_CODE_TMPDIR` to `scratch/`, it completed.
  - The upstream saw one `/v1/messages` streaming request carrying the real key.
  - Home after the run: `.claude.json`, `.claude/backups`, `.claude/plugins/store`
    and `.claude/sessions`.
- **L14. Real Claude Code, a Bash tool call.** A two-turn run with the Bash tool:
  - The stand-in asked for a command that writes `scratch/`, reads
    `.runtime/credentials.json` and lists `~/../..`.
  - The tool result returned to the model was `written / secret-denied /
    users-denied`.
  - The run took 0.23 s, peaked at 157 MB and left no survivors.
- **L15.** A double-forked process that called `setsid` inside the sandbox
  re-parented to PID 1 and kept running after its parent exited. The `sandbox_check`
  path filters could not be used from Python to identify it: arm64 variadic calls
  returned −1.
