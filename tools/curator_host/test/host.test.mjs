import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readFile, rm, symlink, writeFile as writeNodeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { setTimeout as realDelay } from 'node:timers/promises';
import { projectImages, proxyFrom, runCurator, validateConfiguration } from '../host.mjs';
import { listDir, readFile as readTool, viewFrame, writeFile as writeTool } from '../workspace-tools.mjs';

const TOKEN = 'a1'.repeat(32);
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ioAAAAASUVORK5CYII=', 'base64');
export const configuration = () => ({
  schema: 'curator-host/1', effort: 'medium', max_requests: 6, request_timeout_seconds: 10, wall_seconds: 60,
  max_context_images: 4, context_image_block: 2, workbench_timeout_seconds: 5, budget_usd: 1,
  model: { id: 'openai/gpt-6.1-terra', name: 'Terra', reasoning: true, input: ['text', 'image'],
    cost: { input: 1, output: 5, cacheRead: 0.05, cacheWrite: 1.25 }, contextWindow: 262144, maxTokens: 4096,
    thinkingLevelMap: { medium: 'medium' },
    compat: { supportsDeveloperRole: false, supportsStore: false, supportsUsageInStreaming: true, supportsReasoningEffort: true,
      supportsStrictMode: false, maxTokensField: 'max_completion_tokens', thinkingFormat: 'openrouter',
      openRouterRouting: { only: ['openai'], order: ['openai'], allow_fallbacks: false, require_parameters: true } } },
});

function sse(calls, usage = { prompt_tokens: 120, completion_tokens: 15, total_tokens: 135, cost: 0.0002,
  prompt_tokens_details: { cached_tokens: 100 }, completion_tokens_details: { reasoning_tokens: 4 } }, prefix = 'call') {
  const delta = { role: 'assistant', ...(calls.length ? { tool_calls: calls.map(([name, args], index) => ({
    index, id: `${prefix}-${name}-${index}`, type: 'function', function: { name, arguments: JSON.stringify(args) } })) } : { content: 'done' }) };
  const chunks = [{ id: 'g', model: 'backend', choices: [{ index: 0, delta, finish_reason: null }] },
    { id: 'g', model: 'backend', choices: [{ index: 0, delta: {}, finish_reason: calls.length ? 'tool_calls' : 'stop' }] },
    { id: 'g', model: 'backend', choices: [], usage }];
  return new Response(chunks.map(chunk => 'data: ' + JSON.stringify(chunk) + '\n\n').join('') + 'data: [DONE]\n\n',
    { headers: { 'content-type': 'text/event-stream' } });
}

async function workspace(t) {
  const root = await mkdtemp(join(tmpdir(), 'curator-host-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  for (const name of ['trace/frames', 'knowledge', 'submissions', 'drafts', 'scratch', 'workbench']) await mkdir(join(root, name), { recursive: true });
  await writeNodeFile(join(root, 'trace/frames/s-2.png'), png);
  await writeNodeFile(join(root, 'brief.md'), '# Session brief');
  await writeNodeFile(join(root, 'knowledge/facts.jsonl'), '');
  return root;
}

async function session(t, replies, overrides = {}) {
  const root = await workspace(t);
  const events = [], payloads = [];
  let index = 0;
  const fetch = async (url, init) => {
    payloads.push({ url, headers: init.headers, raw_body: init.body, body: JSON.parse(init.body) });
    const next = replies[index++];
    return typeof next === 'function' ? next(init) : next;
  };
  const result = await runCurator({ configuration: configuration(), systemPrompt: 'frozen prompt', brief: '# Session brief', cwd: root,
    env: { CURATOR_PROXY_URL: 'http://127.0.0.1:41999', CURATOR_PROXY_TOKEN: TOKEN, PATH: '/usr/bin:/bin' }, fetch,
    ...overrides, onEvent: event => { events.push(event); overrides.onEvent?.(event); } });
  return { root, events, payloads, result };
}

test('the configuration is closed and matches what the proxy forwards', () => {
  assert.doesNotThrow(() => validateConfiguration(configuration()));
  const mutate = change => { const value = configuration(); change(value); return value; };
  for (const bad of [
    mutate(c => { c.model.compat.maxTokensField = 'max_tokens'; }),
    mutate(c => { c.model.compat.openRouterRouting.allow_fallbacks = true; }),
    mutate(c => { c.model.compat.openRouterRouting.only = ['openai', 'other']; }),
    mutate(c => { c.model.baseUrl = 'https://openrouter.ai/api/v1'; }),
    mutate(c => { c.api_key = 'secret'; }),
    mutate(c => { c.effort = 'high'; }),
    mutate(c => { c.model.id = 'no-vendor'; }),
    mutate(c => { c.context_image_block = 9; }),
    mutate(c => { c.schema = 'curator-host/0'; }),
  ]) assert.throws(() => validateConfiguration(bad));
});

test('only the proxy on loopback is an endpoint', () => {
  assert.equal(proxyFrom({ CURATOR_PROXY_URL: 'http://127.0.0.1:5000', CURATOR_PROXY_TOKEN: TOKEN }).baseUrl, 'http://127.0.0.1:5000/api/v1');
  for (const url of ['https://openrouter.ai', 'http://localhost:5000', 'http://127.0.0.1:5000/x', 'http://evil.example:80', undefined]) {
    assert.throws(() => proxyFrom({ CURATOR_PROXY_URL: url, CURATOR_PROXY_TOKEN: TOKEN }));
  }
  assert.throws(() => proxyFrom({ CURATOR_PROXY_URL: 'http://127.0.0.1:5000' }));
});

test('a scripted session lists, writes a submission and a draft, views a frame and finishes', async t => {
  const submission = { schema: 'curator-submission/1', base_version: 'v0', summary: 's', changes: [] };
  const { root, events, payloads, result } = await session(t, [
    sse([['list_dir', { path: 'trace/frames' }], ['view_frame', { frames: ['s-2'] }]]),
    sse([['write_file', { path: 'submissions/s1/submission.json', content: JSON.stringify(submission) }],
      ['write_file', { path: 'drafts/idea/notes.md', content: 'unfinished' }], ['read_file', { path: '../secret' }]]),
    sse([['finish', { summary: 'wrote one submission' }]]),
  ]);
  assert.deepEqual(result, { ok: true, reason: 'finished', requests: 3, tool_calls: 6 });
  assert.equal(JSON.parse(await readFile(join(root, 'submissions/s1/submission.json'), 'utf8')).base_version, 'v0');
  assert.equal(await readFile(join(root, 'drafts/idea/notes.md'), 'utf8'), 'unfinished');
  // The request the proxy sees: allowed fields only, the token as the key, explicit default tier.
  const body = payloads[0].body;
  assert.equal(payloads[0].url, 'http://127.0.0.1:41999/api/v1/chat/completions');
  assert.equal(body.max_completion_tokens, 4096);
  for (const forbidden of ['max_tokens', 'prompt_cache_key', 'user', 'plugins', 'models']) assert.equal(body[forbidden], undefined);
  assert.ok(payloads.every(payload => payload.body.service_tier === 'default'));
  assert.deepEqual(body.reasoning, { effort: 'medium' });
  assert.deepEqual(body.provider, configuration().model.compat.openRouterRouting);
  assert.deepEqual(body.tools.map(tool => tool.function.name),
    ['list_dir', 'read_file', 'view_frame', 'write_file', 'run_workbench', 'finish']);
  assert.ok(payloads[1].body.messages.some(m => JSON.stringify(m).includes('data:image/png;base64,')));
  // Telemetry: tokens, cost and tool outcomes; never the token.
  const ends = events.filter(event => event.type === 'request-end');
  assert.equal(ends.length, 3);
  assert.deepEqual([ends[0].prompt_tokens, ends[0].completion_tokens, ends[0].cached_tokens, ends[0].reasoning_tokens, ends[0].cost], [120, 15, 100, 4, 0.0002]);
  const calls = events.filter(event => event.type === 'tool-call');
  assert.deepEqual(calls.map(call => [call.name, call.ok]), [['list_dir', true], ['view_frame', true], ['write_file', true],
    ['write_file', true], ['read_file', false], ['finish', true]]);
  assert.ok(calls.every(call => call.bytes > 0 && call.duration_ms >= 0));
  assert.equal(events[0].type, 'host-start');
  assert.equal(events[0].requested_service_tier, 'default');
  assert.equal(events.at(-1).type, 'host-end');
  assert.ok(!JSON.stringify(events).includes(TOKEN));
  assert.ok(!JSON.stringify(payloads.map(p => p.body)).includes(TOKEN));
});

test('write_file refuses everything outside the writable directories', async t => {
  const root = await workspace(t);
  await symlink(tmpdir(), join(root, 'drafts/out'));
  await symlink(join(root, 'brief.md'), join(root, 'scratch/link'));
  for (const path of ['../x', 'submissions/../knowledge/x', '/tmp/x', 'knowledge/facts.jsonl', 'trace/x', 'brief.md', 'workbench/x',
    'submissions', 'submissions/', 'drafts/out/x', 'scratch/link', 'scratch/a\\b', '', 'submissions/\0x']) {
    await assert.rejects(writeTool(root, { path, content: 'x' }), { name: 'ToolError' }, path);
  }
  await assert.rejects(writeTool(root, { path: 'scratch/big', content: 'x'.repeat(524289) }), { name: 'ToolError' });
  assert.equal(await readFile(join(root, 'brief.md'), 'utf8'), '# Session brief');
  await writeTool(root, { path: 'scratch/deep/er/file.txt', content: 'ok' });
  assert.equal(await readFile(join(root, 'scratch/deep/er/file.txt'), 'utf8'), 'ok');
});

test('read tools stay inside the workspace, refuse links and binary files', async t => {
  const root = await workspace(t);
  const outside = await mkdtemp(join(tmpdir(), 'curator-outside-'));
  t.after(() => rm(outside, { recursive: true, force: true }));
  await writeNodeFile(join(outside, 'secret'), 'planted secret');
  await symlink(join(outside, 'secret'), join(root, 'scratch/leak'));
  await symlink(outside, join(root, 'scratch/leakdir'));
  for (const path of ['../secret', `${outside}/secret`, 'scratch/leak', 'scratch/leakdir/secret', 'trace/frames/s-2.png', 'nope']) {
    await assert.rejects(readTool(root, { path }), { name: 'ToolError' }, path);
  }
  await assert.rejects(listDir(root, { path: '..' }), { name: 'ToolError' });
  await assert.rejects(listDir(root, { path: 'scratch/leakdir' }), { name: 'ToolError' });
  await assert.rejects(viewFrame(root, { frame: '../brief' }), { name: 'ToolError' });
  await assert.rejects(viewFrame(root, { frame: 'missing' }), { name: 'ToolError' });
  assert.match((await readTool(root, { path: 'brief.md' })).content[0].text, /Session brief/);
  const bounded = await readTool(root, { path: 'brief.md', max_bytes: 4 });
  assert.match(bounded.content[0].text, /^# Se\n\[truncated: 11 more bytes; use offset=4\]/);
  const listing = (await listDir(root, { path: 'scratch' })).content[0].text;
  assert.match(listing, /link\t-\tleak/);
});

test('every request ends with a budget note, and past four fifths reading tools are refused', async t => {
  // Five requests of a budget of six: the fifth reply asks to read, after 4/6 > 0.5 and 5/6 > 0.8.
  const replies = [...Array.from({ length: 5 }, () => () => sse([['list_dir', {}]])), () => sse([['finish', { summary: 'done' }]])];
  const { events, payloads } = await session(t, replies);
  const notes = payloads.map(payload => payload.body.messages.at(-1));
  assert.ok(notes.every(note => note.role === 'user' && /^Budget: \d+ of 6 requests used/.test(String(note.content?.[0]?.text ?? note.content))));
  assert.match(String(notes[3].content?.[0]?.text ?? notes[3].content), /More than half is spent/);
  assert.match(String(notes[5].content?.[0]?.text ?? notes[5].content), /Reading tools are now refused/);
  const lists = events.filter(event => event.type === 'tool-call' && event.name === 'list_dir');
  assert.equal(lists.at(-1).ok, false);
  assert.match(lists.at(-1).error, /budget is nearly spent/);
  // Every earlier note stays in the history, unchanged, where it was first sent (#489's cache finding).
  const kept = payloads.at(-1).body.messages.filter(m => /^Budget:/.test(String(m.content?.[0]?.text ?? m.content ?? '')));
  assert.deepEqual(kept.map(m => JSON.stringify(m)), notes.map(m => JSON.stringify(m)));
});

test('the dollar budget moves the phase too', async () => {
  const { budgetNote } = await import('../host.mjs');
  assert.match(budgetNote({ requests: 1, maxRequests: 100, spent: 0.6, budget: 1 }).text, /More than half/);
  assert.match(budgetNote({ requests: 1, maxRequests: 100, spent: 0.85, budget: 1 }).text, /refused/);
  assert.doesNotMatch(budgetNote({ requests: 1, maxRequests: 100, spent: 0.1, budget: 1 }).text, /half|refused/);
});

test('view_frame shows up to four frames in one call', async t => {
  const { events, payloads } = await session(t, [
    sse([['view_frame', { frames: ['s-2', 's-2'] }]]), sse([['finish', { summary: 'looked' }]])]);
  assert.equal(events.find(event => event.name === 'view_frame').ok, true);
  assert.equal(JSON.stringify(payloads[1].body).split('"type":"image_url"').length - 1, 2);
});

test('the request limit stops the host and telemetry says why', async t => {
  const replies = Array.from({ length: 8 }, () => () => sse([['list_dir', {}]]));
  const { result, events } = await session(t, replies, { configuration: { ...configuration(), max_requests: 2 } });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'request-limit');
  assert.equal(events.filter(event => event.type === 'request-start').length, 2);
});

test('a provider refusal ends the session with the status, not a retry loop', async t => {
  const refusal = () => new Response(JSON.stringify({ error: { message: 'fields not allowed: x' } }), { status: 400 });
  const { result, events, payloads } = await session(t, [refusal, refusal]);
  assert.equal(result.reason, 'provider-error');
  assert.equal(payloads.length, 1);
  const end = events.find(event => event.type === 'request-end');
  assert.equal(end.status, 400);
  assert.equal(end.failure.kind, 'http-error');
  assert.equal(end.failure.phase, 'http-error');
  assert.ok(!JSON.stringify(events).includes('fields not allowed'));
});

test('stream failures have bounded diagnostics without provider error text or new retries', async t => {
  const data = value => `data: ${JSON.stringify(value)}\n\n`;
  const chunk = { id: 'g', choices: [{ index: 0, delta: {}, finish_reason: null }] };
  const cases = [
    ['error-event', data({ error: { message: 'SECRET provider detail', metadata: { error_type: 'SECRET-type' } } }), 'sdk-stream-error-unknown', 'before-first-chunk'],
    ['malformed', 'data: {SECRET malformed\n\n', 'malformed-sse-json', 'before-first-chunk'],
    ['eof', data(chunk), 'missing-finish-reason', 'streaming'],
    ['unknown-finish', data({ id: 'g', choices: [{ index: 0, delta: {}, finish_reason: 'SECRET' }] }) + 'data: [DONE]\n\n', 'sdk-stream-error-unknown', 'after-finish'],
  ];
  for (const [name, body, kind, phase] of cases) await t.test(name, async child => {
    const { result, events, payloads } = await session(child, [new Response(body, { headers: { 'content-type': 'text/event-stream' } })]);
    assert.equal(result.reason, 'provider-error');
    assert.equal(payloads.length, 1);
    const end = events.find(event => event.type === 'request-end');
    assert.equal(end.status, 200);
    assert.equal(end.failure.kind, kind);
    assert.equal(end.failure.phase, phase);
    assert.equal(end.failure.provider_error_type, null);
    assert.equal(end.usage_reported, false);
    assert.ok(!JSON.stringify(events).includes('SECRET'));
  });
});

test('a body failure after a valid finish stays an unknown stream failure', async t => {
  let pulls = 0;
  const body = new ReadableStream({ pull(controller) {
    if (pulls++ === 0) controller.enqueue(new TextEncoder().encode('data: ' + JSON.stringify({
      id: 'g', choices: [{ index: 0, delta: {}, finish_reason: 'stop' }],
    }) + '\n\n'));
    else controller.error(new Error('SECRET body failure'));
  } });
  const { events, result, payloads } = await session(t, [new Response(body, { headers: { 'content-type': 'text/event-stream' } })]);
  assert.equal(result.reason, 'provider-error');
  assert.equal(payloads.length, 1);
  const end = events.find(event => event.type === 'request-end');
  assert.equal(end.failure.kind, 'sdk-stream-error-unknown');
  assert.equal(end.failure.phase, 'after-finish');
  assert.equal(end.failure.finish_reason, 'stop');
  assert.ok(!JSON.stringify(events).includes('SECRET'));
});

test('a generation lookup reference survives a later stream failure without exposing error content', async t => {
  for (const id of ['gen-fixture_123', 'SECRET not an id', 'gen-' + 'x'.repeat(151)]) await t.test(id.slice(0, 24), async child => {
    const chunk = { id, choices: [{ index: 0, delta: { role: 'assistant' }, finish_reason: null }] };
    const data = value => 'data: ' + JSON.stringify(value) + '\n\n';
    const body = data(chunk) + data(chunk) + data({ error: { message: 'SECRET provider error' } });
    const { result, events } = await session(child, [new Response(body, { headers: { 'content-type': 'text/event-stream' } })]);
    assert.equal(result.reason, 'provider-error');
    const refs = events.filter(event => event.type === 'provider-generation');
    assert.deepEqual(refs.map(({ request_id, generation_id }) => ({ request_id, generation_id })),
      id === 'gen-fixture_123' ? [{ request_id: 'request-1', generation_id: id }] : []);
    assert.ok(!JSON.stringify(events).includes('SECRET'));
  });
});

test('a completed response without accounting is explicit without manufacturing usage', async t => {
  const { events, payloads } = await session(t, [sse([['finish', { summary: 'ok' }]], {})]);
  assert.equal(payloads.length, 1);
  const end = events.find(event => event.type === 'request-end');
  assert.equal(end.failure.kind, 'missing-usage');
  assert.equal(end.failure.phase, 'after-finish');
  assert.equal(end.prompt_tokens, null);
  assert.equal(end.cost, null);
});

test('one retry follows a gateway error, counted as a request', async t => {
  const gateway = () => new Response('bad gateway', { status: 502 });
  const { result, events } = await session(t, [gateway, sse([['finish', { summary: 'ok' }]])]);
  assert.equal(result.ok, true);
  assert.equal(result.requests, 2);
  assert.equal(events.filter(event => event.type === 'request-end' && event.retry).length, 1);
});

const rateLimit = headers => new Response(JSON.stringify({ error: { code: 429,
  message: 'credit verification timed out', metadata: { limit_source: 'openrouter_admission_control' } } }),
{ status: 429, headers });
async function waitFor(predicate) {
  const end = performance.now() + 5000;
  while (!predicate() && performance.now() < end) await realDelay(5);
  assert.ok(predicate(), 'reach the actual retry stage before advancing its timer');
  // Let the SDK install its retry timer after the eligible event.
  await realDelay(5);
}

test('429 honors Retry-After seconds and dates before resending identical bytes', async t => {
  for (const date of [false, true]) await t.test(String(date), async sub => {
    sub.mock.timers.enable({ apis: ['setTimeout'] });
    sub.mock.method(Date, 'now', () => 1_800_000_000_000);
    const controller = new AbortController();
    const after = date ? new Date(Date.now() + 10000).toUTCString() : '10';
    let eligible = false, second = false;
    const pending = session(sub, [rateLimit({ 'retry-after': after }), () => {
      second = true; return sse([['finish', { summary: 'ok' }]]);
    }], { configuration: { ...configuration(), request_timeout_seconds: 20 }, signal: controller.signal,
      onEvent: e => { if (e.type === 'request-end' && e.retry) eligible = true; } });
    try {
      await waitFor(() => eligible);
      sub.mock.timers.tick(9999); await realDelay(10);
      assert.equal(second, false);
      sub.mock.timers.tick(1);
      const { result, payloads, events } = await pending;
      assert.equal(result.ok, true); assert.equal(result.requests, 2);
      assert.equal(payloads[0].raw_body, payloads[1].raw_body);
      assert.ok(payloads.every(payload => payload.body.service_tier === 'default'));
      assert.equal(events.filter(e => e.type === 'request-end' && e.retry).length, 1);
    } finally { controller.abort(); }
  });
});

test('429 without an admissible server delay stays terminal and a repeated 429 gets no third attempt', async t => {
  for (const headers of [{}, { 'retry-after': '' }, { 'retry-after': 'soon' }, { 'retry-after': '-1' },
    { 'retry-after': 'Wed, 1' }, { 'retry-after': 'Wed, 1 Jan 2001' },
    { 'retry-after': 'Wed, 31 Feb 2027 00:00:00 GMT' },
    { 'retry-after': '61' }, { 'retry-after': '0', 'x-should-retry': 'false' }]) await t.test(JSON.stringify(headers), async sub => {
    const { result, payloads } = await session(sub, [rateLimit(headers)]);
    assert.equal(result.reason, 'provider-error'); assert.equal(payloads.length, 1);
  });
  const { result, payloads, events } = await session(t, [rateLimit({ 'retry-after': '0' }), rateLimit({ 'retry-after': '0' })]);
  assert.equal(result.reason, 'provider-error'); assert.equal(result.requests, 2); assert.equal(payloads.length, 2);
  assert.equal(payloads[0].raw_body, payloads[1].raw_body);
  assert.equal(events.filter(e => e.type === 'request-end' && e.retry).length, 1);
});

test('retry backoff retains request, host and cancellation ceilings', async t => {
  for (const kind of ['request-limit', 'request-timeout', 'host-timeout', 'cancelled']) await t.test(kind, async sub => {
    sub.mock.timers.enable({ apis: ['setTimeout'] });
    const controller = new AbortController();
    let eligible = false;
    const limits = { ...configuration(), request_timeout_seconds: 20 };
    if (kind === 'request-limit') limits.max_requests = 1;
    if (kind === 'request-timeout') limits.request_timeout_seconds = 1;
    if (kind === 'host-timeout') limits.wall_seconds = 1;
    const pending = session(sub, [rateLimit({ 'retry-after': '10' })], { configuration: limits, signal: controller.signal,
      onEvent: e => { if (e.type === 'request-end' && e.retry) eligible = true; } });
    try {
      if (kind !== 'request-limit') {
        await waitFor(() => eligible);
        if (kind === 'cancelled') controller.abort();
        else sub.mock.timers.tick(1000);
      }
      const { result, payloads } = await pending;
      assert.equal(result.reason, kind); assert.equal(result.requests, 1); assert.equal(payloads.length, 1);
    } finally { controller.abort(); }
  });
});

test('the original request deadline also covers the second attempt', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const controller = new AbortController();
  let eligible = false, second = false;
  const pending = session(t, [rateLimit({ 'retry-after': '0.6' }), init => {
    second = true;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => resolve(sse([['finish', { summary: 'too late' }]])), 600);
      init.signal.addEventListener('abort', () => { clearTimeout(timer); reject(new Error('aborted')); }, { once: true });
    });
  }], { configuration: { ...configuration(), request_timeout_seconds: 1 }, signal: controller.signal,
    onEvent: e => { if (e.type === 'request-end' && e.retry) eligible = true; } });
  try {
    await waitFor(() => eligible);
    t.mock.timers.tick(600); await waitFor(() => second);
    t.mock.timers.tick(400);
    const { result, payloads } = await pending;
    assert.equal(result.reason, 'request-timeout'); assert.equal(result.requests, 2);
    assert.equal(payloads[0].raw_body, payloads[1].raw_body);
  } finally { controller.abort(); }
});

test('ending without finish is a failure', async t => {
  const { result } = await session(t, [sse([])]);
  assert.deepEqual([result.ok, result.reason], [false, 'ended-without-finish']);
});

test('older frame images are replaced by a marker in whole blocks', () => {
  const message = id => ({ role: 'toolResult', toolCallId: id, content: [{ type: 'image', data: 'AA==', mimeType: 'image/png' }] });
  const messages = ['a', 'b', 'c', 'd', 'e'].map(message);
  assert.equal(projectImages(messages.slice(0, 4), 4, 2).omitted, 0);
  const projected = projectImages(messages, 4, 2);
  assert.equal(projected.omitted, 2);
  assert.equal(projected.messages[0].content[0].type, 'text');
  assert.equal(projected.messages[2].content[0].type, 'image');
  assert.equal(messages[0].content[0].type, 'image');
});

// ---- request serialization (ADR 009 context-stability readiness stage): what a provider's prompt cache sees, with no provider call ----
const noteOf = body => body.messages.at(-1);
const MARKED = '\n[Earlier frame image omitted';
const bodyText = message => typeof message.content === 'string' ? message.content : (message.content ?? []).map(part => part.text ?? '').join('');
const isCarrier = message => message.role === 'user' && Array.isArray(message.content) && message.content[0]?.text === 'Attached image(s) from tool result:';
/** Messages, notes included, without the pixel carriers and the omission markers: what eviction never touches. */
const skeleton = body => body.messages.filter(message => !isCarrier(message)).map(message => JSON.stringify(
  message.role === 'tool' && typeof message.content === 'string' && message.content.includes(MARKED)
    ? { ...message, content: message.content.slice(0, message.content.indexOf(MARKED)) } : message));
const markersOf = body => new Map(body.messages.filter(message => message.role === 'tool' && bodyText(message).includes(MARKED))
  .map(message => [message.tool_call_id, message.content]));

function assertStable(payloads) {
  for (const [index, { body }] of payloads.entries()) {
    assert.equal(JSON.stringify({ ...body, messages: undefined }), JSON.stringify({ ...payloads[0].body, messages: undefined }), `request ${index + 1}: tools and fields are stable`);
    assert.equal(JSON.stringify(body.messages[0]), JSON.stringify(payloads[0].body.messages[0]), 'system prompt is stable');
    assert.equal(noteOf(body).role, 'user');
    assert.match(bodyText(noteOf(body)), /^Budget: /, 'the transient note is the tail');
    if (index === 0) continue;
    const before = skeleton(payloads[index - 1].body), now = skeleton(body);
    // The whole previous request, its note included, is a byte-identical prefix: the provider reuses
    // a cached request only when a later one extends it (#489), so no note is ever rewritten.
    if (JSON.stringify(body) === JSON.stringify(payloads[index - 1].body)) continue;   // a retry resends the same body
    assert.deepEqual(now.slice(0, before.length), before, `request ${index + 1}: previous request is a byte-identical prefix`);
    for (const [id, marker] of markersOf(payloads[index - 1].body)) assert.equal(markersOf(body).get(id), marker, 'a marker never changes once written');
  }
}

test('serialization: appends, eviction, a retry and the tail note keep the prefix byte-identical', async t => {
  const view = n => () => sse([['view_frame', { frames: ['s-2'] }]], undefined, `v${n}`);
  const gateway = () => new Response('bad gateway', { status: 502 });
  const { result, payloads } = await session(t, [view(1), view(2), view(3), view(4), gateway, view(5), view(6), view(7), () => sse([['finish', { summary: 'done' }]])],
    { configuration: { ...configuration(), max_requests: 12 } });
  assert.equal(result.ok, true);
  assert.equal(payloads.length, 9);
  assertStable(payloads);
  // The retried attempt resends the body unchanged.
  assert.equal(JSON.stringify(payloads[4].body), JSON.stringify(payloads[5].body));
  // Four images are allowed in blocks of two: evictions happened, rarely, and the markers name the frame.
  const marked = markersOf(payloads.at(-1).body);
  assert.ok(marked.size >= 2);
  for (const marker of marked.values()) assert.match(marker, /frame s-2\); call view_frame with frames \["s-2"\] to see it again/);
});

test('serialization: the context notice persists once passed and precedes the capacity stop', async t => {
  const usage = tokens => ({ prompt_tokens: tokens, completion_tokens: 10, total_tokens: tokens + 10, cost: 0.0001 });
  const list = tokens => () => sse([['list_dir', {}]], usage(tokens));
  // Below the line, then past three quarters of the window, then within one output of the end.
  const { result, payloads } = await session(t, [list(10_000), list(200_000), list(230_000), list(258_100), list(100)]);
  assert.equal(result.reason, 'context-capacity');
  assert.equal(payloads.length, 4, 'the stopped request is never sent');
  const warned = payloads.map(payload => /nearly full/.test(bodyText(noteOf(payload.body))));
  assert.deepEqual(warned, [false, false, true, true]);
  assert.match(bodyText(noteOf(payloads[3].body)), /about \d+ tokens of room remain before the host stops the session/);
  assertStable(payloads);
});

test('the context stop uses prior usage, so a legal tool result can enter a higher price tier', async t => {
  const root = await workspace(t);
  await writeNodeFile(join(root, 'scratch/large'), 'x'.repeat(112_004));
  const usage = tokens => ({ prompt_tokens: tokens, completion_tokens: 10, total_tokens: tokens + 10, cost: 0.0001 });
  const config = configuration();
  config.model.maxTokens = 16_384;
  const { result, payloads } = await session(t, [
    sse([['read_file', { path: 'scratch/large', max_bytes: 112_004 }]], usage(244_000)),
    sse([['list_dir', {}]], usage(272_001)),
  ], { cwd: root, configuration: config });
  assert.equal(result.reason, 'context-capacity');
  assert.equal(payloads.length, 2, 'the appended tool result is sent before its usage can trigger the stop');
  assert.ok(JSON.stringify(payloads[1].body.messages).includes('x'.repeat(112_004)));
});

test('serialization: the wall-clock limit warns before the stop but never moves the phase', async () => {
  const { budgetNote, FINISH_AT } = await import('../host.mjs');
  const half = budgetNote({ requests: 1, maxRequests: 100, spent: 0, budget: 1, elapsedSeconds: 50, wallSeconds: 100 });
  assert.match(half.text, /50 of 100 s of time used\. More than half the time is used/);
  const late = budgetNote({ requests: 1, maxRequests: 100, spent: 0, budget: 1, elapsedSeconds: 90, wallSeconds: 100 });
  assert.match(late.text, /The time is nearly up: the host stops the session/);
  // Only requests and dollars refuse reading tools; time alone does not.
  assert.ok(late.share < FINISH_AT);
  assert.doesNotMatch(late.text, /refused/);
  assert.doesNotMatch(budgetNote({ requests: 1, maxRequests: 100, spent: 0, budget: 1 }).text, /time used/);
});

test('serialization: a host never sets an affinity header; the proxy owns it', async t => {
  const { payloads } = await session(t, [sse([['list_dir', {}]]), sse([['finish', { summary: 'ok' }]])]);
  for (const payload of payloads) {
    const headers = new Headers(payload.headers);
    for (const name of ['x-session-id', 'x-session-affinity', 'x-client-request-id', 'session_id']) assert.equal(headers.has(name), false, name);
  }
});

test('serialization: a marker names the frame, and one without a label keeps the older text', () => {
  const batch = (id, name) => ({ role: 'toolResult', toolCallId: id, content: [{ type: 'text', text: name ? `frame ${name} (3 bytes)` : 'no label' }, { type: 'image', data: 'AA==', mimeType: 'image/png' }] });
  const projected = projectImages([batch('a', 'sid-1'), batch('b', null), batch('c', 'sid-3')], 1, 2);
  assert.match(projected.messages[0].content[1].text, /tool call a, frame sid-1\); call view_frame with frames \["sid-1"\]/);
  assert.equal(projected.messages[1].content[1].text, '[Earlier frame image omitted to bound the request (tool call b); call view_frame again to see it.]');
  assert.equal(projected.messages[2].content[1].type, 'image');
});
