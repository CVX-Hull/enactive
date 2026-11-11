// One curator session on Pi agent-core: a frozen prompt, six workspace tools, the model proxy as the
// only endpoint. See docs/operations/curator-hosts.md. The host never sees the provider key; it
// presents the per-session proxy token as its API key and writes JSON-lines telemetry without it.
import { Agent } from '@earendil-works/pi-agent-core';
import { Type, AssistantMessageEventStream } from '@earendil-works/pi-ai';
import { stream } from '@earendil-works/pi-ai/api/openai-completions';
import { retryProviderRequest } from '@earendil-works/pi-ai/utils/provider-retry';
import { ToolError, listDir, readFile, runWorkbench, viewFrame, writeFile } from './workspace-tools.mjs';

export const SCHEMA = 'curator-host/1';
export const CONFIG_LIMIT_BYTES = 65536;
const MAX_SUMMARY_CHARS = 2000;
const NARRATION_BYTES = 1024;
const RETRY_STATUSES = [502, 503, 504];
const MAX_RETRY_DELAY_MS = 60_000;
const SERVICE_TIER = 'default';
const levels = ['off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'];
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const positive = value => Number.isSafeInteger(value) && value > 0;
const text = value => typeof value === 'string' && value.length > 0;

export class HostError extends Error {
  constructor(reason) { super(reason); this.reason = reason; }
}
function requireThat(condition, reason = 'invalid-configuration') {
  if (!condition) throw new HostError(reason);
}
function closed(value, allowed) {
  requireThat(object(value) && Object.keys(value).every(key => allowed.includes(key)));
}

function retryHeaders(response) {
  if (RETRY_STATUSES.includes(response.status)) return new Headers({ 'retry-after': '1' });
  if (response.status !== 429 || response.headers.get('x-should-retry') === 'false') return null;
  const after = response.headers.get('retry-after')?.trim();
  if (!after) return null; // Local proxy budget refusals have no server retry instruction.
  const seconds = /^\d+(?:\.\d+)?$/.test(after) ? Number(after) : NaN;
  const date = Date.parse(after);
  // Date.parse alone accepts incomplete dates such as "Wed, 1".
  const delay = Number.isFinite(seconds) ? seconds * 1000
    : Number.isFinite(date) && new Date(date).toUTCString() === after ? date - Date.now() : NaN;
  if (!Number.isFinite(delay) || delay > MAX_RETRY_DELAY_MS) return null;
  return new Headers({ 'retry-after': after });
}

/** The frozen configuration: model, effort and limits. It holds no endpoint, key or header. */
export function validateConfiguration(configuration) {
  requireThat(Buffer.byteLength(JSON.stringify(configuration ?? null)) <= CONFIG_LIMIT_BYTES, 'configuration-too-large');
  closed(configuration, ['schema', 'model', 'effort', 'max_requests', 'request_timeout_seconds', 'wall_seconds',
    'max_context_images', 'context_image_block', 'workbench_timeout_seconds', 'budget_usd']);
  requireThat(configuration.schema === SCHEMA);
  requireThat(typeof configuration.budget_usd === 'number' && Number.isFinite(configuration.budget_usd) && configuration.budget_usd > 0);
  for (const key of ['max_requests', 'request_timeout_seconds', 'wall_seconds', 'max_context_images', 'context_image_block', 'workbench_timeout_seconds']) {
    requireThat(positive(configuration[key]));
  }
  requireThat(configuration.context_image_block <= configuration.max_context_images);
  requireThat(configuration.request_timeout_seconds * 1000 <= 2_147_483_647 && configuration.wall_seconds * 1000 <= 2_147_483_647);
  const model = configuration.model;
  closed(model, ['id', 'name', 'reasoning', 'input', 'cost', 'contextWindow', 'maxTokens', 'thinkingLevelMap', 'compat']);
  requireThat(/^[a-z0-9][a-z0-9_.-]{0,63}\/[a-z0-9][a-z0-9_.:-]{0,127}$/.test(model.id ?? '') && text(model.name));
  requireThat(typeof model.reasoning === 'boolean');
  requireThat(Array.isArray(model.input) && model.input.includes('text') && model.input.includes('image')
    && model.input.every(item => ['text', 'image'].includes(item)));
  requireThat(positive(model.contextWindow) && positive(model.maxTokens) && model.maxTokens <= model.contextWindow);
  closed(model.cost, ['input', 'output', 'cacheRead', 'cacheWrite']);
  requireThat(Object.values(model.cost).every(value => typeof value === 'number' && Number.isFinite(value) && value >= 0));
  requireThat(levels.includes(configuration.effort), 'unsupported-effort');
  requireThat(model.reasoning || configuration.effort === 'off', 'unsupported-effort');
  closed(model.thinkingLevelMap ?? {}, levels);
  if (model.reasoning) {
    requireThat(typeof model.thinkingLevelMap?.[configuration.effort] === 'string', 'unsupported-effort');
  }
  closed(model.compat, ['supportsDeveloperRole', 'supportsStore', 'supportsUsageInStreaming', 'supportsReasoningEffort',
    'supportsStrictMode', 'maxTokensField', 'thinkingFormat', 'openRouterRouting']);
  // The proxy forwards `max_completion_tokens` and requires the default tier; `max_tokens` is refused.
  requireThat(model.compat.maxTokensField === 'max_completion_tokens' && model.compat.thinkingFormat === 'openrouter');
  requireThat(model.compat.supportsStore === false && model.compat.supportsUsageInStreaming === true);
  requireThat(model.compat.supportsReasoningEffort === model.reasoning);
  const routing = model.compat.openRouterRouting;
  closed(routing, ['only', 'order', 'allow_fallbacks', 'require_parameters']);
  requireThat(routing.allow_fallbacks === false && routing.require_parameters === true
    && Array.isArray(routing.only) && routing.only.length === 1 && /^[a-z0-9][a-z0-9_./-]{0,127}$/.test(routing.only[0])
    && Array.isArray(routing.order) && routing.order.length === 1 && routing.order[0] === routing.only[0]);
  return configuration;
}

/** The proxy's loopback origin and the session token, from the sandbox-provided environment. */
export function proxyFrom(env) {
  const url = env.CURATOR_PROXY_URL, token = env.CURATOR_PROXY_TOKEN;
  requireThat(/^http:\/\/127\.0\.0\.1:[0-9]{1,5}$/.test(url ?? ''), 'invalid-proxy-url');
  requireThat(/^[A-Za-z0-9_-]{16,256}$/.test(token ?? ''), 'missing-proxy-token');
  return { baseUrl: `${url}/api/v1`, token };
}

/** Block eviction of the oldest images beyond `maxImages`, so the serialized prefix stays stable
 * between evictions and a request stays well under the proxy's body limit. */
export function projectImages(messages, maxImages, block) {
  const images = [];
  for (const [messageIndex, message] of messages.entries()) {
    if (!Array.isArray(message.content)) continue;
    for (const [contentIndex, part] of message.content.entries()) {
      if (part.type === 'image') {
        // view_frame puts "frame <source id> (<n> bytes)" right before each image it returns.
        const label = /^frame (\S+) \(/.exec(message.content[contentIndex - 1]?.text ?? '');
        images.push({ messageIndex, contentIndex, toolCallId: message.toolCallId ?? null, sourceId: label ? label[1] : null });
      }
    }
  }
  const overflow = images.length - maxImages;
  if (overflow <= 0) return { messages, omitted: 0 };
  const omitted = images.slice(0, Math.min(Math.ceil(overflow / block) * block, images.length));
  const projected = structuredClone(messages);
  for (const image of omitted) {
    // The marker depends on the frame alone, so it is byte-identical on every later request.
    projected[image.messageIndex].content[image.contentIndex] = { type: 'text',
      text: image.sourceId
        ? `[Earlier frame image omitted to bound the request (tool call ${image.toolCallId}, frame ${image.sourceId}); call view_frame with frames ["${image.sourceId}"] to see it again.]`
        : `[Earlier frame image omitted to bound the request (tool call ${image.toolCallId}); call view_frame again to see it.]` };
  }
  return { messages: projected, omitted: omitted.length };
}

/* Budget phases, as a share of the session's requests or dollars, whichever is further along. */
export const WRITE_AT = 0.5;
export const FINISH_AT = 0.8;
const READING_TOOLS = new Set(['list_dir', 'read_file', 'view_frame', 'run_workbench']);

/** The history with each placed note re-inserted where it was first sent: after the first `at`
 * messages. `placed` is append-only with non-decreasing `at`, so the result extends the previous
 * request's messages exactly. */
export function withPlacedNotes(messages, placed) {
  const out = [];
  let next = 0;
  for (let i = 0; i <= messages.length; i++) {
    while (next < placed.length && placed[next].at === i) out.push(placed[next++].message);
    if (i < messages.length) out.push(messages[i]);
  }
  return out;
}

/** The note that ends each request: the budget used so far and what to do now. It stays in the history
 * where it was first sent (see `withPlacedNotes`), so later requests extend this one. Requests and dollars set
 * the phase (and so the refusal of reading tools); the wall-clock limit only warns, because the host
 * stops when it passes. */
export function budgetNote({ requests, maxRequests, spent, budget, elapsedSeconds = 0, wallSeconds = Infinity }) {
  const share = Math.max(requests / maxRequests, spent / budget);
  const time = Number.isFinite(wallSeconds) ? elapsedSeconds / wallSeconds : 0;
  const status = `Budget: ${requests} of ${maxRequests} requests used; about $${spent.toFixed(2)} of $${budget.toFixed(2)} spent`
    + (Number.isFinite(wallSeconds) ? `; ${Math.floor(elapsedSeconds)} of ${wallSeconds} s of time used.` : '.');
  const clock = time >= FINISH_AT ? ' The time is nearly up: the host stops the session when it runs out. Write your submission or draft with write_file now, then call finish.'
    : time >= WRITE_AT ? ' More than half the time is used. Start writing what you have found.' : '';
  if (share >= FINISH_AT) return { share, text: `${status} The budget is nearly spent. Reading tools are now refused: write your submission or draft with write_file now, then call finish.${clock}` };
  if (share >= WRITE_AT) return { share, text: `${status} More than half is spent. Start writing what you have found: a submission for facts you can cite, a draft for the rest.${clock}` };
  return { share, text: status + clock };
}

function resultBytes(result) {
  let total = 0;
  for (const part of result.content ?? []) {
    total += part.type === 'text' ? Buffer.byteLength(part.text) : Buffer.from(part.data ?? '', 'base64').length;
  }
  return total;
}

function narration(content) {
  const bytes = Buffer.from((content ?? []).filter(part => part.type === 'text').map(part => part.text).join('\n'));
  let end = Math.min(bytes.length, NARRATION_BYTES);
  while (end < bytes.length && (bytes[end] & 0xc0) === 0x80) end--;
  return { text: bytes.subarray(0, end).toString('utf8'), omitted_bytes: bytes.length - end };
}

// These are diagnostic signatures from the pinned SDK, never authority to retry or accept a result.
// The SDK flattens provider errors into arbitrary text; do not emit that text or guess its typed code.
function requestFailure(message, status, chunks, sawFinish, accountingComplete) {
  const failed = ['error', 'aborted', 'length'].includes(message.stopReason);
  if (!failed && accountingComplete) return undefined;
  const knownFinish = ['stop', 'tool_calls', 'function_call', 'length', 'content_filter', 'error', 'network_error'];
  const finish = knownFinish.includes(message.rawStopReason) ? message.rawStopReason : null;
  let kind = 'sdk-stream-error-unknown';
  if (!failed) kind = 'missing-usage';
  else if (message.stopReason === 'aborted') kind = 'aborted';
  else if (message.stopReason === 'length') kind = 'output-limit';
  else if (status >= 400) kind = 'http-error';
  else if (message.errorMessage === 'Error reading response: malformed server-sent event JSON.') kind = 'malformed-sse-json';
  else if (message.errorMessage === 'Stream ended without finish_reason') kind = 'missing-finish-reason';
  else if (['error', 'content_filter', 'network_error'].includes(finish)) kind = 'provider-finish-error';
  return { kind, phase: status == null ? 'before-headers' : status >= 400 ? 'http-error'
    : sawFinish ? 'after-finish' : chunks ? 'streaming' : 'before-first-chunk',
    chunks, finish_reason: finish, provider_error_type: null };
}

/** Run one session in `options.cwd`. `options.fetch` lets tests stand in for the proxy. */
export async function runCurator(options) {
  const configuration = validateConfiguration(options.configuration);
  const proxy = proxyFrom(options.env ?? process.env);
  const root = options.cwd ?? process.cwd();
  const started = performance.now();
  const emit = (type, fields = {}) => options.onEvent?.({ type, wall_time: new Date().toISOString(),
    monotonic_ms: Math.round(performance.now() * 1000) / 1000, ...fields });
  const model = { ...configuration.model, api: 'openai-completions', provider: 'openrouter', baseUrl: proxy.baseUrl };
  const effort = configuration.effort;
  let agent, fatal, finished, requests = 0, toolCalls = 0, requestId, requestTimer, inFlight = false;
  let rawUsage, httpStatus, providerChunks = 0, sawFinish = false, lastPromptTokens = 0, contextWarning = false, spent = 0;
  // Notes sent so far, each with the number of history messages it followed (append-only).
  const placedNotes = [];
  const budget = () => budgetNote({ requests, maxRequests: configuration.max_requests, spent, budget: configuration.budget_usd,
    elapsedSeconds: (performance.now() - started) / 1000, wallSeconds: configuration.wall_seconds });
  const stopped = new AbortController();
  const stop = reason => {
    if (fatal) return;
    fatal = reason;
    emit('abort', { reason, request_id: requestId ?? null });
    stopped.abort();
    agent?.abort();
  };
  const failureStream = (reasonModel, reason) => {
    inFlight = false;
    const response = new AssistantMessageEventStream();
    const message = { role: 'assistant', content: [], api: reasonModel.api, provider: reasonModel.provider, model: reasonModel.id,
      usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      stopReason: 'aborted', errorMessage: reason, timestamp: Date.now() };
    response.push({ type: 'error', reason: 'aborted', error: message });
    response.end(message);
    return response;
  };

  const python = options.python ?? (options.env ?? process.env).CURATOR_PYTHON;
  const workbenchEnv = { PATH: (options.env ?? process.env).PATH ?? '/usr/bin:/bin', LANG: 'C.UTF-8', PYTHONDONTWRITEBYTECODE: '1',
    HOME: (options.env ?? process.env).HOME ?? root, TMPDIR: (options.env ?? process.env).TMPDIR ?? root,
    ...((options.env ?? process.env).PYTHONPATH ? { PYTHONPATH: (options.env ?? process.env).PYTHONPATH } : {}) };

  const tools = [
    { name: 'list_dir', label: 'list_dir', description: 'List a directory in the workspace (paths are relative to it). Shows each entry\'s kind and size.',
      parameters: Type.Object({ path: Type.Optional(Type.String({ maxLength: 512 })), offset: Type.Optional(Type.Integer({ minimum: 0 })),
        limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 500 })) }),
      run: args => listDir(root, args) },
    { name: 'read_file', label: 'read_file', description: 'Read a text file in the workspace, at most 262144 bytes per call (default 65536). Use offset to continue a truncated read.',
      parameters: Type.Object({ path: Type.String({ maxLength: 512 }), offset: Type.Optional(Type.Integer({ minimum: 0 })),
        max_bytes: Type.Optional(Type.Integer({ minimum: 1, maximum: 262144 })) }),
      run: args => readFile(root, args) },
    { name: 'view_frame', label: 'view_frame', description: 'Show one to four recorded frames as images in one call. Pass their source ids, as cited in steps and tool records. Choose frames first (steps, workbench diff/similar); every image costs budget.',
      parameters: Type.Object({ frames: Type.Array(Type.String({ maxLength: 160 }), { minItems: 1, maxItems: 4 }) }),
      run: async args => {
        if (!Array.isArray(args.frames) || args.frames.length < 1 || args.frames.length > 4) throw new ToolError('frames must list one to four source ids');
        const content = [];
        for (const frame of args.frames) content.push(...(await viewFrame(root, { frame })).content);
        return { content, details: undefined, isError: false };
      } },
    { name: 'write_file', label: 'write_file', description: 'Write a text file, replacing it, under submissions/, drafts/ or scratch/ only. Parent directories are created.',
      parameters: Type.Object({ path: Type.String({ maxLength: 512 }), content: Type.String({ maxLength: 524288 }) }),
      run: args => writeFile(root, args) },
    { name: 'run_workbench', label: 'run_workbench', description: 'Run `python -m harness.trace.workbench` from workbench/ with these arguments (a list of strings, for example ["steps", "../trace", "--from", "1", "--to", "20"]). Run it with ["--help"] for the commands.',
      parameters: Type.Object({ args: Type.Array(Type.String({ maxLength: 1000 }), { minItems: 1, maxItems: 40 }) }),
      run: args => runWorkbench(root, args, { python, env: workbenchEnv, timeoutSeconds: configuration.workbench_timeout_seconds }) },
    { name: 'finish', label: 'finish', description: 'End the session. Everything not already written to submissions/ or drafts/ is discarded.',
      parameters: Type.Object({ summary: Type.String({ maxLength: MAX_SUMMARY_CHARS }) }),
      run: async args => {
        finished = { summary: args.summary };
        return { content: [{ type: 'text', text: 'Session ending.' }], details: undefined, isError: false, terminate: true };
      } },
  ].map(tool => ({
    name: tool.name, label: tool.label, description: tool.description, parameters: tool.parameters,
    async execute(toolCallId, args) {
      if (fatal) throw new HostError(fatal);
      const before = performance.now();
      let result;
      try {
        if (READING_TOOLS.has(tool.name) && budget().share >= FINISH_AT) {
          throw new ToolError('the budget is nearly spent; write your submission or draft with write_file, then call finish');
        }
        result = await tool.run(args);
      }
      catch (error) {
        if (!(error instanceof ToolError)) {
          result = { content: [{ type: 'text', text: 'the tool failed' }], details: undefined, isError: true };
        } else result = { content: [{ type: 'text', text: `refused: ${error.message}` }], details: undefined, isError: true };
        result.failure = error instanceof ToolError ? error.message.slice(0, 200) : error.name;
      }
      toolCalls++;
      emit('tool-call', { request_id: requestId ?? null, tool_call_id: toolCallId, name: tool.name, ok: result.isError !== true,
        duration_ms: Math.round((performance.now() - before) * 1000) / 1000, bytes: resultBytes(result),
        ...(result.failure ? { error: result.failure } : {}) });
      delete result.failure;
      return result;
    },
  }));

  try {
    requireThat(text(options.systemPrompt) && text(options.brief), 'invalid-input');
    emit('host-start', { schema: SCHEMA, model: model.id, effort, requested_service_tier: SERVICE_TIER, max_requests: configuration.max_requests,
      max_output_tokens: model.maxTokens, context_window: model.contextWindow, request_timeout_seconds: configuration.request_timeout_seconds,
      wall_seconds: configuration.wall_seconds, max_context_images: configuration.max_context_images,
      provider_routing: structuredClone(model.compat.openRouterRouting), tools: tools.map(tool => tool.name) });
    const wallTimer = setTimeout(() => stop('host-timeout'), configuration.wall_seconds * 1000);
    options.signal?.addEventListener('abort', () => stop('cancelled'), { once: true });
    if (options.signal?.aborted) stop('cancelled');
    try {
      agent = new Agent({
        initialState: { systemPrompt: options.systemPrompt, model, thinkingLevel: effort, tools },
        toolExecution: 'sequential',
        transformContext: async messages => {
          if (fatal) return messages;
          try {
            if (lastPromptTokens + model.maxTokens >= model.contextWindow) { stop('context-capacity'); return messages; }
            const projection = projectImages(messages, configuration.max_context_images, configuration.context_image_block);
            // Each request's note stays in the history where it was first sent and is never rewritten, so
            // every request extends the previous one byte for byte (#489: the provider's cache reuses only
            // a request that a later one extends; a tail rewritten each request is never reused). A retry
            // resends the same body below this hook (the fetch wrapper), so it adds no note.
            const notes = [budget().text];
            // Once past the threshold the warning is in every new note (latched), so the host's capacity
            // stop never comes without notice.
            if (lastPromptTokens + model.maxTokens >= model.contextWindow * 0.75) contextWarning = true;
            if (contextWarning) {
              const room = Math.max(0, model.contextWindow - model.maxTokens - lastPromptTokens);
              notes.push(`The context window is nearly full: about ${room} tokens of room remain before the host stops the session. Write any submission or draft now and call finish.`);
            }
            placedNotes.push({ at: messages.length, message: { role: 'user', timestamp: Date.now(), content: [{ type: 'text', text: notes.join(' ') }] } });
            return withPlacedNotes(projection.messages, placedNotes);
          } catch { stop('context-projection-failed'); return messages; }
        },
        finishTurn: () => (fatal || finished ? { action: 'end' } : undefined),
        streamFn: (streamModel, context, streamOptions) => {
          if (fatal) return failureStream(streamModel, fatal);
          if (requests >= configuration.max_requests) { stop('request-limit'); return failureStream(streamModel, fatal); }
          try {
            rawUsage = undefined; httpStatus = undefined; providerChunks = 0; sawFinish = false;
            clearTimeout(requestTimer);
            requestTimer = setTimeout(() => stop('request-timeout'), configuration.request_timeout_seconds * 1000);
            const signal = AbortSignal.any([streamOptions?.signal, stopped.signal].filter(Boolean));
            const actualFetch = options.fetch ?? globalThis.fetch;
            const observedFetch = (url, init) => {
              let attempt = 0;
              const retry = (id, headers) => {
                if (requests >= configuration.max_requests) { stop('request-limit'); throw new HostError(fatal); }
                emit('request-end', { request_id: id, status: httpStatus ?? null, stop_reason: 'error', retry: true,
                  failure: requestFailure({ stopReason: 'error' }, httpStatus, providerChunks, sawFinish, false) });
                // Only host-selected classes reach the SDK's abortable wait.
                const error = new Error('retryable-provider');
                error.status = undefined;
                error.headers = headers;
                throw error;
              };
              return retryProviderRequest(async () => {
                signal.throwIfAborted();
                if (requests >= configuration.max_requests) { stop('request-limit'); throw new HostError(fatal); }
                attempt++;
                const payload = JSON.parse(init.body);
                const id = requestId = `request-${++requests}`;
                inFlight = true;
                httpStatus = undefined;
                emit('request-start', { request_id: id, attempt, payload_bytes: Buffer.byteLength(init.body),
                  message_count: payload.messages?.length ?? 0, image_parts: init.body.split('"type":"image_url"').length - 1 });
                let response;
                try { response = await actualFetch(url, init); }
                catch (error) {
                  httpStatus = null;
                  if (attempt === 1 && !signal.aborted && !fatal) {
                    retry(id, new Headers({ 'retry-after': '1' }));
                  }
                  throw error;
                }
                httpStatus = response.status;
                if (response.status >= 400) {
                  const headers = retryHeaders(response);
                  if (attempt === 1 && headers && !signal.aborted && !fatal) {
                    void response.body?.cancel().catch(() => {});
                    retry(id, headers);
                  }
                }
                return response;
              }, { maxRetries: 1, maxRetryDelayMs: MAX_RETRY_DELAY_MS, signal });
            };
            return stream(streamModel, context, { ...streamOptions, apiKey: proxy.token, fetch: observedFetch, env: {}, signal,
              maxRetries: 0, cacheRetention: 'short', maxTokens: model.maxTokens, timeoutMs: configuration.request_timeout_seconds * 1000,
              reasoningEffort: effort === 'off' ? undefined : effort,
              // Omission can inherit a workspace tier. Use the pinned SDK's payload hook,
              // as the player host does, so the proxy sees an explicit standard-tier request.
              onPayload: payload => ({ ...payload, service_tier: SERVICE_TIER }),
              onProviderStreamEvent: chunk => {
                providerChunks++;
                if (chunk?.choices?.[0]?.finish_reason) sawFinish = true;
                const usage = chunk?.usage ?? chunk?.choices?.[0]?.usage;
                if (object(usage)) rawUsage = usage;
              } });
          } catch {
            stop('provider-error');
            return failureStream(streamModel, fatal);
          }
        },
      });
      agent.subscribe(event => {
        if (event.type !== 'message_end' || event.message.role !== 'assistant') return;
        clearTimeout(requestTimer);
        const message = event.message;
        const text_ = narration(message.content);
        if (text_.text || text_.omitted_bytes) emit('assistant-text', { request_id: requestId ?? null, ...text_ });
        if (inFlight) {
          const usage = rawUsage ?? {};
          const number = value => (typeof value === 'number' && Number.isFinite(value) ? value : null);
          const failure = requestFailure(message, httpStatus, providerChunks, sawFinish,
            number(usage.prompt_tokens) !== null && number(usage.completion_tokens) !== null && number(usage.cost) !== null);
          lastPromptTokens = number(usage.prompt_tokens) ?? lastPromptTokens;
          spent += number(usage.cost) ?? 0;
          emit('request-end', { request_id: requestId, status: httpStatus ?? null, stop_reason: message.stopReason,
            usage_reported: number(usage.prompt_tokens) !== null && number(usage.completion_tokens) !== null,
            prompt_tokens: number(usage.prompt_tokens), completion_tokens: number(usage.completion_tokens),
            cached_tokens: number(usage.prompt_tokens_details?.cached_tokens), cache_write_tokens: number(usage.prompt_tokens_details?.cache_write_tokens),
            reasoning_tokens: number(usage.completion_tokens_details?.reasoning_tokens), cost: number(usage.cost),
            ...(failure ? { failure } : {}) });
        }
        inFlight = false;
        if (['error', 'aborted', 'length'].includes(message.stopReason) && !fatal) {
          stop(message.stopReason === 'error' ? 'provider-error' : `provider-${message.stopReason}`);
        }
      });
      await agent.prompt(options.brief);
      if (!fatal && !finished) stop('ended-without-finish');
    } finally {
      clearTimeout(requestTimer);
      clearTimeout(wallTimer);
    }
  } catch (error) {
    if (!fatal) fatal = error instanceof HostError ? error.reason : 'host-failed';
  }
  const result = { ok: !fatal && finished !== undefined, reason: fatal ?? 'finished', requests, tool_calls: toolCalls };
  emit('host-end', { ...result, summary_chars: finished ? finished.summary.length : 0, elapsed_ms: Math.round(performance.now() - started) });
  return result;
}
