---
date: '2026-10-17'
owner: lead
scope: Engineering-system acceptance — 2026-10-17
status: historical
---

# Engineering-system acceptance — 2026-10-17

Owner: lead. Status: locally verified increment. Scope: documentation, development
controls and CI definition; no game/controller/native behavior changed. The Git
checkpoint containing this report identifies the delivered candidate. Base was
88dd803 (the demonstrated MVP). This is a dated record, not live tool status.

## Delivered outcomes

- Seven principles distinguish user constraints, assumptions and revisable decisions.
- Ten standards map to eleven controls with owners, triggers, evidence, enforcement,
  failure response and coverage limits. The readable map is generated and drift checked.
- Overview/charter/current architecture/protocol/ADRs/operations/work/history have
  distinct roles; the user can review direction without implementation detail.
- Established tools replace generic custom validation/import walking/Markdown parsing.
  jsonschema 4.26.0, Import Linter 2.15, Ruff 0.17.1 and markdown-it-py 4.2.0 are
  development-only, with 14 total pinned distributions and artifact hashes.
- Maintenance/release/exception/research/retention practices have accountable roles
  and triggers. No scheduler or automatic deletion job was introduced.
- Historical MVP provenance is tracked without media or machine-specific build paths.
  Six referenced local artifact/journal byte counts and hashes were reverified;
  the installed Resources/cataclysm-tiles hash matches its historical manifest.

## Validation and review

On macOS 26.6.2 arm64, Python 3.14.7 and Node 26.9.0:

| Lane | Result and scope |
| --- | --- |
| Dependency installation | Hash-required uv install into project .venv succeeded from project cache/public PyPI; pinned transitive packages installed locally |
| Common portable command | `.venv/bin/python tools/check.py` passed: 60 Python tests, four production-JS viewer race scenarios, Python/JS syntax, Ruff, two Import Linter contracts, schema/mapping/protocol/map/file-link checks and whitespace |
| Real-tool negative fixtures | Detected direct/indirect forbidden imports, server-to-CLI/tooling imports, undefined Python name, broken reference-style Markdown links/images; permitted composition passed |
| Governance negative fixtures | Detected missing/unknown/duplicate mappings, invalid fields/paths/hashes, stale generated output and six protocol-version drifts; fresh source fixtures need no ignored demo media |
| User reviewability | Fresh-context reviewer and lead walked overview/immediate links; checked questions below and preserved consequential operating limits |
| Independent technical review | Reviewer inspected scripts, schemas, config, lock, tests, registry/map and current docs; targeted checks passed; no actionable findings remained |
| Staged source export | Full common lane passed on tree `ef964cecc2133caf59b61c86556c9d3aaa455510`, without ignored runtime media; only this result-recording update follows that export |

The source export used the same pinned project interpreter/tools with an isolated
checkout directory and no .runtime media. It installed nothing and launched no game.
The final result-recording update is staged with the same source; the checkpoint
hook reruns the common lane on that fully staged candidate before committing.

## Reviewability walkthrough

| User question | Where it is answered |
| --- | --- |
| What are we trying to achieve, and what constrains it? | Overview → charter purpose/constraints/principles |
| What works and what are the limits? | Overview capability table and pause/planner/error-screen limitations |
| Why is it structured this way? | Overview system picture → current architecture and linked platform/transport decisions |
| What changed and what comes next? | Overview latest increment → brief, acceptance and current work priorities |
| Why should I trust the claims? | Overview → scoped acceptance and control map; native and portable evidence remain separate |

This is a reviewer walkthrough, not a claim that the user has personally approved
comprehension or that long-term maintenance benefits have already been measured.

## Failures and corrections

Initial restricted network resolution failed with DNS denial; the authorized
network run succeeded. Restricted common checks failed nine existing HTTP tests
with loopback EPERM; the full permission-enabled run passed, without skipping or
weakening tests. The initial custom generic validation/import-walker draft was
replaced following the user's reuse requirement; configuration-specific negative
cases exercise the adopted tools.

Independent document review found two current limits stranded in historical
acceptance: an advertised action may lack a usable key binding, and a walk can
report stopped after all requested displacement. Both now appear in current
protocol/runbook guidance. Lead verified them against native/controller sources.

## Remaining limits and maintenance

No fresh native build/gameplay was run because runtime sources and dependencies
were unchanged. Existing native evidence remains the [MVP report](2026-10-17-mvp.md).
CI installation is configured but unexecuted remotely; no remote/branch protection
or hosted required checks exist. Local hooks remain bypassable and inspect the
working tree; partial staging needs isolated candidate verification.

Static imports do not prove dynamic runtime dependencies; source version agreement
does not prove native protocol semantics. Schema validity and file links do not
prove prose truth, media availability, or operator understanding. Heading anchors,
raw HTML links and external availability are not covered by the automated link
check. Formatting/type completeness and semantic design remain review concerns.
Manual control execution is not automatically monitored. Tool upgrades require
review and rerunning configuration-specific negative cases. The 90-day active
maintenance interval and 30-day unreferenced journal eligibility are initial
policies to revise with evidence; no volume metric is a quality target.
