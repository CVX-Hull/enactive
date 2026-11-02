// Zero-token contract test of the production level-role request (#341).
//
// It drives the real level host (runHost) against the real MCP adapter's tool list for the reader profile that
// the campaign freezes, with an intercepting fetch instead of a provider, and inspects the serialized request
// bodies exactly as a provider would receive them. The shadow-2 failure (a version constant the model could not
// see) would have failed here before any spend.
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { runHost, LEVEL_TERMINAL_TOOLS, LEVEL_RESERVED_REQUESTS } from '../host.mjs';

const python = process.env.ENACTIVE_TEST_PYTHON;
const root = process.env.ENACTIVE_TEST_PRODUCTION_ROOT ?? fileURLToPath(new URL('../../../', import.meta.url));
// The model-facing keyword set. Anything else (const, anyOf, oneOf, allOf, $ref, pattern, uniqueItems, format, ...)
// may be dropped or rewritten by a provider's schema conversion, so no call may depend on it.
const PORTABLE = new Set(['type', 'description', 'enum', 'properties', 'required', 'items', 'additionalProperties',
  'minLength', 'maxLength', 'minItems', 'maxItems', 'minimum', 'maximum']);
const HARNESS_OWNED = ['schema', 'version', 'record_id', 'position', 'session', 'actor_id', 'token'];

// The route the campaign uses for a level pass: OpenRouter, a pinned upstream, medium effort.
const model = {id:'google/gemini-3.8-flash', name:'Gemini 3.8 Flash via google-vertex/global', api:'openai-completions',
  provider:'openrouter', baseUrl:'https://openrouter.ai/api/v1', reasoning:true, input:['text', 'image'],
  cost:{input:1.5, output:7.5, cacheRead:0.15, cacheWrite:0.0833333333}, contextWindow:1048576, maxTokens:16384,
  thinkingLevelMap:{medium:'medium'},
  compat:{supportsDeveloperRole:false, supportsStore:false, supportsUsageInStreaming:true, supportsReasoningEffort:true,
    supportsStrictMode:false, maxTokensField:'max_tokens', thinkingFormat:'openrouter',
    openRouterRouting:{only:['google-vertex/global'], order:['google-vertex/global'], allow_fallbacks:false, require_parameters:true}}};
const PASS_REQUESTS = 6;
const levelRoute = {schema:'player-host/5', role:'level', intent_tail_bytes:null, service_tier:'default', model,
  api_key_env:'CONTRACT_TEST_KEY', max_requests:PASS_REQUESTS, max_context_images:30, context_image_block:1,
  request_timeout_seconds:30};

const reply = (name, args) => {
  const chunks = [{id:'r', model:'fixture-backend', choices:[{index:0, delta:{role:'assistant',
      tool_calls:[{index:0, id:`call-${name}`, type:'function', function:{name, arguments:JSON.stringify(args)}}]}, finish_reason:null}]},
    {id:'r', model:'fixture-backend', choices:[{index:0, delta:{}, finish_reason:'tool_calls'}],
      usage:{prompt_tokens:11, completion_tokens:5, total_tokens:16}}];
  return new Response(chunks.map(chunk => 'data: ' + JSON.stringify(chunk) + '\n\n').join('') + 'data: [DONE]\n\n',
    {headers:{'content-type':'text/event-stream'}});
};

/** Every node of a model-facing schema with its path. */
function* nodes(schema, path = []) {
  yield [schema, path];
  for (const [name, child] of Object.entries(schema.properties ?? {})) yield* nodes(child, [...path, name]);
  if (schema.items) yield* nodes(schema.items, [...path, '[]']);
}

async function reader() {
  assert.ok(python, 'Set ENACTIVE_TEST_PYTHON to the project Python');
  const {stdout} = await promisify(execFile)(python, ['-c',
    'import json; from tools.configure_player_tools import configuration; from harness.player_tools import PROFILES; '
    + 'print(json.dumps(dict(enabled=configuration("x", profile="reader")["enabled_tools"], profile=list(PROFILES["reader"]))))'],
    {cwd: root});
  return JSON.parse(stdout);
}

async function productionLevelRequests() {
  const {enabled, profile} = await reader();
  assert.deepEqual(enabled, profile, 'the campaign freezes exactly the reader profile');
  const bodies = [], events = [];
  // Requests 1-4 read the log; 5 and 6 are the reserved terminal-only requests, whose calls the flat-profile
  // custodian behind this MCP double refuses, so the pass uses its whole allowance.
  const sequence = [...Array(PASS_REQUESTS - LEVEL_RESERVED_REQUESTS).fill(['player_log_read', {after:0, limit:5}]),
    ['player_level_keep', {reason:'Still valid', sources:[]}], ['player_level_keep', {reason:'Still valid', sources:[]}]];
  const result = await runHost({configuration:levelRoute,
    mcpConfig:{command:resolve(python), args:[join(root, 'tests/player_service_fixture.py'), '--stdio'], cwd:root, enabled:true,
      enabled_tools:enabled, startup_timeout_sec:10, tool_timeout_sec:5},
    context:'Frozen current player guide', prompt:'Level pass.', model:model.id, effort:'medium', timeoutSeconds:60,
    env:{CONTRACT_TEST_KEY:'contract-key'},
    fetch:async (_url, init) => { bodies.push(init.body); return reply(...sequence[bodies.length - 1]); },
    onEvent:event => events.push(event)});
  return {result, bodies, payloads:bodies.map(body => JSON.parse(body)), events, enabled};
}

test('the production level request is portable, forces a tool call and reserves the last two requests', {timeout:90_000}, async () => {
  const {result, bodies, payloads, events, enabled} = await productionLevelRequests();
  assert.equal(payloads.length, PASS_REQUESTS, 'every allowed request is sent');
  // A terminal call refused on the last allowed request is its own settled reason, never request-limit.
  assert.equal(result.reason, 'level-final-refusal');
  assert.equal(events.find(event => event.type === 'abort').reason, 'level-final-refusal');

  for (const [index, payload] of payloads.entries()) {
    assert.equal(payload.tool_choice, 'required', `request ${index + 1} forces a tool call`);
    const offered = payload.tools.map(tool => tool.function.name);
    if (index < PASS_REQUESTS - LEVEL_RESERVED_REQUESTS) assert.deepEqual(offered, enabled, `request ${index + 1} offers the reader profile`);
    else assert.deepEqual(offered, LEVEL_TERMINAL_TOOLS, `request ${index + 1} offers only the four terminal tools`);
  }

  // The serialized tools, as the provider receives them.
  const serialized = JSON.parse(bodies[0]).tools;
  const wire = JSON.stringify(serialized);
  for (const keyword of ['"const"', '"anyOf"', '"oneOf"', '"allOf"', '"$ref"', '"$defs"', '"pattern"', '"uniqueItems"', '"format"', '"default"'])
    assert.ok(!wire.includes(keyword), `no ${keyword} in any reader tool schema`);

  for (const tool of serialized) {
    const schema = tool.function.parameters;
    assert.equal(schema.type, 'object', tool.function.name);
    for (const [node, path] of nodes(schema)) {
      const where = `${tool.function.name}${path.length ? '.' + path.join('.') : ''}`;
      assert.ok(typeof node.type === 'string' || Array.isArray(node.enum) && node.type, `${where} has a type`);
      for (const keyword of Object.keys(node)) assert.ok(PORTABLE.has(keyword), `${where} uses non-portable keyword ${keyword}`);
      if (node.additionalProperties !== undefined) assert.equal(node.additionalProperties, false, where);
      if (path.length) assert.ok(node.type !== 'object', `${where}: no nested objects`);
      if (node.type === 'array') assert.equal(node.items?.type, 'string', `${where}: arrays hold strings`);
      if (Array.isArray(node.enum)) assert.ok(node.enum.every(value => typeof value === 'string'), `${where}: enums are strings`);
    }
  }

  for (const name of LEVEL_TERMINAL_TOOLS) {
    const {parameters} = serialized.find(tool => tool.function.name === name).function;
    const properties = Object.keys(parameters.properties);
    assert.ok(properties.length > 0, name);
    // Every property is required, and none is a constant the harness owns.
    assert.deepEqual([...parameters.required].sort(), [...properties].sort(), `${name}: every property is required`);
    for (const owned of HARNESS_OWNED) assert.ok(!properties.includes(owned), `${name} must not ask the model for ${owned}`);
  }

  // The closed choices a model must be able to see are visible on the wire as plain string enums.
  const params = name => serialized.find(tool => tool.function.name === name).function.parameters.properties;
  assert.deepEqual(params('player_level_replace').previous_outcome.enum, ['none', 'achieved', 'failed', 'abandoned', 'revised']);
  assert.deepEqual(params('player_level_replace').status.enum, ['open', 'blocked']);
  assert.deepEqual(params('player_level_close').outcome.enum, ['achieved', 'failed', 'abandoned']);
  assert.deepEqual(params('player_level_abstain').reason_code.enum,
    ['insufficient_evidence', 'transient_screen_state', 'no_change_needed', 'other']);
  assert.ok(!wire.includes('player_level_commit'));
});

test('the reserved requests also tell the model that only the pass-ending tools are offered', {timeout:90_000}, async () => {
  const {payloads} = await productionLevelRequests();
  const status = payload => JSON.stringify(payload.messages.at(-1));
  for (const [index, payload] of payloads.entries()) {
    const reserved = index >= PASS_REQUESTS - LEVEL_RESERVED_REQUESTS;
    assert.equal(status(payload).includes('offers only the pass-ending tools'), reserved, `request ${index + 1}`);
    assert.ok(status(payload).includes(`Remaining allowance including this request: ${PASS_REQUESTS - index}.`));
  }
});
