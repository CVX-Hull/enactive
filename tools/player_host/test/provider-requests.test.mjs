import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { runHost, validateConfiguration } from '../host.mjs';
import { realDelay, model, route, usageRecord, reply, rateLimit, scenario } from './host-scenario.mjs';

test('provider errors are nonzero without leaking exception or key',async t=>{
  const {result,events}=await scenario(t,[()=>{throw new Error('fixture-key private upstream details');}]);
  assert.equal(result.ok,false); assert.equal(result.reason,'provider-error');
  assert.ok(!JSON.stringify({result,events}).includes('fixture-key'));
});
test('request deadline aborts actual provider stream',async t=>{
  const configuration=route(); configuration.request_timeout_seconds=.05;
  const {result,payloads,events}=await scenario(t,[init=>new Promise((_,reject)=>init.signal.addEventListener('abort',()=>reject(new Error('aborted')),{once:true}))],{configuration});
  assert.equal(result.ok,false); assert.equal(result.reason,'request-timeout');
  // The timer's own fetch rejection is never a retryable pre-header rejection.
  assert.equal(result.requests,1);assert.equal(payloads.length,1);assert.ok(!events.some(e=>e.type==='provider-retry'));
});
test('response diagnostics count UTF8 fragments and reset for each actual request',async t=>{
  const first=reply('é',[['observe',{}]],true,'思'), second=reply('finished');
  const firstBytes=Buffer.byteLength(await first.clone().text()), secondBytes=Buffer.byteLength(await second.clone().text());
  const {result,events}=await scenario(t,[first,second],{onEvent:event=>{
    if(event.type==='response-complete') Object.freeze(event.response_progress);
  }});
  assert.equal(result.ok,true);
  const completed=events.filter(event=>event.type==='response-complete');
  const a=completed[0].response_progress,b=completed[1].response_progress;
  assert.equal(a.request_id,'request-1');assert.equal(b.request_id,'request-2');
  assert.equal(a.body_bytes,firstBytes);assert.equal(b.body_bytes,secondBytes);
  assert.ok(a.body_chunks>0);assert.equal(a.provider_events,2);assert.equal(b.provider_events,2);
  assert.equal(a.content_bytes,2);assert.equal(a.reasoning_bytes,3);assert.equal(a.tool_argument_bytes,2);
  assert.equal(b.content_bytes,8);assert.equal(b.reasoning_bytes,0);
  assert.equal(b.tool_argument_bytes,Buffer.byteLength(JSON.stringify({disposition:'task_complete',report:'finished',source_ids:[],control_id:null})));
  assert.ok(a.last_field_delta_ms<=a.last_provider_event_ms);
  assert.ok(a.last_body_chunk_ms<=completed[0].monotonic_ms);
  assert.equal(a.scope,'current-http-attempt');
  assert.equal(a.first_reasoning_delta_ms,a.first_provider_event_ms);
  assert.equal(a.first_content_delta_ms,a.first_provider_event_ms);
  assert.equal(a.first_tool_argument_delta_ms,a.first_provider_event_ms);
  assert.equal(b.first_reasoning_delta_ms,null);
  assert.equal(a.response_id,'fixture-response');
  assert.ok(events.find(e=>e.type==='provider-payload-ready').sdk_prepare_ms>=0);
  assert.ok(events.find(e=>e.type==='request-start').host_inspection_ms>=0);
  assert.ok(events.find(e=>e.type==='request-fetch-start').monotonic_ms>=events.find(e=>e.type==='request-start').monotonic_ms);
  assert.equal(events.at(-1).event_output.json_ms,null);
  assert.ok(!JSON.stringify(a).includes('思'));
});
test('partial field output and later heartbeat retain diagnostics without renewing the deadline',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});
  const configuration=route();configuration.request_timeout_seconds=1;
  const controller=new AbortController();let body,parsed=false;
  const argumentsText='{"mode":"ok"}', content='private π';
  const first='data: '+JSON.stringify({model:'fixture-stream',choices:[{index:0,delta:{role:'assistant',content,
    tool_calls:[{index:0,id:'partial',type:'function',function:{name:'mutate',arguments:argumentsText}}]},finish_reason:null}]})+'\n\n';
  const heartbeat=': keepalive\n\n';
  const {result,events,payloads,calls}=await scenario(t,[init=>new Response(new ReadableStream({start(c){
    body=c;c.enqueue(new TextEncoder().encode(first));
    init.signal.addEventListener('abort',()=>c.error(new Error('aborted')),{once:true});
  }}),{headers:{'content-type':'text/event-stream'}})],{configuration,signal:controller.signal,
    expectedAbort:'request-timeout',advanceCleanupTimers:()=>t.mock.timers.tick(1000),
    onEvent:event=>{if(event.type==='response-backend')parsed=true;},
    synchronize:async()=>{
      try {
        const until=Date.now()+5000;
        while(!parsed&&Date.now()<until)await realDelay(20);
        assert.ok(parsed);t.mock.timers.tick(400);
        body.enqueue(new TextEncoder().encode(heartbeat));await realDelay(20);
        t.mock.timers.tick(601);
      } catch(error) {controller.abort();t.mock.timers.tick(10000);throw error;}
    },
  });
  assert.equal(result.reason,'request-timeout');assert.equal(payloads.length,1);assert.equal(calls.length,0);
  const progress=events.find(event=>event.type==='abort').response_progress;
  assert.equal(progress.scope,'current-http-attempt');assert.equal(progress.request_id,'request-1');
  assert.ok(progress.first_tool_argument_delta_ms!==null);
  assert.ok(progress.first_content_delta_ms!==null);
  assert.ok(progress.last_body_chunk_ms>progress.last_field_delta_ms);
  assert.ok(progress.max_body_chunk_gap_ms>0);
  assert.equal(progress.body_bytes,Buffer.byteLength(first+heartbeat));assert.equal(progress.body_chunks,2);
  assert.equal(progress.provider_events,1);assert.equal(progress.content_bytes,Buffer.byteLength(content));
  assert.equal(progress.tool_argument_bytes,Buffer.byteLength(argumentsText));
  assert.ok(progress.last_body_chunk_ms>progress.last_field_delta_ms);
  assert.ok(!JSON.stringify(progress).includes(content));assert.ok(!JSON.stringify(progress).includes(argumentsText));
});
test('diagnostics skip unsupported choice collections just as the pinned parser does',async t=>{
  const unsupported=[{model:'fixture-backend',choices:{}},123].map(chunk=>'data: '+JSON.stringify(chunk)+'\n\n').join('');
  const valid=await reply('ok').text();
  const {result,events}=await scenario(t,[new Response(unsupported+valid,{headers:{'content-type':'text/event-stream'}})]);
  assert.equal(result.ok,true);assert.equal(result.finalText,'ok');
  const progress=events.find(event=>event.type==='response-complete').response_progress;
  assert.equal(progress.provider_events,4);assert.equal(progress.content_bytes,2);
});
test('diagnostic reasoning bytes follow first nonempty alias without counting duplicates',async t=>{
  const chunks=[{choices:[{index:0,delta:{role:'assistant',reasoning_content:'',reasoning:'思',reasoning_text:'duplicate'},finish_reason:null}]},
    {choices:[{index:0,delta:{reasoning_content:'ρ',reasoning:'ρ'},finish_reason:null}]},
    {choices:[{index:0,delta:{reasoning_text:'z',content:'ok'},finish_reason:'stop'}],usage:usageRecord}];
  const body=chunks.map(chunk=>'data: '+JSON.stringify(chunk)+'\n\n').join('')+'data: [DONE]\n\n';
  const {result,events}=await scenario(t,[new Response(body,{headers:{'content-type':'text/event-stream'}}),reply('ok')]);
  assert.equal(result.ok,true);assert.equal(result.finalText,'ok');
  const progress=events.find(event=>event.type==='response-complete').response_progress;
  assert.equal(progress.reasoning_bytes,6);assert.equal(progress.content_bytes,2);assert.equal(progress.provider_events,3);
});
test('abort diagnostics remain unavailable before any actual HTTP attempt',async()=>{
  const events=[];
  const result=await runHost({configuration:{},model:'fixture',effort:'off',timeoutSeconds:5,
    onEvent:event=>events.push(event),fetch:()=>{throw new Error('No provider call allowed');}});
  assert.equal(result.ok,false);assert.equal(result.requests,0);
  assert.equal(events.find(event=>event.type==='abort').response_progress,null);
});
test('rate-limit diagnostic snapshots remain isolated from retry response counters',async t=>{
  const refusal=rateLimit(), refusalBytes=Buffer.byteLength(await refusal.clone().text());
  const {result,events,payloads}=await scenario(t,[refusal,reply('ok')]);
  assert.equal(result.ok,true);assert.deepEqual(payloads[0],payloads[1]);
  const [a,b]=events.filter(event=>event.type==='response-complete').map(event=>event.response_progress);
  assert.equal(a.request_id,'request-1');assert.equal(a.body_bytes,refusalBytes);assert.equal(a.provider_events,0);
  assert.equal(a.last_field_delta_ms,null);assert.equal(b.request_id,'request-2');
  assert.equal(b.provider_events,2);assert.equal(b.content_bytes,2);
  assert.equal(b.tool_argument_bytes,Buffer.byteLength(JSON.stringify({disposition:'task_complete',report:'ok',source_ids:[],control_id:null})));
});
test('host deadline interrupts an actually started tool and closes its child',async t=>{
  // Real initialization cannot consume the controlled deadline. The outer
  // Python watchdog and this real-timer poll still bound a broken fixture.
  t.mock.timers.enable({apis:['setTimeout']});
  const controller=new AbortController();
  const {result,calls}=await scenario(t,[reply(null,[['mutate',{mode:'wait'}]])],{
    timeoutSeconds:10,fixtureToolTimeoutSeconds:30,signal:controller.signal,
    expectedAbort:'host-timeout',advanceCleanupTimers:()=>t.mock.timers.tick(1000),
    synchronize:async({log})=>{
      let started=false;
      try {
        const deadline=Date.now()+10000;
        while(Date.now()<deadline) {
          let recorded=[];
          try { recorded=(await readFile(log,'utf8')).trim().split('\n').filter(Boolean).map(JSON.parse); }
          catch(error) { if(error.code!=='ENOENT') throw error; }
          if(recorded.some(call=>call.tool==='mutate'&&call.phase==='start')) {started=true;break;}
          await realDelay(20);
        }
        assert.ok(started,'fixture tool must start before advancing its host deadline');
      } finally {
        if(!started) controller.abort();
        // Advance the host work/cleanup window before the 30s MCP tool wait.
        t.mock.timers.tick(10000);
      }
    },
  });
  assert.equal(result.ok,false);assert.equal(result.reason,'host-timeout');
  assert.deepEqual(calls.map(call=>[call.tool,call.phase]),[['mutate','start']]);
});
test('cancellation aborts provider and closes real child',async t=>{
  const controller=new AbortController();
  const {result}=await scenario(t,[init=>{setTimeout(()=>controller.abort(),20);return new Promise((_,reject)=>init.signal.addEventListener('abort',()=>reject(new Error('aborted')),{once:true}));}],{signal:controller.signal});
  assert.equal(result.ok,false); assert.equal(result.reason,'cancelled');
});

test('declared reasoning mapping is sent without clamping',async t=>{
  const configuration=route();configuration.model.reasoning=true;
  configuration.model.thinkingLevelMap={max:'high',off:'none'};
  configuration.model.compat.supportsReasoningEffort=true;configuration.model.compat.thinkingFormat='openai';
  const {result,payloads}=await scenario(t,[reply()],{configuration,effort:'max'});
  assert.equal(result.ok,true);assert.equal(payloads[0].reasoning_effort,'high');
  assert.throws(()=>validateConfiguration(configuration,model.id,'xhigh'));
  delete configuration.model.compat.thinkingFormat;
  assert.throws(()=>validateConfiguration(configuration,model.id,'max'));
});
test('known MCP error permits a deliberate next tool decision with original collection retained',async t=>{
  const {result,calls,payloads}=await scenario(t,[reply(null,[['observe',{fail:true}]]),reply(null,[['integer',{value:7}]]),reply()]);
  assert.equal(result.ok,true);assert.deepEqual(calls.map(call=>call.tool),['observe','integer']);
  assert.ok(JSON.stringify(payloads[1]).includes('original_collection'));
  assert.ok(JSON.stringify(payloads[2]).includes('original_collection'));
});

test('frozen output cap reaches providers using the max_tokens compatibility field',async t=>{
  const configuration=route();configuration.model.maxTokens=128;
  configuration.model.compat.maxTokensField='max_tokens';
  const {result,payloads}=await scenario(t,[reply()],{configuration});
  assert.equal(result.ok,true);assert.equal(payloads[0].max_tokens,128);
  assert.equal(payloads[0].max_completion_tokens,undefined);
});

test('absent provider usage remains unknown instead of zero, and the unpriced response ends the run',async t=>{
  const {result,events,calls}=await scenario(t,[reply(null,[['observe',{}]],false),reply()]);
  assert.equal(result.ok,false);assert.equal(result.reason,'cost-unreported');assert.equal(result.requests,1);
  assert.equal(calls.length,0,'no tool is dispatched from a response the host cannot price');
  const completed=events.find(event=>event.type==='response-complete');
  assert.equal(completed.usage_available,false);assert.equal(completed.usage,null);assert.equal(completed.cost_source,null);
});
test('HTTP refusal status is retained before SDK rejection without raw error or invented usage',async t=>{
  const {result,events}=await scenario(t,[new Response(JSON.stringify({error:{message:'fixture-key private provider detail'}}),{status:403,headers:{'content-type':'application/json'}})]);
  assert.equal(result.ok,false);assert.equal(result.reason,'provider-error');
  assert.deepEqual(events.filter(event=>event.type==='response-headers').map(event=>event.status),[403]);
  const completed=events.find(event=>event.type==='response-complete');
  assert.equal(completed.usage_available,false);assert.equal(completed.usage,null);
  assert.ok(!JSON.stringify({result,events}).includes('fixture-key'));
});
test('nonretryable HTTP400 retains bounded normalized identifiers and never retries or logs raw detail',async t=>{
  const {result,events,payloads}=await scenario(t,[new Response(JSON.stringify({error:{code:400,
    message:'fixture-key private validation detail',metadata:{error_type:'invalid_request_error',
      provider_code:'invalid_parameter',limit_source:'fixture-key'}}}),{status:400})]);
  assert.equal(result.reason,'provider-error');assert.equal(result.requests,1);assert.equal(payloads.length,1);
  const refusal=events.find(e=>e.type==='provider-refusal');
  assert.equal(refusal.status,400);assert.equal(refusal.error_code,'400');
  assert.equal(refusal.error_type,'invalid_request_error');assert.equal(refusal.provider_error_code,'invalid_parameter');
  assert.equal(refusal.limit_source,null);assert.ok(!JSON.stringify({result,events}).includes('fixture-key'));
  assert.equal(events.some(e=>e.type==='provider-retry'),false);
});

test('inspected refusal and provider identities retain bounded IDs without raw text or credentials',async t=>{
  const {result,events}=await scenario(t,[rateLimit({type:'invalid_request_error',code:'engine_overloaded',message:'fixture-key private detail'})]);
  assert.equal(result.reason,'provider-error');assert.equal(result.requests,1);
  const refusal=events.find(e=>e.type==='provider-refusal');
  assert.equal(refusal.error_type,'invalid_request_error');assert.equal(refusal.error_code,'engine_overloaded');
  assert.ok(!JSON.stringify(events).includes('fixture-key'));
  const bad=new Response('data: '+JSON.stringify({id:'fixture-key',provider:'fixture-key',choices:[{index:0,delta:{content:'ok'},finish_reason:'stop'}],usage:usageRecord})+'\n\ndata: [DONE]\n\n',
    {headers:{'content-type':'text/event-stream','x-request-id':'fixture-key'}});
  const observed=await scenario(t,[bad,reply()]);
  assert.equal(observed.result.ok,true);
  assert.equal(observed.events.find(e=>e.type==='response-headers').provider_request_id,null);
  const progress=observed.events.find(e=>e.type==='response-complete').response_progress;
  assert.equal(progress.response_id,null);assert.equal(progress.reported_provider,null);
  assert.ok(!JSON.stringify(observed.events).includes('fixture-key'));
});

test('provider attempt and time countdowns are absent from model context',async t=>{
  const {result,payloads,events}=await scenario(t,[reply(null,[['observe',{}]]),reply()]);
  assert.equal(result.ok,true);
  assert.equal(events.filter(event=>event.type==='context-estimate').length,2);
  for(const payload of payloads) {
    for(const marker of ['Host resource status','Remaining allowance','Host decision time remaining','Actual provider HTTP attempts'])
      assert.ok(!JSON.stringify(payload).includes(marker));
  }
});
