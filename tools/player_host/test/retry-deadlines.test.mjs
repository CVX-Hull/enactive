import test from 'node:test';
import assert from 'node:assert/strict';
import { realDelay, route, reply, rateLimit, scenario, eventStream } from './host-scenario.mjs';

test('observed twenty-second server delay is honored once under original timers',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});
  const configuration=route();configuration.request_timeout_seconds=30;
  let eligible=false,second=false;
  const waitFor=async predicate=>{
    const until=Date.now()+5000;
    while(!predicate()&&Date.now()<until)await realDelay(10);
    assert.ok(predicate(),'actual fixture stage must precede controlled clock advance');
  };
  const {result,payloads,events}=await scenario(t,[rateLimit({code:429,message:'Rate limit exceeded',
    metadata:{error_type:'rate_limit_exceeded',provider_code:'rate_limited',limit_source:'upstream_provider_shared_pool',
      raw:'fixture-key private body must never be logged'}},{'retry-after-ms':'20000'}),()=>{second=true;return reply();}],{
    configuration,timeoutSeconds:60,
    onEvent:e=>{if(e.type==='provider-retry')eligible=true;},
    synchronize:async()=>{
      await waitFor(()=>eligible);t.mock.timers.tick(19999);await realDelay(20);
      assert.equal(second,false,'never retry before the requested delay');
      t.mock.timers.tick(1);await waitFor(()=>second);
    },
  });
  assert.equal(result.ok,true);assert.equal(result.requests,2);
  assert.equal(payloads.length,2);assert.deepEqual(payloads[0],payloads[1]);
  const refusal=events.find(e=>e.type==='provider-refusal');
  assert.equal(refusal.error_type,'rate_limit_exceeded');assert.equal(refusal.provider_error_code,'rate_limited');
  assert.equal(refusal.limit_source,'upstream_provider_shared_pool');
  assert.ok(!JSON.stringify(events).includes('private body'));
});
test('request timeout and cancellation interrupt backoff without a second attempt',async t=>{
  for (const cancel of [false,true]) await t.test(String(cancel),async sub=>{
    const configuration=route();configuration.request_timeout_seconds=.1;
    const controller=new AbortController();
    const {result,payloads,events}=await scenario(sub,[()=>{
      if(cancel) setTimeout(()=>controller.abort(),20);
      return rateLimit(undefined,{'retry-after-ms':'20000'});
    },reply()],{configuration,signal:controller.signal});
    assert.equal(result.reason,cancel?'cancelled':'request-timeout');
    const progress=events.find(event=>event.type==='abort').response_progress;
    assert.equal(progress.scope,'last-http-attempt');assert.equal(progress.request_id,'request-1');
    assert.equal(result.requests,1);assert.equal(payloads.length,1);
    assert.equal(events.filter(e=>e.type==='response-complete').length,1);
  });
});
test('a stalled refusal body is cancellable without waiting for its cancel hook',async t=>{
  const controller=new AbortController();
  const {result,payloads}=await scenario(t,[()=>{
    setTimeout(()=>controller.abort(),20);
    return new Response(new ReadableStream({cancel:()=>new Promise(()=>{})}),{status:429});
  }],{signal:controller.signal});
  assert.equal(result.reason,'cancelled');assert.equal(result.requests,1);assert.equal(payloads.length,1);
});
test('a stalled stream peek is cancellable without waiting for its cancel hook',async t=>{
  const controller=new AbortController();
  const {result,payloads}=await scenario(t,[()=>{
    setTimeout(()=>controller.abort(),20);
    return new Response(new ReadableStream({start(c){c.enqueue(new TextEncoder().encode(': keep-alive\n\n'));},
      cancel:()=>new Promise(()=>{})}),{headers:{'content-type':'text/event-stream'}});
  }],{signal:controller.signal});
  assert.equal(result.reason,'cancelled');assert.equal(result.requests,1);assert.equal(payloads.length,1);
});
test('a transport error or first [DONE] before any data event is retried once',async t=>{
  const broken=()=>new Response(new ReadableStream({start(c){c.enqueue(new TextEncoder().encode(': keep-alive\n\n'));c.error(new Error('reset'));}}),
    {headers:{'content-type':'text/event-stream'}});
  for (const first of [broken, ()=>eventStream('data: [DONE]\n\n')]) {
    const {result,events}=await scenario(t,[first(),reply()]);
    assert.equal(result.ok,true);assert.equal(result.requests,2);
    assert.equal(events.find(e=>e.type==='provider-retry').retry_class,'stream-start-error');
  }
});
test('both HTTP attempts share the original request timer',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});
  const configuration=route();configuration.request_timeout_seconds=1;
  const controller=new AbortController();
  let eligible=false, secondStarted=false;
  const waitFor=async predicate=>{
    const until=Date.now()+5000;
    while(!predicate() && Date.now()<until) await realDelay(20);
    assert.ok(predicate(),'fixture must reach the controlled retry stage');
  };
  const {result,payloads,events}=await scenario(t,[
    rateLimit(undefined,{'retry-after-ms':'600'}),
    init=>{
      secondStarted=true;
      return new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>resolve(reply()),600);
        init.signal.addEventListener('abort',()=>{clearTimeout(timer);reject(new Error('aborted'));},{once:true});
      });
    },
  ],{configuration,signal:controller.signal,
    expectedAbort:'request-timeout',advanceCleanupTimers:()=>t.mock.timers.tick(1000),
    onEvent:e=>{if(e.type==='provider-retry'&&e.stage==='eligible')eligible=true;},
    synchronize:async()=>{
      try {
        await waitFor(()=>eligible);
        t.mock.timers.tick(600);
        await waitFor(()=>secondStarted);
        t.mock.timers.tick(401);
        await realDelay(20);
        // A wrongly renewed timer would permit the response at1200ms; the
        // original1000ms timer must already have aborted that fetch.
        t.mock.timers.tick(200);
      } catch(error) {
        controller.abort();t.mock.timers.tick(10000);throw error;
      }
    },
  });
  assert.equal(result.reason,'request-timeout');assert.equal(result.requests,2);
  assert.equal(payloads.length,2);
  assert.deepEqual(events.filter(e=>e.type==='response-complete').map(e=>e.request_id),['request-1','request-2']);
});
test('host deadline also covers provider retry backoff',async t=>{
  // Startup under CI load may exceed the host's work window. Reach the
  // actual eligible backoff first, then advance only the controlled clock.
  t.mock.timers.enable({apis:['setTimeout']});
  const controller=new AbortController();
  let eligible=false, abortReason;
  const {result,payloads,events}=await scenario(t,[rateLimit(undefined,{'retry-after-ms':'4000'}),reply()],{
    timeoutSeconds:2,fixtureStartupDelay:1.6,signal:controller.signal,
    expectedAbort:'host-timeout',advanceCleanupTimers:()=>t.mock.timers.tick(1000),
    onEvent:e=>{if(e.type==='provider-retry'&&e.stage==='eligible')eligible=true;
      if(e.type==='abort')abortReason=e.reason;},
    synchronize:async()=>{
      try {
        const until=Date.now()+10000;
        while(!eligible&&Date.now()<until)await realDelay(20);
        assert.ok(eligible,'fixture must enter actual retry backoff before its deadline tick');
        t.mock.timers.tick(2001);
        assert.equal(abortReason,'host-timeout');
      } finally {
        if(!eligible)controller.abort();
        t.mock.timers.tick(10000);
      }
    },
  });
  assert.equal(result.reason,'host-timeout');assert.equal(payloads.length,1);
  assert.equal(result.requests,1);
  assert.equal(events.filter(e=>e.type==='provider-retry'&&e.stage==='started').length,0);
});
test('a partial provider stream is never retried and cannot dispatch its tool',async t=>{
  const first='data: '+JSON.stringify({choices:[{index:0,delta:{role:'assistant',tool_calls:[{index:0,id:'partial',type:'function',function:{name:'mutate',arguments:'{"mode":"ok"}'}}]},finish_reason:null}]})+'\n\n';
  // Error on the next pull so the partial tool call really is delivered first.
  const {result,payloads,calls}=await scenario(t,[new Response(new ReadableStream({start(c){
    c.enqueue(new TextEncoder().encode(first));
  },pull(c){c.error(new Error('fixture-key private stream failure'));}},{highWaterMark:0}),{headers:{'content-type':'text/event-stream'}}),reply()]);
  assert.equal(result.reason,'provider-error');assert.equal(payloads.length,1);assert.equal(calls.length,0);
});
