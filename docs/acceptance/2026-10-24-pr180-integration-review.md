---
owner: lead
status: historical
date: 2026-10-24
scope: Source integration review and focused repairs after23cc5e4; no new native or gameplay qualification
---

# Integrated source checkpoint review

The user requested wrapping up open PRs before audit remediation. PR180 was the
only open PR:300files,45,589 additions and3,532 deletions at23cc5e4. The lead chose
one coordinated source integration rather than intermediate incompatible contracts.
Five independent component reviews cover player ingress/context, mission/lifecycle,
memory/program/reflection, native/controller, and observer/setup. They review
critical flows and changed contracts; they are not an exhaustive line-by-line or
security audit, human GitHub approval, or successful full-campaign acceptance.

## Findings and repairs

- Lifecycle phase checkpoints incorrectly fell back to a historical ACK after a
  newer healthy current capture. Resume, control, stage commit, Save and identity
  inspection now retain the current checkpoint separately from immutable delivery
  and identity-screen proof. Current drift ends batching for another decision;
  non-equivalent confirmations lose stage consent and diagnostics remain fenced.
- Repeated known zero-admission busy responses stranded an advisory Claim behind
  its local stage. Only the validated Claim busy receipt releases that stage for
  another bounded call. Missing/uncertain/admitted receipts and submissions retain
  collection-only behavior and original identity.
- Image deduplication remembered images before response construction succeeded.
  Presentation now occurs after background work returns. Formatting failures,
  cancellation with a still-running worker, and intervening historical images
  cannot establish a false last-shown fingerprint.
- Procedure context read every dependency image before enforcing its work limit.
  It now checks qualified closure size first, shares one operation cache and counts
  verified candidates even when packet bytes later omit them. Canonical selection
  remains strict; complete handoff still fails rather than silently truncates.

Focused regressions pass:126 client/memory/library tests in2.694s;46 existing
lifecycle/load/ACK tests in49.017s; eight targeted capture/presentation tests in1.555s;
61 final client/tool/MCP and additional lifecycle tests in7.303s. These lanes overlap
and their counts must not be summed as unique tests. Earlier HTTP fixture attempts
were denied loopback setup; the later allowed lane passes. Worker library tests
were denied worktree-local runtime creation; the integrated126-test lane covers
that library. Ruff and fast structural checks pass. Independent verify-fix reviews
find no remaining actionable defect in their changed scopes.

The native reviewer checks retained build/source correspondence without launching
or rebuilding CDDA. No new game, benchmark, save mutation or graphical probe is
performed. Fresh024 and its unproved prompt-observation failure remain failed and
owned by #145/#176; these source defects are not asserted as its production cause.
Full independent survival, actual host responsiveness, wider native support and
causal learning remain unaccepted. The [audit](2026-10-24-architecture-governance-audit.md)
retains original findings; #75/#198/#199 own the subsequent remediation.

Exact candidate checks, protected merge and merged-main verification are separate
publication evidence owned by [PR180](https://github.com/CVX-Hull/enactive/pull/180).
This report does not claim those later events merely because focused checks pass.
