---
owner: lead
status: historical
kind: change
date: '2026-11-12'
scope: 'The repository setting that auto-closes issues on merge turned off, and the manual closing-reference check before each merge removed, on the owner''s decision of 12 November 2026 (#556)'
---

# Issue auto-close turned off, 12 November 2026

Before each merge the lead read the pull request's closing references and required
none. The step existed because a closing phrase once closed an issue before its
validation ([#75](https://github.com/CVX-Hull/enactive/issues/75)); writing "does not
close" in prose does not stop GitHub's keyword parsing.

The owner decided on 12 November 2026 to replace the step with the repository setting
that removes the cause ([#556](https://github.com/CVX-Hull/enactive/issues/556)).

- **What changed on GitHub.** In the repository's Settings, under General and Issues,
  "Auto-close issues with merged linked pull requests" is unticked. The owner signed
  in and approved the change; the lead made it in the browser and confirmed after a
  reload that it had saved. The setting belongs to this repository only.
- **What changed in the documents.** The work-items page and the work standard state
  that merging closes nothing and name the setting. The manual check is gone.
- **What covers the risk now.** The setting. The failure it stops is Low in the
  [risk register](../risks.md) terms, an issue shown as done early, and it cannot occur
  while the setting is off.
- **Limit.** GitHub's API does not expose this setting, so no check can read it. If
  someone turns it on again, the manual check is needed again; the work-items page says
  so.
