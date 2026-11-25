// R-KEY-LEAK and R-OVERSPEND: bounded, redacted classification and one shared retry.
import test from 'node:test';
import assert from 'node:assert/strict';
import {rateLimit, reply, route, scenario} from './host-scenario.mjs';

const privateMessage = 'private prompt from the request';
const privateRaw = 'private provider response content';
const privateExcerpt = 'private prompt';
const oversizedLabel = 'x'.repeat(65);
const response = (error, {nested = true, headers, usage} = {}) => new Response(JSON.stringify({
  ...(nested ? {error} : error), usage,
}), {status:403, headers:{'content-type':'application/json', 'retry-after-ms':'0', ...headers}});
const upstream = () => ({code:403, message:`Upstream provider returned an error. ${privateMessage}`,
  metadata:{provider_name:'Fixture Endpoint', provider_code:'endpoint_refused', raw:privateRaw}});
const ofType = (events, type) => events.filter(event => event.type === type);

test('terminal HTTP 403 classes win over provider attribution and disclose no free text', async t => {
  const cases = [
    ['credits-or-limit', {code:'insufficient_quota'}, true],
    ['credits-or-limit', {message:'API key spending limit exceeded'}, false],
    ['credits-or-limit', {metadata:{limit_source:'gateway_credits'}}, true],
    ['moderation', {metadata:{reasons:['content_filter']}}, false],
    ['moderation', {metadata:{reasons:['violence']}}, true],
    ['moderation', {metadata:{flagged_input:privateMessage}}, true],
    ['moderation', {message:'The prompt was flagged'}, true],
    ['moderation', {metadata:{raw:{error:{message:`Safety policy triggered. ${privateRaw}`}}}}, true],
    ['auth', {metadata:{error_type:'authentication_error'}}, true],
    ['auth', {metadata:{raw:'{"error":{"message":"Invalid API key"}}'}}, true],
    ['auth', {metadata:{raw:'{"error":{"type":"forbidden"}}'}}, true],
    ['auth', {metadata:{raw:'Account suspended'}}, true],
    ['auth', {message:'No permission to access this resource'}, false],
    ['unknown', {metadata:{provider_name:'fixture-key'}}, true],
    ['unknown', {metadata:{provider_name:'<untrusted provider>'}}, false],
    ['unknown', {metadata:{provider_name:privateMessage, reason:privateRaw}}, true],
    ['unknown', {metadata:{provider_name:privateExcerpt}}, true],
    ['unknown', {metadata:{provider_name:oversizedLabel}}, true],
  ];
  for (const [refusalClass, fields, nested] of cases) {
    const error = {message:privateMessage, ...fields,
      metadata:{provider_name:'Fixture Endpoint', raw:privateRaw, ...fields.metadata}};
    const {result, events} = await scenario(t, [response(error, {nested}), reply()]);
    const [refusal] = ofType(events, 'provider-refusal');
    assert.equal(refusal.refusal_class, refusalClass);
    assert.equal(refusal.provider_name, refusalClass === 'unknown' ? null : 'Fixture Endpoint');
    assert.equal(refusal.reason, null);
    assert.equal(result.reason, 'provider-error');
    assert.equal(result.requests, 1);
    assert.deepEqual(ofType(events, 'provider-retry'), []);
    for (const value of ['fixture-key', privateMessage, privateRaw, privateExcerpt, oversizedLabel, error.message]) {
      assert.ok(!JSON.stringify({result, events}).includes(value));
    }
  }
});

test('OpenRouter moderation with provider attribution stops after one attempt', async t => {
  const {result, bodies, events} = await scenario(t, [response({code:403, message:'',
    metadata:{reasons:['violence'], flagged_input:privateMessage, provider_name:'OpenAI'}}), reply()]);
  const [refusal] = ofType(events, 'provider-refusal');
  assert.deepEqual([refusal.refusal_class, refusal.provider_name], ['moderation', 'OpenAI']);
  assert.equal(result.reason, 'provider-error');
  assert.equal(bodies.length, 1);
  assert.deepEqual(ofType(events, 'provider-retry'), []);
  assert.ok(!JSON.stringify({result, events}).includes(privateMessage));
});

test('secret-bearing diagnostic fields are null even when surrounded by identifier characters', async t => {
  const {events} = await scenario(t, [response({type:'type-fixture-key', code:'prefix-fixture-key-suffix',
    message:`Invalid key fixture-key. ${privateMessage}`, metadata:{provider_name:'Endpoint fixture-key',
      provider_code:'error-fixture-key', limit_source:'fixture-key', reason:'reason-fixture-key', raw:privateRaw}})]);
  const [diagnostic] = ofType(events, 'provider-refusal');
  assert.equal(diagnostic.refusal_class, 'auth');
  for (const field of ['provider_name', 'error_type', 'error_code', 'provider_error_code', 'limit_source', 'reason']) {
    assert.equal(diagnostic[field], null, field);
  }
  assert.ok(!JSON.stringify(events).includes('fixture-key'));
});

test('an upstream HTTP 403 retries with the identical body, one notice and separate cost records', async t => {
  const configuration = {...route(), spend_limit_usd:'0.5',unpriced_request_usd:'0.05'};
  const {result, events, bodies} = await scenario(t, [response(upstream(), {usage:{cost:0.03}}), reply()],
    {configuration, finishReserveUsd:'0.4'});
  assert.equal(result.ok, true);
  assert.equal(result.requests, 2);
  assert.equal(bodies[1], bodies[0]);
  assert.deepEqual(ofType(events, 'tail-notice').map(event => [event.request_id, event.kinds]), [['request-1', ['spend-limit']]]);
  const [refusal] = ofType(events, 'provider-refusal');
  assert.deepEqual([refusal.refusal_class, refusal.provider_name, refusal.error_code, refusal.provider_error_code],
    ['upstream-provider', 'Fixture Endpoint', '403', 'endpoint_refused']);
  assert.deepEqual(ofType(events, 'provider-retry').map(event => [event.stage, event.request_id, event.retry_class ?? event.previous_request_id]),
    [['eligible', 'request-1', 'provider-403-failover'], ['started', 'request-2', 'request-1']]);
  assert.deepEqual(ofType(events, 'response-complete').map(event => event.counted_cost_usd), ['0.03', '0.000038']);
  for (const value of [privateMessage, privateRaw]) assert.ok(!JSON.stringify(events).includes(value));
});

test('the HTTP 403 retry shares the attempt budget with other refusals', async t => {
  for (const [first, second, retryClass] of [
    [response(upstream()), response(upstream(), {nested:false}), 'provider-403-failover'],
    [response(upstream()), rateLimit(), 'provider-403-failover'],
    [rateLimit(), response(upstream()), 'rate-limit'],
  ]) {
    const {result, bodies, events} = await scenario(t, [first, second, reply()]);
    assert.equal(result.reason, 'provider-error');
    assert.equal(result.requests, 2);
    assert.equal(bodies[1], bodies[0]);
    assert.deepEqual(ofType(events, 'provider-retry').filter(event => event.stage === 'eligible').map(event => event.retry_class), [retryClass]);
  }
});

test('HTTP 403 failover respects retry suppression, spend and the refusal body bound', async t => {
  const configuration = {...route(), spend_limit_usd:'0.3'};
  for (const [failure, reason] of [
    [response(upstream(), {headers:{'x-should-retry':'false'}}), 'provider-error'],
    [response(upstream(), {usage:{cost:0.3}}), 'spend-limit'],
    [response({...upstream(), message:'x'.repeat(17_000)}), 'provider-error'],
    [new Response(`Unrecognized ${privateRaw}`, {status:403}), 'provider-error'],
  ]) {
    const {result, events} = await scenario(t, [failure, reply()], {configuration});
    assert.equal(result.reason, reason);
    assert.equal(result.requests, 1);
    assert.deepEqual(ofType(events, 'provider-retry'), []);
  }
});
