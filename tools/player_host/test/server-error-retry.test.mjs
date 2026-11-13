import test from 'node:test';
import assert from 'node:assert/strict';
import { route, reply, rateLimit, scenario } from './host-scenario.mjs';

function serverError(status = 503, headers = {}, body = JSON.stringify({error:{code:status,message:'fixture-key upstream unavailable'}})) {
  return new Response(body,{status,headers:{'content-type':'application/json','retry-after-ms':'0',...headers}});
}
function inFlightBudget(headers = {'retry-after':'0'}, metadata = {limit_source:'openrouter_in_flight_budget',reason:'in_flight_budget_exhausted'}) {
  return new Response(JSON.stringify({error:{code:402,message:'fixture-key in-flight hold',metadata}}),
    {status:402,headers:{'content-type':'application/json',...headers}});
}
// Every attempt of one logical request sends the identical serialized body.
function assertRetry({result,payloads,events}, {ok,attempts,classes,started=classes.length,reason='provider-error'}) {
  assert.equal(result.ok,ok);if(!ok)assert.equal(result.reason,reason);
  assert.equal(result.requests,attempts);assert.equal(payloads.length,attempts);
  const starts=events.filter(e=>e.type==='request-start');
  assert.ok(starts.every(e=>e.payload_sha256===starts[0].payload_sha256 && e.logical_request_id==='request-1'));
  assert.deepEqual(events.filter(e=>e.type==='provider-retry'&&e.stage==='eligible').map(e=>e.retry_class),classes);
  assert.equal(events.filter(e=>e.type==='provider-retry'&&e.stage==='started').length,started);
  assert.deepEqual(events.filter(e=>e.type==='response-complete').map(e=>e.request_id),starts.map(e=>e.request_id));
  assert.ok(!JSON.stringify({result,events}).includes('fixture-key'));
}
test('503 then success retries once with the identical body',async t=>{
  const observed=await scenario(t,[serverError(),reply()]);
  assertRetry(observed,{ok:true,attempts:2,classes:['server-error']});
  assert.deepEqual(observed.events.filter(e=>e.type==='response-headers').map(e=>e.status),[503,200]);
  assert.equal(observed.events.find(e=>e.type==='response-complete').http_status,503);
});
test('pre-header fetch rejection then success retries once',async t=>{
  const observed=await scenario(t,[()=>Promise.reject(new TypeError('fixture-key connect reset')),reply()]);
  assertRetry(observed,{ok:true,attempts:2,classes:['pre-header-rejection']});
  assert.deepEqual(observed.events.filter(e=>e.type==='response-headers').map(e=>e.status),[200]);
  assert.equal(observed.events.find(e=>e.type==='response-complete').http_status,null);
});
test('an HTML 502 body is eligible by status alone',async t=>{
  const observed=await scenario(t,[serverError(502,{'content-type':'text/html'},'<html><body>Bad gateway fixture-key</body></html>'),reply()]);
  assertRetry(observed,{ok:true,attempts:2,classes:['server-error']});
  assert.equal(observed.events.find(e=>e.type==='provider-refusal').error_code,null);
});
test('a 503 whose refusal body cannot be read stays eligible by status',async t=>{
  for (const body of [()=>new ReadableStream({start(c){c.error(new Error('fixture-key reset'));}}),()=>'x'.repeat(17000)]) await t.test(typeof body(),async sub=>{
    const observed=await scenario(sub,[()=>serverError(503,{},body()),reply()]);
    assertRetry(observed,{ok:true,attempts:2,classes:['server-error']});
    assert.equal(observed.events.find(e=>e.type==='provider-refusal').body_read,false);
  });
});
test('one retry is shared across classes and a second transient failure is terminal',async t=>{
  for (const [name,sequence,classes] of [
    ['429-503',()=>[rateLimit(),serverError()],['rate-limit']],
    ['503-503',()=>[serverError(),serverError()],['server-error']],
    ['503-504',()=>[serverError(),serverError(504)],['server-error']],
    ['429-402',()=>[rateLimit(),inFlightBudget()],['rate-limit']],
    ['rejection-503',()=>[()=>Promise.reject(new TypeError('fixture-key')),serverError()],['pre-header-rejection']],
  ]) await t.test(name,async sub=>{
    assertRetry(await scenario(sub,[...sequence(),reply()]),{ok:false,attempts:2,classes});
  });
});
test('suppressed, undeclared and partial-stream failures are terminal without retry',async t=>{
  // Erroring in start() would discard the queued chunk; error on the next pull so
  // the partial data really is delivered before the reset.
  const partial=()=>new Response(new ReadableStream({start(c){
    c.enqueue(new TextEncoder().encode('data: '+JSON.stringify({choices:[{index:0,delta:{role:'assistant',content:'par'},finish_reason:null}]})+'\n\n'));
  },pull(c){c.error(new Error('fixture-key reset after headers'));}},{highWaterMark:0}),{headers:{'content-type':'text/event-stream'}});
  for (const [name,response] of [
    ['503-suppressed',()=>serverError(503,{'x-should-retry':'false'})],
    ...[500,501,408,409,418].map(status=>[String(status),()=>serverError(status)]),
    ['partial-200',partial],
  ]) await t.test(name,async sub=>{
    const observed=await scenario(sub,[response(),reply()]);
    assertRetry(observed,{ok:false,attempts:1,classes:[]});
    if(name==='503-suppressed')assert.equal(observed.events.find(e=>e.type==='response-headers').retry_suppressed,true);
  });
});
test('request timeout during 503 backoff is never retried',async t=>{
  const configuration=route();configuration.request_timeout_seconds=.1;
  const observed=await scenario(t,[serverError(503,{'retry-after-ms':'20000'}),reply()],{configuration});
  assertRetry(observed,{ok:false,attempts:1,classes:['server-error'],started:0,reason:'request-timeout'});
});
test('documented in-flight 402 with Retry-After retries once and records its reason',async t=>{
  const observed=await scenario(t,[inFlightBudget(),reply()]);
  assertRetry(observed,{ok:true,attempts:2,classes:['in-flight-budget']});
  const refusal=observed.events.find(e=>e.type==='provider-refusal');
  assert.equal(refusal.limit_source,'openrouter_in_flight_budget');assert.equal(refusal.reason,'in_flight_budget_exhausted');
  assert.equal(observed.events.find(e=>e.type==='response-headers').requested_retry_delay_ms,0);
});
test('every other 402 stays terminal',async t=>{
  for (const [name,response] of [
    ['missing-retry-after',()=>inFlightBudget({})],
    ['retry-after-ms-only',()=>inFlightBudget({'retry-after-ms':'0'})],
    ['unparseable-retry-after',()=>inFlightBudget({'retry-after':'soon'})],
    ['empty-retry-after',()=>inFlightBudget({'retry-after':''})],
    ['delay-over-cap',()=>inFlightBudget({'retry-after':'61'})],
    ['credits',()=>inFlightBudget(undefined,{limit_source:'openrouter_credits',reason:'weight_exceeds_budget'})],
    ['no-limit-source',()=>inFlightBudget(undefined,{reason:'in_flight_budget_exhausted'})],
    ['mismatched-reason',()=>inFlightBudget(undefined,{limit_source:'openrouter_in_flight_budget',reason:'weight_exceeds_budget'})],
    ['not-json',()=>new Response('in_flight_budget_exhausted openrouter_in_flight_budget',{status:402,headers:{'retry-after':'0'}})],
  ]) await t.test(name,async sub=>{
    // An over-cap server delay is refused by the SDK helper after eligibility.
    const overCap=name==='delay-over-cap';
    assertRetry(await scenario(sub,[response(),reply()]),{ok:false,attempts:1,classes:overCap?['in-flight-budget']:[],started:0});
  });
});
