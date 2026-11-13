// Provider-reported cost in the trace (#555, R-OVERSPEND): evidence only in telemetry
// version 3. The usage records and expected costs are shared with the curator's test
// (tests/test_curator_openrouter.py), because the two hosts cannot share code.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { reportedCostUsd } from '../host.mjs';
import { route, reply, rateLimit, scenario } from './host-scenario.mjs';

const vectors = JSON.parse(await readFile(new URL('../../../tests/fixtures/provider-usage-cost.json', import.meta.url), 'utf8'));
const tokens = {prompt_tokens:11, completion_tokens:5, total_tokens:16};
const pilot = vectors.cases[0].usage;
// Everything a response-complete event says apart from its clock readings and the new field.
const settledFields = ({wall_time, monotonic_ms, response_progress, reported_cost_usd, ...rest}) => rest;
const priced = () => {
  const configuration = route();
  configuration.model.cost = {input:1, output:2, cacheRead:0, cacheWrite:0};
  return configuration;
};

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
test('a streamed usage record with a cost is recorded without changing any other response field', async t => {
  const plain = await scenario(t, [reply('finished', [], tokens)], {configuration:priced()});
  const costed = await scenario(t, [reply('finished', [], {...pilot, ...tokens})], {configuration:priced()});
  const [before] = plain.events.filter(event => event.type === 'response-complete');
  const [after] = costed.events.filter(event => event.type === 'response-complete');
  assert.equal(before.reported_cost_usd, null);
  assert.equal(after.reported_cost_usd, '0.000038');
  // The event as the host emitted it for this response before the field existed (captured on
  // main at 4784cb4): the configured-rate estimate, 11 input at $1 and 5 output at $2 per
  // million, keeps its place, its floating-point value and its label.
  const unchanged = {type:'response-complete', request_id:'request-1', model:'fixture-model', provider:'fixture',
    stop_reason:'toolUse', usage_available:true, usage:{input:11, output:5, cacheRead:0, cacheWrite:0, reasoning:0, totalTokens:16,
      cost:{input:0.000011, output:0.000009999999999999999, cacheRead:0, cacheWrite:0, total:0.000021}}, cost_source:'configured-rates'};
  assert.deepEqual(settledFields(before), unchanged);
  assert.deepEqual(settledFields(after), unchanged);
  assert.deepEqual(Object.keys(after), ['type', 'wall_time', 'monotonic_ms', ...Object.keys(unchanged).slice(1), 'reported_cost_usd', 'response_progress']);
  assert.deepEqual(costed.result, plain.result);
  assert.deepEqual(costed.events.map(event => event.type), plain.events.map(event => event.type));
});
test('an absent or malformed cost is recorded as null and the run goes on as before', async t => {
  for (const usage of [tokens, {...tokens, cost:'0.000038'}, {...tokens, cost:-0.000038}, {...tokens, cost:0.00001, is_byok:true}]) {
    const {result, events} = await scenario(t, [reply(null, [['observe', {}]], usage), reply('finished', [], pilot)]);
    assert.equal(result.ok, true); assert.equal(result.requests, 2);
    const completed = events.filter(event => event.type === 'response-complete');
    assert.deepEqual(completed.map(event => event.reported_cost_usd), [null, '0.000038']);
    assert.deepEqual(completed.map(event => event.usage_available), [true, true]);
  }
});
test('a cost is recorded without token counts, which stay unknown', async t => {
  const {result, events} = await scenario(t, [reply('finished', [], {cost:0.000038})]);
  assert.equal(result.ok, true);
  const completed = events.find(event => event.type === 'response-complete');
  assert.equal(completed.reported_cost_usd, '0.000038');
  assert.equal(completed.usage_available, false); assert.equal(completed.usage, null); assert.equal(completed.cost_source, null);
});
test('a response with no usage record and a refused first attempt both record a null cost', async t => {
  const missing = await scenario(t, [reply('finished', [], false)]);
  assert.equal(missing.events.find(event => event.type === 'response-complete').reported_cost_usd, null);
  const retried = await scenario(t, [rateLimit(), reply('finished', [], pilot)]);
  assert.equal(retried.result.ok, true);
  assert.deepEqual(retried.events.filter(event => event.type === 'response-complete').map(event => event.reported_cost_usd), [null, '0.000038']);
});
