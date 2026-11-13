---
owner: lead
status: historical
kind: measurement
date: '2026-11-13'
scope: 'How many tokens a tool result costs before and after the short form (#606), measured two ways on the sealed traces of the seven-day lineage (#397) and the held-out lineage (#522): from the provider''s reported usage alone, which works for any model, and with a published tokenizer checked against that usage. No run, game launch or model call was made'
---

# Token counts of tool results, before and after the short form (#606)

## At a glance

- **Question.** How many tokens does a `computer_input` result cost the playing model,
  before and after the short form, and how can that be counted for any model?
- **Answer.**
  - **A result falls from a median of 636 tokens to 47**, and the first 150 results of
    an actor cost 112,216 fewer tokens (median of the seven actors that reached 150).
    The recorded median prompt at request 150 is 181,800 tokens, so that prompt would
    be about 69,600.
  - **A method that needs no tokenizer gets within about 6% of that.** It uses only the
    usage the provider reports: from one request to the next, the prompt grows by what
    was added. Fitted on that growth, a byte of result text costs 0.327 tokens, which
    gives 44 tokens for a short result and 598 for a full one.
  - **A tokenizer is exact here, and the same usage shows it.** With OpenAI's published
    `o200k_base` encoding, the tokens of the added result text predict the prompt's
    growth with a slope of 1.0006 (seven-day lineage) and 1.0008 (held-out lineage), and
    a median error of 0.2 and 0.1 tokens.
- **The rule this supports.** Count from the provider's reported usage, which every
  provider gives. Treat a tokenizer as a claim to be checked against that usage for the
  route in use, never as a fact about a model.
- **Not known.** The count for any other model or provider. Whether the route's model
  uses `o200k_base` for everything: this shows it for tool-result text. The effect on
  play.

Terms are in the [glossary](../glossary.md).

## Method

All commands were run from the main checkout at `10b2c93`, on sealed traces read in
place. The two tokenizer scripts ran in a throwaway environment outside the checkout
that held `tiktoken` 0.14.0; nothing was added to the project.

**Growth between consecutive requests.** Within one actor's trace, request `n+1`
contains everything request `n` did, plus the model's reply to `n`, plus the result of
the one tool call that reply made. So the difference in prompt tokens (`usage.input +
usage.cacheRead + usage.cacheWrite`) is the cost of what was added. Pairs are left out
when the host dropped images between them, when a notice was added, or when the reply
made no call or more than one. That leaves 1,817 pairs in the seven-day lineage and
1,655 in the held-out lineage.

**From usage alone.** The growth is fitted, by least squares, on the bytes of the
result text, the reply's output tokens, the number of images and a constant.

**With a tokenizer.** The growth is fitted on the tokens of the result text under the
encoding, the reply's visible output tokens, its reasoning tokens, the number of images
and a constant. If the encoding is the model's, the first slope is 1.

**The short form.** Each recorded `computer_input` result is rebuilt in the short form
with the same fields as `short_result` in `harness/player_view.py`, and both texts are
counted with the encoding.

## Results

| Quantity | Seven-day lineage | Held-out lineage |
| --- | ---: | ---: |
| Request pairs | 1,817 | 1,655 |
| **From usage alone:** tokens per byte of result text | 0.3273 | 0.3263 |
| Residual, median and 95th percentile | 12.8; 51.0 | 9.1; 36.0 |
| Predicted tokens for a 135-byte result; for 1,827 bytes | 44; 598 | 44; 596 |
| **With `o200k_base`:** slope on result-text tokens | 1.0006 | 1.0008 |
| Slope on the reply's visible output tokens; on its reasoning tokens | 0.9972; 0.9937 | 0.9932; 1.0000 |
| Tokens per image; constant per turn | 730.3; 14.7 | 727.7; 17.2 |
| Residual, median and 95th percentile | 0.2; 1.0 | 0.1; 0.2 |
| Share of pairs within 5 tokens | 98.2% | 99.9% |

Short form, seven-day lineage, 1,915 `computer_input` results, counted with
`o200k_base`:

| | Before | After |
| --- | ---: | ---: |
| Tokens per result, median | 636 | 47 |
| Range after | – | 44 to 52 |
| All results | 1,478,017 | 90,774 |
| Call arguments, median | 41 | 41 |

- **The total falls by 93.9%.**
- **A turn's text is about 88 tokens** with short results: 47 for the result and 41 for
  the call's arguments.
- **The reply's reasoning stays in the prompt.** Its slope is 1: each reasoning token
  the model spends is read again on every later request.
- **An image costs about 729 tokens** on this route. OpenAI's documented rule for
  32-pixel patches gives 720 for a 960 by 640 frame; the rest is framing.
- **With `cl100k_base`, an older encoding, the simpler fit gave a slope of 1.03**
  against 1.02 for `o200k_base`, so the check can tell one encoding from another, but
  only narrowly on this text.

## What this means

- **The context design's estimate holds.** It put the prompt at request 150 near 75,000
  tokens from a fit, then near 66,000 from bytes. Counted, it is about 69,600.
- **For another model or provider**, the usage method applies unchanged, because it
  reads only what the provider reports. A tokenizer for that model can be added as a
  check: it is trusted for a route only while its slope on that route's recorded usage
  is 1.
- **A tracked reader is the next step**, so that these figures come from a command and
  not from scripts in a record
  ([#609](https://github.com/CVX-Hull/enactive/issues/609)).

## Limits

- **One route and one model.** Both lineages ran `openai/gpt-6.1-terra` through
  OpenRouter.
- **The usage fit is an average.** It is within about 6% for these results; text with a
  different mix of words and identifiers would differ.
- **The image and constant terms of the usage fit are not separable**, because almost
  every turn has one image. Their sum is what the fit supports.
- **The short results were never sent to the model.** Their counts are the encoding's,
  on the strength of the slope check, not the provider's.
- **OpenAI's documentation was read through a summarising tool** by an explorer on
  13 November 2026: the [tokenizer's model table](https://raw.githubusercontent.com/openai/tiktoken/main/tiktoken/model.py),
  the [token counting guide](https://developers.openai.com/api/docs/guides/token-counting)
  and the [vision guide](https://developers.openai.com/api/docs/guides/images-vision),
  all undated. None names this model's encoding or its image rule.

## Appendix: the scripts

One-off scripts. Each takes run directories, for example
`.runtime/evidence/397-seven-day/computer-sessions/sd1a*`.

From usage alone (the project's own Python):

```python
import glob, json, sys, numpy as np
rows = []
for path in sorted(p for run in sys.argv[1:] for p in glob.glob(run + "/actors/*/host.jsonl")):
    prompt, out, omitted, notice, results, order = {}, {}, {}, set(), {}, []
    for line in open(path):
        e = json.loads(line); t = e["type"]
        if t == "request-start": order.append(e["request_id"])
        elif t == "context-image-projection": omitted[e["request_id"]] = e["omitted_images"]
        elif t == "tail-notice": notice.add(e["request_id"])
        elif t == "response-complete" and e.get("usage_available"):
            u = e["usage"]; prompt[e["request_id"]] = u["input"] + u["cacheRead"] + u["cacheWrite"]; out[e["request_id"]] = u["output"]
        elif t == "tool-result":
            c = e["result"].get("content") or []
            results.setdefault(e["request_id"], []).append((sum(len(p.get("text", "").encode()) for p in c if p.get("type") == "text"), sum(p.get("type") == "image_reference" for p in c)))
    for a, b in zip(order, order[1:]):
        if a in prompt and b in prompt and omitted.get(a) == omitted.get(b) and b not in notice and len(results.get(a, [])) == 1:
            rows.append((prompt[b] - prompt[a], results[a][0][0], out[a], results[a][0][1]))
d = np.array(rows, float); X = np.c_[d[:, 1], d[:, 2], d[:, 3], np.ones(len(d))]
coef, *_ = np.linalg.lstsq(X, d[:, 0], rcond=None); res = d[:, 0] - X @ coef
print(f"{len(d)} pairs: {coef[0]:.4f} tokens per byte of result text, {coef[1]:.3f} per output token of the reply, {coef[2]:.1f} per image, constant {coef[3]:.1f}; residual median abs {np.median(abs(res)):.1f}, 95th pct {np.percentile(abs(res), 95):.1f}")
print(f"predicted for a 135-byte result: {coef[0] * 135:.0f} tokens; for 1,827 bytes: {coef[0] * 1827:.0f}")
```

With the tokenizer (an environment that has `tiktoken`):

```python
import glob, json, sys, numpy as np, tiktoken
enc = tiktoken.get_encoding("o200k_base"); rows = []
for path in sorted(p for run in sys.argv[1:] for p in glob.glob(run + "/actors/*/host.jsonl")):
    prompt, out, reason, omitted, notice, calls, results, order = {}, {}, {}, {}, set(), {}, {}, []
    for line in open(path):
        e = json.loads(line); t = e["type"]
        if t == "request-start": order.append(e["request_id"])
        elif t == "context-image-projection": omitted[e["request_id"]] = e["omitted_images"]
        elif t == "tail-notice": notice.add(e["request_id"])
        elif t == "response-complete" and e.get("usage_available"):
            u = e["usage"]; r = e["request_id"]; prompt[r] = u["input"] + u["cacheRead"] + u["cacheWrite"]; out[r] = u["output"]; reason[r] = u.get("reasoning", 0)
        elif t == "tool-start": calls.setdefault(e["request_id"], []).append(e["arguments"])
        elif t == "tool-result":
            c = e["result"].get("content") or []
            results.setdefault(e["request_id"], []).append(("".join(p.get("text", "") for p in c if p.get("type") == "text"), sum(p.get("type") == "image_reference" for p in c)))
    for a, b in zip(order, order[1:]):
        if a not in prompt or b not in prompt or omitted.get(a) != omitted.get(b) or b in notice or len(calls.get(a, [])) != 1 or len(results.get(a, [])) != 1: continue
        text, images = results[a][0]
        rows.append((prompt[b] - prompt[a], len(enc.encode(text)), out[a] - reason[a], reason[a], images))
d = np.array(rows, float); X = np.c_[d[:, 1], d[:, 2], d[:, 3], d[:, 4], np.ones(len(d))]
coef, *_ = np.linalg.lstsq(X, d[:, 0], rcond=None); res = d[:, 0] - X @ coef
print(f"{len(d)} pairs: result-text tokens {coef[0]:.4f}, visible output {coef[1]:.4f}, reasoning {coef[2]:.4f}, per image {coef[3]:.1f}, constant {coef[4]:.1f}")
print(f"residual: median abs {np.median(abs(res)):.1f}, 95th pct abs {np.percentile(abs(res), 95):.1f}, within 5 tokens {np.mean(abs(res) <= 5):.3f}")
```

The short-form count tokenises each recorded `computer_input` result text and its
rebuilt short form (`schema`, `status`, and `source_id`, `width` and `height` where
there is a frame) with the same encoding, and sums the difference over each actor's
first 150 results.
