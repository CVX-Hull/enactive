---
owner: lead
review_trigger: Prospective gate design or evidence, a change to the isolation boundary, a macOS or host update, or an escape-suite failure
status: active
date: 2026-11-08
scope: ADR 009 research on project-local sandbox mechanisms on this Mac, session costs and resistance to gate gaming
---

# Curator sandbox

This page compares mechanisms for [ADR 009's isolation boundary](decisions/009-curated-player.md#isolation)
and asks how a gate that scores submissions on later traces can resist gaming.

Search and retrieval date: **2026-11-08**. Conclusions whose newest support predates
2025-05-08 are flagged *stale*. Host: macOS 27.2 (26B123), Apple silicon. This page
calls the two coding-agent hosts studied the *first* and *second host*; their names,
versions and host-specific settings are on the operator page
[curator hosts](operations/curator-hosts.md).

## Finding

The [curator](components/curator.md) uses a project-owned, default-deny Seatbelt
profile, a polling supervisor and a key-holding loopback model proxy. Of the
mechanisms evaluated on this Mac, Seatbelt alone confines reads, writes and network
together without an install. The [baseline and workbench record](acceptance/2026-11-08-adr009-p0.md)
reports the escape-suite results against the real listeners.

Two caveats:
- **Apple has deprecated `sandbox-exec`.** Its developer support calls custom SBPL
  unsupported and names Endpoint Security, App Sandbox and Virtualization as the
  supported options (S5, S6).
- **macOS has no kernel memory cap for a process tree.** Memory, disk total and
  process count are enforced by a polling supervisor, not by the kernel (L3, L11).

## Brief and sources named

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

**Read scope.** The web fetch tool summarizes page text. "Full text" below means
read through that tool. Some PDFs were read only to abstract and introduction. The
quoted Apple guidance (S6) and local man pages (L4) are checked against their text.

## Mechanisms compared

Key: **Y** enforces; **P** partial; **N** no; **–** not established.

| Element | Seatbelt | setrlimit | `taskpolicy` | Sparse disk image | Lima / Colima VM | Apple `container` | First host's own sandbox | Second host's own sandbox |
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
| Status | Deprecated; unsupported by Apple DTS (S5, S6); used by Chromium (S7, stale) and by both hosts (S1, S8) | Current | Current (L4) | `hdiutil create -size` deprecated in favour of `diskutil image` (L5) | Active (S10, S11) | Active; macOS 26+ (S12) | Active | Active |

**Alternatives and limits**

- VMs and containers: VM state under existing per-user directories, or a global
  install. VMs are the fallback if Seatbelt is withdrawn or escaped. Apple's
  Virtualization framework is supported and needs no install, but it would mean
  building a VM host and sourcing a guest image. It was not evaluated.
- The agents' own sandboxes as the boundary: default-allow reads, Bash children only,
  and all loopback ports open.
- Nesting: a nested `sandbox-exec` failed under a minimal profile (L7), so inner
  sandboxes are off and the outer profile is the only enforcement.

The [sandbox source](../harness/curator/sandbox.py) specifies the allowlists for
reads, devices and Mach services. The profile denies POSIX shared memory and
semaphores. The launcher supplies a fresh home and a minimal environment, closes
inherited descriptors other than its redirected standard streams, and starts the
host in its own process group.

**Proxy reuse review (S-CODE).** The gateway documentation (S13, S16) names
LiteLLM, Envoy and mitmproxy. The review found no evidence that they support both
worst-case cost reservation and request-body allowlists. The lead owns the
[project proxy](../harness/curator/proxy.py) and retires it if a vetted gateway meets
both requirements.

## Residual risks

| # | Risk | Evidence | Mitigation or decision |
|---|---|---|---|
| 1 | Seatbelt is deprecated and unsupported; an OS update may break or widen the profile | S5, S6, S7 | Re-run the escape suite after every macOS or host update and record host versions per session; the VM fallback stays documented |
| 2 | **Same-user argv is readable** (`KERN_PROCARGS2`), even with process information restricted. Environments were unreadable in the probe | L12 | Keep credentials out of argv |
| 3 | **Memory, disk total and process count are polled.** Use can exceed the bound between polls. Open files that have been unlinked are outside the disk total | L3, L11 | The supervisor kills on breach. Per-file and open-file limits bound unlinked files. A sparse disk image (L5) is an option for a hard disk cap. See [what the sandbox bounds](operations/curator-hosts.md#what-the-sandbox-bounds) |
| 4 | **An orphaned descendant outside the process group** cannot be safely identified at close. It can keep using memory and write to the workspace while close-out reads it | L15 | It inherits the profile and CPU limit. Cleanup removes the workspace and revokes its token. Close-out uses descriptor-relative reads and refuses swapped links. Clearing file flags during removal is still path-based because macOS offers Python no descriptor-relative `chflags`. See [session close-out](design/curator-session.md#session-close-out) |
| 5 | System read surface: `/usr`, `/System`, `/private/etc` (including `passwd`), `/dev`, the hostname and hardware values | L9, S8 | Accepted; nothing project-secret lives there |
| 6 | A kernel or Seatbelt bug defeats the shared-kernel boundary | S3 | Use a VM if the threat model requires a separate kernel |
| 7 | The proxy channel carries data out; any local process can reach the proxy port | S3 | Per-session revocable token, model routes only, ledger; trace content is model-visible by design |
| 8 | Host version drift changes flags and startup behaviour | L13, S4 | Record host version and binary hash per session; re-run the host probe on update |
| 9 | The first host writes a shared temporary root under `/tmp` unless its temporary-directory variable is set; allowing that path would share state with other sessions | L13 | The runner points the variable at `scratch/` ([curator hosts](operations/curator-hosts.md)); the profile never allows `/tmp` |
| 10 | The second host is unverified under the profile and has no adapter for its model API | S9, L8 | See [host operations](operations/curator-hosts.md) for adapter and stand-in probe requirements |
| 11 | The provider may bill partial output. A charge over its reservation can push recorded spend past the cap before revocation, while already admitted requests are in flight | [Proxy accounting](components/curator.md#failure-bounds-and-ownership) | A cut stream without reported usage keeps the reservation. A reported charge above its reservation revokes the session |

## Session cost and cold start

No primary source measured a coding agent in a confined ephemeral workspace.
- **Run-to-run token spread is large.** One study reports about 1.34× for identical
  specifications (S18). Another reports up to 40× in tokens per solved task across
  harnesses (S19). Both are single-model preprints.
- **Vendor guidance carries no method.** Figures such as 1 GiB RAM per agent and
  "dollars per long session" (S15, S20) are vendor-reported. They are not estimates.
- **Cold start adds prompt cost.** Without a cache hit, the system prompt and
  workspace context incur the provider's uncached rates (S20). The
  [shadow-session record](acceptance/2026-11-08-curator-shadow-454.md) measures first-request tokens and latency for its configuration.
- **Local startup.** The first host reached a local stand-in in under 0.25 s (L13).

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

**Hypotheses for the prospective gate.** The sources do not test a gate that scores
knowledge or programs on later traces.
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
| S1 | [First host's sandboxing docs](https://code.claude.com/docs/en/sandboxing) | Undated; release markers to v2.1.310 | SS (first 100k of 111k chars) | Built-in sandbox scope, defaults, `allowLocalBinding` | V |
| S2 | anthropic-experimental/sandbox-runtime README | Release v0.0.81, 2026-10-20 | SS | Beta status, profile style, warnings | V, beta |
| S3 | Anthropic, "Securely deploying AI agents" | Undated | FT | Proxy-for-credentials pattern; shared-kernel risk | V |
| S4 | [First host's headless docs](https://code.claude.com/docs/en/headless) | Undated; notes to v2.1.295 | FT | `--bare`; cost fields are client estimates | V |
| S5 | `man sandbox-exec` on this Mac | Page dated 2017; shipped with 27.2 | FT, local | "DEPRECATED" | Current as shipped |
| S6 | Apple Developer Forums thread 777509 | Posts Mar 2025, Sep 2026, Oct 2026 | SS, quotes checked against text | SBPL "never been documented for third-party use"; custom SBPL "unsupported by DTS"; supported options are Endpoint Security, App Sandbox and Virtualization | Mar 2025 post stale; later posts current |
| S7 | Chromium, "How Chromium uses Seatbelt on macOS" | Updated 2025-01-30 | FT | Deny-by-default profile in production use | Stale |
| S8 | [Second host's sandboxing source](https://github.com/openai/codex/tree/main/codex-rs/sandboxing) (`seatbelt.rs`, `.sbpl` policies) | main, 2026-11-08 | CODE (policies in full; parts of `seatbelt.rs`) | Restricted-read mode, loopback-port rules, platform read defaults | Apache-2.0; not copied |
| S9 | [Second host's configuration schema](https://github.com/openai/codex/blob/main/codex-rs/core/config.schema.json) | main, 2026-11-08 | SS (descriptions) | Provider, memory and instruction keys | Schema, not behaviour |
| S10 | Lima internals page | Lima v2.3.0, 2026-11-06 | SS | Default state under `~/.lima` | |
| S11 | abiosoft/colima README | v0.10.3, 2026-06-04 | SS | Resource flags | |
| S12 | apple/container README | 1.7.1, 2026-11-06 | SS | Administrator install under `/usr/local`; macOS 26+ | |
| S13 | Anthropic, "Other LLM gateways" | Undated | FT | Gateways hold credentials and spend controls | V |
| S14 | [First host's memory docs](https://code.claude.com/docs/en/memory) | Undated | SS | Auto-memory switches | V |
| S15 | Anthropic, "Hosting the Agent SDK" | Undated | FT | Ephemeral pattern; resource guidance | V |
| S16 | [First host's gateway docs](https://code.claude.com/docs/en/llm-gateway-connect) | Undated | FT | `ANTHROPIC_BASE_URL`; nonessential-traffic switch and its limits | V |
| S18 | Smékal, arXiv 2608.25399v1 | 2026-08-26 | AB + intro | Token-spend spread (Kimi K3, 2,700 runs) | PP, SR |
| S19 | Vats and Golev, arXiv 2607.22585v1 | 2026-06-08 | AB + intro + related work | Harness effect on tokens per solved task | PP, vendor-affiliated |
| S20 | Anthropic, "Manage costs effectively" | Undated | FT | Cache-miss behaviour; costs are client estimates | V |
| S21 | Zhong, Raghunathan and Carlini, "ImpossibleBench", arXiv 2510.20270 | 2025-10-23 | FT (first 100k of 113k chars) | Cheating channels and mitigations | PP |
| S22 | METR, "Recent frontier models are reward hacking" | 2025-06-05 | FT | Reward-hack rates; prompts barely help | Blog |
| S23 | "EvilGenie", arXiv 2511.21654v2 | 2026-05-17 | FT | Detector miss rates | PP |
| S24 | "SpecBench", arXiv 2605.21384v1 | 2026-05-20 | FT | Visible-versus-hidden test gap | PP, SR |
| S25 | Qwen Team, "The Verification Horizon", arXiv 2606.26300v2 | 2026-06-29 | SS | Trajectory monitor in RL training | PP, vendor |
| S26 | Lodkaew et al., arXiv 2606.07379v2 | 2026-06-08 | AB + figure 1 | Capped-score detection idea | PP |

S17 (the second host's security pages) held almost no detail and supports nothing.

## Local observations

All were made on this Mac on 2026-11-08, as single runs. They demonstrate that the
boundary exists; they are not a security evaluation.

- **Mechanism and host observations (L1 to L8).**
  - **L1.** A deny-default profile built from the second host's policies allowed workspace
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
  - **L8.** Host `--help` flags and binary locations: two single native binaries
    (307 MB and 235 MB), both linking only system libraries
    ([curator hosts](operations/curator-hosts.md)).
- **L9.** The project's profile refused reads of the repository and home and writes
  to `trace/`, and allowed workspace reads and `scratch/` writes. With the Mach
  service allowlist it also refused access to the pasteboard and Launch Services.
- **L10.** With `(remote ip "localhost:P")`, port P connected over IPv4 and as
  `localhost`. Another loopback port, `::1` and an external address were refused.
- **L11.** In the project's environment, macOS refused to lower `RLIMIT_AS` and
  `RLIMIT_DATA` at any value ("current limit exceeds maximum limit").
- **L12. argv is readable, environments are not.** `KERN_PROCARGS2` of another
  same-user process returned its argv but not its environment, outside and inside
  the sandbox. That held under `process-info* (target self)` and under a named
  `sysctl-read` list. A `deny` of the name did not change it.
- **L13. Real first host, one turn.** The host ran headless in its minimal mode, with
  the proxy as its base URL and the session token as its key, against a local
  Messages-shape stand-in ([curator hosts](operations/curator-hosts.md)).
  - A shared temporary root under `/tmp` was refused with `EPERM`. With `scratch/`
    as its temporary directory, the host completed in at most 0.24 s and left a
    charge from the stand-in's synthetic usage in the ledger.
  - The upstream saw one `/v1/messages` streaming request carrying the real key.
  - The fresh home afterwards held only the host's own configuration, backups, plugin
    store and sessions directories.
- **L14. Real first host, a shell tool call.** A two-turn run with the host's shell tool:
  - The stand-in asked for a command that writes `scratch/`, reads
    `.runtime/credentials.json` and lists `~/../..`.
  - The tool result returned to the model was `written / secret-denied /
    users-denied`.
  - The run took 0.23 s, peaked at 157 MB and left no survivors.
- **L15.** A double-forked process that called `setsid` inside the sandbox
  re-parented to PID 1 and kept running after its parent exited. The `sandbox_check`
  path filters could not be used from Python to identify it: arm64 variadic calls
  returned −1.
