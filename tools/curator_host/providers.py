"""The model providers a curator host can reach, as values for `harness.curator.proxy.ModelProxy`.

The proxy is provider-neutral; each `Provider` here carries what is specific to one provider: its
route, key header, request allowlists, extra refusals, forwarded headers and how a response's
usage becomes dollars. Provider and model names belong in the host adapters (S-ARCH, ADR 010).

Image reservation (`harness.curator.proxy.IMAGE_TOKENS`): a provider bills an image by its pixels
after scaling, not by its encoding. Anthropic bills about width x height / 750 tokens after scaling
to at most about 1.15 megapixels (about 1,600 tokens).
"""
from __future__ import annotations

from decimal import Decimal

from harness.curator.proxy import Price, Provider, response_events, usage_events

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
# (#454; ADR 009 open decision 2). Checked on 8 November 2026 against
# openrouter.ai/docs/api/reference/overview, /docs/use-cases/usage-accounting and /docs/faq:
# - usage, including `cost`, is always returned, and the base currency is US dollars;
# - `plugins` (`web` is live web search), `models` and `route` (fallback models), `prompt`, `debug`
#   and `user` are left out of the allowlist;
# - `image_url` accepts remote URLs, so only `data:` URLs pass.
# The fields are those the project's curator host serializer sends for an OpenRouter model.

# Provider preferences that only choose among backends for the requested model.
ROUTING = frozenset({'order', 'only', 'ignore', 'allow_fallbacks', 'require_parameters', 'data_collection', 'zdr'})


def _openrouter_tool(tool: dict) -> str | None:
    return None if tool.get('type') == 'function' else 'only function tools are allowed'


def _openrouter_request(request: dict) -> str | None:
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
    return (usage.get('prompt_tokens', 0) * price.worst_input + usage.get('completion_tokens', 0) * price.output) / PER


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
               'tools', 'tool_choice', 'reasoning', 'provider', 'store'}),
    frozenset({'text', 'image_url', 'function', 'reasoning.text', 'reasoning.summary', 'reasoning.encrypted'}),
    tool_refusal=_openrouter_tool, cost=_openrouter_cost, request_refusal=_openrouter_request,
    affinity_header='x-session-id', response_error=_openrouter_error, **COMMON)
