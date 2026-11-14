// The dollar limit from provider-reported cost (#555, R-OVERSPEND). The usage records and
// expected costs are shared with the curator's test (tests/test_curator_openrouter.py),
// because the two hosts cannot share code.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { reportedCostUsd } from '../host.mjs';
import { route, reply, rateLimit, scenario } from './host-scenario.mjs';

const vectors = JSON.parse(await readFile(new URL('../../../tests/fixtures/provider-usage-cost.json', import.meta.url), 'utf8'));
const tokens = {prompt_tokens:11, completion_tokens:5, total_tokens:16};
const pilot = vectors.cases[0].usage;
const limited = (spend_limit_usd, unpriced_request_usd = '0.25') => ({...route(), max_requests:8, spend_limit_usd, unpriced_request_usd});
const look = cost => reply(null, [['observe', {}]], {...tokens, cost});
const counted = events => events.filter(event => event.type === 'response-complete')
  .map(event => [event.request_id, event.counted_cost_usd, event.cost_counted_as, event.spent_usd]);
const settled = events => { const {spent_usd, unpriced_requests} = events.at(-1); return {spent_usd, unpriced_requests}; };

test('shared usage records give the reported cost the curator gives', () => {
  assert.ok(vectors.cases.length >= 6);
  for (const {name, usage, player_host: expected} of vectors.cases) {
    assert.equal(reportedCostUsd([usage]), expected, name);
    assert.ok(expected === null || /^(0|[1-9][0-9]*)(\.[0-9]*[1-9])?$/.test(expected), name);
  }
});
test('several usage records of one response: the largest counts and one malformed record leaves the cost unknown', () => {
  assert.equal(reportedCostUsd([]), null);
  assert.equal(reportedCostUsd([tokens, {...tokens, cost:0.00002}, {...tokens, cost:0.000038}, tokens]), '0.000038');
  assert.equal(reportedCostUsd([{...tokens, cost:0.000038}, {...tokens, cost:0.00002}]), '0.000038');
  assert.equal(reportedCostUsd([{...tokens, cost:0.000038}, {...tokens, cost:'0.000038'}]), null);
  assert.equal(reportedCostUsd([{...tokens, cost:-1}, {...tokens, cost:0.000038}]), null);
});
test('a reported cost is counted as the provider reported it, beside the unchanged configured-rate estimate', async t => {
  const configuration = route();
  configuration.model.cost = {input:1, output:2, cacheRead:0, cacheWrite:0};
  const {result, events} = await scenario(t, [reply('finished', [], {...pilot, ...tokens})], {configuration});
  assert.equal(result.ok, true);
  const start = events.find(event => event.type === 'host-start');
  assert.deepEqual([start.schema, start.telemetry_version, start.spend_limit_usd, start.unpriced_request_usd], ['player-host/5', 5, '100', '0.25']);
  const {wall_time, monotonic_ms, response_progress, ...completed} = events.find(event => event.type === 'response-complete');
  // 11 input tokens at $1 and 5 output at $2 per million: the estimate keeps its floating-point value and its label.
  assert.deepEqual(completed, {type:'response-complete', request_id:'request-1', model:'fixture-model', provider:'fixture',
    stop_reason:'toolUse', usage_available:true, usage:{input:11, output:5, cacheRead:0, cacheWrite:0, reasoning:0, totalTokens:16,
      cost:{input:0.000011, output:0.000009999999999999999, cacheRead:0, cacheWrite:0, total:0.000021}}, cost_source:'configured-rates',
    reported_cost_usd:'0.000038', counted_cost_usd:'0.000038', cost_counted_as:'provider-reported', spent_usd:'0.000038'});
  assert.deepEqual(settled(events), {spent_usd:'0.000038', unpriced_requests:0});
});
test('the limit stops the host before the next request, and the overshoot is at most one request', async t => {
  // Limit $0.01 and three responses reporting $0.004 each: the third takes the total to $0.012, so the fourth is refused.
  const {result, payloads, events, calls} = await scenario(t, [look(0.004), look(0.004), look(0.004), reply()], {configuration:limited('0.01')});
  assert.equal(result.ok, false); assert.equal(result.reason, 'spend-limit');
  assert.equal(result.requests, 3); assert.equal(payloads.length, 3); assert.equal(calls.length, 3);
  assert.deepEqual(counted(events), [['request-1', '0.004', 'provider-reported', '0.004'], ['request-2', '0.004', 'provider-reported', '0.008'],
    ['request-3', '0.004', 'provider-reported', '0.012']]);
  assert.deepEqual(settled(events), {spent_usd:'0.012', unpriced_requests:0});
  const abort = events.find(event => event.type === 'abort');
  assert.equal(abort.reason, 'spend-limit'); assert.equal(events.filter(event => event.type === 'request-start').length, 3);
});
test('the total is an exact decimal sum where floating point would let one more request through', async t => {
  assert.ok(0.1 + 0.7 < 0.8, 'the floating-point sum falls short of the limit');
  const {result, payloads, events} = await scenario(t, [look(0.1), look(0.7), reply()], {configuration:limited('0.8')});
  assert.equal(result.reason, 'spend-limit'); assert.equal(payloads.length, 2);
  assert.deepEqual(settled(events), {spent_usd:'0.8', unpriced_requests:0});
});
test('a cost with more digits than a declared amount may have is written and summed as plain decimal text', async t => {
  // 19 and 23 fractional digits, the second from a number JavaScript prints with an exponent.
  assert.equal(String(1.2345678901234566e-7), '1.2345678901234566e-7');
  const {result, events} = await scenario(t, [look(0.0034500000000000004), look(1.2345678901234566e-7), reply('finished', [], {cost:0.25})]);
  assert.equal(result.ok, true);
  assert.deepEqual(counted(events), [['request-1', '0.0034500000000000004', 'provider-reported', '0.0034500000000000004'],
    ['request-2', '0.00000012345678901234566', 'provider-reported', '0.00345012345678901274566'],
    ['request-3', '0.25', 'provider-reported', '0.25345012345678901274566']]);
  assert.deepEqual(events.filter(event => event.type === 'response-complete').map(event => event.reported_cost_usd),
    ['0.0034500000000000004', '0.00000012345678901234566', '0.25']);
  assert.deepEqual(settled(events), {spent_usd:'0.25345012345678901274566', unpriced_requests:0});
});
test('a successful response with no usable cost stops the host, whether or not token counts arrived', async t => {
  for (const usage of [tokens, {...tokens, cost:'0.000038'}, {...tokens, cost:-0.000038}, {...tokens, cost:0.00001, is_byok:true}, false]) {
    const {result, payloads, events, calls} = await scenario(t, [reply(null, [['observe', {}]], usage), reply()]);
    assert.equal(result.ok, false); assert.equal(result.reason, 'cost-unreported');
    assert.equal(payloads.length, 1); assert.equal(calls.length, 0);
    const completed = events.find(event => event.type === 'response-complete');
    assert.equal(completed.stop_reason, 'toolUse'); assert.equal(completed.reported_cost_usd, null);
    assert.equal(completed.usage_available, usage !== false);
    assert.deepEqual(counted(events), [['request-1', '0.25', 'unpriced-bound', '0.25']]);
    assert.deepEqual(settled(events), {spent_usd:'0.25', unpriced_requests:1});
  }
});
test('a cost reported without token counts is counted and the run goes on', async t => {
  const {result, events} = await scenario(t, [reply(null, [['observe', {}]], {cost:0.000038}), reply('finished', [], {cost:0.000038})]);
  assert.equal(result.ok, true); assert.equal(result.requests, 2);
  const completed = events.filter(event => event.type === 'response-complete');
  assert.deepEqual(completed.map(event => [event.usage_available, event.usage, event.cost_source]), [[false, null, null], [false, null, null]]);
  assert.deepEqual(settled(events), {spent_usd:'0.000076', unpriced_requests:0});
});
test('a refused request counts at the bound, and its retry is a separate request', async t => {
  const {result, events} = await scenario(t, [rateLimit(), reply('finished', [], pilot)], {configuration:limited('1')});
  assert.equal(result.ok, true);
  assert.deepEqual(counted(events), [['request-1', '0.25', 'unpriced-bound', '0.25'], ['request-2', '0.000038', 'provider-reported', '0.250038']]);
  assert.deepEqual(settled(events), {spent_usd:'0.250038', unpriced_requests:1});
  const terminal = await scenario(t, [new Response(JSON.stringify({error:{message:'refused'}}), {status:403, headers:{'content-type':'application/json'}})],
    {configuration:limited('1')});
  assert.equal(terminal.result.reason, 'provider-error');
  assert.deepEqual(counted(terminal.events), [['request-1', '0.25', 'unpriced-bound', '0.25']]);
});
test('the limit refuses a retry once the failed attempt has taken the total to it', async t => {
  const {result, payloads, events} = await scenario(t, [rateLimit(), reply()], {configuration:limited('0.25')});
  assert.equal(result.ok, false); assert.equal(result.reason, 'spend-limit');
  assert.equal(payloads.length, 1); assert.equal(result.requests, 1);
  assert.equal(events.some(event => event.type === 'provider-retry'), false);
  assert.deepEqual(settled(events), {spent_usd:'0.25', unpriced_requests:1});
});
test('a request aborted at its deadline counts once, at the bound', async t => {
  const configuration = limited('1'); configuration.request_timeout_seconds = .05;
  const hang = init => new Promise((_, reject) => init.signal.addEventListener('abort', () => reject(new Error('aborted')), {once:true}));
  const {result, events} = await scenario(t, [hang], {configuration});
  assert.equal(result.reason, 'request-timeout'); assert.equal(result.requests, 1);
  assert.deepEqual(counted(events), [['request-1', '0.25', 'unpriced-bound', '0.25']]);
  assert.deepEqual(settled(events), {spent_usd:'0.25', unpriced_requests:1});
});
