// Request-serialization proof for the actor host (ADR 009 P1.0), with no provider call: every
// request body is captured at the fetch boundary and compared with the one before it. The prompt
// cache of any provider can only help if each request extends the last byte for byte, so this
// asserts the prefix, the tool table, the system prompt and the provider-affinity header.
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PassThrough } from 'node:stream';
import { runHost, projectImageContext, requestWarningAt, wallWarningMs, sessionAffinityId } from '../host.mjs';

const python = process.env.ENACTIVE_TEST_PYTHON;
const fixture = fileURLToPath(new URL('../../../tests/fixtures/player_host_mcp.py', import.meta.url));
const tools = ['observe', 'mutate', 'integer', 'observe_source', 'player_handoff'];
const openRouterModel = { id: 'vendor/fixture', name: 'OpenRouter fixture', api: 'openai-completions', provider: 'openrouter',
  baseUrl: 'https://openrouter.ai/api/v1', reasoning: false, input: ['text', 'image'], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
  contextWindow: 100000, maxTokens: 1024,
  compat: { supportsDeveloperRole: false, supportsStore: false, supportsUsageInStreaming: true,
    openRouterRouting: { only: ['fixture-backend'], order: ['fixture-backend'], allow_fallbacks: false, require_parameters: true } } };
const route = (overrides = {}) => ({ schema: 'player-host/3', context_reserve_tokens: 4096, service_tier: 'default', model: structuredClone(openRouterModel),
  api_key_env: 'OFFLINE_TEST_KEY', max_requests: 40, max_context_images: 4, context_image_block: 2, request_timeout_seconds: 5, ...overrides });

function reply(content, calls = [], prefix = 'call') {
  const message = { role: 'assistant', ...(calls.length ? { tool_calls: calls.map(([name, args], index) => ({ index, id: `${prefix}-${index}`, type: 'function',
    function: { name, arguments: JSON.stringify(args) } })) } : { content }) };
  const chunks = [{ id: 'r', model: 'fixture-backend', choices: [{ index: 0, delta: message, finish_reason: null }] },
    { id: 'r', model: 'fixture-backend', choices: [{ index: 0, delta: {}, finish_reason: calls.length ? 'tool_calls' : 'stop' }],
      usage: { prompt_tokens: 11, completion_tokens: 5, total_tokens: 16 } }];
  return new Response(chunks.map(chunk => 'data: ' + JSON.stringify(chunk) + '\n\n').join('') + 'data: [DONE]\n\n', { headers: { 'content-type': 'text/event-stream' } });
}
const finish = () => reply(null, [['player_finish', { disposition: 'task_complete', report: 'done', source_ids: [], control_id: null }]]);
const look = n => reply(null, [['observe_source', { n }]], `c${n}-`);
const rateLimit = () => new Response(JSON.stringify({ error: { type: 'rate_limit_error', message: 'Rate limit exceeded' } }),
  { status: 429, headers: { 'content-type': 'application/json', 'retry-after-ms': '0' } });

/** One host run against the offline MCP fixture; every fetch is captured with its headers. */
async function host(t, replies, { session = '2'.repeat(32), actorId = '3'.repeat(32), configuration = route(), context = 'Frozen player guide',
  prompt = 'Offline mission', enabledTools = tools, timeoutSeconds = 20 } = {}) {
  assert.ok(python, 'Set ENACTIVE_TEST_PYTHON to a Python with the official mcp package');
  const dir = await mkdtemp(join(tmpdir(), 'pi-serialization-'));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const captured = [], events = [];
  let index = 0;
  const fetch = async (_url, init) => {
    captured.push({ headers: new Headers(init.headers), body: init.body, payload: JSON.parse(init.body) });
    const next = replies[index++];
    return typeof next === 'function' ? await next() : next;
  };
  const mcpConfig = { command: resolve(python), args: [fixture, join(dir, 'calls.jsonl'), join(dir, 'pid')], cwd: dir, enabled: true, required: true,
    enabled_tools: enabledTools, startup_timeout_sec: 5, tool_timeout_sec: 2, default_tools_approval_mode: 'never', tools: {} };
  const result = await runHost({ session, actorId, pendingControlId: null, control: new PassThrough(), configuration, mcpConfig, context, prompt,
    model: configuration.model.id, effort: 'off', timeoutSeconds, env: { OFFLINE_TEST_KEY: 'fixture-key' }, fetch, onEvent: event => events.push(event) });
  return { result, captured, events, payloads: captured.map(item => item.payload) };
}

const noticePattern = /^Host (context capacity|request allowance|time allowance)/;
const text = message => typeof message.content === 'string' ? message.content : (message.content ?? []).map(part => part.text ?? '').join('');
const isNotice = message => message.role === 'user' && noticePattern.test(text(message));
// Notices stay in the history where they were first sent (#489's cache finding), so the whole
// previous request, notices included, is compared.
const withoutTail = payload => payload.messages;
// The serializer sends a tool batch's pixels in one following user message, so evicting every image
// of a batch removes that message. Eviction changes nothing else: its two footprints are removed
// here, the carrier message and the marker text appended to a tool result.
const MARKER = '\nHistorical pixels omitted';
const carrier = message => message.role === 'user' && Array.isArray(message.content) && message.content[0]?.text === 'Attached image(s) from tool result:';
const skeleton = payload => withoutTail(payload).filter(message => !carrier(message)).map(message =>
  JSON.stringify(message.role === 'tool' && typeof message.content === 'string' && message.content.includes(MARKER)
    ? { ...message, content: message.content.slice(0, message.content.indexOf(MARKER)) } : message));
const markers = payload => new Map(withoutTail(payload).filter(message => message.role === 'tool' && typeof message.content === 'string' && message.content.includes(MARKER))
  .map(message => [message.tool_call_id, message.content]));
const sentImages = payload => withoutTail(payload).filter(carrier).reduce((sum, message) => sum + message.content.length - 1, 0);

/** The cache contract between consecutive requests: the whole previous request, its notices
 * included, is a byte-for-byte prefix of the next, except that eviction may replace pixels with an
 * omission marker, once per image and unchanged afterwards. Everything but `messages` is identical.
 * Returns the omission markers of the last request. */
function assertStablePrefixes(payloads) {
  for (let i = 0; i < payloads.length; i++) {
    const { messages: _messages, ...rest } = payloads[i];
    assert.equal(JSON.stringify(rest), JSON.stringify({ ...payloads[0], messages: undefined }), `request ${i + 1}: fields other than messages are stable`);
    assert.equal(JSON.stringify(payloads[i].messages[0]), JSON.stringify(payloads[0].messages[0]), `request ${i + 1}: system prompt is stable`);
    if (i === 0) continue;
    const previous = skeleton(payloads[i - 1]), current = skeleton(payloads[i]);
    assert.ok(current.length >= previous.length, `request ${i + 1} only appends`);
    assert.deepEqual(current.slice(0, previous.length), previous, `request ${i + 1}: previous request is a byte-identical prefix`);
    // A marker, once written, is byte-identical on every later request; pixels never come back.
    for (const [id, marker] of markers(payloads[i - 1])) assert.equal(markers(payloads[i]).get(id), marker, `marker of ${id} is stable`);
    assert.ok(sentImages(payloads[i]) + markers(payloads[i]).size >= sentImages(payloads[i - 1]) + markers(payloads[i - 1]).size, 'no image vanishes without a marker');
    // Every notice sent earlier is still there, unchanged (it is part of the compared prefix), and only
    // a new request adds one: the notice count never falls.
    assert.ok(payloads[i].messages.filter(isNotice).length >= payloads[i - 1].messages.filter(isNotice).length, 'no notice is dropped');
  }
  return markers(payloads.at(-1));
}

test('an OpenRouter session sends one constant x-session-id derived from its identities, and records it', async t => {
  const { result, captured, events } = await host(t, [look(1), look(2), look(3), finish()]);
  assert.equal(result.ok, true);
  const expected = sessionAffinityId('2'.repeat(32));
  assert.deepEqual([...new Set(captured.map(item => item.headers.get('x-session-id')))], [expected]);
  assert.equal(events.find(event => event.type === 'host-start').session_affinity_id, expected);
  // Per mechanical session: constant across requests, distinct between sessions.
  assert.notEqual(expected, sessionAffinityId('5'.repeat(32)));
  assert.equal(expected, sessionAffinityId('2'.repeat(32)));
  // Derived from audit identities only; never the credential.
  assert.ok(!JSON.stringify(events).includes('fixture-key'));
  assert.ok(captured.every(item => !item.headers.has('x-session-affinity') && !item.headers.has('x-client-request-id')));
});

test('first request, appends, eviction and a retried request keep a byte-identical prefix', async t => {
  const replies = [look(1), look(2), look(3), look(4), look(5), rateLimit(), look(6), look(7), look(8), look(9), finish()];
  const { result, captured, payloads, events } = await host(t, replies);
  assert.equal(result.ok, true);
  // Nine looks, one finish and one retried attempt.
  assert.equal(payloads.length, 11);
  const rewritten = assertStablePrefixes(payloads);
  // 4 images allowed, blocks of 2: evictions happened, and each omitted message was rewritten once.
  assert.ok(rewritten.size >= 4);
  assert.equal(events.filter(event => event.type === 'context-image-projection' && event.omitted_images > 0).length > 0, true);
  // The retried attempt resends the identical body.
  assert.equal(captured[5].body, captured[6].body);
  // Every marker names the frame's source ID and how to read it again.
  const last = payloads.at(-1).messages.filter(message => message.role === 'tool' && text(message).includes('Historical pixels omitted'));
  assert.equal(last.length, rewritten.size);
  for (const message of last) {
    const id = /source_id=([a-f0-9]{32}-\d+);/.exec(text(message))?.[1];
    assert.ok(id, text(message));
    assert.ok(text(message).includes(`read source_id ${id} with player_source`));
  }
  // The affinity value stayed constant throughout, retry included.
  assert.equal(new Set(captured.map(item => item.headers.get('x-session-id'))).size, 1);
});

test('the request-limit notice is added on every request near the limit and kept where it was sent', async t => {
  const configuration = route({ max_requests: 10 });
  const { result, payloads, events } = await host(t, [...Array.from({ length: 9 }, (_, turn) => look(turn + 1)), finish()], { configuration });
  assert.equal(result.ok, true);
  assert.equal(payloads.length, 10);
  const withNotice = payloads.map(payload => isNotice(payload.messages.at(-1)));
  assert.equal(requestWarningAt(10), 2);
  assert.deepEqual(withNotice, [false, false, false, false, false, false, false, false, true, true]);
  assert.match(text(payloads[8].messages.at(-1)), /2 of 10 model requests remain, this one included/);
  assert.match(text(payloads[9].messages.at(-1)), /1 of 10 model requests remain/);
  assertStablePrefixes(payloads);
  assert.deepEqual(events.filter(event => event.type === 'tail-notice').map(event => [event.request_id, event.kinds]),
    [['request-9', ['request-limit']], ['request-10', ['request-limit']]]);
  // The first notice names the way out the model has, handoff or finish; it stays in the context, so a
  // later one only updates the figure.
  assert.match(text(payloads[8].messages.at(-1)), /player_handoff/);
  assert.match(text(payloads[8].messages.at(-1)), /player_finish/);
  assert.doesNotMatch(text(payloads[9].messages.at(-1)), /player_handoff|player_finish/);
  assert.equal(payloads[9].messages.filter(isNotice).length, 2, 'both notices are in the last request');
});

test('the context notice persists on every request once passed and warns before the capacity stop', async t => {
  const configuration = route({ context_reserve_tokens: 6000, model: { ...structuredClone(openRouterModel), contextWindow: 24000, maxTokens: 1024 } });
  // About 70,000 characters of guide is roughly 17,000 estimated tokens: under the warning line,
  // then each look adds a little until the notice and finally the capacity stop.
  const context = 'guide '.repeat(11600);
  const { result, payloads, events } = await host(t, Array.from({ length: 60 }, (_, turn) => look(turn + 1)), { configuration, context });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'context-capacity');
  const warned = payloads.map(payload => isNotice(payload.messages.at(-1)) && /^Host context capacity/.test(text(payload.messages.at(-1))));
  const first = warned.indexOf(true);
  assert.ok(first >= 0, 'the warning came before the stop');
  assert.ok(warned.slice(first).every(Boolean), 'once passed, every later request carries it');
  assert.ok(!warned.slice(0, first).some(Boolean));
  assert.match(text(payloads.at(-1).messages.at(-1)), /tokens of room remain before the host must stop/);
  assertStablePrefixes(payloads);
  const estimates = events.filter(event => event.type === 'context-estimate').map(event => event.tokens);
  assert.ok(estimates.at(-1) + 1024 >= 24000, 'the stop is the capacity rule');
});

test('the time notice warns before the work deadline and does not alter the prefix', async t => {
  assert.equal(wallWarningMs(100_000), 50_000);
  assert.equal(wallWarningMs(3_600_000), 360_000);
  const slow = async () => { await new Promise(done => setTimeout(done, 2800)); return look(2); };
  const { payloads, events } = await host(t, [look(1), slow, look(3), finish()], { timeoutSeconds: 6 });
  const noticed = payloads.map(payload => isNotice(payload.messages.at(-1)) && /^Host time allowance/.test(text(payload.messages.at(-1))));
  assert.equal(noticed[0], false);
  assert.ok(noticed.at(-1), 'the last request warns of the deadline');
  assert.ok(events.some(event => event.type === 'tail-notice' && event.kinds.includes('host-timeout')));
  assertStablePrefixes(payloads);
});

test('actors of one package share a byte-identical system prompt and tool table, across handoff and admissions', async t => {
  const runs = [];
  // Actor 1 hands off; the successor, then a new admission's first actor, run the same package.
  const handoff = await host(t, [look(1), reply(null, [['player_handoff', { ids: [], summary: 'carry on' }]])]);
  assert.equal(handoff.result.reason, 'handoff');
  runs.push(handoff);
  runs.push(await host(t, [look(1), finish()], { actorId: '4'.repeat(32), prompt: `Offline mission\n\nCurrent mechanical session=${'2'.repeat(32)}; your actor=${'4'.repeat(32)}; these audit IDs grant no authority.\n\nhandoff` }));
  runs.push(await host(t, [look(1), finish()], { session: '5'.repeat(32), actorId: '6'.repeat(32), prompt: `Offline mission\n\nCurrent mechanical session=${'5'.repeat(32)}; your actor=${'6'.repeat(32)}; these audit IDs grant no authority.` }));
  for (const run of runs) assert.ok(run.result.ok);
  const systems = runs.map(run => JSON.stringify(run.payloads[0].messages[0]));
  assert.equal(new Set(systems).size, 1, 'one system prompt for every actor');
  assert.ok(!systems[0].includes('2'.repeat(32)) && !systems[0].includes('3'.repeat(32)), 'no per-actor identity in the system prompt');
  const tables = runs.map(run => JSON.stringify(run.payloads[0].tools));
  assert.equal(new Set(tables).size, 1, 'one tool table for every actor');
  assert.ok(JSON.parse(tables[0]).some(tool => tool.function.name === 'player_handoff'), 'the table keeps player_handoff');
  for (const run of runs) {
    assert.equal(new Set(run.payloads.map(payload => JSON.stringify(payload.tools))).size, 1);
    assertStablePrefixes(run.payloads);
    // Each host's own affinity value is constant within it.
    assert.equal(new Set(run.captured.map(item => item.headers.get('x-session-id'))).size, 1);
  }
  const values = runs.map(run => run.captured[0].headers.get('x-session-id'));
  // The successor shares its predecessor's session, and so its value; a new admission does not.
  assert.equal(values[0], values[1], 'one value across actors of a session');
  assert.notEqual(values[0], values[2], 'a new session gets a new value');
  // The first user message is where an actor meets its own IDs.
  assert.ok(text(runs[2].payloads[0].messages[1]).includes(`your actor=${'6'.repeat(32)}`));
});

test('image markers name the source of the frame and are a function of the frame alone', () => {
  const message = (id, n) => ({ role: 'toolResult', toolCallId: id, content: [{ type: 'text', text: '{}' }, { type: 'image', data: Buffer.from(`pixels-${n}`).toString('base64'), mimeType: 'image/png' }] });
  const history = Array.from({ length: 5 }, (_, n) => message(`t${n}`, n));
  const sources = new Map(history.map((entry, n) => [entry.toolCallId, `src-${n}`]));
  const first = projectImageContext(history.slice(0, 4), 3, 2, sources);
  const second = projectImageContext(history, 3, 2, sources);
  // Image 0 and 1 omitted in a block; the marker carries the source and does not change when more frames arrive.
  assert.match(first.messages[0].content[1].text, /toolCallId=t0; source_id=src-0; image_index=0; SHA256=[a-f0-9]{64}\. .*read source_id src-0 with player_source/);
  assert.equal(JSON.stringify(first.messages[0]), JSON.stringify(second.messages[0]));
  // Without a known source the older marker text is unchanged.
  const bare = projectImageContext(history, 3, 2);
  assert.match(bare.messages[0].content[1].text, /toolCallId=t0; image_index=0; SHA256=/);
  assert.ok(!bare.messages[0].content[1].text.includes('source_id'));
});
