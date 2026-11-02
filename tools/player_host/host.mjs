import { isDeepStrictEqual } from 'node:util';
import { createHash } from 'node:crypto';
import { Agent } from '@earendil-works/pi-agent-core';
import { Type, AssistantMessageEventStream, isRetryableAssistantError } from '@earendil-works/pi-ai';
import { stream } from '@earendil-works/pi-ai/api/openai-completions';
import { retryProviderRequest } from '@earendil-works/pi-ai/utils/provider-retry';
import { McpClient, StdioTransport, toLlmContent } from '@earendil-works/pi-mcp';
import { createValidationFeedback, FIX_LINE } from './validation-feedback.mjs';

export const INPUT_LIMIT_BYTES = 1_048_576;
// A level pass ends with exactly one of these calls, and a recorder pass with exactly one of the episode calls. On its last
// LEVEL_RESERVED_REQUESTS requests a pass role's host offers only its own terminal tools.
export const LEVEL_TERMINAL_TOOLS = ['player_level_keep', 'player_level_replace', 'player_level_close', 'player_level_abstain'];
export const EPISODE_TERMINAL_TOOLS = ['player_episode_record', 'player_episode_abstain'];
export const LEVEL_RESERVED_REQUESTS = 2;
// The pass roles. `prefix` names the role's events, tool-refusal reasons and settlement reasons.
const PASS_ROLES = {
  level: {prefix:'level', tools:LEVEL_TERMINAL_TOOLS, unended:'level-no-proposal'},
  recorder: {prefix:'episode', tools:EPISODE_TERMINAL_TOOLS, unended:'episode-no-record'}};
// One line after a tool's example call, for what a minimal example cannot show.
const TERMINAL_NOTES = {
  player_level_replace:'In this example previous_outcome is "none" with an empty previous_reason, which is valid only when there is no current subgoal; whenever there is one, set previous_outcome to achieved, failed, abandoned or revised and give previous_reason.',
  player_episode_record:'In this example observation_status is empty, which is valid only when no subgoal was pushed; otherwise give one entry (seen, not_yet or contradicted) per expected observation of the pushed subgoal, in order. changed and residual may be empty.'};
// The recorder's pushed input: frames the host reads itself, so no image crosses the 1 MiB stdin bound.
export const PASS_INPUT_SCHEMA = 'player-pass-input/1';
export const FRAME_ROLES = ['baseline', 'in-episode', 'last'];
export const MAX_FRAMES = 7;
// openai@7.19.0 client.mjs reads these despite Pi's scoped env option.
// Their values can alter request headers or enable raw SDK logging.
const AMBIENT_PROVIDER_SETTINGS = ['OPENAI_LOG', 'OPENAI_CUSTOM_HEADERS', 'OPENAI_ORG_ID', 'OPENAI_PROJECT_ID'];
const MCP_LIMIT_BYTES = 32 * 1_048_576;
const PROVIDER_ERROR_LIMIT_BYTES = 16_384;
// Adopt the pinned SDK helper's maintained default; original request/host
// deadlines and one retry remain the outer bounds.
const MAX_RETRY_DELAY_MS = 60000;
// Upstream gateway failures are eligible by status alone; 500 and other codes stay terminal.
const SERVER_RETRY_STATUSES = [502, 503, 504];
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const positive = value => typeof value === 'number' && Number.isFinite(value) && value > 0;
const text = value => typeof value === 'string' && value.length > 0;
const levels = ['off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'];
export class HostError extends Error {
  constructor(reason) { super(reason); this.reason = reason; }
}
function requireThat(condition, reason = 'invalid-configuration') {
  if (!condition) throw new HostError(reason);
}
function closed(value, allowed) {
  requireThat(object(value) && Object.keys(value).every(key => allowed.includes(key)));
}
function finiteMilliseconds(seconds) {
  return positive(seconds) && seconds * 1000 <= 2_147_483_647;
}
function bounded(value) {
  requireThat(Buffer.byteLength(typeof value === 'string' ? value : JSON.stringify(value)) <= INPUT_LIMIT_BYTES, 'input-too-large');
}

/** One frozen route, without credential values, ambient discovery or effort clamping. */
export function validateConfiguration(configuration, selectedModel, effort) {
  bounded(configuration);
  closed(configuration, ['schema', 'role', 'intent_tail_bytes', 'model', 'api_key_env', 'max_requests', 'max_context_images', 'context_image_block', 'request_timeout_seconds', 'service_tier']);
  requireThat(configuration.schema === 'player-host/6');
  // An actor may carry the intent tail, whose fixed allocation is the one bound of INTENT_TAIL_BYTES; a level or a recorder never does.
  requireThat(['actor', 'level', 'recorder'].includes(configuration.role));
  requireThat(configuration.intent_tail_bytes === null
    || (configuration.role === 'actor' && configuration.intent_tail_bytes === INTENT_TAIL_BYTES));
  requireThat(/^[A-Za-z_][A-Za-z0-9_]*$/.test(configuration.api_key_env ?? '') && !AMBIENT_PROVIDER_SETTINGS.includes(configuration.api_key_env));
  requireThat(Number.isSafeInteger(configuration.max_requests) && configuration.max_requests > 0);
  requireThat(Number.isSafeInteger(configuration.max_context_images) && configuration.max_context_images > 0);
  requireThat(Number.isSafeInteger(configuration.context_image_block) && configuration.context_image_block > 0
    && configuration.context_image_block <= configuration.max_context_images);
  requireThat(finiteMilliseconds(configuration.request_timeout_seconds));
  requireThat(['default', 'priority'].includes(configuration.service_tier));
  const model = configuration.model;
  closed(model, ['id', 'name', 'api', 'provider', 'baseUrl', 'input', 'reasoning', 'thinkingLevelMap', 'cost', 'contextWindow', 'maxTokens', 'compat', 'type']);
  requireThat(model.api === 'openai-completions' && model.id === selectedModel && text(model.id) && text(model.name) && text(model.provider));
  requireThat(model.type === undefined || model.type === 'chat');
  requireThat(typeof model.reasoning === 'boolean');
  requireThat(Array.isArray(model.input) && model.input.includes('text') && model.input.includes('image') && model.input.every(item => ['text', 'image'].includes(item)));
  requireThat(Number.isSafeInteger(model.contextWindow) && model.contextWindow > 0 && Number.isSafeInteger(model.maxTokens) && model.maxTokens > 0 && model.maxTokens <= model.contextWindow);
  closed(model.cost, ['input', 'output', 'cacheRead', 'cacheWrite']);
  requireThat(['input', 'output', 'cacheRead', 'cacheWrite'].every(key => typeof model.cost[key] === 'number' && Number.isFinite(model.cost[key]) && model.cost[key] >= 0));
  let url;
  try { url = new URL(model.baseUrl); } catch { throw new HostError('invalid-configuration'); }
  requireThat(['https:', 'http:'].includes(url.protocol) && !url.username && !url.password && !url.search && !url.hash);
  const openRouter = model.provider === 'openrouter';
  requireThat(openRouter || url.hostname !== 'openrouter.ai');
  if (openRouter) {
    requireThat(url.origin === 'https://openrouter.ai' && url.pathname.replace(/\/$/, '') === '/api/v1');
    requireThat(configuration.service_tier === 'default');
    const routing = model.compat?.openRouterRouting;
    closed(routing, ['only', 'order', 'allow_fallbacks', 'require_parameters']);
    requireThat(routing.allow_fallbacks === false && routing.require_parameters === true
      && Array.isArray(routing.only) && routing.only.length === 1
      && typeof routing.only[0] === 'string' && /^[a-z0-9][a-z0-9_./-]{0,127}$/.test(routing.only[0])
      && Array.isArray(routing.order) && routing.order.length === 1 && routing.order[0] === routing.only[0]);
  } else requireThat(model.compat?.openRouterRouting === undefined);
  requireThat(levels.includes(effort), 'unsupported-effort');
  requireThat(model.reasoning || effort === 'off', 'unsupported-effort');
  if (model.thinkingLevelMap !== undefined) {
    closed(model.thinkingLevelMap, levels);
    requireThat(Object.values(model.thinkingLevelMap).every(value => value === null || text(value)));
  }
  if (model.reasoning) {
    requireThat(object(model.thinkingLevelMap) && Object.hasOwn(model.thinkingLevelMap, effort) && model.thinkingLevelMap[effort] !== null, 'unsupported-effort');
    requireThat(model.compat?.supportsReasoningEffort === true && model.compat.thinkingFormat === (openRouter ? 'openrouter' : 'openai'), 'unsupported-effort');
  }
  // Pi owns the direct OpenAI and OpenRouter serializers; other formats require
  // conformance evidence before expanding this closed reader.
  if (model.compat !== undefined) {
    closed(model.compat, ['supportsDeveloperRole', 'supportsStore', 'supportsUsageInStreaming', 'supportsReasoningEffort', 'supportsStrictMode', 'maxTokensField', 'requiresToolResultName', 'requiresAssistantAfterToolResult', 'requiresThinkingAsText', 'requiresMistralToolIds', 'thinkingFormat', 'openRouterRouting']);
    for (const [key, value] of Object.entries(model.compat)) {
      if (key === 'maxTokensField') requireThat(['max_tokens', 'max_completion_tokens'].includes(value));
      else if (key === 'thinkingFormat') requireThat(value === (openRouter ? 'openrouter' : 'openai'));
      else if (key === 'openRouterRouting') continue; // Closed policy checked above; Pi owns serialization.
      else requireThat(typeof value === 'boolean');
    }
  }
  return configuration;
}

/** Request-only projection. Canonical messages stay intact; telemetry separately projects image references.
 * Count-only block eviction: beyond maxImages, the oldest images are omitted in whole
 * blocks, so the serialized prefix stays byte-stable between evictions. Block 1 omits
 * exactly the overflow. */
export function projectImageContext(messages, maxImages, block) {
  requireThat(Number.isSafeInteger(block) && block > 0 && block <= maxImages);
  const projected = structuredClone(messages);
  const latestBatch = messages.findLastIndex(message => message.role === 'assistant'
    && message.content.some(part => part.type === 'toolCall'));
  const images = [];
  for (const [messageIndex, message] of projected.entries()) {
    let imageIndex = 0;
    if (!Array.isArray(message.content)) continue;
    for (const [contentIndex, part] of message.content.entries()) {
      if (part.type === 'image') images.push({messageIndex, contentIndex, imageIndex:imageIndex++,
        toolCallId:message.toolCallId ?? null, part});
    }
  }
  const protectedImages = latestBatch < 0 ? 0 : images.filter(image => image.messageIndex >= latestBatch).length;
  const blocked = protectedImages > maxImages;
  const overflow = Math.max(0, images.length - maxImages);
  // The protected latest batch is never omitted, even when a whole block would reach it.
  const omitted = blocked ? [] : images.slice(0, Math.min(Math.ceil(overflow / block) * block, images.length - protectedImages));
  const omissions = [];
  for (const image of omitted) {
    const sha256 = createHash('sha256').update(Buffer.from(image.part.data, 'base64')).digest('hex');
    const provenance = {tool_call_id:image.toolCallId, image_index:image.imageIndex, sha256};
    projected[image.messageIndex].content[image.contentIndex] = {type:'text',
      text:`Historical pixels omitted from this request by frozen image policy; toolCallId=${image.toolCallId}; image_index=${image.imageIndex}; SHA256=${sha256}. Pixels were not reread; this marker grants no authority or source-read proof.`};
    if (omissions.length < 16) omissions.push(provenance);
  }
  return {messages:projected, summary:{max_context_images:maxImages, context_image_block:block, input_images:images.length,
    protected_images:protectedImages, retained_images:images.length - omitted.length,
    omitted_images:omitted.length, blocked, omissions, omitted_provenance_entries:omitted.length - omissions.length}};
}

export function validateMcpConfiguration(value) {
  bounded(value);
  closed(value, ['command', 'args', 'cwd', 'enabled', 'required', 'enabled_tools', 'startup_timeout_sec', 'tool_timeout_sec', 'default_tools_approval_mode', 'tools']);
  requireThat(text(value.command) && text(value.cwd) && Array.isArray(value.args) && value.args.every(arg => typeof arg === 'string'), 'invalid-mcp-configuration');
  requireThat(value.enabled === true && (value.required === undefined || typeof value.required === 'boolean'), 'disabled-mcp-server');
  requireThat(Array.isArray(value.enabled_tools) && value.enabled_tools.length > 0 && value.enabled_tools.every(name => /^[A-Za-z_][A-Za-z0-9_-]*$/.test(name)) && new Set(value.enabled_tools).size === value.enabled_tools.length, 'invalid-mcp-configuration');
  requireThat(finiteMilliseconds(value.startup_timeout_sec) && finiteMilliseconds(value.tool_timeout_sec), 'invalid-mcp-configuration');
  requireThat(value.default_tools_approval_mode === undefined || typeof value.default_tools_approval_mode === 'string', 'invalid-mcp-configuration');
  requireThat(value.tools === undefined || (object(value.tools) && Object.entries(value.tools).every(([name, options]) => value.enabled_tools.includes(name) && object(options))), 'invalid-mcp-configuration');
  return value;
}

function payloadSize(payload) {
  let textParts = 0, textBytes = 0, imageParts = 0, imageBytes = 0;
  for (const message of payload.messages ?? []) {
    const parts = typeof message.content === 'string' ? [{type:'text', text:message.content}] : message.content ?? [];
    for (const part of parts) {
      if (part.type === 'text') { textParts++; textBytes += Buffer.byteLength(part.text); }
      if (part.type === 'image_url') {
        imageParts++;
        const data = part.image_url?.url?.split(',', 2)[1];
        if (data) imageBytes += Buffer.from(data, 'base64').length;
      }
    }
    for (const call of message.tool_calls ?? []) {
      textParts++; textBytes += Buffer.byteLength(call.function?.arguments ?? '');
    }
  }
  return {text_parts:textParts, text_bytes:textBytes, image_parts:imageParts, image_bytes:imageBytes, message_count:payload.messages?.length ?? 0};
}

/** Evidence projection only. Pi receives the unchanged actual MCP result. */
export function projectToolResultForTelemetry(result) {
  let imageIndex = 0;
  const projected = structuredClone(result);
  if (Array.isArray(projected.content)) projected.content = projected.content.map(part => {
    if (part.type !== 'image') return part;
    const bytes = Buffer.from(part.data, 'base64');
    return {type:'image_reference', media_type:part.mimeType, bytes:bytes.length,
      sha256:createHash('sha256').update(bytes).digest('hex'), image_index:imageIndex++};
  });
  return projected;
}

function assistantNarration(content) {
  const bytes = Buffer.from((content ?? []).filter(part => part.type === 'text').map(part => part.text).join('\n'));
  let end = Math.min(bytes.length, 8192);
  // Keep the narration valid UTF-8 when a code point crosses the byte cap.
  while (end < bytes.length && (bytes[end] & 0xc0) === 0x80) end--;
  return {text:bytes.subarray(0, end).toString('utf8'), omitted_bytes:bytes.length - end};
}

// Inspect only a bounded refusal, never assistant output. Reader cancellation
// releases a pending read without waiting on an untrusted source's cancel hook.
async function refusalBody(response, signal) {
  signal.throwIfAborted();
  if (!response.body) return '';
  const reader = response.body.getReader(), chunks = [];
  let bytes = 0;
  const cancel = () => { void reader.cancel().catch(() => {}); };
  signal.addEventListener('abort', cancel, {once:true});
  try {
    for (;;) {
      signal.throwIfAborted();
      const {done, value} = await reader.read();
      signal.throwIfAborted();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > PROVIDER_ERROR_LIMIT_BYTES) {
        cancel();
        throw new HostError('provider-error');
      }
      chunks.push(value);
    }
    return new TextDecoder('utf-8', {fatal:true}).decode(Buffer.concat(chunks));
  } finally {
    signal.removeEventListener('abort', cancel);
    reader.releaseLock();
  }
}

// Bounded timing summaries, not a token log or provider-internal clock.
const progressGroups = ['body_chunk', 'provider_event', 'field_delta', 'reasoning_delta', 'content_delta', 'tool_argument_delta'];
function progressTimes() {
  return Object.fromEntries(progressGroups.flatMap(name =>
    [[`first_${name}_ms`, null], [`last_${name}_ms`, null], [`max_${name}_gap_ms`, 0]]));
}
function markProgress(progress, name, at) {
  const previous = progress[`last_${name}_ms`];
  if (progress[`first_${name}_ms`] === null) progress[`first_${name}_ms`] = at;
  if (previous !== null) progress[`max_${name}_gap_ms`] = Math.max(progress[`max_${name}_gap_ms`], at - previous);
  progress[`last_${name}_ms`] = at;
}
function diagnosticId(value, secret) {
  return typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.:/ -]{0,159}$/.test(value)
    && !value.includes(secret) ? value : null;
}
function refusalDiagnostic(body, secret) {
  try {
    const error = JSON.parse(body)?.error;
    return {error_type:diagnosticId(error?.metadata?.error_type ?? error?.type, secret),
      error_code:diagnosticId(Number.isSafeInteger(error?.code) ? String(error.code) : error?.code, secret),
      provider_error_code:diagnosticId(error?.metadata?.provider_code, secret),
      limit_source:diagnosticId(error?.metadata?.limit_source, secret),
      reason:diagnosticId(error?.metadata?.reason, secret)};
  } catch { return {error_type:null, error_code:null, provider_error_code:null, limit_source:null, reason:null}; }
}

// Preserve the server's retry instruction without logging arbitrary headers or
// refusal text. The maintained SDK owns delay selection and enforcement.
// Seconds or an HTTP date, read as the pinned retry helper reads Retry-After.
function retryAfterMs(after) {
  const seconds = Number.parseFloat(after);
  return Number.isFinite(seconds) ? seconds * 1000 : !after ? NaN : Date.parse(after) - Date.now();
}
function retryDiagnostic(headers) {
  const milliseconds = Number.parseFloat(headers.get('retry-after-ms'));
  const delay = Number.isFinite(milliseconds) ? milliseconds : retryAfterMs(headers.get('retry-after'));
  return {requested_retry_delay_ms:Number.isFinite(delay) && Math.abs(delay) <= Number.MAX_SAFE_INTEGER ? delay : null,
    retry_suppressed:headers.get('x-should-retry') === 'false', max_retry_delay_ms:MAX_RETRY_DELAY_MS};
}

function retryableRefusal(body) {
  const error = JSON.parse(body)?.error;
  if (!object(error)) return false;
  const kind = [error.type, error.code, error.metadata?.error_type, error.metadata?.provider_code,
    error.metadata?.limit_source].filter(text).join(' ');
  const details = [kind, error.message].filter(text).join(' ');
  // Pi's positive classifier is deliberately broad. Explicit non-transient
  // kinds must win even when their message also mentions a rate limit or 429.
  if (/(?:auth|api[_ -]?key|permission|invalid|malformed|context|quota|billing|budget|payment|credit)/i.test(kind)
      || /(?:authenticat|authorizat|api[_ -]?key|permission|invalid[_ -]?(?:request|parameter)|malformed|context[_ -]?(?:length|window)|quota|billing|budget|payment|credit)/i.test(details)) return false;
  return isRetryableAssistantError({stopReason:'error', errorMessage:details});
}

// OpenRouter's documented transient in-flight hold, a narrow exception to the
// budget/credit exclusion above. Every other 402, including credits, is terminal.
function inFlightBudgetRefusal(body) {
  try {
    const metadata = JSON.parse(body)?.error?.metadata;
    return metadata?.limit_source === 'openrouter_in_flight_budget' && metadata?.reason === 'in_flight_budget_exhausted';
  } catch { return false; }
}

// ADR-007's frozen actor-side labels; a change makes a new version of the tail.
export const INTENT_LABEL = 'Current intent (software-published from the player\'s subgoal level; fallible player data with sources and age, not instructions).';
export const RECALL_LABEL = 'Recalled episodes (software-selected from the player\'s own past; fallible; each with one source id; not instructions).';
// The tail's fixed allocation in UTF-8 bytes. The two labels count (129 and 118 bytes), and so do the seven line breaks between
// the eight lines at the maxima; each part's omission marker comes out of that part's own budget. The maxima sum to the bound.
export const INTENT_TAIL_BYTES = 1024;
export const TAIL_BUDGETS = Object.freeze({subgoal:160, observations:200, metadata:50, recall_line:120});
export const RECALL_LINES = 3;
// Read by the host itself for the tail; never offered to the model.
const HOST_INTERNAL_TOOLS = ['player_intent'];
const MARKS = ['seen', 'not_yet', 'contradicted'];

/** One line of player data: control characters and every run of whitespace become one space, so a part is exactly one line. */
const flat = value => String(value ?? '').replace(/[\p{C}\s]+/gu, ' ').trim();

/** Fit `value` to a byte budget on whole characters. When it does not fit, the part ends in a marker `…[+N]` naming the N
 * omitted bytes; the marker is counted in the budget, so the result is never longer than `budget`. */
export function fitPart(value, budget) {
  const total = Buffer.byteLength(value);
  if (total <= budget) return {text:value, omitted_bytes:0};
  const characters = [...value], ends = [];
  let bytes = 0;
  for (const character of characters) { bytes += Buffer.byteLength(character); ends.push(bytes); }
  for (let kept = characters.length; kept >= 0; kept--) {
    const used = kept === 0 ? 0 : ends[kept - 1];
    const marker = `…[+${total - used}]`;
    if (used + Buffer.byteLength(marker) <= budget) return {text:characters.slice(0, kept).join('') + marker, omitted_bytes:total - used};
  }
  throw new HostError('invalid-intent-budget');
}

function intentShape(value) {
  const valid = condition => requireThat(condition, 'invalid-intent');
  valid(object(value) && value.schema === 'player-intent/2' && value.audience === 'tail' && object(value.recall) && Array.isArray(value.recall.items));
  if (value.subgoal !== null) {
    const goal = value.subgoal;
    valid(object(goal) && text(goal.record_id) && typeof goal.text === 'string' && Array.isArray(goal.expected_observations)
      && goal.expected_observations.every(item => object(item) && typeof item.text === 'string' && (item.status === null || MARKS.includes(item.status)))
      && Number.isFinite(goal.confidence));
    valid(object(value.age) && typeof value.age.same_session === 'boolean' && Number.isFinite(value.age.seconds)
      && (value.age.inputs_since_commit === null || Number.isSafeInteger(value.age.inputs_since_commit)));
  }
  for (const item of value.recall.items) {
    valid(object(item) && typeof item.attempted === 'string' && (item.first_source === null || typeof item.first_source === 'string')
      && Array.isArray(item.observation_status) && item.observation_status.every(mark => MARKS.includes(mark)));
  }
}

/** The outcome of a recalled episode: how many of its subgoal's expected observations it showed. */
function outcomeOf(marks) {
  if (marks.length === 0) return 'no subgoal';
  const contradicted = marks.filter(mark => mark === 'contradicted').length;
  return `seen ${marks.filter(mark => mark === 'seen').length}/${marks.length}${contradicted ? `, ${contradicted} contradicted` : ''}`;
}

// The least attempt text a recall line keeps beside its source id and outcome (a marker alone takes 8 bytes).
const MIN_ATTEMPT_BYTES = 12;
/** A recall line: the one full source id of the record's first cited frame, its outcome, then its attempt text. */
function recallLine(item) {
  const budget = TAIL_BUDGETS.recall_line;
  const id = text(item.first_source) && !/[\p{C}\s]/u.test(item.first_source) ? item.first_source : '(no frame cited)';
  // A source id is never cut: fall back to the id alone, then to saying that it is too long to show.
  const lead = [`${id} (${outcomeOf(item.observation_status)}) `, `${id} `, '(frame id too long to show) ']
    .find(candidate => Buffer.byteLength(candidate) + MIN_ATTEMPT_BYTES <= budget);
  const attempt = fitPart(flat(item.attempted), budget - Buffer.byteLength(lead));
  return {text:(lead + attempt.text).trimEnd(), omitted_bytes:attempt.omitted_bytes};
}

/** The request-only intent tail from one `player-intent/2` value; null means the read failed.
 *
 * The allocation is fixed at INTENT_TAIL_BYTES: the intent label, then a subgoal line, an observations line and a metadata
 * line, then the recall label and up to RECALL_LINES lines, each part within TAIL_BUDGETS. A part over its budget is cut inside
 * that budget and takes room from no other, so recall is never displaced. `parts` reports each part's bytes and omitted bytes
 * (`omitted_bytes` totals them). A value of the wrong shape throws, and the caller then shows the failed-read text. */
export function formatIntentTail(value, maxBytes = INTENT_TAIL_BYTES) {
  requireThat(maxBytes === INTENT_TAIL_BYTES, 'invalid-intent-budget');
  if (value === null) {
    const unavailable = `${INTENT_LABEL}\nUnavailable: the intent read failed or was malformed; no intent is shown.`;
    return {text:unavailable, tail_bytes:Buffer.byteLength(unavailable), surfaced_bytes:0, omitted_bytes:0, parts:[]};
  }
  intentShape(value);
  const parts = [], lines = [INTENT_LABEL];
  const add = (part, line, omitted_bytes = 0) => { parts.push({part, bytes:Buffer.byteLength(line), omitted_bytes}); lines.push(line); };
  const fit = (part, line, budget) => { const fitted = fitPart(line, budget); add(part, fitted.text, fitted.omitted_bytes); };
  const goal = value.subgoal, age = value.age;
  if (goal === null) add('subgoal', 'No committed intent.');
  else {
    fit('subgoal', `Subgoal: ${flat(goal.text)}`, TAIL_BUDGETS.subgoal);
    fit('observations', 'Expected: ' + (goal.expected_observations.map(item => (item.status === null ? '' : `[${item.status}] `) + flat(item.text)).join('; ') || 'none stated'), TAIL_BUDGETS.observations);
    fit('metadata', `${age.inputs_since_commit === null ? 'earlier actor' : `${age.inputs_since_commit} inputs`}, ${Math.round(Math.max(0, age.seconds))}s, `
      + `${age.same_session ? 'this session' : 'earlier session'}; conf ${goal.confidence.toFixed(1)}; id ${flat(goal.record_id).slice(0, 8)}`, TAIL_BUDGETS.metadata);
  }
  const items = value.recall.items.slice(0, RECALL_LINES);
  if (items.length) {
    lines.push(RECALL_LABEL);
    items.forEach((item, index) => { const line = recallLine(item); add(`recall-${index + 1}`, line.text, line.omitted_bytes); });
  }
  const tail = lines.join('\n');
  requireThat(Buffer.byteLength(tail) <= INTENT_TAIL_BYTES, 'invalid-intent-budget');
  return {text:tail, tail_bytes:Buffer.byteLength(tail), surfaced_bytes:parts.reduce((total, part) => total + part.bytes, 0),
    omitted_bytes:parts.reduce((total, part) => total + part.omitted_bytes, 0), parts};
}

function levelResult(result) {
  if (result.isError === true) return null;
  try { return JSON.parse(result.content?.find(part => part.type === 'text')?.text); } catch { return null; }
}
const recordIds = value => Array.isArray(value.records) ? value.records.map(r => r?.id).filter(text) : [];

/** Level telemetry from one keep, replace or close result; local tool errors are not passes.
 * `subgoal_id` is the subgoal bound at push and `derived` its `{observations, stalled}` after the call (null with no subgoal). */
export function levelCommitEvent(result) {
  const value = levelResult(result);
  if (!object(value) || value.schema !== 'player-level-commit/4' || !['committed', 'discarded'].includes(value.status)
      || !['keep', 'replace', 'close'].includes(value.action)) return null;
  return {type:value.status === 'committed' ? 'level-commit' : 'level-discard', action:value.action, reason:value.reason,
    position:value.position, inputs_since:value.inputs_since, staleness_inputs:value.staleness_inputs,
    subgoal_id:text(value.subgoal_id) ? value.subgoal_id : null, derived:object(value.derived) ? value.derived : null,
    record_ids:recordIds(value), kept:Array.isArray(value.kept) ? value.kept.filter(text) : []};
}

/** A terminal tool's `player-transport/1` unknown receipt: the adapter lost the response and, for a reader, offers no collection.
 * Whether the call committed is known only to the store, so the pass ends and the driver reconciles `identity`.
 * `prefix` is the pass role's (`level` or `episode`). */
export function uncertainEvent(result, prefix) {
  const value = levelResult(result);
  if (!object(value) || value.schema !== 'player-transport/1' || value.status !== 'unknown') return null;
  return {type:`${prefix}-uncertain`, identity:text(value.operation_id) ? value.operation_id : null};
}

/** Level telemetry from one valid `player_level_abstain` result; it ends the pass with nothing written. */
export function levelAbstainEvent(result) {
  const value = levelResult(result);
  if (!object(value) || value.schema !== 'player-level-abstain/2' || value.status !== 'abstained'
      || !text(value.reason_code) || !text(value.reason)) return null;
  return {type:'level-abstain', reason_code:value.reason_code, reason:value.reason};
}

const episodeFields = value => ({first_position:value.first_position, last_position:value.last_position,
  subgoal_id:text(value.subgoal_id) ? value.subgoal_id : null, record_ids:recordIds(value)});
/** Recorder telemetry from one `player_episode_record` result that settled the episode as recorded (never a local tool error).
 * `counted` says whether the marks counted, `closed` whether software closed the subgoal in the same transaction, and
 * `observations` and `stalled` are the derived state after the record (null with no subgoal). */
export function episodeRecordEvent(result) {
  const value = levelResult(result);
  if (!object(value) || value.schema !== 'player-episode-record/1' || value.status !== 'recorded' || value.settled !== 'recorded') return null;
  return {type:'episode-record', ...episodeFields(value), counted:value.counted === true, closed:value.closed === true,
    observations:Array.isArray(value.observations) ? value.observations : null, stalled:typeof value.stalled === 'boolean' ? value.stalled : null};
}

/** Recorder telemetry from one valid `player_episode_abstain` result; the episode settles as abstained, with no marks.
 * The code and reason are the call's own arguments, which the receipt does not repeat. */
export function episodeAbstainEvent(result, args) {
  const value = levelResult(result);
  if (!object(value) || value.schema !== 'player-episode-abstain/1' || value.status !== 'abstained' || value.settled !== 'abstained'
      || !object(args) || !text(args.reason_code) || !text(args.reason)) return null;
  return {type:'episode-abstain', ...episodeFields(value), reason_code:args.reason_code, reason:args.reason};
}

/** The pass-ending event for a terminal tool's result, or null for a rejected call. */
function terminalEvent(name, result, args) {
  if (name === 'player_level_abstain') return levelAbstainEvent(result);
  if (name === 'player_episode_record') return episodeRecordEvent(result);
  if (name === 'player_episode_abstain') return episodeAbstainEvent(result, args);
  return levelCommitEvent(result);
}

/** The recorder's pushed input: a `player-pass-input/1` document on stdin, `{schema, text, frames}`. `frames` are the episode's
 * frames in order, each `{source_id, role}`: at most one baseline, at most one last, and at most MAX_FRAMES in all. The host
 * reads each frame itself through `player_source`, so no image crosses the bound on the prompt. */
export function parsePassInput(prompt) {
  let value;
  try { value = JSON.parse(prompt); } catch { throw new HostError('invalid-pass-input'); }
  const valid = condition => requireThat(condition, 'invalid-pass-input');
  valid(object(value) && Object.keys(value).length === 3 && value.schema === PASS_INPUT_SCHEMA && text(value.text)
    && Array.isArray(value.frames) && value.frames.length <= MAX_FRAMES);
  for (const frame of value.frames) valid(object(frame) && Object.keys(frame).length === 2 && text(frame.source_id)
    && frame.source_id.length <= 128 && !/[\p{C}\s]/u.test(frame.source_id) && FRAME_ROLES.includes(frame.role));
  valid(new Set(value.frames.map(frame => frame.source_id)).size === value.frames.length
    && ['baseline', 'last'].every(role => value.frames.filter(frame => frame.role === role).length <= 1));
  return value;
}

/** Pi 1.4.0 declares a request's tools in the transcript: system messages carry `toolsAdded`/`toolsRemoved` declarations. */
export function declaredTools(messages) {
  const tools = new Map();
  for (const message of messages.filter(entry => entry.role === 'system')) {
    for (const tool of message.toolsRemoved ?? []) tools.delete(tool.name);
    for (const tool of message.toolsAdded ?? []) tools.set(tool.name, tool);
  }
  return [...tools.values()];
}

/** The transcript with only the named tools declared, for one request; the executable tool set and history are unchanged. */
export function restrictTools(messages, names) {
  return messages.map(message => message.role === 'system' && message.toolsAdded
    ? {...message, toolsAdded:message.toolsAdded.filter(tool => names.includes(tool.name))} : message);
}

/** Dotted paths where `after` differs from `before` (first four), for a refusal that names what the SDK changed. */
export function changedFields(before, after, prefix = '') {
  if (isDeepStrictEqual(before, after)) return [];
  if (!object(before) || !object(after)) return [prefix || 'arguments'];
  const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])];
  return keys.flatMap(key => changedFields(before[key], after[key], prefix ? `${prefix}.${key}` : key)).slice(0, 4);
}

/** True when the latest assistant turn called one of the pass's terminal tools and every terminal call in it was refused (an error result). */
export function refusedTerminalCall(messages, terminalTools = LEVEL_TERMINAL_TOOLS) {
  const index = messages.findLastIndex(message => message.role === 'assistant');
  if (index < 0) return false;
  const terminal = (messages[index].content ?? []).filter(part => part.type === 'toolCall' && terminalTools.includes(part.name));
  const results = messages.slice(index + 1).filter(message => message.role === 'toolResult');
  return terminal.length > 0 && terminal.every(call =>
    results.some(message => message.toolCallId === call.id && message.isError === true));
}

// This actual MCP receipt ends this host only. The driver independently checks
// canonical issuance/context and actual host/MCP quiescence before succession.
function inspectHandoff(name, args, result, pending) {
  if (!['player_handoff', 'computer_result'].includes(name)) return {};
  const direct = name === 'player_handoff';
  // Reading an unrelated or earlier actor's issuance never arms settlement.
  if (!direct && (!pending || args.operation_id !== pending.operation_id)) return {};
  // A local rejection/no-submit result provides no origin, even when it carries
  // plausible-looking IDs. Preserve explicit model correction/collection.
  if (result.isError === true) return {};
  let value;
  try {
    value = JSON.parse(result.content?.find(part => part.type === 'text')?.text);
  } catch {
    throw new HostError('invalid-handoff-receipt');
  }
  const id = value => typeof value === 'string' && /^[a-f0-9]{32}$/.test(value);
  const valid = condition => requireThat(condition, 'invalid-handoff-receipt');
  valid(object(value) && id(value.operation_id) && id(value.session) && id(value.actor_id)
    && value.kind === 'handoff');
  const origin = {operation_id:value.operation_id, session:value.session, actor_id:value.actor_id};
  if (pending) valid(isDeepStrictEqual(origin, pending));
  if (direct && value.schema === 'player-transport/1') {
    valid(value.status === 'unknown' && typeof value.reason === 'string');
    return {pending:origin};
  }
  valid(value.schema === 'computer-operation/1');
  if (['pending', 'unknown'].includes(value.status)) {
    valid(value.handoff === null);
    return {pending:origin};
  }
  if (value.status === 'refused') {
    valid(value.handoff === null);
    return {};
  }
  const issued = value.handoff;
  valid(value.status === 'sealed' && object(issued)
    && issued.schema === 'player-handoff/2' && issued.grants_authority === false
    && issued.operation_id === origin.operation_id && issued.session === origin.session
    && issued.actor_id === origin.actor_id && id(issued.context_id)
    && typeof issued.context_sha256 === 'string' && /^[a-f0-9]{64}$/.test(issued.context_sha256)
    && positive(issued.sealed_wall));
  return {pending:origin, completed:{session:origin.session, actor_id:origin.actor_id,
    handoff_id:origin.operation_id, context_id:issued.context_id, context_sha256:issued.context_sha256}};
}

/** Run one finite host. fetch injection exercises the actual Pi serializer in tests. */
export async function runHost(options) {
  const started = performance.now();
  const outputStats = {events:0, callback_ms:0, max_callback_ms:0, json_ms:null, enqueue_ms:null, bytes:null, backpressure_signals:null};
  const emit = (type, fields = {}) => {
    const event = {type, wall_time:new Date().toISOString(), monotonic_ms:performance.now() - started, ...fields};
    const before = performance.now(), sink = options.onEvent?.(event);
    const elapsed = performance.now() - before;
    outputStats.events++; outputStats.callback_ms += elapsed;
    outputStats.max_callback_ms = Math.max(outputStats.max_callback_ms, elapsed);
    // The maintained CLI supplies synchronous JSON/enqueue measurements. Other
    // event consumers need not implement a sink contract; drain/disk time is unknown.
    if (object(sink)) for (const key of ['json_ms', 'enqueue_ms', 'bytes', 'backpressure_signals']) {
      if (typeof sink[key] === 'number' && Number.isFinite(sink[key]) && sink[key] >= 0) outputStats[key] = (outputStats[key] ?? 0) + sink[key];
    }
  };
  let agent, client, transport, fatal, closing = false, requests = 0, requestId, requestTimer, requestInFlight = false, requestUsageAvailable = false;
  let workTimer, deadlineTimer;
  let responseProgress, handoff, pendingHandoff, passEnded = false, passUncertain = false;
  // Logical requests: one per streamFn call, whatever its provider retries; `reserved` is the current one's.
  let logicalRequests = 0, reserved = false;
  const progressSnapshot = () => responseProgress ? {...responseProgress,
    scope:requestInFlight ? 'current-http-attempt' : 'last-http-attempt'} : null;
  const stopped = new AbortController();
  const stop = reason => {
    if (fatal) return;
    fatal = reason;
    emit('abort', {reason, request_id:requestId, response_progress:progressSnapshot()});
    stopped.abort();
    agent?.abort();
    // Start owned transport closure immediately, including while MCP connect is
    // pending. The single finally block still awaits the same close operation.
    void close();
  };
  let closePromise;
  function close() {
    closing = true;
    return closePromise ??= (async () => {
      try { if (client) await client.close(); else if (transport) await transport.close(); }
      catch { if (!fatal) { fatal = 'mcp-cleanup-failed'; emit('abort', {reason:fatal, request_id:requestId, response_progress:progressSnapshot()}); } }
    })();
  }
  const cancellation = () => stop('cancelled');
  function failureStream(model, reason) {
    requestInFlight = false;
    const response = new AssistantMessageEventStream();
    const message = {role:'assistant', content:[], api:model.api, provider:model.provider, model:model.id,
      usage:{input:0, output:0, cacheRead:0, cacheWrite:0, totalTokens:0, cost:{input:0, output:0, cacheRead:0, cacheWrite:0, total:0}},
      stopReason:'aborted', errorMessage:reason, timestamp:Date.now()};
    response.push({type:'error', reason:'aborted', error:message});
    response.end(message);
    return response;
  }
  try {
    requireThat(positive(options.timeoutSeconds), 'invalid-host-timeout');
    const totalMs = options.timeoutSeconds * 1000;
    requireThat(Number.isFinite(totalMs) && totalMs <= 2_147_483_647, 'invalid-host-timeout');
    const cleanupBudget = Math.min(1000, totalMs / 4);
    const workDeadline = started + totalMs - cleanupBudget;
    workTimer = setTimeout(() => stop('host-timeout'), totalMs - cleanupBudget);
    deadlineTimer = setTimeout(() => stop('host-timeout'), totalMs);
    options.signal?.addEventListener('abort', cancellation, {once:true});
    if (options.signal?.aborted) stop('cancelled');
    const configuration = validateConfiguration(options.configuration, options.model, options.effort);
    const mcp = validateMcpConfiguration(options.mcpConfig);
    // A level or a recorder pass ends on one of its terminal tools; an actor has none.
    const pass = PASS_ROLES[configuration.role];
    // At the start of a logical request (before it is counted): two or fewer HTTP attempts or logical requests remain.
    const reservedWindow = () => pass !== undefined
      && (configuration.max_requests - requests <= LEVEL_RESERVED_REQUESTS || configuration.max_requests - logicalRequests <= LEVEL_RESERVED_REQUESTS);
    requireThat(typeof options.prompt === 'string' && typeof options.context === 'string', 'invalid-input');
    bounded(options.prompt); bounded(options.context);
    // A recorder's prompt is its structured pushed input; it is refused before any connection or request.
    const passInput = configuration.role === 'recorder' ? parsePassInput(options.prompt) : null;
    emit('host-start', {telemetry_version:2, schema:configuration.schema, role:configuration.role, intent_tail_bytes:configuration.intent_tail_bytes, requested_service_tier:configuration.service_tier, model:configuration.model.id, provider:configuration.model.provider, api:configuration.model.api, effort:options.effort, max_output_tokens:configuration.model.maxTokens, context_window:configuration.model.contextWindow, thinking_level_map:{...configuration.model.thinkingLevelMap}, reasoning_format:configuration.model.compat?.thinkingFormat ?? null, provider_routing:configuration.model.compat?.openRouterRouting ? structuredClone(configuration.model.compat.openRouterRouting) : null, max_requests:configuration.max_requests, max_context_images:configuration.max_context_images, context_image_block:configuration.context_image_block, unsupported_features:['compaction', 'session-restore', 'model-fallback', 'reconnect', 'replay', 'ambient-tools', 'resource-discovery'], missing_endpoints:['model-attention', 'server-inference-start', 'physical-paint'], cleanup_budget_ms:cleanupBudget});
    if (fatal) throw new HostError(fatal);
    requireThat(!AMBIENT_PROVIDER_SETTINGS.some(name => Object.hasOwn(process.env, name)), 'ambient-provider-configuration');
    // The MCP subprocess gets only locale and executable lookup, never provider
    // credentials, personal configuration, proxy variables or unrelated secrets.
    const childEnv = {PATH:process.env.PATH ?? '/usr/bin:/bin', LANG:process.env.LANG ?? 'C.UTF-8'};
    transport = new StdioTransport({command:mcp.command, args:mcp.args, cwd:mcp.cwd, env:childEnv, inheritEnv:false, stderr:'pipe', maxStderrBytes:8192, maxMessageBytes:MCP_LIMIT_BYTES, closeTimeoutMs:Math.max(1, Math.floor(cleanupBudget / 2))});
    client = new McpClient({name:'enactive-player-host', version:'0.1.0', requestTimeoutMs:Math.min(mcp.startup_timeout_sec * 1000, totalMs - cleanupBudget)});
    transport.onError(() => stop('mcp-transport-error'));
    client.onError(() => stop('mcp-client-error'));
    client.onClose(() => { if (!closing) stop('mcp-connection-closed'); });
    await client.connect(transport);
    if (fatal) throw new HostError(fatal);
    emit('mcp-connected', {child_pid:transport.pid});
    const discovered = await client.listTools({signal:stopped.signal, timeoutMs:mcp.startup_timeout_sec * 1000});
    const names = new Map(discovered.map(tool => [tool.name, tool]));
    requireThat(names.size === discovered.length && mcp.enabled_tools.every(name => names.has(name)), 'missing-required-tools');
    requireThat(!mcp.enabled_tools.some(name => HOST_INTERNAL_TOOLS.includes(name)), 'host-internal-tool-enabled');
    if (configuration.intent_tail_bytes !== null) requireThat(names.has('player_intent'), 'missing-required-tools');
    // Each role enables exactly its own terminal tools: a pass role all of them, and no other role any.
    const passTools = Object.values(PASS_ROLES).flatMap(role => role.tools);
    requireThat((pass?.tools ?? []).every(name => mcp.enabled_tools.includes(name)), 'missing-required-tools');
    requireThat(mcp.enabled_tools.every(name => !passTools.includes(name) || pass?.tools.includes(name)), 'unexpected-pass-tools');
    // Frames are read through the recorder's own `player_source`, which the host never offers beyond the frozen table.
    if (passInput?.frames.length) requireThat(mcp.enabled_tools.includes('player_source'), 'missing-required-tools');
    if (pass) emit(`${pass.prefix}-pass`, passInput ? {frames:passInput.frames.map(frame => ({...frame}))} : {});
    const tools = mcp.enabled_tools.map(name => {
      const schema = names.get(name);
      requireThat(object(schema.inputSchema), 'invalid-mcp-schema');
      return {name, label:name, description:schema.description ?? name, parameters:Type.Unsafe(schema.inputSchema), async execute(toolCallId, args, signal) {
        if (fatal || signal?.aborted) throw new HostError(fatal ?? 'cancelled');
        emit('tool-start', {request_id:requestId, tool_call_id:toolCallId, tool:name, arguments:args});
        let result;
        try { result = await client.callTool(name, args, {signal, timeoutMs:mcp.tool_timeout_sec * 1000}); }
        catch { stop('mcp-call-failed'); throw new HostError(fatal); }
        if (fatal) throw new HostError(fatal);
        emit('tool-result', {request_id:requestId, tool_call_id:toolCallId, tool:name, result:projectToolResultForTelemetry(result)});
        if (pass?.tools.includes(name)) {
          // A level's keep, replace or close that becomes a commit or discard, a recorder's record, or a valid abstain, ends the
          // pass; a rejected call does not. So does a lost transport: a reader cannot collect, so the pass ends and the driver
          // reconciles the identity.
          const uncertain = uncertainEvent(result, pass.prefix);
          const ending = uncertain ?? terminalEvent(name, result, args);
          if (ending) {
            const {type, ...fields} = ending;
            emit(type, {request_id:requestId, tool_call_id:toolCallId, ...(uncertain ? {tool:name} : {}), ...fields});
            passEnded = true;
            passUncertain ||= uncertain !== null;
          }
        }
        try {
          const transition = inspectHandoff(name, args, result, pendingHandoff);
          if (transition.pending) pendingHandoff = transition.pending;
          if (transition.completed) handoff = transition.completed;
          if (handoff) emit('handoff', {request_id:requestId, tool_call_id:toolCallId, ...handoff, grants_authority:false});
        } catch {
          // Pi turns thrown tool errors into model-visible results. Latch the
          // host failure too so incoherent completion cannot schedule more work.
          stop('invalid-handoff-receipt');
          throw new HostError(fatal);
        }
        const content = toLlmContent(result);
        if (result.isError === true) content.unshift({type:'text', text:'MCP isError: true'});
        return {content, details:undefined, isError:result.isError === true};
      }};
    });
    // A pass role's refusals name each failing field, its rule, the allowed values and a valid example call.
    const validationFeedback = createValidationFeedback(tools, diagnostic =>
      emit('tool-validation-feedback', {request_id:`request-${requests + 1}`, ...diagnostic}),
      pass ? {names:pass.tools, terminal:pass.tools, notes:TERMINAL_NOTES} : {});
    agent = new Agent({
      initialState:{systemPrompt:options.context + (client.instructions ? '\n\nMCP server instructions:\n' + client.instructions : ''), model:configuration.model, thinkingLevel:options.effort, tools},
      toolExecution:'sequential',
      transformContext:async messages => {
        if (fatal) return messages;
        // Pi requires this hook never to throw/reject. Latch a terminal stop and
        // return safe canonical context; streamFn checks it before charging/fetch.
        try {
          // Memoize against canonical SDK objects before image projection clones
          // them. Earlier diagnostic text remains stable in subsequent prefixes.
          const projectionStarted = performance.now();
          const projection = projectImageContext(validationFeedback(messages), configuration.max_context_images, configuration.context_image_block);
          emit('context-image-projection', {request_id:`request-${requests + 1}`, projection_ms:performance.now() - projectionStarted, ...projection.summary});
          if (projection.summary.blocked) stop('context-image-limit');
          let intent = '';
          if (configuration.intent_tail_bytes !== null) {
            // A failed read shows no intent and never stops the actor or gates its input.
            let value = null;
            try {
              const result = await client.callTool('player_intent', {}, {signal:stopped.signal, timeoutMs:mcp.tool_timeout_sec * 1000});
              const parsed = JSON.parse(result.content?.find(part => part.type === 'text')?.text);
              if (result.isError !== true && object(parsed) && parsed.schema === 'player-intent/2') value = parsed;
            } catch { value = null; }
            if (fatal) return messages;
            let tail;
            // Record data is free-form player data: an unexpected shape shows "Unavailable", never a stop.
            try { tail = formatIntentTail(value, configuration.intent_tail_bytes); }
            catch { value = null; tail = formatIntentTail(null, configuration.intent_tail_bytes); }
            // Per part: bytes surfaced and bytes omitted by the fixed allocation.
            emit('intent-tail', {request_id:`request-${requests + 1}`, available:value !== null,
              record_id:value?.subgoal?.record_id ?? null, tail_bytes:tail.tail_bytes, surfaced_bytes:tail.surfaced_bytes,
              omitted_bytes:tail.omitted_bytes, parts:tail.parts, age:value?.age ?? null});
            intent = '\n\n' + tail.text;
          }
          // Request-only bookkeeping follows history, preserving the stable
          // system/tool prefix and canonical messages. Retries reuse this snapshot.
          return [...projection.messages, {role:'user', timestamp:Date.now(), content:[{type:'text', text:
            'Host resource status (software-generated at context construction):\n' +
            `Actual provider HTTP attempts charged before this request: ${requests}/${configuration.max_requests}.\n` +
            `Remaining allowance including this request: ${configuration.max_requests - requests}.\n` +
            (reservedWindow()
              ?'This request offers only the pass-ending tools; end the pass with exactly one of them.\n' : '') +
            `Host decision time remaining at this snapshot: ${Math.max(0,(workDeadline-performance.now())/1000).toFixed(3)} seconds. Custodian time is a separate horizon.\n` +
            'An eligible retry can consume another attempt before the next status update. ' +
            'This is resource bookkeeping, not a human task, gameplay evidence, source-read proof, authority or a latency/quality metric.' + intent}]}];
        } catch {
          stop('context-projection-failed');
          return messages;
        }
      },
      beforeToolCall:({toolCall, args}) => {
        if (fatal) return {block:true, reason:fatal, terminate:true};
        if (handoff) {
          emit('tool-refused', {request_id:requestId, tool_call_id:toolCall.id, tool:toolCall.name, reason:'handoff', dispatched:false});
          return {block:true, reason:'Host ended after completed handoff; no further tool dispatch.', terminate:true};
        }
        if (passEnded) {
          emit('tool-refused', {request_id:requestId, tool_call_id:toolCall.id, tool:toolCall.name, reason:`${pass.prefix}-ended`, dispatched:false});
          return {block:true, reason:`The ${configuration.role} pass ended with its terminal call; no further tool dispatch.`, terminate:true};
        }
        // A reserved request offers only the terminal tools. A model can still name another tool, which is executable
        // but refused here, so the reservation holds and the refusal says which tools to call.
        if (pass && reserved && !pass.tools.includes(toolCall.name)) {
          emit('tool-refused', {request_id:requestId, tool_call_id:toolCall.id, tool:toolCall.name, reason:`${pass.prefix}-reserved`, dispatched:false});
          return {block:true, reason:`${toolCall.name} is not offered on this request and was not run: only ${pass.tools.join(', ')} are available. `
            + `Call exactly one of them.\n${FIX_LINE}`};
        }
        if (!isDeepStrictEqual(toolCall.arguments, args)) {
          emit('tool-refused', {request_id:requestId, tool_call_id:toolCall.id, tool:toolCall.name, reason:'tool-arguments-changed', dispatched:false});
          const fields = changedFields(toolCall.arguments, args).join(', ');
          return {block:true, reason:`MCP input not sent: the SDK changed the arguments of ${toolCall.name} (field ${fields}); resend the call with ${fields} given exactly as the schema requires, without nulls or coerced values.`
            + (pass?.tools.includes(toolCall.name) ? `\n${FIX_LINE}` : '')};
        }
      },
      // Pi's per-result terminate hint requires every result in the batch to
      // terminate. finishTurn also handles ordinary tools preceding a handoff
      // or a pass's ending call.
      finishTurn:() => handoff || passEnded ? {action:'end'} : undefined,
      streamFn:(model, context, streamOptions) => {
        if (fatal) return failureStream(model, fatal);
        if (requests >= configuration.max_requests) {
          // A refused terminal call on the last allowed request left no budget to correct it: its own settled reason.
          stop(pass && refusedTerminalCall(context.messages, pass.tools) ? `${pass.prefix}-final-refusal` : 'request-limit');
          return failureStream(model, fatal);
        }
        // A logical request that starts with LEVEL_RESERVED_REQUESTS or fewer HTTP attempts or logical requests left offers
        // only the terminal tools, so a refused call can be repaired. A provider retry resends its logical request's
        // declarations: the window is decided once, here.
        reserved = reservedWindow();
        logicalRequests++;
        if (reserved) {
          context = {...context, messages:restrictTools(context.messages, pass.tools)};
          emit(`${pass.prefix}-reserved-request`, {request_id:`request-${requests + 1}`, logical_request_id:`request-${logicalRequests}`,
            offered_tools:declaredTools(context.messages).map(tool => tool.name)});
        }
        const apiKey = (options.env ?? process.env)[configuration.api_key_env];
        if (!text(apiKey)) { stop('missing-api-key'); return failureStream(model, fatal); }
        try {
          requestUsageAvailable = false;
          requestTimer = setTimeout(() => stop('request-timeout'), Math.min(configuration.request_timeout_seconds * 1000, totalMs));
          const requestSignal = AbortSignal.any([streamOptions.signal, stopped.signal].filter(Boolean));
          const backendModels = new Set(), observedServiceTiers = new Set();
          const streamStarted = performance.now(), logicalRequestId = `request-${requests + 1}`, logicalNumber = `request-${logicalRequests}`;
          let payloadReadyAt;
          const actualFetch = options.fetch ?? globalThis.fetch;
          let attempts = 0, previousRequestId;
          // End an eligible first attempt and hand its server delay to the SDK
          // helper. Status is omitted so only the host's declared classes decide.
          const retry = (attemptId, retryClass, status, headers) => {
            emit('response-complete', {request_id:attemptId, model:model.id, provider:model.provider, stop_reason:'error', http_status:status, usage_available:false, usage:null, cost_source:null, response_progress:progressSnapshot()});
            requestInFlight = false;
            if (requests >= configuration.max_requests) {
              stop('request-limit');
              throw new HostError(fatal);
            }
            previousRequestId = attemptId;
            emit('provider-retry', {stage:'eligible', request_id:attemptId, retry_class:retryClass, max_retry_delay_ms:MAX_RETRY_DELAY_MS});
            const error = new Error(`provider-${retryClass}`);
            error.status = undefined;
            error.headers = new Headers();
            for (const name of ['retry-after-ms', 'retry-after']) {
              const value = headers?.get(name);
              if (value != null) error.headers.set(name, value);
            }
            throw error;
          };
          const observedFetch = (url, init) => retryProviderRequest(async () => {
            requestSignal.throwIfAborted();
            if (fatal) throw new HostError(fatal);
            if (requests >= configuration.max_requests) {
              stop('request-limit');
              throw new HostError(fatal);
            }
            const fetchEntered = performance.now();
            requireThat(typeof init?.body === 'string', 'invalid-provider-payload');
            const payload = JSON.parse(init.body);
            const sizes = {...payloadSize(payload), payload_bytes:Buffer.byteLength(init.body),
              payload_sha256:createHash('sha256').update(init.body).digest('hex')};
            const inspectionMs = performance.now() - fetchEntered;
            const attemptId = requestId = `request-${++requests}`;
            const attemptProgress = responseProgress = {request_id:attemptId, body_bytes:0, body_chunks:0,
              provider_events:0, content_bytes:0, reasoning_bytes:0,
              tool_argument_bytes:0, response_id:null, reported_provider:null, ...progressTimes()};
            requestInFlight = true;
            attempts++;
            if (previousRequestId) emit('provider-retry', {stage:'started', request_id:attemptId, previous_request_id:previousRequestId});
            emit('request-start', {request_id:attemptId, logical_request_id:logicalNumber, model:model.id, provider:model.provider,
              sdk_after_payload_ms:attempts === 1 && payloadReadyAt !== undefined ? fetchEntered - payloadReadyAt : null,
              host_inspection_ms:inspectionMs, ...sizes});
            let response;
            emit('request-fetch-start', {request_id:attemptId});
            try { response = await actualFetch(url, init); }
            catch {
              // A rejected fetch has no response headers. Timeout and abort latch first.
              if (!fatal && !requestSignal.aborted && attempts === 1) retry(attemptId, 'pre-header-rejection', null, null);
              if (!fatal) stop('provider-error');
              throw new HostError(fatal);
            }
            if (fatal || requestSignal.aborted) {
              void response.body?.cancel().catch(() => {});
              throw new HostError(fatal ?? 'provider-error');
            }
            const server = SERVER_RETRY_STATUSES.includes(response.status);
            emit('response-headers', {request_id:attemptId, status:response.status, provider_request_id:
              diagnosticId(response.headers.get('x-request-id'), apiKey),
              ...(server || [402, 429].includes(response.status) ? retryDiagnostic(response.headers) : {})});
            let first = false;
            const body = response.body?.pipeThrough(new TransformStream({transform(chunk, controller) {
              attemptProgress.body_bytes += chunk.byteLength;
              attemptProgress.body_chunks++;
              markProgress(attemptProgress, 'body_chunk', performance.now() - started);
              if (!first) { first = true; emit('response-first-chunk', {request_id:attemptId}); }
              controller.enqueue(chunk);
            }}));
            response = new Response(body ?? null, {status:response.status, statusText:response.statusText, headers:response.headers});
            if (response.status < 400) return response;
            let errorBody = null;
            // A declared 5xx stays eligible by status when its refusal body is
            // unreadable; 402 and 429 need their bounded body classifiers.
            try { errorBody = await refusalBody(response, requestSignal); }
            catch (error) { if (!server || fatal || requestSignal.aborted) throw error; }
            emit('provider-refusal', {request_id:attemptId, status:response.status, body_read:errorBody !== null, ...refusalDiagnostic(errorBody ?? '', apiKey)});
            // One shared retry per logical request, whatever the first class was.
            if (attempts === 1 && response.headers.get('x-should-retry') !== 'false') {
              if (server) retry(attemptId, 'server-error', response.status, response.headers);
              if (response.status === 429 && retryableRefusal(errorBody)) retry(attemptId, 'rate-limit', 429, response.headers);
              if (response.status === 402 && Number.isFinite(retryAfterMs(response.headers.get('retry-after'))) && inFlightBudgetRefusal(errorBody)) retry(attemptId, 'in-flight-budget', 402, response.headers);
            }
            if (errorBody === null) throw new HostError('provider-error');
            return new Response(errorBody, {status:response.status, headers:response.headers});
          }, {maxRetries:1, maxRetryDelayMs:MAX_RETRY_DELAY_MS, signal:requestSignal});
          // The outer request timer includes classification, SDK backoff and
          // both HTTP attempts. Disable the provider stream's nested retries.
          // A level pass must end in a terminal call, so its provider is required to call a tool.
          return stream(model, context, {...streamOptions, ...(pass ? {toolChoice:'required'} : {}), apiKey, fetch:observedFetch, env:{}, signal:requestSignal, maxRetries:0, cacheRetention:'short', maxTokens:model.maxTokens, timeoutMs:configuration.request_timeout_seconds * 1000, reasoningEffort:options.effort === 'off' ? undefined : options.effort,
            onPayload:payload => {
              payloadReadyAt = performance.now();
              emit('provider-payload-ready', {request_id:logicalRequestId, sdk_prepare_ms:payloadReadyAt - streamStarted});
              return model.provider === 'openrouter' ? {...payload, service_tier:'default'}
                : configuration.service_tier === 'priority' ? {...payload, service_tier:'priority'} : undefined;
            },
            onProviderStreamEvent:chunk => {
            responseProgress.provider_events++;
            const eventAt = performance.now() - started;
            markProgress(responseProgress, 'provider_event', eventAt);
            responseProgress.response_id ??= diagnosticId(chunk?.id, apiKey);
            responseProgress.reported_provider ??= diagnosticId(chunk?.provider, apiKey);
            const delta = Array.isArray(chunk?.choices) ? chunk.choices[0]?.delta : undefined;
            const bytes = value => typeof value === 'string' ? Buffer.byteLength(value) : 0;
            const contentBytes = bytes(delta?.content);
            const reasoning = [delta?.reasoning_content, delta?.reasoning, delta?.reasoning_text].find(text);
            const reasoningBytes = bytes(reasoning);
            const toolBytes = (Array.isArray(delta?.tool_calls) ? delta.tool_calls : [])
              .reduce((total, call) => total + bytes(call?.function?.arguments), 0);
            responseProgress.content_bytes += contentBytes;
            responseProgress.reasoning_bytes += reasoningBytes;
            responseProgress.tool_argument_bytes += toolBytes;
            if (contentBytes + reasoningBytes + toolBytes > 0) markProgress(responseProgress, 'field_delta', eventAt);
            if (contentBytes > 0) markProgress(responseProgress, 'content_delta', eventAt);
            if (reasoningBytes > 0) markProgress(responseProgress, 'reasoning_delta', eventAt);
            if (toolBytes > 0) markProgress(responseProgress, 'tool_argument_delta', eventAt);
            // Optional provider echo only; missing/unrecognized values remain unknown.
            // This does not change delivery, retries, configured prices or authority.
            const tier = chunk?.service_tier;
            if (['default', 'priority', 'flex'].includes(tier) && !observedServiceTiers.has(`${requestId}:${tier}`)) {
              observedServiceTiers.add(`${requestId}:${tier}`);
              emit('response-service-tier', {request_id:requestId, applied_service_tier:tier});
            }
            const usage = chunk?.usage ?? chunk?.choices?.[0]?.usage;
            // Pi initializes absent usage to zero. Only publish normalized totals
            // when the provider actually reported both input and output counts.
            if (Number.isFinite(usage?.prompt_tokens) && Number.isFinite(usage?.completion_tokens)) requestUsageAvailable = true;
            if (typeof chunk?.model === 'string' && !backendModels.has(chunk.model)) {
              backendModels.add(chunk.model);
              emit('response-backend', {request_id:requestId, backend_model:chunk.model});
            }
          }});
        } catch {
          stop('provider-error');
          return failureStream(model, fatal);
        }
      },
    });
    agent.subscribe(event => {
      if (event.type === 'message_end' && event.message.role === 'assistant') {
        clearTimeout(requestTimer);
        const message = event.message;
        const narration = assistantNarration(message.content);
        if (narration.text || narration.omitted_bytes) emit('assistant-text', {request_id:requestId, ...narration});
        // Every terminal call the model made, so a refusal that never reached tool-start (unparseable arguments, a
        // validation refusal, a host refusal) can be told from a dispatched call.
        if (pass) for (const part of message.content ?? []) {
          if (part.type === 'toolCall' && pass.tools.includes(part.name)) {
            emit(`${pass.prefix}-terminal-call`, {request_id:requestId, tool_call_id:part.id, tool:part.name, arguments_error:Object.hasOwn(part, 'argumentsError')});
          }
        }
        if (requestInFlight) emit('response-complete', {request_id:requestId, model:message.model, provider:message.provider, stop_reason:message.stopReason, usage_available:requestUsageAvailable, usage:requestUsageAvailable ? message.usage : null, cost_source:requestUsageAvailable ? (message.usage?.cost?.totalFromProvider === true ? 'provider' : 'configured-rates') : null, response_progress:progressSnapshot()});
        requestInFlight = false;
        if (['error', 'aborted', 'length', 'deferred'].includes(message.stopReason) && !fatal) stop(message.stopReason === 'error' ? 'provider-error' : `provider-${message.stopReason}`);
      }
    });
    let first = options.prompt;
    if (passInput) {
      // The recorder's frames reach it as image parts of its first message, each marked with its source id and role. The host
      // reads them with the recorder's own `player_source` before any request; a frame it cannot read ends the pass unrequested.
      const content = [{type:'text', text:passInput.text}];
      for (const frame of passInput.frames) {
        let image;
        try {
          const result = await client.callTool('player_source', {source_id:frame.source_id}, {signal:stopped.signal, timeoutMs:mcp.tool_timeout_sec * 1000});
          image = result.isError === true ? undefined : result.content?.find(part => part.type === 'image' && typeof part.data === 'string' && text(part.mimeType));
        } catch { image = undefined; }
        if (fatal) throw new HostError(fatal);
        if (!image) { stop('frame-read-failed'); throw new HostError(fatal); }
        const bytes = Buffer.from(image.data, 'base64');
        emit('episode-frame', {source_id:frame.source_id, role:frame.role, media_type:image.mimeType, bytes:bytes.length,
          sha256:createHash('sha256').update(bytes).digest('hex')});
        content.push({type:'text', text:`Frame ${frame.source_id} (${frame.role}):`}, {type:'image', data:image.data, mimeType:image.mimeType});
      }
      first = {role:'user', content, timestamp:Date.now()};
    }
    await agent.prompt(first);
    const terminal = agent.state.messages.findLast(message => message.role === 'assistant');
    if (!fatal && passUncertain) stop(`${pass.prefix}-uncertain`);
    else if (!fatal && pass && !passEnded) stop(pass.unended);
    else if (!fatal && terminal?.stopReason !== 'stop' && !((handoff || passEnded) && terminal?.stopReason === 'toolUse')) stop('incomplete-terminal-response');
  } catch (error) {
    if (!fatal) stop(error instanceof HostError ? error.reason : 'host-failed');
  } finally {
    clearTimeout(requestTimer); clearTimeout(workTimer);
    options.signal?.removeEventListener('abort', cancellation);
    await close();
    clearTimeout(deadlineTimer);
  }
  const terminal = agent?.state.messages.findLast(message => message.role === 'assistant');
  const finalText = !fatal && !handoff ? (terminal?.content ?? []).filter(part => part.type === 'text').map(part => part.text).join('\n') : '';
  const result = {ok:!fatal, reason:fatal ?? (handoff ? 'handoff' : 'completed'), requests, finalText};
  emit('settled', {ok:result.ok, reason:result.reason, requests, event_output:{...outputStats}, native_cleanup_claimed:false});
  return result;
}
