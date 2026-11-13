---
owner: lead
status: historical
kind: measurement
date: '2026-11-12'
scope: 'Six real requests on the pinned player route on 12 November 2026 to see whether OpenRouter reports the cost of each response, with what request shape and whether the route uses the caller''s own provider key (#555); one route, one day, no failed or cut-off request'
---

# Provider cost pilot on the player route, 12 November 2026

## Why

The [proposal](../design/provider-reported-spend-limit.md) to cap player runs by a
dollar limit from provider-reported cost
([#555](https://github.com/CVX-Hull/enactive/issues/555)) depends on OpenRouter reporting
a cost with each response on the player route. Nothing in the project showed that it
does. The library the player host uses asks for usage in the stream and then discards
any cost field, so no sealed trace holds one. The proposal's first step was therefore
a pilot, and its rule was that the work stops if cost is not reported. The owner
approved a few real requests for it, about five cents in total (decision 4 on #555).

## What was sent

The lead sent six small requests through OpenRouter to the player route's pinned model,
`openai/gpt-6.1-terra`, served by provider `openai`, and kept the usage record of each
response as it came back.

| | Request | Shape |
| --- | --- | --- |
| 1 | Plain reply | Streamed with `stream_options.include_usage`, which is what the host sends today |
| 2 | Plain reply | As 1, with the request option OpenRouter documents for usage accounting, `usage: {include: true}` |
| 3 | Tool call | As 1 |
| 4 | Long prompt, first time | As 1; the prompt is written to the cache |
| 5 | The same long prompt again | As 1; the prompt is read from the cache |
| 6 | Plain reply | Not streamed |

## What came back

Every request returned HTTP 200 and exactly one usage record, and every record carried
a `cost`.

| | Prompt tokens | Completion tokens | Cache read tokens | Cache write tokens | Reported cost (USD) | Own-key flag (`is_byok`) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 13 | 5 | 0 | 0 | 0.000038 | false |
| 2 | 13 | 5 | 0 | 0 | 0.000038 | false |
| 3 | 48 | 18 | 0 | 0 | 0.000138 | false |
| 4 | 3,229 | 5 | 0 | 3,226 | 0.0040605 | false |
| 5 | 3,229 | 5 | 3,226 | 0 | 0.0001893 | false |
| 6 | 13 | 5 | 0 | 0 | 0.000038 | false |

In every record `cost_details.upstream_inference_cost` equals `cost`. The six raw
records are in [the pilot output](assets/provider-cost-pilot-555.jsonl).

## Conclusion

- OpenRouter reports the cost of each response on this route with the request exactly
  as the host sends it today: streamed, with `stream_options.include_usage`.
- The extra request option is not needed. Requests 1 and 2 returned the same record.
- The route is not on the caller's own provider key: `is_byok` is false throughout,
  so the reported `cost` is the whole charge.
- The cost follows cache pricing: the repeated long prompt cost about a twentieth of
  its first sending.

The proposal therefore goes on to its next step, recording this cost in the host trace.

## Spend

The six records report $0.0045018 in total, about half a cent.

## Limits

- One route, one day and six requests. Another model, provider or date may differ.
- No request failed, timed out or was cut off mid-stream, so the pilot does not show
  whether such a request carries a cost record or is billed.
- No own-key route was exercised. The rule for one, the fee plus the upstream inference
  cost, comes from the curator's existing reading of OpenRouter's usage record, not
  from this pilot.
- The total is what the records say. This record does not check it against the
  account's billing page.
