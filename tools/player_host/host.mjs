import { isDeepStrictEqual } from 'node:util';
import { setTimeout as delay } from 'node:timers/promises';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Agent } from '@earendil-works/pi-agent-core';
import { Type, AssistantMessageEventStream, isRetryableAssistantError } from '@earendil-works/pi-ai';
import { stream } from '@earendil-works/pi-ai/api/openai-completions';
import { retryProviderRequest } from '@earendil-works/pi-ai/utils/provider-retry';
import { estimateContextTokens, estimateMessageTokens } from '@earendil-works/pi-ai/utils/estimate';
import { McpClient, StdioTransport, toLlmContent } from '@earendil-works/pi-mcp';
import { validateKnowledge, updateDelivery, updateEntry, coverageEntry,
  openingBriefing, cutBriefing, cutMarker, substantiveDelta, representsUpdate,
  CUT_BRIEFING_CHARS, versionNumber } from './knowledge.mjs';
import { advanceAgendaCut, agendaForPrompt, agendaRefSet, agendaToolParameters, applyAgendaTool,
  emptyAgenda, validateAgenda } from './agenda.mjs';

export const INPUT_LIMIT_BYTES = 1_048_576;
export const CONTROL_LIMIT_BYTES = 4096;
const identity = value => typeof value === 'string' && /^[a-f0-9]{32}$/.test(value);
const STOP_TEXT = 'Automation control: orderly stop requested. Finish up and stop. Use player_finish with disposition external_stop_complete and the control_id below when finished. The player chooses ordinary actions; this control does not certify game persistence or native exit.';
// openai@7.19.0 client.mjs reads these despite Pi's scoped env option.
// Their values can alter request headers or enable raw SDK logging.
const AMBIENT_PROVIDER_SETTINGS = ['OPENAI_LOG', 'OPENAI_CUSTOM_HEADERS', 'OPENAI_ORG_ID', 'OPENAI_PROJECT_ID'];
const MCP_LIMIT_BYTES = 32 * 1_048_576;
// How often a running host looks for a newer listed knowledge version between its other refreshes.
const UPDATE_POLL_MS = 1000;
const UPDATE_READ_TIMEOUT_MS = 2000;
const UPDATE_READER = fileURLToPath(new URL('./update-reader.mjs', import.meta.url));
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
const costKeys = ['input', 'output', 'cacheRead', 'cacheWrite'];
function validateCost(cost) {
  closed(cost, costKeys);
  requireThat(costKeys.every(key => Object.hasOwn(cost, key) && Number.isFinite(cost[key]) && cost[key] >= 0));
}
function finiteMilliseconds(seconds) {
  return positive(seconds) && seconds * 1000 <= 2_147_483_647;
}
function bounded(value) {
  requireThat(Buffer.byteLength(typeof value === 'string' ? value : JSON.stringify(value)) <= INPUT_LIMIT_BYTES, 'input-too-large');
}

/** Bounded flat JSONL; an unfinished line never grows beyond the wire cap. */
function listenControl(input, session, actorId, accept, fail) {
  let pending = Buffer.alloc(0);
  const data = chunk => {
    chunk = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    let offset = 0;
    while (offset < chunk.length) {
      const newline = chunk.indexOf(10, offset);
      const end = newline < 0 ? chunk.length : newline;
      if (pending.length + end - offset > CONTROL_LIMIT_BYTES) { fail('control-too-large'); return; }
      pending = Buffer.concat([pending, chunk.subarray(offset, end)]);
      if (newline < 0) return;
      try {
        const line = new TextDecoder('utf-8', {fatal:true}).decode(pending);
        const command = JSON.parse(line);
        // All five keys and values are strings. Ten JSON string tokens also
        // rejects duplicate keys, which JSON.parse alone would silently erase.
        requireThat(object(command) && Object.keys(command).length === 5
          && Object.keys(command).every(key => ['schema', 'id', 'session', 'actor_id', 'type'].includes(key))
          && line.match(/"(?:\\.|[^"\\])*"/g)?.length === 10
          && command.schema === 'player-control/1' && command.type === 'orderly_stop'
          && identity(command.id) && command.session === session && command.actor_id === actorId,
          'invalid-control');
        accept(command);
      } catch { fail('invalid-control'); return; }
      pending = Buffer.alloc(0);
      offset = newline + 1;
    }
  };
  const end = () => fail('control-eof');
  const error = () => fail('control-failed');
  input.on('data', data); input.once('end', end); input.once('error', error);
  if (input.readableEnded || input.destroyed) fail('control-eof');
  return () => { input.off('data', data); input.off('end', end); input.off('error', error); input.pause(); };
}

/** One frozen route, without credential values, ambient discovery or effort clamping. */
export function validateConfiguration(configuration, selectedModel, effort) {
  bounded(configuration);
  closed(configuration, ['schema', 'model', 'api_key_env', 'max_context_images', 'context_image_block', 'request_timeout_seconds', 'service_tier', 'context_reserve_tokens', 'spend_limit_usd', 'unpriced_request_usd', 'context_cut', 'endpoint_costs']);
  requireThat(configuration.schema === 'player-host/13');
  // Positive decimal text for this actor's spend limit and one in-flight request allowance.
  const spendLimit = amountFromText(configuration.spend_limit_usd), bound = amountFromText(configuration.unpriced_request_usd);
  requireThat(spendLimit !== null && spendLimit[0] > 0n && bound !== null && bound[0] > 0n);
  requireThat(/^[A-Za-z_][A-Za-z0-9_]*$/.test(configuration.api_key_env ?? '') && !AMBIENT_PROVIDER_SETTINGS.includes(configuration.api_key_env));
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
  requireThat(Number.isSafeInteger(configuration.context_reserve_tokens)
    && configuration.context_reserve_tokens >= model.maxTokens
    && configuration.context_reserve_tokens < model.contextWindow);
  const cut = configuration.context_cut;
  if (cut !== null) {
    closed(cut, ['high_mark', 'low_mark', 'min_free']);
    requireThat(Number.isSafeInteger(cut.low_mark) && cut.low_mark >= 1
      && Number.isSafeInteger(cut.high_mark) && cut.high_mark > cut.low_mark && cut.high_mark < model.contextWindow
      && Number.isSafeInteger(cut.min_free) && cut.min_free >= 1);
  }
  validateCost(model.cost);
  let url;
  try { url = new URL(model.baseUrl); } catch { throw new HostError('invalid-configuration'); }
  requireThat(['https:', 'http:'].includes(url.protocol) && !url.username && !url.password && !url.search && !url.hash);
  const profile = providerProfile(model);
  profile.validateRoute(configuration, url);
  requireThat(levels.includes(effort), 'unsupported-effort');
  requireThat(model.reasoning || effort === 'off', 'unsupported-effort');
  if (model.thinkingLevelMap !== undefined) {
    closed(model.thinkingLevelMap, levels);
    requireThat(Object.values(model.thinkingLevelMap).every(value => value === null || text(value)));
  }
  if (model.reasoning) {
    requireThat(object(model.thinkingLevelMap) && Object.hasOwn(model.thinkingLevelMap, effort) && model.thinkingLevelMap[effort] !== null, 'unsupported-effort');
    requireThat(model.compat?.supportsReasoningEffort === true && model.compat.thinkingFormat === profile.thinkingFormat, 'unsupported-effort');
  }
  // Pi owns the direct OpenAI and OpenRouter serializers; other formats require
  // conformance evidence before expanding this closed reader.
  if (model.compat !== undefined) {
    closed(model.compat, ['supportsDeveloperRole', 'supportsStore', 'supportsUsageInStreaming', 'supportsReasoningEffort', 'supportsStrictMode', 'maxTokensField', 'requiresToolResultName', 'requiresAssistantAfterToolResult', 'requiresThinkingAsText', 'requiresMistralToolIds', 'thinkingFormat', 'openRouterRouting']);
    for (const [key, value] of Object.entries(model.compat)) {
      if (key === 'maxTokensField') requireThat(['max_tokens', 'max_completion_tokens'].includes(value));
      else if (key === 'thinkingFormat') requireThat(value === profile.thinkingFormat);
      else if (key === 'openRouterRouting') continue; // Closed policy checked above; Pi owns serialization.
      else requireThat(typeof value === 'boolean');
    }
  }
  return configuration;
}

/** Remaining work time (ms) at or below which the tail notice warns of the host deadline. */
export const wallWarningMs = workMs => Math.min(Math.max(workMs * 0.1, 60_000), workMs / 2);

/** How many of the oldest images the projection below omits from these messages, without copying them:
 * whole blocks beyond maxImages, never an image of the latest tool batch, none when that batch alone
 * exceeds maxImages (`blocked`). */
export function imageOmission(messages, maxImages, block) {
  const latestBatch = messages.findLastIndex(message => message.role === 'assistant'
    && message.content.some(part => part.type === 'toolCall'));
  let images = 0, protectedImages = 0;
  for (const [messageIndex, message] of messages.entries()) {
    if (!Array.isArray(message.content)) continue;
    for (const part of message.content) if (part.type === 'image') {
      images++;
      if (latestBatch >= 0 && messageIndex >= latestBatch) protectedImages++;
    }
  }
  const blocked = protectedImages > maxImages;
  const overflow = Math.max(0, images - maxImages);
  // The protected latest batch is never omitted, even when a whole block would reach it.
  const omitted = blocked ? 0 : Math.min(Math.ceil(overflow / block) * block, images - protectedImages);
  return {images, protectedImages, blocked, omitted};
}

/** Request-only projection. Canonical messages stay intact; telemetry separately projects image references.
 * Count-only block eviction: beyond maxImages, the oldest images are omitted in whole
 * blocks, so the serialized prefix stays byte-stable between evictions. Block 1 omits
 * exactly the overflow. `sourceOf` gives the source identity of one canonical tool-result
 * message (keyed by that message, never by its tool call ID, which a later response may
 * reuse); an omission marker names it, so the player can read the frame again by source ID.
 * The marker is a function of the frame alone, so it stays byte-identical on every later request. */
export function projectImageContext(messages, maxImages, block, sourceOf = () => null) {
  requireThat(Number.isSafeInteger(block) && block > 0 && block <= maxImages);
  const projected = structuredClone(messages);
  const {protectedImages, blocked, omitted:omittedCount} = imageOmission(messages, maxImages, block);
  const images = [], occurrences = new Map();
  for (const [messageIndex, message] of projected.entries()) {
    let imageIndex = 0;
    if (!Array.isArray(message.content)) continue;
    const toolCallId = message.toolCallId ?? null;
    // Which result with this tool call ID this is, so a reused ID still names its own message.
    const occurrence = toolCallId === null ? 0 : occurrences.get(toolCallId) ?? 0;
    if (toolCallId !== null && message.role === 'toolResult') occurrences.set(toolCallId, occurrence + 1);
    const sourceId = sourceOf(messages[messageIndex]) ?? null;
    for (const [contentIndex, part] of message.content.entries()) {
      if (part.type === 'image') images.push({messageIndex, contentIndex, imageIndex:imageIndex++,
        toolCallId, occurrence, sourceId, part});
    }
  }
  const omitted = images.slice(0, omittedCount);
  const omissions = [];
  // Complete ordered record for the context manifest; the summary caps its preview.
  const omittedDetails = new Map();
  for (const image of omitted) {
    const decoded = Buffer.from(image.part.data, 'base64');
    const sha256 = createHash('sha256').update(decoded).digest('hex');
    omittedDetails.set(image, {sha256, bytes:decoded.length});
    const provenance = {tool_call_id:image.toolCallId, image_index:image.imageIndex, sha256};
    const {sourceId} = image;
    projected[image.messageIndex].content[image.contentIndex] = {type:'text',
      text:`Historical pixels omitted from this request by frozen image policy; toolCallId=${image.toolCallId}; ${sourceId != null ? `source_id=${sourceId}; ` : ''}image_index=${image.imageIndex}; SHA256=${sha256}. Pixels were not reread; this marker grants no authority or source-read proof.${sourceId != null ? ` To see this frame again, read source_id ${sourceId} with player_source.` : ''}`};
    if (omissions.length < 16) omissions.push(provenance);
  }
  // `source_id` and `occurrence` attribute each image to its own canonical result for the manifest.
  return {messages:projected, images:images.map(image => ({tool_call_id:image.toolCallId, image_index:image.imageIndex,
    source_id:image.sourceId, occurrence:image.occurrence,
    ...(omittedDetails.has(image) ? {omitted:true, ...omittedDetails.get(image)} : {omitted:false})})),
    summary:{max_context_images:maxImages, context_image_block:block, input_images:images.length,
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

const sha256Hex = data => createHash('sha256').update(data).digest('hex');
/** The history with each placed notice re-inserted where it was first sent: after the first `at`
 * messages. `placed` is append-only with non-decreasing `at`, so the result extends the previous
 * request's messages exactly. */
export function withPlacedNotices(messages, placed) {
  const out = [];
  let next = 0;
  for (let i = 0; i <= messages.length; i++) {
    while (next < placed.length && placed[next].at === i) out.push(placed[next++].message);
    if (i < messages.length) out.push(messages[i]);
  }
  return out;
}

const userMessage = text => ({role:'user', timestamp:Date.now(), content:[{type:'text', text}]});
const imageCount = messages => messages.reduce((total, message) => total + (Array.isArray(message.content)
  ? message.content.filter(part => part.type === 'image').length : 0), 0);
const heuristicTokens = messages => messages.reduce((total, message) => total + estimateMessageTokens(message), 0);
const noUsage = {input:0, output:0, cacheRead:0, cacheWrite:0, totalTokens:0};
const UNCOVERED_OPERATION = Symbol('uncovered-operation');

function contextTokens(messages) {
  const estimate = estimateContextTokens(messages);
  // Provider usage can be absent or exclude serializer overhead.
  const heuristic = heuristicTokens(messages);
  return {tokens:Math.max(estimate.tokens, heuristic), usageTokens:estimate.usageTokens, heuristicTokens:heuristic};
}

/** Each assistant and its contiguous results form one indivisible turn. */
function contextTurns(messages, operationsByResult) {
  const turns = [];
  for (let index = 1; index < messages.length; index++) {
    if (messages[index].role !== 'assistant') continue;
    const start = index;
    const creatingOps = [];
    while (messages[index + 1]?.role === 'toolResult') {
      const operation = operationsByResult.get(messages[++index]);
      if (operation !== undefined) creatingOps.push(operation);
    }
    turns.push({start, end:index + 1, creatingOps});
  }
  return turns;
}

/** The provider-affinity value of one mechanical session: a digest of the session identity (not
 * random per request), so every request of every actor in the session carries the same value and a
 * successor reaches the backend that holds the shared system-prompt and tool-table prefix. It is a
 * digest of an audit identity, not a credential, and is recorded in `host-start`. */
export const sessionAffinityId = session => 'enactive-' + sha256Hex(`player-host-session/1\0${session}`).slice(0, 48);
const TEXT_FIELDS = ['reasoning_content', 'reasoning', 'reasoning_text'];

/** Ordered parts of one actually serialized chat-completions payload, as digests only.
 * Parts are listed per message in payload order (reasoning, text/content, tool calls);
 * an image evicted from the request is listed as an `omitted` image directly after the
 * tool-result text that carries its marker. `images` is projectImageContext's ordered
 * image list, which attributes each image to the tool call and the source identity of its
 * own result, even when a later result reuses the call ID. Bodies and image bytes are never returned. */
export function payloadManifestParts(payload, images = []) {
  const parts = [], toolNames = new Map(), omitted = new Map(), toolSeen = new Map();
  // Omitted images wait for their own tool message: the n-th result with a call ID is the n-th tool message with it.
  const resultKey = (id, occurrence) => JSON.stringify([id, occurrence ?? 0]);
  for (const image of images) if (image.omitted) {
    const key = resultKey(image.tool_call_id, image.occurrence);
    omitted.set(key, [...omitted.get(key) ?? [], image]);
  }
  const sentImages = images.filter(image => !image.omitted);
  const sentParts = (payload.messages ?? []).flatMap(message => Array.isArray(message.content) ? message.content : [])
    .filter(part => part?.type === 'image_url').length;
  const attributed = sentImages.length === sentParts;
  let sentSeen = 0;
  const textPart = (role, kind, value, extra = {}) => parts.push({role, kind, bytes:Buffer.byteLength(value), sha256:sha256Hex(value), ...extra});
  const imagePart = (role, image) => parts.push({role, kind:'image', bytes:image.bytes, sha256:image.sha256,
    ...(image.tool_call_id != null ? {tool_call_id:image.tool_call_id, image_index:image.image_index} : {}),
    ...(image.source_id != null ? {source_id:image.source_id} : {}), state:image.omitted ? 'omitted' : 'sent'});
  const emitOmitted = key => { for (const image of omitted.get(key) ?? []) imagePart('tool', image); omitted.delete(key); };
  for (const message of payload.messages ?? []) {
    const role = message.role === 'developer' ? 'system' : message.role;
    for (const key of TEXT_FIELDS) if (typeof message[key] === 'string' && message[key]) textPart(role, 'reasoning', message[key]);
    const tool = role === 'tool';
    const identity = tool ? {tool_call_id:message.tool_call_id, tool:toolNames.get(message.tool_call_id) ?? null} : {};
    const kind = tool ? 'tool_result_text' : 'text';
    if (typeof message.content === 'string') textPart(role, kind, message.content, identity);
    else if (Array.isArray(message.content)) for (const part of message.content) {
      if (part?.type === 'text' && typeof part.text === 'string') textPart(role, kind, part.text, identity);
      else if (part?.type === 'image_url') {
        const url = typeof part.image_url?.url === 'string' ? part.image_url.url : '';
        const comma = url.startsWith('data:') ? url.indexOf(',') : -1;
        const bytes = comma < 0 ? Buffer.from(url) : Buffer.from(url.slice(comma + 1), 'base64');
        const attribution = attributed ? sentImages[sentSeen] : undefined;
        sentSeen++;
        imagePart(role, {tool_call_id:attribution?.tool_call_id, image_index:attribution?.image_index,
          source_id:attribution?.source_id, omitted:false, bytes:bytes.length, sha256:sha256Hex(bytes)});
      }
    }
    for (const call of message.tool_calls ?? []) {
      toolNames.set(call.id, call.function?.name ?? null);
      textPart(role, 'tool_call', JSON.stringify(call), {tool_call_id:call.id, tool:call.function?.name ?? null});
    }
    if (tool) {
      const occurrence = toolSeen.get(message.tool_call_id) ?? 0;
      toolSeen.set(message.tool_call_id, occurrence + 1);
      emitOmitted(resultKey(message.tool_call_id, occurrence));
    }
  }
  // A marker whose tool message is not in the payload still stays visible.
  for (const id of [...omitted.keys()]) emitOmitted(id);
  return parts;
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

/** The full record of a result the tool server shortened for the model: its structured content (the operation
 * record of a computer observe, input or handoff). Null for a result the model reads whole. */
const resultRecord = result => object(result?.structuredContent) ? result.structuredContent : null;

/** Source identity of a computer/source tool result, else null: `source.source_id` of its full record, or of its
 * JSON text where the model reads the result whole (`computer_result`, `player_source`). */
function resultSourceId(result) {
  const valid = id => typeof id === 'string' && id.length > 0 && id.length <= 128;
  const record = resultRecord(result);
  const sourceIdOf = value => {
    if (!object(value)) return null;
    if (value.schema === 'player-source-read/2') {
      if (value.status !== 'available') return null;
      if (valid(value.source_id)) return value.source_id;
    }
    return valid(value.source?.source_id) ? value.source.source_id : null;
  };
  const structured = sourceIdOf(record);
  if (structured !== null) return structured;
  for (const part of (Array.isArray(result?.content) ? result.content : []).filter(part => part.type === 'text').slice(0, 8)) {
    let value;
    try { value = JSON.parse(part.text); } catch { continue; }
    const id = sourceIdOf(value);
    if (id !== null) return id;
  }
  return null;
}

/** Whether one computer input result leaves its delivery uncertain: a partial or unknown operation record, or a
 * transport receipt (no record; its first text) whose outcome is unknown. */
function uncertainDelivery(result, record) {
  if (record) return record.schema === 'player-computer-operation/1' && ['partial', 'unknown'].includes(record.status);
  let value;
  try { value = JSON.parse((Array.isArray(result?.content) ? result.content : []).find(part => part.type === 'text')?.text); }
  catch { return false; }
  return object(value) && value.schema === 'player-transport/2' && value.status === 'unknown';
}
/** Calls that may still follow an uncertain input in its turn: collection, reads and the input stop. */
const AFTER_UNCERTAIN_INPUT = new Set(['computer_result', 'player_result', 'player_source', 'player_knowledge_read',
  'player_knowledge_query', 'player_agenda', 'computer_stop']);

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
function refusalDiagnostic(error, secret) {
  const metadata = error?.metadata;
  const raw = metadata?.raw;
  let structuredRaw = raw;
  if (typeof raw === 'string') {
    try { structuredRaw = JSON.parse(raw); } catch { /* Keep plain text as classification input. */ }
  }
  const rawError = structuredRaw?.error;
  const refusalText = [error?.message, error?.error, raw, structuredRaw?.message, rawError,
    rawError?.message, rawError?.error].filter(text);
  const safeId = value => {
    const id = diagnosticId(Number.isSafeInteger(value) ? String(value) : value, secret);
    return id !== null && !refusalText.some(part => part.trim() === id.trim()) ? id : null;
  };
  const providerLabel = typeof metadata?.provider_name === 'string' ? safeId(metadata.provider_name) : null;
  const providerEcho = providerLabel?.includes(' ') && [...refusalText, metadata?.flagged_input].filter(text)
    .some(part => part.toLowerCase().includes(providerLabel.toLowerCase()));
  const providerName = providerLabel && providerLabel.length <= 64 && !providerEcho
    && /^[A-Za-z0-9][A-Za-z0-9_.:/-]*(?: [A-Za-z0-9_.:/-]+){0,2}$/.test(providerLabel) ? providerLabel : null;
  const identifier = value => {
    const id = safeId(value);
    return id && !id.includes(' ') ? id : null;
  };
  const words = values => values.filter(value => typeof value === 'string' || Number.isSafeInteger(value))
    .join(' ').replace(/[_-]+/g, ' ');
  const reasons = Array.isArray(metadata?.reasons) ? metadata.reasons : [metadata?.reasons];
  const kind = words([error?.code, error?.type, metadata?.provider_code, metadata?.limit_source, metadata?.error_type,
    structuredRaw?.code, structuredRaw?.type, rawError?.code, rawError?.type]);
  const details = words([kind, ...refusalText, metadata?.reason,
    ...reasons.flatMap(reason => object(reason) ? [reason.code, reason.type, reason.reason, reason.message] : [reason])]);
  // Free-form text is classification input only. Explicit terminal evidence wins over provider attribution.
  let refusalClass = 'unknown';
  if (metadata?.flagged_input != null || (Array.isArray(metadata?.reasons) && metadata.reasons.length > 0)
      || /\b(?:moderat(?:ion|ed)|flagged|safety|policy|guardrails?|blocklist|content filter(?:ed|ing)?|(?:blocked|prohibited) content|(?:content|prompt) blocked)\b/i.test(details)) {
    refusalClass = 'moderation';
  } else if (/\b(?:401|forbidden)\b/i.test(kind)
      || /\b(?:auth|authentication|authorization|unauthori[sz]ed|not authori[sz]ed|permissions?|access (?:is )?denied|forbidden access|disabled|suspended|banned|not allowed)\b/i.test(details)
      || /\b(?:(?:invalid|expired|revoked|missing) (?:api |access )?(?:key|token|credentials?)|(?:key|token|credentials?) (?:is |are )?(?:invalid|expired|revoked|missing))\b/i.test(details)) {
    refusalClass = 'auth';
  } else if (text(metadata?.limit_source)
      || /\b(?:quota|billing|budget|credits?|balance|insufficient funds|payment required|(?:spend(?:ing)?|usage|account|key|rate|request) limits?)\b/i.test(details)) {
    refusalClass = 'credits-or-limit';
  } else if (providerName !== null) {
    refusalClass = 'upstream-provider';
  }
  return {refusal_class:refusalClass, provider_name:providerName,
    error_type:identifier(metadata?.error_type ?? error?.type), error_code:identifier(error?.code),
    provider_error_code:identifier(metadata?.provider_code), limit_source:identifier(metadata?.limit_source),
    reason:identifier(metadata?.reason)};
}

// The provider's own statement of what one response cost, in US dollars (#555). The host
// counts it toward the route's dollar limit. The rule is the curator's `reported_cost`
// (tools/curator_host/providers.py), and both hosts' tests run the usage records in
// tests/fixtures/provider-usage-cost.json. On a route that is not on the caller's own
// provider key the cost is the larger of `cost` and `cost_details.upstream_inference_cost`;
// on an own-key route (`is_byok` true) it is their sum; the largest record of a response
// wins. Where the curator raises on a malformed record, the cost here is unknown (null),
// never a guess.
// Money never passes through floating-point arithmetic. Each JSON number becomes, once, the
// shortest decimal that reads back as the same number (the provider's own digits for up to
// 15 significant digits), held as [units, scale] meaning units / 10^scale with BigInt units.
const MALFORMED_COST = Symbol('malformed-cost');
function decimalAmount(value) {
  if (value == null) return null;
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return MALFORMED_COST;
  const [digits, exponent = '0'] = String(value).split('e');
  const [whole, fraction = ''] = digits.split('.');
  const scale = fraction.length - Number(exponent);
  return scale < 0 ? [BigInt(whole + fraction) * 10n ** BigInt(-scale), 0] : [BigInt(whole + fraction), scale];
}
function alignedUnits([a, m], [b, n]) {
  const scale = Math.max(m, n);
  return [a * 10n ** BigInt(scale - m), b * 10n ** BigInt(scale - n), scale];
}
function largerAmount(x, y) {
  const [a, b] = alignedUnits(x, y);
  return a >= b ? x : y;
}
function usageRecordCost(usage) {
  const cost = decimalAmount(usage.cost), details = usage.cost_details ?? {};
  if (cost === MALFORMED_COST || !object(details)) return MALFORMED_COST;
  const upstream = decimalAmount(details.upstream_inference_cost);
  if (upstream === MALFORMED_COST || (usage.is_byok != null && typeof usage.is_byok !== 'boolean')) return MALFORMED_COST;
  if (usage.is_byok === true) {
    if (!cost || !upstream) return MALFORMED_COST;
    const [a, b, scale] = alignedUnits(cost, upstream);
    return [a + b, scale];
  }
  return cost || upstream ? largerAmount(cost ?? [0n, 0], upstream ?? [0n, 0]) : null;
}
// One more usage record of the same response: null (no cost yet), an amount or MALFORMED_COST.
function withUsageRecord(soFar, usage) {
  if (soFar === MALFORMED_COST) return soFar;
  const cost = usageRecordCost(usage);
  return cost === MALFORMED_COST || !soFar ? cost : cost ? largerAmount(soFar, cost) : soFar;
}
// A dollar amount of the route: plain decimal text, at most twelve whole and eighteen fractional digits.
const AMOUNT_TEXT = /^(0|[1-9][0-9]{0,11})(\.[0-9]{1,18})?$/;
function amountFromText(value) {
  if (typeof value !== 'string' || !AMOUNT_TEXT.test(value)) return null;
  const [whole, fraction = ''] = value.split('.');
  return [BigInt(whole + fraction), fraction.length];
}
function addAmounts(x, y) {
  const [a, b, scale] = alignedUnits(x, y);
  return [a + b, scale];
}
// Plain decimal text: no exponent, no trailing zeros, "0" for zero.
function amountText(cost) {
  if (!cost || cost === MALFORMED_COST) return null;
  const [units, scale] = cost;
  const digits = units.toString().padStart(scale + 1, '0');
  const fraction = digits.slice(digits.length - scale).replace(/0+$/, '');
  return digits.slice(0, digits.length - scale) + (fraction ? `.${fraction}` : '');
}
/** Reported cost of one response from its usage records: a decimal string, or null when none is usable. */
export const reportedCostUsd = usageRecords => amountText(usageRecords.reduce(withUsageRecord, null));

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

// Read a successful event stream up to its first `data:` event (at most 64 KiB)
// without delivering anything to the SDK. An error object as that first event, or
// a stream that ends with no data, means no output reached the player, so the
// request is safe to retry. Otherwise the buffered bytes are replayed unchanged.
const PEEK_LIMIT = 65536;
async function peekFirstEvent(response, signal, extractCost) {
  signal.throwIfAborted();
  const reader = response.body.getReader();
  // As in refusalBody: cancellation releases a pending read without waiting on
  // an untrusted source's cancel hook.
  const cancel = () => { void reader.cancel().catch(() => {}); };
  signal.addEventListener('abort', cancel, {once:true});
  const chunks = [];
  let bytes = 0, done = false, broken = false, first = null;
  // Event-stream fields parsed line by line as chunks arrive, so the first event does not depend on where
  // chunk boundaries fall: a CR LF may be split across chunks, and one event may carry several data lines.
  let pending = '', dataLines = [], sawData = false;
  const decoder = new TextDecoder();
  const feed = (text, final = false) => {
    pending += text;
    for (;;) {
      const end = /\r\n|\r|\n/.exec(pending);
      // A CR at the end of what has arrived may be the first half of a CR LF.
      if (!end || (end[0] === '\r' && end.index === pending.length - 1 && !final)) return;
      const line = pending.slice(0, end.index);
      pending = pending.slice(end.index + end[0].length);
      if (line === '') {
        if (dataLines.length) { first = dataLines.join('\n'); return; }
        continue;
      }
      if (line.startsWith(':')) continue;
      const colon = line.indexOf(':');
      if ((colon < 0 ? line : line.slice(0, colon)) !== 'data') continue;
      const value = colon < 0 ? '' : line.slice(colon + 1);
      dataLines.push(value.startsWith(' ') ? value.slice(1) : value);
      sawData = true;
    }
  };
  try {
    while (first === null && bytes < PEEK_LIMIT) {
      signal.throwIfAborted();
      let step;
      // A transport error before any data event reached the SDK is retryable.
      try { step = await reader.read(); }
      catch (error) { signal.throwIfAborted(); broken = true; break; }
      signal.throwIfAborted();
      if (step.done) { done = true; feed(decoder.decode(), true); break; }
      chunks.push(step.value);
      const remaining = PEEK_LIMIT - bytes;
      bytes += step.value.byteLength;
      const slice = step.value.byteLength > remaining ? step.value.subarray(0, remaining) : step.value;
      feed(decoder.decode(slice, {stream:true}));
    }
  } catch (error) {
    cancel();
    throw error;
  } finally {
    signal.removeEventListener('abort', cancel);
  }
  let event = null;
  if (first !== null && first.trim() !== '[DONE]') {
    try { event = JSON.parse(first); } catch { /* Leave malformed events for the SDK. */ }
  }
  const errorEvent = object(event?.error);
  // A partial data event that then breaks stays terminal, as before, including a data line still arriving.
  const noData = !sawData && !/^data(?::|$)/.test(pending);
  const failed = errorEvent || first?.trim() === '[DONE]' || ((broken || done) && noData);
  const replay = new ReadableStream({
    start(controller) { for (const chunk of chunks) controller.enqueue(chunk); if (done) controller.close(); },
    async pull(controller) {
      const step = await reader.read();
      if (step.done) controller.close(); else controller.enqueue(step.value);
    },
    cancel(reason) { return reader.cancel(reason); },
  });
  return {failed, reported:errorEvent ? extractCost(null, event) : null, cancel:() => reader.cancel().catch(() => {}),
    response:new Response(replay, {status:response.status, statusText:response.statusText, headers:response.headers})};
}

/** The parsed body of one serialized provider attempt, or a HostError naming why it must not be sent: a body
 * that is not JSON text, or (on an OpenRouter route) a missing session-affinity header. Pi enables that header
 * by its own detection; this fails closed before any charge if a maintained-SDK change ever stops sending it. */
export function providerPayload(init, provider, affinityId) {
  requireThat(typeof init?.body === 'string', 'invalid-provider-payload');
  providerProfile({provider, api:'openai-completions'}).checkAffinity(init, affinityId);
  try { return JSON.parse(init.body); } catch { throw new HostError('invalid-provider-payload'); }
}

function retryableRefusal(error) {
  if (!object(error)) return false;
  const kind = [error.type, error.code, error.metadata?.error_type, error.metadata?.provider_code,
    error.metadata?.limit_source].filter(text).join(' ');
  const details = [kind, error.message].filter(text).join(' ');
  // Authorization, key, permission, malformed-request and context-length errors are never transient.
  if (/(?:auth|api[_ -]?key|permission|invalid|malformed|context)/i.test(kind)
      || /(?:authenticat|authorizat|api[_ -]?key|permission|invalid[_ -]?(?:request|parameter)|malformed|context[_ -]?(?:length|window))/i.test(details)) return false;
  // OpenRouter's admission control is a transient hold. It can arrive with no
  // message, or cite the account balance while automatic refill catches up
  // (development runs B6 and B7), so balance wording does not make it terminal.
  if (error.metadata?.limit_source === 'openrouter_admission_control') return true;
  // Pi's positive classifier is deliberately broad. Explicit non-transient
  // kinds must win even when their message also mentions a rate limit or 429.
  if (/(?:quota|billing|budget|payment|credit)/i.test(kind)
      || /(?:quota|billing|budget|payment|credit)/i.test(details)) return false;
  return isRetryableAssistantError({stopReason:'error', errorMessage:details});
}

// OpenRouter's documented transient in-flight hold, a narrow exception to the
// budget/credit exclusion above. Every other 402, including credits, is terminal.
function inFlightBudgetRefusal(error) {
  const metadata = error?.metadata;
  return metadata?.limit_source === 'openrouter_in_flight_budget' && metadata?.reason === 'in_flight_budget_exhausted';
}

function validateOpenRouterRoute(configuration, url) {
  const {model} = configuration;
  requireThat(url.origin === 'https://openrouter.ai' && url.pathname.replace(/\/$/, '') === '/api/v1');
  requireThat(configuration.service_tier === 'default');
  const routing = model.compat?.openRouterRouting;
  closed(routing, ['only', 'order', 'allow_fallbacks', 'require_parameters']);
  const {only, order} = routing;
  requireThat(routing.allow_fallbacks === false && routing.require_parameters === true
    && Array.isArray(only) && (only.length === 1 || only.length === 2) && new Set(only).size === only.length
    && [...only].every(tag => typeof tag === 'string' && /^[a-z0-9][a-z0-9_./-]{0,127}$/.test(tag))
    && Array.isArray(order) && order.length === only.length && only.every((tag, index) => order[index] === tag));
  if (only.length === 2) {
    const costs = configuration.endpoint_costs;
    closed(costs, only);
    requireThat(only.every(tag => Object.hasOwn(costs, tag)));
    const [primary, secondary] = only.map(tag => costs[tag]);
    validateCost(primary);
    validateCost(secondary);
    requireThat(costKeys.every(key => model.cost[key] === Math.max(primary[key], secondary[key])));
  } else requireThat(configuration.endpoint_costs === null);
}
function validateDirectRoute(configuration, url) {
  requireThat(url.hostname !== 'openrouter.ai' && configuration.model.compat?.openRouterRouting === undefined
    && configuration.endpoint_costs === null);
}

const streamUsage = chunk => chunk?.usage ?? chunk?.choices?.[0]?.usage;
const completionsProfile = {
  stream,
  extractCost(soFar, chunk) {
    const usage = streamUsage(chunk);
    return object(usage) ? withUsageRecord(soFar, usage) : soFar;
  },
  retryClass(status, diagnostic, error, headers) {
    if (SERVER_RETRY_STATUSES.includes(status)) return 'server-error';
    if (status === 403 && diagnostic.refusal_class === 'upstream-provider') return 'provider-403-failover';
    if (status === 429 && retryableRefusal(error)) return 'rate-limit';
    if (status === 402 && Number.isFinite(retryAfterMs(headers.get('retry-after'))) && inFlightBudgetRefusal(error))
      return 'in-flight-budget';
    return null;
  },
};
const PROVIDER_PROFILES = Object.freeze({
  'openai-completions': {
    openrouter: {...completionsProfile, validateRoute:validateOpenRouterRoute, thinkingFormat:'openrouter',
      checkAffinity(init, affinityId) {
        requireThat(new Headers(init.headers).get('x-session-id') === affinityId, 'session-affinity-missing');
      },
      serviceTier:payload => ({...payload, service_tier:'default'})},
    direct: {...completionsProfile, validateRoute:validateDirectRoute, thinkingFormat:'openai',
      checkAffinity() {},
      serviceTier:(payload, tier) => tier === 'priority' ? {...payload, service_tier:'priority'} : payload},
  },
});

function providerProfile({provider, api}) {
  const profiles = Object.hasOwn(PROVIDER_PROFILES, api) ? PROVIDER_PROFILES[api] : null;
  requireThat(profiles);
  // The route historically accepts arbitrary direct-provider names on the one closed API.
  return Object.hasOwn(profiles, provider) ? profiles[provider] : profiles.direct;
}

// This actual MCP receipt ends this host only. The driver independently checks
// canonical issuance/context and actual host/MCP quiescence before succession.
function inspectHandoff(name, args, result, pending, session, actorId) {
  if (!['player_handoff', 'computer_result'].includes(name)) return {};
  const direct = name === 'player_handoff';
  // Reading an unrelated or earlier actor's issuance never arms settlement.
  if (!direct && (!pending || args.operation_id !== pending.operation_id)) return {};
  // A local rejection/no-submit result provides no origin, even when it carries
  // plausible-looking IDs. Preserve explicit model correction/collection.
  if (result.isError === true) return {};
  let value;
  try {
    // A direct handoff is shortened for the model; its full record is the structured content. A collection
    // returns the record whole, and a transport receipt has no record: both are the first text.
    value = resultRecord(result) ?? JSON.parse(result.content?.find(part => part.type === 'text')?.text);
  } catch {
    throw new HostError('invalid-handoff-receipt');
  }
  const id = value => typeof value === 'string' && /^[a-f0-9]{32}$/.test(value);
  const valid = condition => requireThat(condition, 'invalid-handoff-receipt');
  const isTransport = object(value) && value.schema === 'player-transport/2';
  valid(object(value) && id(value.operation_id) && id(value.session) && id(value.actor_id)
    && (isTransport ? value.kind === (direct ? 'handoff' : name) : value.kind === 'handoff')
    && value.session === session && value.actor_id === actorId);
  const origin = {operation_id:value.operation_id, session:value.session, actor_id:value.actor_id};
  if (pending) valid(isDeepStrictEqual(origin, pending));
  if (isTransport) {
    valid(value.status === 'unknown' && typeof value.reason === 'string');
    return {pending:origin};
  }
  valid(value.schema === 'player-computer-operation/1');
  if (['pending', 'unknown'].includes(value.status)) {
    valid(value.handoff === null);
    return {pending:origin};
  }
  if (value.status === 'refused') {
    valid(value.handoff === null);
    // Collection proves the pending original will never seal.
    return {refused:true};
  }
  const issued = value.handoff;
  valid(value.status === 'sealed' && object(issued)
    && issued.schema === 'player-handoff/1' && issued.grants_authority === false
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
  let agent, client, transport, fatal, closing = false, requests = 0, requestId, requestTimer, requestInFlight = false, requestUsageAvailable = false, requestReportedCost = null;
  // Every HTTP attempt gets a response-complete record. Only provider prices debit the dollar limit.
  // A completed attempt without a usable price stays unknown and remains in the observed count.
  let spent = [0n, 0], unpricedRequests = 0, spendLimit, unpricedBound;
  let knowledge, lastAnnouncedKnowledge, boundaryKnowledge, finishReserve, agenda = emptyAgenda();
  const earnedRefs = new Set();
  const earnKnowledgeRefs = version => {
    for (const article of version.articles) earnedRefs.add(article.id);
    for (const fact of version.facts) {
      earnedRefs.add(fact.id);
      if (fact.state_key) earnedRefs.add(fact.state_key);
      for (const id of fact.citation_source_ids) earnedRefs.add(id);
    }
    for (const id of [...Object.keys(version.history.replaced), ...version.history.retracted, ...version.history.ended])
      earnedRefs.add(id);
  };
  // `projectedOmissions` is how many images the last request's projection omitted from its active history.
  let briefing, currentBriefingTokens, cutState, cutRestored = false, projectedOmissions = 0;
  let cutDemand = [], heldCut;
  let unsentDeliveries = [];
  // The assistant message whose call is being dispatched, and the one whose input delivery became uncertain.
  let dispatchingTurn, uncertainTurn;
  const countAttempt = reported => {
    const priced = reported !== null && reported !== MALFORMED_COST;
    if (priced) spent = addAmounts(spent, reported);
    else unpricedRequests++;
    return {counted_cost_usd:priced ? amountText(reported) : null,
      cost_counted_as:priced ? 'provider-reported' : 'unpriced', spent_usd:amountText(spent)};
  };
  const lessThan = (a, b) => { const [x,y] = alignedUnits(a,b); return x < y; };
  // Live delivery of a newer delivered-knowledge version (`--knowledge-updates`). The driver appends one
  // `knowledge-update-entry/1` line for each version it has verified and written beside the list. A refresh
  // off the request path reads whole unread lines and their files in an isolated helper process, verifies
  // them and stages them in memory; building a player request only takes what is staged, and closing the
  // helper kills any stalled read immediately so it never delays settlement or CLI exit.
  let updatesOffset = 0, skippingUpdateLine = false, updateRefresh = null, refreshAgain = false, updatesPoll, updatesClosed = false;
  let updateReader = null, updateReaderBuf = '', updateReadSeq = 0;
  const pendingReads = new Map();
  const pendingKnowledgeUpdates = new Map();
  const pendingCoverageUpdates = [];
  const coveredByVersion = new Map();
  const pendingRefusals = [];
  const failUpdateReads = () => {
    for (const resolve of pendingReads.values()) resolve(null);
    pendingReads.clear();
  };
  const closeUpdateReader = () => {
    const child = updateReader;
    updateReader = null;
    updateReaderBuf = '';
    failUpdateReads();
    if (!child) return;
    child.stdin?.destroy();
    child.stdout?.destroy();
    try { child.kill('SIGKILL'); } catch {}
    child.unref();
  };
  const ensureUpdateReader = () => {
    if (updatesClosed) return null;
    if (updateReader) return updateReader;
    const childEnv = {PATH:process.env.PATH ?? '/usr/bin:/bin', LANG:process.env.LANG ?? 'C.UTF-8'};
    const child = spawn(process.execPath, [UPDATE_READER], {env:childEnv, stdio:['pipe', 'pipe', 'ignore']});
    updateReader = child;
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', chunk => {
      updateReaderBuf += chunk;
      let newline;
      while ((newline = updateReaderBuf.indexOf('\n')) >= 0) {
        const line = updateReaderBuf.slice(0, newline);
        updateReaderBuf = updateReaderBuf.slice(newline + 1);
        if (!line) continue;
        try {
          const reply = JSON.parse(line);
          const resolve = pendingReads.get(reply.id);
          if (resolve) { pendingReads.delete(reply.id); resolve(reply.ok ? Buffer.from(reply.data, 'base64') : null); }
        } catch {}
      }
    });
    const ended = () => { if (updateReader !== child) return; updateReader = null; failUpdateReads(); };
    child.on('error', ended);
    child.on('exit', ended);
    child.stdin.on('error', () => {});
    child.unref();
    return child;
  };
  const updateReadTimeoutMs = positive(options.updateReadTimeoutMs) ? options.updateReadTimeoutMs : UPDATE_READ_TIMEOUT_MS;
  const readUpdateFile = (path, offset = null, limit = null) => new Promise(resolve => {
    const child = ensureUpdateReader();
    if (!child) { resolve(null); return; }
    const id = ++updateReadSeq;
    const finish = value => { clearTimeout(timer); resolve(value); };
    const timer = setTimeout(() => {
      if (!pendingReads.has(id)) return;
      // A stalled read wedged the helper process: terminate it so the next read spawns a fresh helper.
      if (updateReader === child) closeUpdateReader();
      else { pendingReads.delete(id); finish(null); }
    }, updateReadTimeoutMs);
    timer.unref();
    pendingReads.set(id, finish);
    try { child.stdin.write(JSON.stringify({id, path, offset, limit}) + '\n'); }
    catch { pendingReads.delete(id); finish(null); }
  });
  const unreadUpdateLines = async () => {
    const data = await readUpdateFile(options.knowledgeUpdates, updatesOffset, INPUT_LIMIT_BYTES);
    if (!data || data.length === 0) return [];
    let start = 0;
    if (skippingUpdateLine) {
      // The rest of a line over the input bound is consumed through its newline, never read as an entry.
      const newline = data.indexOf(10);
      if (newline < 0) { updatesOffset += data.length; return []; }
      skippingUpdateLine = false;
      start = newline + 1;
    }
    const end = data.lastIndexOf(10);
    if (end < start) {
      // A line still being appended is read once it is whole; one over the input bound is never an entry.
      if (start > 0 || data.length < INPUT_LIMIT_BYTES) { updatesOffset += start; return []; }
      updatesOffset += data.length;
      skippingUpdateLine = true;
      return [''];
    }
    updatesOffset += end + 1;
    return data.subarray(start, end).toString('utf8').split('\n').filter(line => line.trim());
  };
  // Refusals wait in memory with the version held when they were decided and are recorded when the next
  // request is built (or when the actor ends), so the refresh itself never writes telemetry between events.
  const refuseUpdate = (entry, reason, extra = {}) => { if (!updatesClosed) pendingRefusals.push({kind:'update', outcome:'refused',
    version:entry?.version ?? null, previous_version:knowledge.version, coverage:entry?.coverage ?? null, reason, ...extra}); };
  const flushRefusals = () => { for (const event of pendingRefusals.splice(0)) emit('knowledge-delivery', event); };
  const heldNumber = () => versionNumber(knowledge.version) ?? -1;
  // The listed file as the adopted version would be, or the reason it is refused.
  const verifiedUpdate = async entry => {
    const foreign = () => knowledge.repository_id !== null && entry.repository_id !== knowledge.repository_id;
    if (foreign()) return 'repository-mismatch';
    const data = await readUpdateFile(join(dirname(options.knowledgeUpdates), entry.file));
    if (!data) return 'file-unreadable';
    if (foreign()) return 'repository-mismatch';
    if (sha256Hex(data) !== entry.sha256) return 'sha256-mismatch';
    let value;
    try { value = validateKnowledge(JSON.parse(data.toString('utf8'))); } catch { return 'invalid-delivered-knowledge'; }
    return value.version === entry.version && value.commit === entry.commit && value.repository_id === entry.repository_id
      && isDeepStrictEqual(value.coverage, entry.coverage) ? value : 'entry-mismatch';
  };
  // Unread entries are verified newest first and held until request preparation picks the newest one that fits
  // within context capacity, so an oversized newer version can still fall back to an older verified candidate.
  const refreshOnce = async () => {
    const entries = [];
    for (const line of await unreadUpdateLines()) {
      if (updatesClosed) return;
      const entry = updateEntry(line);
      if (entry) {
        entries.push(entry);
        continue;
      }
      const coverage = coverageEntry(line);
      if (!coverage) refuseUpdate(null, 'invalid-entry');
      else if (coverage.session === options.session) pendingCoverageUpdates.push(coverage);
    }
    entries.sort((a, b) => b.number - a.number);
    for (const entry of entries) {
      if (updatesClosed) return;
      if (entry.number <= heldNumber()) { refuseUpdate(entry, 'not-newer'); continue; }
      if (pendingKnowledgeUpdates.has(entry.number)) { refuseUpdate(entry, 'superseded'); continue; }
      const value = await verifiedUpdate(entry);
      if (updatesClosed) return;
      if (typeof value === 'string') { refuseUpdate(entry, value); continue; }
      if (entry.number <= heldNumber()) { refuseUpdate(entry, 'not-newer'); continue; }
      if (pendingKnowledgeUpdates.has(entry.number)) { refuseUpdate(entry, 'superseded'); continue; }
      pendingKnowledgeUpdates.set(entry.number, {entry, knowledge:value});
    }
  };
  // Starts a refresh unless one is outstanding, in which case that one runs once more when it finishes.
  // Nothing waits for it.
  const refreshUpdates = () => {
    if (!options.knowledgeUpdates || updatesClosed) return;
    if (updateRefresh) { refreshAgain = true; return; }
    updateRefresh = (async () => {
      do { refreshAgain = false; await refreshOnce(); } while (refreshAgain && !updatesClosed);
    })().catch(error => refuseUpdate(null, 'update-check-failed', {error_name:error?.name ?? null}))
      .finally(() => { updateRefresh = null; });
  };
  let workTimer, deadlineTimer;
  let responseProgress, handoff, pendingHandoff, finish, control, unlistenControl, requestControlId;
  let controlMessage, controlAt, pendingTailNotice, logicalDeliveries = [];
  const controlAccepted = new AbortController();
  let releaseInitialControl;
  const initialControlReady = new Promise(resolve => { releaseInitialControl = resolve; });
  let affinityId, noticeSteps = {};
  // Each placed message keeps its boundary in canonical history until a cut removes it.
  let placedNotices = [];
  const recentCalls = new Set();
  const intentByResult = new WeakMap(), dispatchedIntents = new Map();
  const settleDeliveries = (outcome, receivingId) => {
    for (const {value, target} of logicalDeliveries.splice(0)) {
      if (outcome === 'delivered') lastAnnouncedKnowledge = target;
      emit('knowledge-delivery', {...value, outcome, receiving_player_request_id:receivingId});
    }
  };
  // Context manifest state: the latest projection's ordered images and the previous manifest
  // (part keys and omitted indexes) for deltas.
  let contextImages = [], manifestBase = null;
  const toolOperations = new Map();
  // A tool result's source identity is pinned to its canonical content, never to its call ID.
  const operationsByResult = new WeakMap(), sourcesByContent = new WeakMap();
  const sourceOf = message => Array.isArray(message?.content) ? sourcesByContent.get(message.content) ?? null : null;
  // Delta against the previous attempt's manifest: the leading parts identical to it are
  // counted, not repeated. Replay rule: contract `context-manifest` row.
  const nextContextManifest = (attemptId, payload) => {
    const parts = payloadManifestParts(payload, contextImages);
    const keys = parts.map(part => JSON.stringify(part));
    const previous = manifestBase?.keys ?? [];
    let reused = 0;
    while (reused < previous.length && reused < keys.length && previous[reused] === keys[reused]) reused++;
    const omittedIndexes = parts.flatMap((part, index) => part.state === 'omitted' ? [index] : []);
    const changed = !isDeepStrictEqual(omittedIndexes, manifestBase?.omitted ?? []);
    const event = {request_id:attemptId, base_request_id:manifestBase?.requestId ?? null, reused_prefix_parts:reused,
      part_count:parts.length, parts:parts.slice(reused).map((part, offset) => ({index:reused + offset, ...part})),
      ...(changed ? {omitted_image_indexes:omittedIndexes} : {})};
    manifestBase = {requestId:attemptId, keys, omitted:omittedIndexes};
    return event;
  };
  const assistantControls = new WeakMap();
  const progressSnapshot = () => responseProgress ? {...responseProgress,
    scope:requestInFlight ? 'current-http-attempt' : 'last-http-attempt'} : null;
  let streamRecoveryAvailable = true;
  const stopped = new AbortController();
  const stop = reason => {
    if (fatal) return;
    fatal = reason;
    emit('abort', {reason, request_id:requestId, response_progress:progressSnapshot()});
    stopped.abort();
    releaseInitialControl();
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
  let reserveReached = false;
  const reserveWaitMs = options.spendReserveWaitMs ?? 2000;
  const admitsOrdinary = () => lessThan(addAmounts(spent, addAmounts(finishReserve, unpricedBound)), spendLimit);
  const admitPlayer = async projectedControl => {
    const signal = projectedControl ? stopped.signal : AbortSignal.any([stopped.signal, controlAccepted.signal]);
    const ready = () => {
      if (fatal) throw new HostError(fatal);
      if (!lessThan(spent, spendLimit)) throw new HostError('spend-limit');
      return control && projectedControl !== control.id ? 'superseded' : null;
    };
    const reason = ready();
    if (reason) return reason;
    if (projectedControl || admitsOrdinary()) return null;
    if (!reserveReached) {
      reserveReached = true;
      emit('spend-reserve-reached', {actor_id:options.actorId, spent_usd:amountText(spent),
        spend_limit_usd:amountText(spendLimit), finish_reserve_usd:amountText(finishReserve), unpriced_bound_usd:amountText(unpricedBound)});
    }
    const waiting = new AbortController();
    const timerSignal = AbortSignal.any([signal, waiting.signal]);
    const timeout = delay(reserveWaitMs, undefined, {signal:timerSignal}).catch(error => {
      if (error.name !== 'AbortError') throw error;
    });
    try {
      await timeout;
      const reason = ready();
      if (reason) return reason;
      throw new HostError('spend-reserve-timeout');
    } finally { waiting.abort(); }
  };
  function failureStream(model, reason) {
    const response = new AssistantMessageEventStream();
    const message = {role:'assistant', content:[], api:model.api, provider:model.provider, model:model.id,
      usage:{input:0, output:0, cacheRead:0, cacheWrite:0, totalTokens:0, cost:{input:0, output:0, cacheRead:0, cacheWrite:0, total:0}},
      stopReason:'aborted', errorMessage:reason, timestamp:Date.now()};
    response.push({type:'error', reason:'aborted', error:message});
    response.end(message);
    return response;
  }
  function settlePlayerAttempt(message) {
    const reported = amountText(requestReportedCost);
    emit('response-complete', {request_id:requestId, model:message.model, provider:message.provider,
      reported_provider:responseProgress?.reported_provider ?? null, stop_reason:message.stopReason,
      usage_available:requestUsageAvailable, usage:requestUsageAvailable ? message.usage : null,
      cost_source:requestUsageAvailable ? 'configured-rates' : null, reported_cost_usd:reported,
      ...countAttempt(requestReportedCost), response_progress:progressSnapshot()});
    requestInFlight = false;
    return reported;
  }
  try {
    requireThat(positive(options.timeoutSeconds), 'invalid-host-timeout');
    const totalMs = options.timeoutSeconds * 1000;
    requireThat(Number.isFinite(totalMs) && totalMs <= 2_147_483_647, 'invalid-host-timeout');
    const cleanupBudget = Math.min(1000, totalMs / 4);
    workTimer = setTimeout(() => stop('host-timeout'), totalMs - cleanupBudget);
    deadlineTimer = setTimeout(() => stop('host-timeout'), totalMs);
    options.signal?.addEventListener('abort', cancellation, {once:true});
    if (options.signal?.aborted) stop('cancelled');
    try { agenda = validateAgenda(options.agenda === undefined ? emptyAgenda() : options.agenda); }
    catch { throw new HostError('invalid-agenda'); }
    const configuration = validateConfiguration(options.configuration, options.model, options.effort);
    const mcp = validateMcpConfiguration(options.mcpConfig);
    requireThat(identity(options.session) && identity(options.actorId) && options.control?.on
      && (options.pendingControlId === null || identity(options.pendingControlId)), 'invalid-control-binding');
    requireThat(typeof options.prompt === 'string' && typeof options.context === 'string', 'invalid-input');
    bounded(options.prompt); bounded(options.context);
    requireThat(options.knowledgeUpdates == null || text(options.knowledgeUpdates), 'invalid-input');
    for (const thread of agenda.threads) for (const ref of thread.refs ?? []) earnedRefs.add(ref);
    knowledge = lastAnnouncedKnowledge = boundaryKnowledge = validateKnowledge(options.knowledge);
    earnKnowledgeRefs(knowledge);
    if (options.knowledgeUpdates) {
      // Refreshes start now, on a timer and after each player response; none keeps the process alive.
      refreshUpdates();
      updatesPoll = setInterval(refreshUpdates, UPDATE_POLL_MS);
      updatesPoll.unref();
    }
    finishReserve = amountFromText(options.finishReserveUsd);
    requireThat(finishReserve !== null, 'invalid-finish-reserve');
    affinityId = sessionAffinityId(options.session);
    spendLimit = amountFromText(configuration.spend_limit_usd);
    const [limitUnits, reserveUnits, spendScale] = alignedUnits(spendLimit, finishReserve);
    const workBudget = largerAmount([0n, 0], [limitUnits - reserveUnits, spendScale]);
    const warningBand = largerAmount([25n, 2], [workBudget[0] * 15n, workBudget[1] + 2]);
    const spendWarningThreshold = lessThan(workBudget, warningBand) ? workBudget : warningBand;
    unpricedBound = amountFromText(configuration.unpriced_request_usd);
    emit('host-start', {telemetry_version:13, schema:configuration.schema, session:options.session, actor_id:options.actorId,
      requested_service_tier:configuration.service_tier, model:configuration.model.id, provider:configuration.model.provider,
      api:configuration.model.api, effort:options.effort, max_output_tokens:configuration.model.maxTokens,
      context_window:configuration.model.contextWindow, context_reserve_tokens:configuration.context_reserve_tokens,
      context_cut:configuration.context_cut, thinking_level_map:{...configuration.model.thinkingLevelMap},
      reasoning_format:configuration.model.compat?.thinkingFormat ?? null,
      provider_routing:structuredClone(configuration.model.compat?.openRouterRouting ?? null),
      endpoint_costs:structuredClone(configuration.endpoint_costs),
      spend_limit_usd:configuration.spend_limit_usd, unpriced_request_usd:configuration.unpriced_request_usd,
      max_context_images:configuration.max_context_images, context_image_block:configuration.context_image_block,
      unsupported_features:['compaction', 'session-restore', 'model-fallback', 'reconnect', 'replay', 'ambient-tools', 'resource-discovery'],
      missing_endpoints:['model-attention', 'server-inference-start', 'physical-paint'], cleanup_budget_ms:cleanupBudget,
      session_affinity_id:affinityId});
    unlistenControl = listenControl(options.control, options.session, options.actorId, command => {
      if (control) {
        if (!isDeepStrictEqual(control, command)) stop('conflicting-control');
        return;
      }
      if (options.pendingControlId !== null && command.id !== options.pendingControlId) {
        stop('invalid-initial-control'); return;
      }
      control = command;
      cutDemand = [];
      heldCut = undefined;
      controlMessage = userMessage(`${STOP_TEXT}\ncontrol_id: ${control.id}`);
      releaseInitialControl();
      controlAccepted.abort();

      emit('control-accepted', {control_id:control.id, session:control.session, actor_id:control.actor_id, control_type:control.type});
      agent?.steer(controlMessage);
    }, stop);
    // A successor's pending command is declared before spawn. Scheduler order
    // cannot let it start ordinary work while the parent is still writing it.
    if (options.pendingControlId !== null) await initialControlReady;
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
    const localNames = ['player_finish', 'player_agenda'];
    requireThat(names.size === discovered.length && localNames.every(name => !names.has(name))
      && mcp.enabled_tools.every(name => names.has(name)), 'missing-required-tools');
    const recordIntent = (toolCallId, intent) => {
      if (typeof intent !== 'string' || !intent.isWellFormed() || [...intent].length > 512
          || ![...intent].some(character => character === '\ufeff' || !/[\s\x1c-\x1f\x85]/u.test(character))
          || /[\r\n\v\f\x1c-\x1e\x85\u2028\u2029]/u.test(intent)) return false;
      recentCalls.delete(intent);
      recentCalls.add(intent);
      if (recentCalls.size > 5) recentCalls.delete(recentCalls.values().next().value);
      if (configuration.context_cut !== null) dispatchedIntents.set(toolCallId, intent);
      return true;
    };
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
        // A stop or an unverified input receipt never permits a stalled inference
        // to earn extra work. Ordinary collection of the original ID stays available.
        if (name === 'computer_stop') streamRecoveryAvailable = false;
        const createsOperation = name === 'computer_input' || name === 'computer_observe';
        const record = resultRecord(result);
        const completedOperation = createsOperation && record?.schema === 'player-computer-operation/1'
          && record.status === 'completed' && name === `computer_${record.kind}`
          && record.actor_id === options.actorId && record.session === options.session;
        if (createsOperation) streamRecoveryAvailable &&= completedOperation;
        // The rest of this turn was chosen before this delivery was known; only collection and reads follow it.
        if (name === 'computer_input' && uncertainDelivery(result, record)) uncertainTurn = dispatchingTurn;
        // One model-facing content array: its identity pins the result's source for projection and cuts.
        const content = toLlmContent(result);
        const sourceId = resultSourceId(result);
        if (sourceId !== null) {
          sourcesByContent.set(content, sourceId);
          earnedRefs.add(sourceId);
        }
        emit('tool-result', {request_id:requestId, tool_call_id:toolCallId, tool:name, result:projectToolResultForTelemetry(result)});
        try {
          const transition = inspectHandoff(name, args, result, pendingHandoff, options.session, options.actorId);
          if (transition.pending) pendingHandoff = transition.pending;
          // A definitive refusal of the pending original leaves nothing to collect.
          if (transition.refused) pendingHandoff = undefined;
          if (transition.completed) handoff = transition.completed;
          if (handoff) emit('handoff', {request_id:requestId, tool_call_id:toolCallId, ...handoff, grants_authority:false});
        } catch {
          // Pi turns thrown tool errors into model-visible results. Latch the
          // host failure too so incoherent completion cannot schedule more work.
          stop('invalid-handoff-receipt');
          throw new HostError(fatal);
        }
        if (result.isError !== true && !['refused', 'rejected'].includes(record?.status))
          recordIntent(toolCallId, args.intent);
        if (result.isError === true) content.unshift({type:'text', text:'MCP isError: true'});
        if (configuration.context_cut !== null && (createsOperation || name === 'player_handoff')) {
          const op = identity(record?.operation_id) && record.actor_id === options.actorId
            && record.session === options.session ? record.operation_id : UNCOVERED_OPERATION;
          toolOperations.set(toolCallId, op);
        }
        return {content, details:undefined, isError:result.isError === true};
      }};
    });
    tools.push({name:'player_agenda', label:'player_agenda',
      description:'Read or maintain your working threads across cuts, handoffs, and resumes. Use read, upsert (id, title, status on creation), set_status (id, status), or clear_completed. Cite earned evidence IDs in refs. Only you interpret stop_when.',
      parameters:Type.Unsafe(agendaToolParameters),
      async execute(toolCallId, args) {
        let result;
        try {
          requireThat(args.intent?.trim(), 'invalid-agenda-intent');
          result = applyAgendaTool(agenda, args, earnedRefs);
          requireThat(recordIntent(toolCallId, args.intent), 'invalid-agenda-intent');
        } catch (error) {
          return {content:[{type:'text', text:JSON.stringify({error:error.message})}], isError:true};
        }
        if (result.changed) {
          agenda = result.agenda;
          emit('player-agenda', {request_id:requestId, tool_call_id:toolCallId, op:args.op, cut_count:agenda.cut_count,
            thread_count:agenda.threads.length, active_count:agenda.threads.filter(thread =>
              thread.status === 'active' || thread.status === 'paused').length, agenda});
        }
        return {content:[{type:'text', text:JSON.stringify(result.summary)}]};
      }});
    tools.push({name:'player_finish', label:'player_finish', description:'Direct player claim that this task is complete or cannot continue, or that accepted automation stop is complete. This stops automation; it certifies neither game persistence nor native exit.',
      parameters:Type.Unsafe({type:'object', additionalProperties:false, required:['intent', 'disposition', 'report', 'source_ids', 'control_id'], properties:{
        intent:{type:'string', minLength:1, maxLength:512, pattern:'^[^\\r\\n\\v\\f\\u0085\\u2028\\u2029]+$'},
        cites:{type:'array', maxItems:16, uniqueItems:true, items:{type:'string', minLength:1, maxLength:128}},
        disposition:{enum:['task_complete', 'cannot_continue', 'external_stop_complete']}, report:{type:'string', maxLength:8192},
        source_ids:{type:'array', maxItems:16, uniqueItems:true, items:{type:'string', minLength:1, maxLength:128}},
        control_id:{anyOf:[{type:'null'}, {type:'string', pattern:'^[a-f0-9]{32}$'}]}}}),
      async execute(toolCallId, args) {
        requireThat(!fatal && !handoff && !finish, 'host-already-stopped');
        // An unresolved handoff may still seal; collect it with computer_result before finishing.
        requireThat(!pendingHandoff, 'handoff-pending');
        requireThat(args.intent.trim().length > 0 && args.intent.isWellFormed()
          && (args.cites ?? []).every(id => id.isWellFormed()), 'invalid-finish');
        requireThat(args.report.isWellFormed() && args.source_ids.every(id => id.isWellFormed()), 'invalid-finish');
        requireThat(args.disposition === 'external_stop_complete'
          ? control !== undefined && args.control_id === control.id
          : args.control_id === null, 'invalid-finish-control');
        finish = structuredClone(args);
        emit('player-finish', {request_id:requestId, tool_call_id:toolCallId, ...finish, player_claim:true, game_persistence:'unverified', native_exit:'unverified'});
        return {content:[{type:'text', text:'Player finish claim accepted; automation is ending.'}], details:undefined, terminate:true};
      }});
    const model = configuration.model;
    const project = messages => projectImageContext(messages, configuration.max_context_images,
      configuration.context_image_block, sourceOf);
    const fits = tokens => tokens + model.maxTokens < model.contextWindow;
    const baseContext = (validated, state, notices) => {
      if (!state) return withPlacedNotices(validated, notices);
      const {cutMessageIndex, firstFreshMessageIndex, promptMessage, markerMessage} = state;
      const suffix = validated.slice(cutMessageIndex).map((message, offset) =>
        message.role === 'assistant' && cutMessageIndex + offset < firstFreshMessageIndex
          ? {...message, usage:noUsage} : message);
      // Pi keeps both the frozen system prompt and the tool table in this first message.
      const surviving = notices.filter(({at}) => at >= cutMessageIndex)
        .map(notice => ({...notice, at:notice.at - cutMessageIndex}));
      return [validated[0], promptMessage, markerMessage, ...withPlacedNotices(suffix, surviving)];
    };
    const halvingStep = (remaining, threshold) => {
      if (threshold <= 0 || remaining > threshold) return 0;
      return 1 + Number(remaining * 2 <= threshold) + Number(remaining * 4 <= threshold)
        + Number(remaining * 8 <= threshold);
    };
    const tailNotice = (tokens, steps, at, workLeftMs) => {
      const lines = [], kinds = [];
      const room = Math.max(0, model.contextWindow - model.maxTokens - tokens);
      const [workUnits, spentUnits, remainingScale] = alignedUnits(workBudget, spent);
      const workLeft = largerAmount([0n, 0], [workUnits - spentUnits, remainingScale]);
      const [left, threshold] = alignedUnits(workLeft, spendWarningThreshold);
      const hasHandoff = mcp.enabled_tools.includes('player_handoff');
      const spendWarning = left <= threshold;
      const wrapUp = control
        ? 'Finish up and use player_finish under the accepted automation control.'
        : !spendWarning && hasHandoff
          ? 'Request the existing player_handoff with the context you need to retain (if it reports that no successor is available, use player_finish), or use player_finish if you cannot continue.'
          : 'Use player_finish, reporting where play stands.';
      const add = (kind, step, wording) => {
        if (step <= (steps[kind] ?? 0)) return;
        lines.push(wording(!steps[kind]));
        kinds.push(kind);
        steps[kind] = step;
      };
      add('context-capacity', halvingStep(room, configuration.context_reserve_tokens - model.maxTokens), first => {
        if (!first) return `Host context capacity: about ${room} tokens of room remain before the host must stop.`;
        const advice = control || spendWarning || hasHandoff
          ? `Host context capacity is approaching. ${wrapUp}`
          : 'Host context capacity is approaching and no successor actor is available. Use player_finish before context runs out, reporting where play stands.';
        const support = configuration.context_cut !== null
          ? 'No text summarization or history restoration is available.' : 'No compaction or history restoration is available.';
        return `${advice} ${support} About ${room} tokens of room remain before the host must stop.`;
      });
      add('host-timeout', workLeftMs > 0 ? halvingStep(workLeftMs, wallWarningMs(totalMs - cleanupBudget)) : 0, first => {
        const left = workLeftMs >= 120_000 ? `${Math.ceil(workLeftMs / 60_000)} minutes` : `${Math.ceil(workLeftMs / 1000)} seconds`;
        const remaining = `Host time allowance: about ${left} remain before the host stops.`;
        return first ? `${remaining} ${wrapUp}` : remaining;
      });
      // Compare the spend steps as exact decimal amounts even on the boundary.
      if (threshold > 0n && left <= threshold) {
        const step = 1 + Number(left * 2n <= threshold) + Number(left * 4n <= threshold) + Number(left * 8n <= threshold);
        add('spend-limit', step, first => {
          const remaining = `Host spend allowance: about $${amountText(workLeft)} of work budget remains before the ending reserve.`;
          const handoffAdvice = !control && hasHandoff ? ' Avoid starting a fresh actor with player_handoff.' : '';
          return first ? `${remaining} Wrap up with player_finish, reporting where play stands.${handoffAdvice}` : remaining;
        });
      }
      return lines.length ? {at, message:userMessage(lines.join('\n')), kinds, tokens} : null;
    };
    const planRequest = (validated, target, state, fresh, workLeftMs) => {
      const at = validated.length;
      const notices = state === cutState ? [...placedNotices] : placedNotices.flatMap(notice => {
        if (notice.update) {
          if (state.replacedUpdates.has(notice.update)) return [];
          return [{...notice, at:Math.max(notice.at, state.cutMessageIndex)}];
        }
        if (notice.at < state.cutMessageIndex) return [];
        const contextLine = notice.kinds?.indexOf('context-capacity') ?? -1;
        if (contextLine < 0) return [notice];
        if (notice.kinds.length === 1) return [];
        const kinds = notice.kinds.filter(kind => kind !== 'context-capacity');
        const lines = notice.message.content[0].text.split('\n').filter((_, index) => index !== contextLine);
        return [{...notice, kinds, message:userMessage(lines.join('\n'))}];
      });
      const deliveries = fresh ? [{value:fresh, target}] : briefing ? [{value:briefing, target:knowledge}] : [];
      let suppressed;
      if (!fresh && target !== knowledge) {
        const pending = new Set(unsentDeliveries.map(({value}) => value));
        for (let i = notices.length - 1; i >= 0; i--) {
          if (pending.has(notices[i].update)) notices.splice(i, 1);
        }
        const update = updateDelivery(lastAnnouncedKnowledge, target, {agendaRefs:agendaRefSet(agenda)});
        if (update) {
          notices.push({at, message:userMessage(update.text), update});
          deliveries.push({value:update, target});
        } else suppressed = {kind:'update', outcome:'empty-suppressed', version:target.version,
          previous_version:lastAnnouncedKnowledge.version, coverage:target.coverage};
      }
      if (control && controlAt === undefined) notices.push({at, message:controlMessage});
      const raw = baseContext(validated, state, notices);
      const projection = project(raw);
      const priorSteps = {...noticeSteps};
      if (fresh) delete priorSteps['context-capacity'];
      const steps = {...priorSteps};
      const tail = tailNotice(contextTokens(projection.messages).tokens, steps, at, workLeftMs);
      if (tail) {
        notices.push(tail);
        projection.messages.push(tail.message);
      }
      const estimate = contextTokens(projection.messages);
      return {projection, estimate, notices, steps, priorSteps, tail, deliveries, suppressed, state,
        controlId:control && raw.includes(controlMessage) ? control.id : undefined,
        fits:fits(estimate.tokens), briefingTokens:fresh ? state.briefingTokens : currentBriefingTokens};
    };
    const planVersion = (validated, target, workLeftMs) => {
      const original = planRequest(validated, target, cutState, null, workLeftMs);
      const cfg = configuration.context_cut;
      if (cfg === null || cutRestored || control) return {plan:original, demand:[]};
      const before = original.estimate.tokens, images = original.projection.summary.input_images;
      const demand = [...cutDemand];
      const pressure = [before - currentBriefingTokens > cfg.high_mark && 'high_mark',
        original.projection.summary.omitted_images > projectedOmissions && 'image_peak'].filter(Boolean);
      for (const trigger of pressure) if (!demand.includes(trigger)) demand.push(trigger);
      if (!demand.length && original.fits) return {plan:original, demand};
      let coveredVersion = -1, effectiveCoveredOp = null;
      for (const [version, operation] of coveredByVersion) {
        if (version > coveredVersion && version <= (versionNumber(target.version) ?? -1)) {
          coveredVersion = version;
          effectiveCoveredOp = operation;
        }
      }
      const turns = contextTurns(validated, operationsByResult);
      const boundary = effectiveCoveredOp === null ? -1 : turns.findIndex(turn => turn.creatingOps.includes(effectiveCoveredOp));
      const maxCovered = turns[boundary]?.creatingOps.at(-1) === effectiveCoveredOp ? boundary : boundary - 1;
      const start = cutState?.cutMessageIndex ?? 2;
      const cuttable = turns.slice(0, Math.max(0, Math.min(maxCovered, turns.length - 2) + 1))
        .filter(turn => turn.start >= start);
      const eligible = cuttable.length;
      const searchKey = JSON.stringify([target.version, coveredVersion, effectiveCoveredOp, cuttable.at(-1)?.end ?? start,
        agenda]);
      const decision = {triggers:demand, covered_through_operation_id:effectiveCoveredOp,
        knowledge_version:target.version, tokens_before:before, images_before:images};
      const normalSearch = demand.length && eligible >= cfg.min_free && heldCut?.searchKey !== searchKey;
      const rescue = !original.fits && eligible > 0;
      if (normalSearch || rescue) {
        let nextAgenda;
        try { nextAgenda = advanceAgendaCut(agenda); }
        catch {
          // The next count can add a byte to an exactly full continuation.
          const reason = 'insufficient-cover';
          const edge = JSON.stringify([reason, effectiveCoveredOp]);
          return {plan:original, demand, held:{edge, searchKey}, event:edge === heldCut?.edge ? null :
            {...decision, outcome:'held-back', reason, available_turns:eligible, min_free:cfg.min_free}};
        }
        // Leave room for the briefing envelope before assigning the remainder to substantive changes.
        const changesSince = substantiveDelta(boundaryKnowledge, target, {
          agendaRefs:agendaRefSet(nextAgenda), maxChars:CUT_BRIEFING_CHARS - 2_000,
        });
        const reservedChars = changesSince.empty ? 0 : JSON.stringify({changes_since:changesSince}).length;
        const fresh = cutBriefing(target, {queryText:[options.prompt, ...recentCalls].join(' '), agenda:nextAgenda, reservedChars});
        const briefingTokens = estimateMessageTokens(userMessage(fresh.text));
        const replacedUpdates = new Set(placedNotices.flatMap(({update}) =>
          update && representsUpdate(update.delta, changesSince, fresh.text) ? [update] : []));
        const promptMessage = userMessage(options.prompt + '\n\n' + fresh.text);
        const sourceIds = new Set(cutState?.sourceIds);
        const recentIntents = new Set(cutState?.recentIntents);
        const alreadyRemoved = cutState?.removedTurns ?? 0;
        const imageTarget = configuration.max_context_images - configuration.context_image_block;
        let result, fallback, rescuePlan, cutMessageIndex = start;
        for (const [offset, turn] of cuttable.entries()) {
          const k = offset + 1;
          for (const message of validated.slice(cutMessageIndex, turn.end)) {
            const sourceId = sourceOf(message);
            if (sourceId !== null) sourceIds.add(sourceId);
            const intent = intentByResult.get(message);
            if (intent !== undefined) {
              recentIntents.delete(intent);
              recentIntents.add(intent);
              if (recentIntents.size > 5) recentIntents.delete(recentIntents.values().next().value);
            }
          }
          cutMessageIndex = turn.end;
          if ((!normalSearch || k < cfg.min_free) && (!rescue || rescuePlan)) continue;
          const removedTurns = alreadyRemoved + k;
          const markerMessage = userMessage(cutMarker({removedTurns, coveredThroughOperationId:effectiveCoveredOp,
            knowledgeVersion:target.version, sourceIds:[...sourceIds], recentIntents:[...recentIntents],
            changesSince, agenda:agendaForPrompt(nextAgenda)}));
          const state = {cutMessageIndex, firstFreshMessageIndex:validated.length, promptMessage, markerMessage,
            nextAgenda, replacedUpdates, briefingTokens, removedTurns, sourceIds:[...sourceIds], recentIntents:[...recentIntents]};
          const plan = planRequest(validated, target, state, fresh, workLeftMs);
          const reduces = plan.estimate.tokens < before;
          if (normalSearch && k >= cfg.min_free) {
            const meetsTargets = plan.estimate.tokens - briefingTokens <= cfg.low_mark
              && plan.projection.summary.input_images <= imageTarget;
            if (meetsTargets && plan.fits) result ??= plan;
            if (k === cuttable.length && !result && plan.fits && reduces) fallback = plan;
          }
          if (rescue && plan.fits && reduces) rescuePlan ??= plan;
          if (!normalSearch && rescuePlan) break;
        }
        const plan = result ?? fallback ?? rescuePlan;
        const cutResult = result ? 'target' : fallback ? 'best_effort' : 'rescue';
        if (plan) return {plan, demand:[], event:{...decision, outcome:'cut', cut_result:cutResult,
          uncovered_turns:0, removed_turns:plan.state.removedTurns - alreadyRemoved, cumulative_removed_turns:plan.state.removedTurns,
          tokens_after:plan.estimate.tokens, briefing_tokens:briefingTokens,
          images_after:plan.projection.summary.input_images, source_ids_count:plan.state.sourceIds.length}};
      }
      if (!demand.length) return {plan:original, demand};
      const reason = eligible === 0 ? 'uncovered' : eligible < cfg.min_free ? 'below-min-free' : 'insufficient-cover';
      const edge = JSON.stringify([reason, effectiveCoveredOp]);
      return {plan:original, demand, held:{edge, searchKey}, event:edge === heldCut?.edge ? null :
        {...decision, outcome:'held-back', reason, available_turns:eligible, min_free:cfg.min_free}};
    };
    let canonicalLength;
    const prepareRequest = messages => {
      // Steering wakes Pi if the accepted command arrived during inference. The host places the
      // canonical control message itself, including when it supersedes a body still in backoff.
      const validated = messages.filter(message => message !== controlMessage);
      canonicalLength = validated.length;
      for (const entry of pendingCoverageUpdates.splice(0)) {
        if (entry.restored) { cutRestored = true; cutDemand = []; heldCut = undefined; }
        else if (entry.actor_id === options.actorId) coveredByVersion.set(versionNumber(entry.version), entry.operation_id);
      }
      const startedProjection = performance.now();
      const workLeftMs = totalMs - cleanupBudget - (startedProjection - started);
      const candidates = [...pendingKnowledgeUpdates.values()].sort((a, b) => b.entry.number - a.entry.number);
      pendingKnowledgeUpdates.clear();
      const previousVersion = knowledge.version;
      let choice, target = knowledge;
      for (const candidate of candidates) {
        const {entry} = candidate;
        if (choice) { refuseUpdate(entry, 'superseded', {previous_version:previousVersion}); continue; }
        if (entry.number <= heldNumber()) { refuseUpdate(entry, 'not-newer'); continue; }
        if (knowledge.repository_id !== null && candidate.knowledge.repository_id !== knowledge.repository_id) {
          refuseUpdate(entry, 'repository-mismatch'); continue;
        }
        let trial;
        try { trial = planVersion(validated, candidate.knowledge, workLeftMs); }
        catch (error) {
          refuseUpdate(entry, 'update-check-failed', {error_name:error?.name ?? null});
          continue;
        }
        if (trial.plan.fits && !trial.plan.projection.summary.blocked
            && trial.plan.estimate.tokens + configuration.context_reserve_tokens < model.contextWindow) {
          choice = trial;
          target = candidate.knowledge;
        } else refuseUpdate(entry, 'context-capacity');
      }
      choice ??= planVersion(validated, knowledge, workLeftMs);
      const {plan} = choice;
      if (target !== knowledge) earnKnowledgeRefs(target);
      knowledge = target;
      if (plan.state !== cutState) {
        agenda = plan.state.nextAgenda;
        boundaryKnowledge = lastAnnouncedKnowledge = target;
      }
      cutState = plan.state;
      cutDemand = choice.demand;
      heldCut = choice.held;
      currentBriefingTokens = plan.briefingTokens;
      placedNotices = plan.notices;
      pendingTailNotice = plan.tail && {...plan.tail, steps:plan.steps};
      noticeSteps = plan.priorSteps;
      if (control) controlAt ??= canonicalLength;
      requestControlId = plan.controlId;
      unsentDeliveries = unsentDeliveries.filter(({value}) =>
        value.kind !== 'update' || plan.notices.some(notice => notice.update === value));
      unsentDeliveries.push(...plan.deliveries);
      briefing = null;
      flushRefusals();
      const nextId = `request-${requests + 1}`;
      if (plan.suppressed) emit('knowledge-delivery', plan.suppressed);
      if (choice.event) emit('context-cut', {request_id:nextId, ...choice.event});
      const {projection, estimate} = plan;
      contextImages = projection.images;
      projectedOmissions = projection.summary.omitted_images;
      emit('context-image-projection', {request_id:nextId, projection_ms:performance.now() - startedProjection, ...projection.summary});
      if (projection.summary.blocked) stop('context-image-limit');
      const {tokens, usageTokens, heuristicTokens} = estimate;
      requireThat(Number.isSafeInteger(tokens) && tokens >= 0, 'context-estimate-failed');
      emit('context-estimate', {request_id:nextId, tokens, usage_tokens:usageTokens,
        heuristic_tokens:heuristicTokens, heuristic:true, exact:false});
      if (!plan.fits) stop('context-capacity');
      return projection.messages;
    };
    agent = new Agent({
      initialState:{systemPrompt:options.context + (client.instructions ? '\n\nMCP server instructions:\n' + client.instructions : ''), model, thinkingLevel:options.effort, tools},
      toolExecution:'sequential',
      sessionId:affinityId,
      transformContext:async messages => {
        if (fatal) return messages;
        // Pi requires this hook never to throw/reject. Latch a stop before any fetch.
        try { return prepareRequest(messages); }
        catch { stop('context-projection-failed'); return messages; }
      },
      beforeToolCall:({toolCall, args, assistantMessage}) => {
        if (fatal) return {block:true, reason:fatal, terminate:true};
        if (handoff || finish) {
          emit('tool-refused', {request_id:requestId, tool_call_id:toolCall.id, tool:toolCall.name, reason:handoff ? 'handoff' : 'player-finish', dispatched:false});
          return {block:true, reason:'Host ended after completed handoff; no further tool dispatch.', terminate:true};
        }
        if (control && (assistantControls.get(assistantMessage) !== control.id || toolCall.name === 'player_handoff')) {
          emit('tool-refused', {request_id:requestId, tool_call_id:toolCall.id, tool:toolCall.name, reason:'orderly-stop', dispatched:false, delivery:'undelivered'});
          return {block:true, reason:'Undelivered: automation stop supersedes this unsent call. Follow the labelled control message; no new handoff is admitted.'};
        }
        if (uncertainTurn === assistantMessage && !AFTER_UNCERTAIN_INPUT.has(toolCall.name)) {
          emit('tool-refused', {request_id:requestId, tool_call_id:toolCall.id, tool:toolCall.name, reason:'uncertain-input', dispatched:false});
          return {block:true, reason:'Not sent: an earlier computer_input in this turn has a partial or unknown delivery. Collect it with computer_result and decide again; input is never replayed.'};
        }
        if (!isDeepStrictEqual(toolCall.arguments, args)) {
          emit('tool-refused', {request_id:requestId, tool_call_id:toolCall.id, tool:toolCall.name, reason:'tool-arguments-changed', dispatched:false});
          return {block:true, reason:'MCP input not sent: SDK changed arguments; explicitly correct the call.'};
        }
        dispatchingTurn = assistantMessage;
      },
      // Pi's per-result terminate hint requires every result in the batch to
      // terminate. finishTurn also handles ordinary tools preceding a handoff.
      finishTurn:() => fatal || handoff || finish ? {action:'end'} : {action:'continue'},
      streamFn:async (model, context, streamOptions) => {
        if (fatal) return failureStream(model, fatal);
        const apiKey = (options.env ?? process.env)[configuration.api_key_env];
        if (!text(apiKey)) { stop('missing-api-key'); return failureStream(model, fatal); }
        try {
          const timeoutMs = configuration.request_timeout_seconds * 1000;
          const profile = providerProfile(model);
          let requestSignal, recoverableResponse = false, stalled = false, originalDigest;
          const backendModels = new Set(), observedServiceTiers = new Set();
          let logicalRequestId = `request-${requests + 1}`;
          let streamStarted, payloadReadyAt;
          const actualFetch = options.fetch ?? globalThis.fetch;
          let attempts = 0, previousRequestId, retryQueued = false, superseded = false;
          const addAcceptedControl = () => {
            const placements = [...logicalDeliveries];
            settleDeliveries('undelivered', requestId);
            unsentDeliveries.unshift(...placements);
            requestControlId = control.id;
            controlAt ??= canonicalLength;
            const messages = pendingTailNotice ? context.messages.slice(0, -1) : [...context.messages];
            if (pendingTailNotice) placedNotices.pop();
            placedNotices.push({at:controlAt, message:controlMessage});
            messages.push(controlMessage);
            const steps = {...noticeSteps};
            const tail = tailNotice(contextTokens(messages).tokens, steps, controlAt, totalMs - cleanupBudget - (performance.now() - started));
            if (tail) {
              placedNotices.push(tail);
              messages.push(tail.message);
            }
            pendingTailNotice = tail && {...tail, steps};
            context = {...context, messages};
            requireThat(fits(contextTokens(messages).tokens), 'context-capacity');
            logicalRequestId = `request-${requests + 1}`;
            attempts = 0;
            previousRequestId = undefined;
            originalDigest = undefined;
            retryQueued = recoverableResponse = stalled = superseded = false;
          };
          const admit = async () => {
            do {
              if (await admitPlayer(requestControlId) || (control && requestControlId !== control.id)) return false;
              if (fatal) throw new HostError(fatal);
              if (!lessThan(spent, spendLimit)) throw new HostError('spend-limit');
            } while (!requestControlId && !admitsOrdinary());
            return true;
          };
          if (!await admit()) {
            addAcceptedControl();
            await admit();
          }
          // End an eligible first attempt and hand its server delay to the SDK
          // helper. Status is omitted so only the host's declared classes decide.
          const retry = async (attemptId, retryClass, status, headers) => {
            emit('response-complete', {request_id:attemptId, model:model.id, provider:model.provider,
              reported_provider:responseProgress?.reported_provider ?? null, stop_reason:'error', http_status:status,
              usage_available:false, usage:null, cost_source:null, reported_cost_usd:amountText(requestReportedCost),
              ...countAttempt(requestReportedCost), response_progress:progressSnapshot()});
            requestInFlight = false;
            if (!await admit()) {
              superseded = true;
              throw new Error('orderly-stop-superseded');
            }
            retryQueued = true;
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
          // The SDK turns a thrown fetch error into its own generic failure. A host reason is latched first,
          // so the first fail-closed reason is the one the actor settles with. A retry signal is no HostError.
          const latched = attempt => async (url, init) => {
            try { return await attempt(url, init); }
            catch (error) { if (error instanceof HostError) stop(error.reason); throw error; }
          };
          const observedFetch = (url, init) => retryProviderRequest(latched(async () => {
            requestSignal.throwIfAborted();
            if (fatal) throw new HostError(fatal);
            superseded = !await admit();
            if (superseded) throw new Error('orderly-stop-superseded');
            requestSignal.throwIfAborted();
            if (fatal) throw new HostError(fatal);
            retryQueued = false;
            const fetchEntered = performance.now();
            const payload = providerPayload(init, model.provider, affinityId);
            const sizes = {...payloadSize(payload), payload_bytes:Buffer.byteLength(init.body),
              payload_sha256:createHash('sha256').update(init.body).digest('hex')};
            if (stalled) requireThat(sizes.payload_sha256 === originalDigest, 'stream-recovery-context-changed');
            originalDigest ??= sizes.payload_sha256;
            backendModels.clear();
            const inspectionMs = performance.now() - fetchEntered;
            const attemptId = requestId = `request-${++requests}`;
            logicalDeliveries.push(...unsentDeliveries.splice(0));
            if (pendingTailNotice) {
              const {kinds, tokens, steps} = pendingTailNotice;
              noticeSteps = steps;
              emit('tail-notice', {request_id:attemptId, kinds, tokens});
              pendingTailNotice = null;
            }
            const attemptProgress = responseProgress = {request_id:attemptId, body_bytes:0, body_chunks:0,
              provider_events:0, content_bytes:0, reasoning_bytes:0,
              tool_argument_bytes:0, response_id:null, reported_provider:null, ...progressTimes()};
            requestInFlight = true;
            requestUsageAvailable = false;
            requestReportedCost = null;
            attempts++;
            if (previousRequestId) emit('provider-retry', {stage:'started', request_id:attemptId, previous_request_id:previousRequestId});
            emit('request-start', {request_id:attemptId, request_role:'player', logical_request_id:logicalRequestId, model:model.id, provider:model.provider,
              sdk_after_payload_ms:(attempts === 1 || stalled) && payloadReadyAt !== undefined ? fetchEntered - payloadReadyAt : null,
              host_inspection_ms:inspectionMs, ...sizes});
            emit('context-manifest', nextContextManifest(attemptId, payload));
            let response;
            emit('request-fetch-start', {request_id:attemptId});
            try { response = await actualFetch(url, init); }
            catch {
              // A rejected fetch has no response headers. Timeout and abort latch first.
              if (!fatal && !requestSignal.aborted && attempts === 1) return retry(attemptId, 'pre-header-rejection', null, null);
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
              ...(server || [402, 403, 429].includes(response.status) ? retryDiagnostic(response.headers) : {})});
            let first = false;
            const body = response.body?.pipeThrough(new TransformStream({transform(chunk, controller) {
              attemptProgress.body_bytes += chunk.byteLength;
              attemptProgress.body_chunks++;
              markProgress(attemptProgress, 'body_chunk', performance.now() - started);
              if (!first) { first = true; emit('response-first-chunk', {request_id:attemptId}); }
              controller.enqueue(chunk);
            }}));
            response = new Response(body ?? null, {status:response.status, statusText:response.statusText, headers:response.headers});
            if (response.status < 400) {
              if (!response.body || !/event-stream/i.test(response.headers.get('content-type') ?? '')) return response;
              let peeked;
              try { peeked = await peekFirstEvent(response, requestSignal, profile.extractCost); }
              catch (error) { if (!fatal && !requestSignal.aborted) stop('provider-error'); throw new HostError(fatal ?? 'provider-error'); }
              requestReportedCost = peeked.reported;
              if (peeked.failed && attempts === 1 && response.headers.get('x-should-retry') !== 'false' && !fatal && !requestSignal.aborted) {
                // Release the refused stream without waiting on an untrusted source's cancel hook.
                void peeked.cancel();
                emit('provider-refusal', {request_id:attemptId, status:response.status, body_read:true, stream_start_error:true,
                  ...refusalDiagnostic(null, apiKey)});
                return retry(attemptId, 'stream-start-error', response.status, response.headers);
              }
              recoverableResponse = response.status === 200 && !peeked.failed && response.headers.get('x-should-retry') !== 'false';
              return peeked.response;
            }
            let errorBody = null;
            // A declared 5xx stays eligible by status when its refusal body is
            // unreadable; 402 and 429 need their bounded body classifiers.
            try { errorBody = await refusalBody(response, requestSignal); }
            catch (error) { if (!server || fatal || requestSignal.aborted) throw error; }
            let refusal = null;
            if (errorBody) {
              try { refusal = JSON.parse(errorBody); } catch { /* Unrecognized refusal body. */ }
            }
            if (object(refusal?.usage)) requestReportedCost = profile.extractCost(null, refusal);
            const error = refusal?.error;
            const diagnosticError = object(error) ? error : refusal;
            const diagnostic = refusalDiagnostic(diagnosticError, apiKey);
            emit('provider-refusal', {request_id:attemptId, status:response.status, body_read:errorBody !== null, ...diagnostic});
            // One shared retry per logical request, whatever the first class was.
            if (attempts === 1 && response.headers.get('x-should-retry') !== 'false') {
              const retryClass = profile.retryClass(response.status, diagnostic, error, response.headers);
              if (retryClass) return retry(attemptId, retryClass, response.status, response.headers);
            }
            if (errorBody === null) throw new HostError('provider-error');
            return new Response(errorBody, {status:response.status, headers:response.headers});
          }), {maxRetries:stalled ? 0 : 1, maxRetryDelayMs:MAX_RETRY_DELAY_MS, signal:requestControlId ? requestSignal : AbortSignal.any([requestSignal, controlAccepted.signal])});
          // Transport refusals share one deadline across classification, backoff and retry.
          // The provider stream itself must never retry.
          const providerStream = () => profile.stream(model, context, {...streamOptions, apiKey, fetch:observedFetch, env:{}, signal:requestSignal, maxRetries:0, cacheRetention:'short', maxTokens:model.maxTokens, timeoutMs:configuration.request_timeout_seconds * 1000, reasoningEffort:options.effort === 'off' ? undefined : options.effort,
            onPayload:payload => {
              payloadReadyAt = performance.now();
              emit('provider-payload-ready', {request_id:`request-${requests + 1}`, sdk_prepare_ms:payloadReadyAt - streamStarted});
              return profile.serviceTier(payload, configuration.service_tier);
            },
            onProviderStreamEvent:chunk => {
            responseProgress.provider_events++;
            if (chunk?.error || (Array.isArray(chunk?.choices) && chunk.choices.some(choice => choice?.finish_reason != null))) recoverableResponse = false;
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
            const usage = streamUsage(chunk);
            // Pi initializes absent usage to zero. Only publish normalized totals
            // when the provider actually reported both input and output counts.
            if (Number.isFinite(usage?.prompt_tokens) && Number.isFinite(usage?.completion_tokens)) requestUsageAvailable = true;
            // The SDK discards the provider's cost, so it is read here from the same record.
            requestReportedCost = profile.extractCost(requestReportedCost, chunk);
            if (typeof chunk?.model === 'string' && !backendModels.has(chunk.model)) {
              backendModels.add(chunk.model);
              emit('response-backend', {request_id:requestId, backend_model:chunk.model});
            }
          }});
          // Only a completed turn crosses into Pi's agent context. In particular,
          // syntactically complete tool arguments in a timed-out delta have no authority.
          for (;;) {
            const deadline = new AbortController();
            streamStarted = performance.now();
            requestSignal = AbortSignal.any([streamOptions.signal, stopped.signal, deadline.signal].filter(Boolean));
            requestTimer = setTimeout(() => {
              if (attempts === 1 && recoverableResponse && responseProgress?.last_field_delta_ms != null
                  && streamRecoveryAvailable && !pendingHandoff && !control && !requestSignal.aborted) {
                stalled = true;
                deadline.abort();
              } else stop('request-timeout');
            }, Math.min(timeoutMs, totalMs));
            let terminal;
            for await (const event of providerStream()) {
              if (!terminal && (event.type === 'done' || event.type === 'error')) {
                terminal = event;
                // The attempt has finished, so its deadline no longer applies to it.
                clearTimeout(requestTimer);
              }
            }
            clearTimeout(requestTimer);
            if (!fatal && (superseded || (retryQueued && control && requestControlId !== control.id))) {
              // A rejected attempt is already settled. Its unsent retry is replaced by a fresh logical
              // request, which still carries any knowledge projected at this boundary.
              addAcceptedControl();
              await admit();
              continue;
            }
            if (!terminal) {
              stop('incomplete-provider-stream');
              return failureStream(model, fatal);
            }
            if (deadline.signal.aborted && !fatal) {
              if (!recoverableResponse || terminal.type !== 'error' || terminal.error.stopReason !== 'aborted' || streamOptions.signal?.aborted) {
                stop('request-timeout');
              } else {
                const previous = requestId;
                settlePlayerAttempt(terminal.error);
                if (control && requestControlId !== control.id) {
                  addAcceptedControl();
                  await admit();
                } else if (!await admit()) {
                  addAcceptedControl();
                  await admit();
                } else {
                  streamRecoveryAvailable = false;
                  previousRequestId = previous;
                  emit('provider-retry', {stage:'eligible', request_id:previous, retry_class:'incomplete-stream-timeout', max_retry_delay_ms:0});
                }
                continue;
              }
            }
            if (fatal) {
              if (requestInFlight) settlePlayerAttempt(terminal.type === 'error' ? terminal.error : terminal.message);
              return failureStream(model, fatal);
            }
            const completed = new AssistantMessageEventStream();
            completed.push(terminal);
            completed.end();
            return completed;
          }
        } catch (error) {
          // A host reason raised here (or already latched) is the reason the actor settles with.
          stop(error instanceof HostError ? error.reason : 'provider-error');
          return failureStream(model, fatal);
        }
      },
    });
    agent.subscribe(event => {
      if (event.type === 'message_end' && event.message.role === 'toolResult') {
        const {toolCallId} = event.message;
        const intent = dispatchedIntents.get(toolCallId);
        if (dispatchedIntents.delete(toolCallId)) intentByResult.set(event.message, intent);
        const operation = toolOperations.get(toolCallId);
        // Pin the operation to its canonical result even if a later response reuses the call ID.
        if (toolOperations.delete(toolCallId)) operationsByResult.set(event.message, operation);
      }
      if (event.type === 'message_end' && event.message.role === 'assistant') {
        clearTimeout(requestTimer);
        const message = event.message;
        assistantControls.set(message, requestControlId);
        const narration = assistantNarration(message.content);
        if (narration.text || narration.omitted_bytes) emit('assistant-text', {request_id:requestId, ...narration});
        const failed = ['error', 'aborted', 'length', 'deferred'].includes(message.stopReason);
        if (requestInFlight) {
          const successful = !fatal && !failed;
          const reported = settlePlayerAttempt(message);
          settleDeliveries(successful && reported !== null ? 'delivered' : 'undelivered', requestId);
          // A run never continues on a successful response it cannot price.
          if (successful && reported === null) stop('cost-unreported');
        } else settleDeliveries('undelivered', requestId);
        requestInFlight = false;
        if (failed && !fatal) stop(message.stopReason === 'error' ? 'provider-error' : `provider-${message.stopReason}`);
        // A version listed during this request is read while the response's tools run.
        refreshUpdates();
      }
    });
    if (control) agent.steer(controlMessage);
    briefing = openingBriefing(knowledge, {queryText:options.prompt, agenda});
    currentBriefingTokens = estimateMessageTokens(userMessage(briefing.text));
    await agent.prompt(options.prompt + '\n\n' + briefing.text);
    if (!fatal && !handoff && !finish) stop('incomplete-terminal-response');
  } catch (error) {
    if (!fatal) stop(error instanceof HostError ? error.reason : 'host-failed');
  } finally {
    // An outstanding refresh is terminated rather than awaited: a stalled read must not hold up settlement or CLI exit.
    clearInterval(updatesPoll);
    flushRefusals();
    updatesClosed = true;
    closeUpdateReader();
    if (briefing) emit('knowledge-undelivered', {...briefing, reason:'actor-ended'});
    settleDeliveries('undelivered', requestId);
    for (const {value} of unsentDeliveries) emit('knowledge-undelivered', {...value, reason:'actor-ended'});
    clearTimeout(requestTimer); clearTimeout(workTimer);
    options.signal?.removeEventListener('abort', cancellation);
    await close();
    unlistenControl?.();
    clearTimeout(deadlineTimer);
  }
  const finalText = !fatal && finish ? finish.report : '';
  const controlId = !fatal && finish ? finish.control_id : control?.id ?? null;
  const result = {ok:!fatal, reason:fatal ?? (handoff ? 'handoff' : finish.disposition), requests, finalText, agenda, control_id:controlId};
  emit('settled', {ok:result.ok, reason:result.reason, requests, player_requests:requests, spent_usd:amountText(spent), unpriced_requests:unpricedRequests, control_id:controlId,
    accepted_control_id:control?.id ?? null, event_output:{...outputStats}, native_cleanup_claimed:false});
  return result;
}
