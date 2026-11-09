---
owner: lead
status: historical
date: '2026-11-08'
scope: 'The Enactive Project reduced to four statuses, Priority on leaves and Horizon on outcomes, with every item''s earlier field values exported first (ADR 010 L5, #503)'
---

# Project simplification, 8 November 2026

[ADR 010](../decisions/010-streamlined-delivery.md)'s owner decision 4 reduced the Project
to the statuses Backlog, Ready, In progress and Done, Priority on leaves and Horizon on
outcomes, with no hand-kept dates. The current rules are in
[work items](../workflows/work-items.md).

**Export first.** Before any field or option was removed, every Project item and every
field value it held was exported to [`items.json`](assets/project-2026-11-08/items.json)
(`project-export/1`: the field list with options, then one row per item with its issue or
pull request number, title, state, URL and field values). At export the Project held 243
items; 154 had a Started date, 238 a Size, and one leaf (#504) was in Review.

**Changes.**
- The Review and Validation status options were removed; the one item in Review was
  moved to In progress first. The other options kept their identifiers, so no item's
  status changed.
- The Size, Confidence, Started and Finished fields were deleted. Their values are in the
  export.
- The Current iteration, Backlog and Needs attention views select leaves by Status
  instead of Horizon; Direction still groups outcomes by Horizon.
