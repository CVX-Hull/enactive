import test from 'node:test';
import assert from 'node:assert/strict';
import { route, reply, rateLimit, scenario, eventStream } from './host-scenario.mjs';

test('eligible 429 consumes a separate attempt with identical context and one tool execution',async t=>{
  const {result,events,payloads,calls}=await scenario(t,[
    rateLimit({type:'rate_limit_error',message:'Rate limited; fixture-key private upstream text'}),
    reply(null,[['mutate',{mode:'ok',index:1}]]),reply()]);
  assert.equal(result.ok,true);assert.equal(result.requests,3);
  assert.deepEqual(payloads[0],payloads[1]);
  assert.ok(payloads.every(payload=>!JSON.stringify(payload).includes('charged before this request')));
  const starts=events.filter(e=>e.type==='request-start');
  assert.deepEqual(starts.map(e=>e.request_id),['request-1','request-2','request-3']);
  assert.equal(starts[0].payload_sha256,starts[1].payload_sha256);
  assert.deepEqual(events.filter(e=>e.type==='response-headers').map(e=>e.status),[429,200,200]);
  const completed=events.filter(e=>e.type==='response-complete');
  assert.deepEqual(completed.map(e=>e.request_id),starts.map(e=>e.request_id));
  assert.equal(completed[0].http_status,429);assert.equal(completed[0].usage,null);
  assert.equal(completed[0].usage_available,false);assert.equal(completed[0].cost_source,null);
  assert.equal(completed[1].usage_available,true);
  assert.deepEqual(calls.map(c=>[c.index,c.phase]),[[1,'start'],[1,'end']]);
  assert.equal(events.find(e=>e.type==='tool-start').request_id,'request-2');
  assert.ok(!JSON.stringify({result,events}).includes('fixture-key'));
});

test('a stream that fails before its first data event is retried once',async t=>{
  const keepAlive=': OPENROUTER PROCESSING\n\n'.repeat(3);
  for (const failed of [keepAlive+'data: {"error":{"message":"Upstream error","code":502}}\n\n', keepAlive]) {
    const {result,events}=await scenario(t,[eventStream(failed),reply()]);
    assert.equal(result.ok,true);assert.equal(result.requests,2);
    assert.equal(events.find(e=>e.type==='provider-retry').retry_class,'stream-start-error');
  }
});
test('a stream error after delivered data is not retried',async t=>{
  const first={id:'fixture-response',model:'fixture-backend',choices:[{index:0,delta:{role:'assistant',content:'partial'},finish_reason:null}]};
  const late=eventStream('data: '+JSON.stringify(first)+'\n\ndata: {"error":{"message":"Upstream error","code":502}}\n\n');
  const {result,events}=await scenario(t,[late,reply()]);
  assert.equal(result.ok,false);assert.equal(result.requests,1);
  assert.ok(!events.some(e=>e.type==='provider-retry'));
});
test('repeated stream-start errors stop after two charged attempts',async t=>{
  const failed=()=>eventStream('data: {"error":{"message":"Upstream error","code":502}}\n\n');
  const {result,payloads}=await scenario(t,[failed(),failed(),reply()]);
  assert.equal(result.ok,false);assert.equal(result.requests,2);assert.equal(payloads.length,2);
});
test('message-less OpenRouter admission-control 429 is retried once',async t=>{
  const {result,events}=await scenario(t,[
    rateLimit({code:429,metadata:{limit_source:'openrouter_admission_control'}}),reply()]);
  assert.equal(result.ok,true);assert.equal(result.requests,2);
  assert.deepEqual(events.filter(e=>e.type==='response-headers').map(e=>e.status),[429,200]);
  assert.equal(events.find(e=>e.type==='provider-retry').retry_class,'rate-limit');
  // Balance wording under admission control stays transient while refill catches up.
  const balance=await scenario(t,[
    rateLimit({code:429,message:'Insufficient credits; add credits to continue',metadata:{limit_source:'openrouter_admission_control'}}),reply()]);
  assert.equal(balance.result.ok,true);assert.equal(balance.result.requests,2);
  // Authorization and malformed-request errors stay terminal even under admission control.
  for (const message of ['Invalid API key','Malformed request','Context length exceeded']) {
    const terminal=await scenario(t,[
      rateLimit({code:429,message,metadata:{limit_source:'openrouter_admission_control'}}),reply()]);
    assert.equal(terminal.result.ok,false);assert.equal(terminal.result.requests,1);
  }
});
test('repeated 429 stops after exactly two charged attempts',async t=>{
  const {result,payloads,events,calls}=await scenario(t,[rateLimit(),rateLimit(),reply()]);
  assert.equal(result.ok,false);assert.equal(result.reason,'provider-error');
  assert.equal(result.requests,2);assert.equal(payloads.length,2);assert.equal(calls.length,0);
  assert.deepEqual(events.filter(e=>e.type==='response-complete').map(e=>e.request_id),['request-1','request-2']);
});
test('429 at the request cap stops before backoff or another fetch',async t=>{
  const configuration=route();configuration.max_requests=1;
  const {result,payloads,events}=await scenario(t,[rateLimit(),reply()],{configuration});
  assert.equal(result.reason,'request-limit');assert.equal(result.requests,1);assert.equal(payloads.length,1);
  assert.equal(events.filter(e=>e.type==='response-complete').length,1);
  assert.ok(!events.some(e=>e.type==='provider-retry'));
});
test('quota, authorization and malformed 429 errors remain terminal despite retry-looking text',async t=>{
  for (const error of [
    {code:'insufficient_quota',message:'Rate limited'},
    {type:'quota_exceeded',message:'Rate limited'},
    {code:429,message:'Rate limited',metadata:{error_type:'quota_exceeded'}},
    {code:429,message:'Rate limit exceeded',metadata:{limit_source:'openrouter_credits'}},
    {type:'authentication_error',code:'invalid_api_key',message:'Rate limit exceeded'},
    {type:'auth_error',message:'Rate limit exceeded'},
    {type:'invalid_request_error',code:'invalid_parameter',message:'HTTP 429'},
    {type:'rate_limit_error',message:'Invalid API key; too many requests'},
    {message:'Billing limit reached; rate limit exceeded'},
    {message:'Quota exhausted; too many requests'},
    {message:'Payment required; too many requests'},
    {message:'Your account has exhausted its credits. Rate limit exceeded.'},
    {message:'Unknown fixture-key private detail'},
  ]) await t.test(JSON.stringify(error),async sub=>{
    const {result,payloads,events}=await scenario(sub,[rateLimit(error),reply()]);
    assert.equal(result.reason,'provider-error');assert.equal(result.requests,1);assert.equal(payloads.length,1);
    assert.ok(!JSON.stringify({result,events}).includes('fixture-key'));
  });
});
test('retry suppression header and excessive server delay do not send another attempt',async t=>{
  for (const headers of [{'x-should-retry':'false'},{'retry-after-ms':'61000'}]) await t.test(JSON.stringify(headers),async sub=>{
    const {result,payloads,events}=await scenario(sub,[rateLimit(undefined,headers),reply()]);
    assert.equal(result.reason,'provider-error');assert.equal(result.requests,1);assert.equal(payloads.length,1);
    assert.equal(events.filter(e=>e.type==='response-complete').length,1);
    const observed=events.find(e=>e.type==='response-headers');
    assert.equal(observed.requested_retry_delay_ms,headers['retry-after-ms'] === '61000' ? 61000 : 0);
    assert.equal(observed.retry_suppressed,headers['x-should-retry'] === 'false');
    assert.equal(observed.max_retry_delay_ms,60000);
  });
});
test('malformed and oversized refusal bodies cannot authorize a retry',async t=>{
  for (const body of ['not JSON',JSON.stringify({error:{message:'Rate limit '+ 'x'.repeat(17000)}})]) await t.test(String(body.length),async sub=>{
    const {result,payloads}=await scenario(sub,[new Response(body,{status:429}),reply()]);
    assert.equal(result.reason,'provider-error');assert.equal(result.requests,1);assert.equal(payloads.length,1);
  });
});
