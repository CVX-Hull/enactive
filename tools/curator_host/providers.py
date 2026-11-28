"""The model providers a curator host can reach, as values for `harness.curator.proxy.ModelProxy`.

The proxy is provider-neutral; each `Provider` here carries what is specific to one provider: its
route, key header, request allowlists, extra refusals, forwarded headers and how a response's
usage becomes dollars. Provider and model names belong in the host adapters (S-ARCH, ADR 010).

Image reservation uses pixels after provider scaling. The Terra bound for 960x640 PNGs
is route-specific. Other images retain the proxy's generic bound.
"""
from __future__ import annotations

import base64
from decimal import Decimal
import json

from harness.curator.proxy import IMAGE_TOKENS, Price, Provider, body_token_bound, canonical_bytes, inline_images, response_events, usage_events

PER = Decimal(1_000_000)

# Headers the proxy has always passed for every provider: the API version and the beta flags (the
# latter only from the proxy's frozen set).
COMMON = dict(forward_headers=frozenset({'anthropic-version'}), beta_header='anthropic-beta')


# -- Anthropic messages ------------------------------------------------------------------------
def _anthropic_tool(tool: dict) -> str | None:
    if 'input_schema' not in tool or tool.get('type') not in (None, 'custom'):
        return 'only client tools with an input schema are allowed'
    return None


def _checked_token_usage(usage: dict[str, int], body: bytes, required: tuple[str, ...], optional: tuple[str, ...] = ()) -> None:
    if any(name not in usage for name in required):
        raise ValueError('required token accounting is missing')
    for found in usage_events(body):
        for name in (*required, *optional):
            if name in found and (not isinstance(found[name], int) or isinstance(found[name], bool) or found[name] < 0):
                raise ValueError('invalid token accounting')
        if 'cache_creation' in found and 'cache_creation_input_tokens' not in found:
            nested = found['cache_creation']
            if nested is not None and (not isinstance(nested, dict) or any(
                    not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in nested.values())):
                raise ValueError('invalid cache token accounting')


def _anthropic_cost(price: Price, usage: dict[str, int], body: bytes) -> Decimal:
    _checked_token_usage(usage, body, ('input_tokens', 'output_tokens'),
                         ('cache_creation_input_tokens', 'cache_read_input_tokens'))
    return (usage.get('input_tokens', 0) * price.input + usage.get('output_tokens', 0) * price.output
            + usage.get('cache_creation_input_tokens', 0) * price.cache_write
            + usage.get('cache_read_input_tokens', 0) * price.cache_read) / PER


ANTHROPIC = Provider(
    'anthropic', frozenset({'/v1/messages'}), 'x-api-key', 'max_tokens',
    frozenset({'model', 'max_tokens', 'messages', 'system', 'tools', 'tool_choice', 'stream', 'metadata',
               'stop_sequences', 'thinking', 'output_config', 'cache_control', 'temperature', 'top_p', 'top_k',
               'context_management'}),
    frozenset({'text', 'image', 'tool_use', 'tool_result', 'thinking', 'redacted_thinking'}),
    tool_refusal=_anthropic_tool, cost=_anthropic_cost, **COMMON)


# -- OpenRouter chat completions ---------------------------------------------------------------
# (#454; ADR 009's owner decision on the curator's spend cap and model). Checked on 8 November 2026 against
# openrouter.ai/docs/api/reference/overview, /docs/use-cases/usage-accounting and /docs/faq:
# - usage, including `cost`, is always returned, and the base currency is US dollars;
# - `plugins` (`web` is live web search), `models` and `route` (fallback models), `prompt`, `debug`
#   and `user` are left out of the allowlist;
# - `image_url` accepts remote URLs, so only `data:` URLs pass.
# The fields are those the project's curator host serializer sends for an OpenRouter model.

# Provider preferences that only choose among backends for the requested model.
ROUTING = frozenset({'order', 'only', 'ignore', 'allow_fallbacks', 'require_parameters', 'data_collection', 'zdr'})
TERRA = 'openai/gpt-6.1-terra'
PNG_960X640_PREFIX = 'data:image/png;base64,' + base64.b64encode(
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR' + (960).to_bytes(4) + (640).to_bytes(4)).decode()
# Four such frames added about 3,600 prompt tokens in the sealed #896-b A7 trace.
# Reserve for the route's full image detail, including variation across frames.
TERRA_FRAME_TOKENS = 3_000


def _pinned_terra(model: str, request: object) -> bool:
    routing = request.get('provider') if isinstance(request, dict) else None
    return (model == TERRA and isinstance(routing, dict)
            and routing.keys() == {'only', 'order', 'allow_fallbacks', 'require_parameters'}
            and routing['allow_fallbacks'] is False and routing['require_parameters'] is True
            and routing['only'] == routing['order'] and routing['only'] in (['openai'], ['openai/flex']))


def _openrouter_prompt_bound(model: str, body: bytes, request: object) -> int:
    if not _pinned_terra(model, request):
        return body_token_bound(model, body, request)
    messages = request.get('messages', [])
    tools = request.get('tools') or []
    if not isinstance(messages, list) or not isinstance(tools, list):
        return body_token_bound(model, body, request)
    return _terra_bound(body, messages, request) + 32 * len(tools)


def suffix_prompt_bound(model: str, suffix_messages: list, request: object) -> int:
    body = canonical_bytes(suffix_messages)
    suffix_request = {'messages': suffix_messages}
    if _pinned_terra(model, request):
        return _terra_bound(body, suffix_messages, suffix_request)
    return body_token_bound(model, body, suffix_request) + 256 + 32 * len(suffix_messages)


def _terra_bound(body: bytes, messages: list, request: dict) -> int:
    # Text in a message is tokenized as decoded content. Exclude the wire JSON's
    # escaping for that content only. Keep the complete byte bound for arguments,
    # schemas and unfamiliar shapes, and allow for provider-side prompt framing.
    saved = 0
    for message in messages:
        content = message.get('content') if isinstance(message, dict) else None
        parts = content if isinstance(content, list) else []
        texts = [content] if isinstance(content, str) else [
            part.get('text') for part in parts if isinstance(part, dict) and part.get('type') == 'text']
        for value in texts:
            if isinstance(value, str):
                saved += len(json.dumps(value)) - 2 - len(value.encode('utf-8', 'backslashreplace'))
    image_adjustment = sum((TERRA_FRAME_TOKENS if data.startswith(PNG_960X640_PREFIX) else IMAGE_TOKENS) - len(data)
                           for data in inline_images(request))
    return len(body) - saved + image_adjustment + 256 + 32 * len(messages)


def _openrouter_tool(tool: dict) -> str | None:
    return None if tool.get('type') == 'function' else 'only function tools are allowed'


def _openrouter_request(request: dict) -> str | None:
    if request.get('service_tier') not in ('default', 'flex'):
        return 'the service tier must be explicitly requested as default or flex'
    routing = request.get('provider')
    if routing is not None and not (isinstance(routing, dict) and set(routing) <= ROUTING):
        return 'provider routing may only order, require or restrict providers'
    if request.get('store') not in (None, False):
        return 'provider-side storage is not allowed'
    return None


def _amount(value) -> Decimal | None:
    if isinstance(value, (Decimal, int)) and not isinstance(value, bool):
        amount = Decimal(value)
        if amount.is_finite() and amount >= 0:
            return amount
    return None


def reported_cost(body: bytes) -> Decimal | None:
    """The whole charge for a request (US dollars), or None when the provider reported none.

    OpenRouter's `usage.cost` is what it bills the account. On a bring-your-own-key route that is
    only its fee: the provider bills `cost_details.upstream_inference_cost` to the operator's own
    key. Both are counted, so the cap tracks the real spend on either route.
    Null/absent amounts permit token fallback; malformed values or incomplete BYOK charges raise
    ValueError so the proxy retains the reservation instead of silently treating them as zero.
    """
    charges = []
    for found in usage_events(body):
        cost = _amount(found.get('cost'))
        if found.get('cost') is not None and cost is None:
            raise ValueError('invalid reported cost')
        details = found.get('cost_details')
        if details is not None and not isinstance(details, dict):
            raise ValueError('invalid cost details')
        details = details or {}
        upstream = _amount(details.get('upstream_inference_cost'))
        if details.get('upstream_inference_cost') is not None and upstream is None:
            raise ValueError('invalid upstream cost')
        if found.get('is_byok') is not None and not isinstance(found['is_byok'], bool):
            raise ValueError('invalid billing route indicator')
        if found.get('is_byok') is True and (cost is None or upstream is None):
            raise ValueError('incomplete bring-your-own-key accounting')
        if cost is None and upstream is None:
            continue
        charges.append((cost or Decimal(0)) + (upstream or Decimal(0)) if found.get('is_byok') is True
                       else max(cost or Decimal(0), upstream or Decimal(0)))
    return max(charges) if charges else None


def _openrouter_cost(price: Price, usage: dict[str, int], body: bytes) -> Decimal:
    # The provider's reported charge is authoritative. Without it, all prompt tokens are
    # charged at the highest input-side price, so cache writes are never undercounted.
    reported = reported_cost(body)
    if reported is not None:
        return reported
    _checked_token_usage(usage, body, ('prompt_tokens', 'completion_tokens'))
    prompt = usage['prompt_tokens']
    return price.at(prompt).charge(prompt, usage['completion_tokens'])


# OpenRouter's canonical error types (errors-and-debugging, checked 11 November 2026).
# Values are an allowlist: arbitrary messages, metadata and provider-native codes never leave here.
ERROR_TYPES = frozenset({'context_length_exceeded', 'max_tokens_exceeded', 'token_limit_exceeded', 'string_too_long',
                         'authentication', 'permission_denied', 'payment_required', 'rate_limit_exceeded',
                         'provider_overloaded', 'provider_unavailable', 'invalid_request', 'invalid_prompt',
                         'not_found', 'refusal', 'content_policy_violation', 'invalid_image', 'image_too_large',
                         'image_too_small', 'server', 'timeout', 'unmapped', 'precondition_failed',
                         'payload_too_large', 'unprocessable', 'unsupported_image_format', 'image_not_found',
                         'image_download_failed'})


def _openrouter_error(body: bytes) -> dict | None:
    for event in response_events(body):
        error = event.get('error')
        if not isinstance(error, dict):
            continue
        metadata = error.get('metadata')
        kind = metadata.get('error_type') if isinstance(metadata, dict) else None
        code = error.get('code')
        return dict(kind='provider-error-event', error_type=kind if isinstance(kind, str) and kind in ERROR_TYPES else None,
                    error_code=code if isinstance(code, int) and not isinstance(code, bool) and 100 <= code <= 599 else None)
    return None


OPENROUTER = Provider(
    'openrouter', frozenset({'/api/v1/chat/completions'}), 'authorization', 'max_completion_tokens',
    frozenset({'model', 'messages', 'stream', 'stream_options', 'max_completion_tokens', 'temperature', 'top_p',
               'tools', 'tool_choice', 'reasoning', 'provider', 'store', 'service_tier'}),
    frozenset({'text', 'image_url', 'function', 'reasoning.text', 'reasoning.summary', 'reasoning.encrypted'}),
    tool_refusal=_openrouter_tool, cost=_openrouter_cost, request_refusal=_openrouter_request,
    affinity_header='x-session-id', response_error=_openrouter_error, prompt_bound=_openrouter_prompt_bound,
    suffix_bound=suffix_prompt_bound, **COMMON)
