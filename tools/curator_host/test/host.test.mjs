import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readFile, rm, symlink, writeFile as writeNodeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
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
  prompt_tokens_details: { cached_tokens: 100 }, completion_tokens_details: { reasoning_tokens: 4 } }) {
  const delta = { role: 'assistant', ...(calls.length ? { tool_calls: calls.map(([name, args], index) => ({
    index, id: `call-${name}-${index}`, type: 'function', function: { name, arguments: JSON.stringify(args) } })) } : { content: 'done' }) };
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
    payloads.push({ url, headers: init.headers, body: JSON.parse(init.body) });
    const next = replies[index++];
    return typeof next === 'function' ? next(init) : next;
  };
  const result = await runCurator({ configuration: configuration(), systemPrompt: 'frozen prompt', brief: '# Session brief', cwd: root,
    env: { CURATOR_PROXY_URL: 'http://127.0.0.1:41999', CURATOR_PROXY_TOKEN: TOKEN, PATH: '/usr/bin:/bin' }, fetch,
    onEvent: event => events.push(event), ...overrides });
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
  // The request the proxy sees: allowed fields only, the token as the key, no service tier.
  const body = payloads[0].body;
  assert.equal(payloads[0].url, 'http://127.0.0.1:41999/api/v1/chat/completions');
  assert.equal(body.max_completion_tokens, 4096);
  for (const forbidden of ['max_tokens', 'service_tier', 'prompt_cache_key', 'user', 'plugins', 'models']) assert.equal(body[forbidden], undefined);
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
  // The note is transient: no earlier note survives in a later request's history.
  assert.ok(payloads.at(-1).body.messages.slice(0, -1).every(m => !/^Budget:/.test(String(m.content?.[0]?.text ?? m.content ?? ''))));
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
  assert.match(end.error_body, /fields not allowed/);
});

test('one retry follows a gateway error, counted as a request', async t => {
  const gateway = () => new Response('bad gateway', { status: 502 });
  const { result, events } = await session(t, [gateway, sse([['finish', { summary: 'ok' }]])]);
  assert.equal(result.ok, true);
  assert.equal(result.requests, 2);
  assert.equal(events.filter(event => event.type === 'request-end' && event.retry).length, 1);
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
