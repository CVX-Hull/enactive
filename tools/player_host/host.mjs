import { isDeepStrictEqual } from 'node:util';
import { Agent } from '@earendil-works/pi-agent-core';
import { Type, AssistantMessageEventStream } from '@earendil-works/pi-ai';
import { stream } from '@earendil-works/pi-ai/api/openai-completions';
import { McpClient, StdioTransport, toLlmContent } from '@earendil-works/pi-mcp';

export const INPUT_LIMIT_BYTES = 1_048_576;
// openai@7.19.0 client.mjs reads these despite Pi's scoped env option.
// Their values can alter request headers or enable raw SDK logging.
const AMBIENT_PROVIDER_SETTINGS = ['OPENAI_LOG', 'OPENAI_CUSTOM_HEADERS', 'OPENAI_ORG_ID', 'OPENAI_PROJECT_ID'];
const MCP_LIMIT_BYTES = 32 * 1_048_576;
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
  closed(configuration, ['schema', 'model', 'api_key_env', 'max_requests', 'request_timeout_seconds']);
  requireThat(configuration.schema === 'pi-player-host/1');
  requireThat(/^[A-Za-z_][A-Za-z0-9_]*$/.test(configuration.api_key_env ?? '') && !AMBIENT_PROVIDER_SETTINGS.includes(configuration.api_key_env));
  requireThat(Number.isSafeInteger(configuration.max_requests) && configuration.max_requests > 0);
  requireThat(finiteMilliseconds(configuration.request_timeout_seconds));
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
  requireThat(levels.includes(effort), 'unsupported-effort');
  requireThat(model.reasoning || effort === 'off', 'unsupported-effort');
  if (model.thinkingLevelMap !== undefined) {
    closed(model.thinkingLevelMap, levels);
    requireThat(Object.values(model.thinkingLevelMap).every(value => value === null || text(value)));
  }
  if (model.reasoning) {
    requireThat(object(model.thinkingLevelMap) && Object.hasOwn(model.thinkingLevelMap, effort) && model.thinkingLevelMap[effort] !== null, 'unsupported-effort');
    requireThat(model.compat?.supportsReasoningEffort === true && model.compat.thinkingFormat === 'openai', 'unsupported-effort');
  }
  // The pilot admits the ordinary OpenAI reasoning-effort format only. Additional
  // Pi formats require conformance evidence before expanding this closed reader.
  if (model.compat !== undefined) {
    closed(model.compat, ['supportsDeveloperRole', 'supportsStore', 'supportsUsageInStreaming', 'supportsReasoningEffort', 'supportsStrictMode', 'maxTokensField', 'requiresToolResultName', 'requiresAssistantAfterToolResult', 'requiresThinkingAsText', 'requiresMistralToolIds', 'thinkingFormat']);
    for (const [key, value] of Object.entries(model.compat)) {
      if (key === 'maxTokensField') requireThat(['max_tokens', 'max_completion_tokens'].includes(value));
      else if (key === 'thinkingFormat') requireThat(value === 'openai');
      else requireThat(typeof value === 'boolean');
    }
  }
  return configuration;
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
  return {text_parts:textParts, text_bytes:textBytes, image_parts:imageParts, image_bytes:imageBytes, payload_bytes:Buffer.byteLength(JSON.stringify(payload))};
}

/** Run one finite host. fetch injection exercises the actual Pi serializer in tests. */
export async function runHost(options) {
  const started = performance.now();
  const emit = (type, fields = {}) => options.onEvent?.({type, wall_time:new Date().toISOString(), monotonic_ms:performance.now() - started, ...fields});
  let agent, client, transport, fatal, closing = false, requests = 0, requestId, requestTimer, requestInFlight = false, requestUsageAvailable = false;
  let workTimer, deadlineTimer;
  const stopped = new AbortController();
  const stop = reason => {
    if (fatal) return;
    fatal = reason;
    emit('abort', {reason, request_id:requestId});
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
      catch { if (!fatal) { fatal = 'mcp-cleanup-failed'; emit('abort', {reason:fatal}); } }
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
    workTimer = setTimeout(() => stop('host-timeout'), totalMs - cleanupBudget);
    deadlineTimer = setTimeout(() => stop('host-timeout'), totalMs);
    options.signal?.addEventListener('abort', cancellation, {once:true});
    if (options.signal?.aborted) stop('cancelled');
    const configuration = validateConfiguration(options.configuration, options.model, options.effort);
    const mcp = validateMcpConfiguration(options.mcpConfig);
    requireThat(typeof options.prompt === 'string' && typeof options.context === 'string', 'invalid-input');
    bounded(options.prompt); bounded(options.context);
    emit('host-start', {schema:configuration.schema, model:configuration.model.id, provider:configuration.model.provider, api:configuration.model.api, effort:options.effort, max_requests:configuration.max_requests, unsupported_features:['compaction', 'session-restore', 'model-fallback', 'reconnect', 'replay', 'ambient-tools', 'resource-discovery'], missing_endpoints:['model-attention', 'server-inference-start', 'physical-paint'], cleanup_budget_ms:cleanupBudget});
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
        emit('tool-result', {request_id:requestId, tool_call_id:toolCallId, tool:name, result});
        const content = toLlmContent(result);
        if (result.isError === true) content.unshift({type:'text', text:'MCP isError: true'});
        return {content, details:undefined, isError:result.isError === true};
      }};
    });
    agent = new Agent({
      initialState:{systemPrompt:options.context + (client.instructions ? '\n\nMCP server instructions:\n' + client.instructions : ''), model:configuration.model, thinkingLevel:options.effort, tools},
      toolExecution:'sequential',
      beforeToolCall:({toolCall, args}) => {
        if (fatal) return {block:true, reason:fatal, terminate:true};
        if (!isDeepStrictEqual(toolCall.arguments, args)) {
          emit('tool-refused', {request_id:requestId, tool_call_id:toolCall.id, tool:toolCall.name, reason:'tool-arguments-changed', dispatched:false});
          return {block:true, reason:'MCP input not sent: SDK changed arguments; explicitly correct the call.'};
        }
      },
      streamFn:(model, context, streamOptions) => {
        if (fatal) return failureStream(model, fatal);
        if (requests >= configuration.max_requests) { stop('request-limit'); return failureStream(model, fatal); }
        const apiKey = (options.env ?? process.env)[configuration.api_key_env];
        if (!text(apiKey)) { stop('missing-api-key'); return failureStream(model, fatal); }
        try {
          requestId = `request-${++requests}`;
          requestUsageAvailable = false;
          requestTimer = setTimeout(() => stop('request-timeout'), Math.min(configuration.request_timeout_seconds * 1000, totalMs));
          const requestSignal = AbortSignal.any([streamOptions.signal, stopped.signal].filter(Boolean));
          let first = false;
          const backendModels = new Set();
          const actualFetch = options.fetch ?? globalThis.fetch;
          const observedFetch = async (url, init) => {
            if (fatal) throw new HostError(fatal);
            let response;
            try { response = await actualFetch(url, init); }
            catch { if (!fatal) stop('provider-error'); throw new HostError(fatal); }
            emit('response-headers', {request_id:requestId, status:response.status});
            if (!response.body) return response;
            const body = response.body.pipeThrough(new TransformStream({transform(chunk, controller) {
              if (!first) { first = true; emit('response-first-chunk', {request_id:requestId}); }
              controller.enqueue(chunk);
            }}));
            return new Response(body, {status:response.status, statusText:response.statusText, headers:response.headers});
          };
          requestInFlight = true;
          return stream(model, context, {...streamOptions, apiKey, fetch:observedFetch, env:{}, signal:requestSignal, maxRetries:0, cacheRetention:'short', maxTokens:model.maxTokens, timeoutMs:configuration.request_timeout_seconds * 1000, reasoningEffort:options.effort === 'off' ? undefined : options.effort, onPayload:payload => {
            if (fatal) throw new HostError(fatal);
            emit('request-start', {request_id:requestId, model:model.id, provider:model.provider, ...payloadSize(payload)});
          }, onProviderStreamEvent:chunk => {
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
        if (requestInFlight) emit('response-complete', {request_id:requestId, model:message.model, provider:message.provider, stop_reason:message.stopReason, usage_available:requestUsageAvailable, usage:requestUsageAvailable ? message.usage : null, cost_source:requestUsageAvailable ? (message.usage?.cost?.totalFromProvider === true ? 'provider' : 'configured-rates') : null});
        requestInFlight = false;
        if (['error', 'aborted', 'length', 'deferred'].includes(message.stopReason) && !fatal) stop(message.stopReason === 'error' ? 'provider-error' : `provider-${message.stopReason}`);
      }
    });
    await agent.prompt(options.prompt);
    const terminal = agent.state.messages.findLast(message => message.role === 'assistant');
    if (!fatal && terminal?.stopReason !== 'stop') stop('incomplete-terminal-response');
  } catch (error) {
    if (!fatal) stop(error instanceof HostError ? error.reason : 'host-failed');
  } finally {
    clearTimeout(requestTimer); clearTimeout(workTimer);
    options.signal?.removeEventListener('abort', cancellation);
    await close();
    clearTimeout(deadlineTimer);
  }
  const terminal = agent?.state.messages.findLast(message => message.role === 'assistant');
  const finalText = !fatal ? (terminal?.content ?? []).filter(part => part.type === 'text').map(part => part.text).join('\n') : '';
  const result = {ok:!fatal, reason:fatal ?? 'completed', requests, finalText};
  emit('settled', {ok:result.ok, reason:result.reason, requests, native_cleanup_claimed:false});
  return result;
}
