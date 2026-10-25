import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { runHost, validateConfiguration, validateMcpConfiguration, INPUT_LIMIT_BYTES } from '../host.mjs';

const realSetTimeout = globalThis.setTimeout;
const realDelay = ms => new Promise(resolve=>realSetTimeout(resolve,ms));
const python = process.env.ENACTIVE_TEST_PYTHON;
const fixture = fileURLToPath(new URL('server.py', import.meta.url));
const png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ioAAAAASUVORK5CYII=';
const model = { id: 'fixture-model', name: 'Offline fixture', api: 'openai-completions', provider: 'fixture', baseUrl: 'https://fixture.invalid/v1', reasoning: false, input: ['text', 'image'], cost: {input:0, output:0, cacheRead:0, cacheWrite:0}, contextWindow: 100000, maxTokens: 1024, compat: { supportsDeveloperRole:false, supportsStore:false, supportsUsageInStreaming:true } };
const route = () => ({schema:'pi-player-host/1', model:structuredClone(model), api_key_env:'OFFLINE_TEST_KEY', max_requests:4, request_timeout_seconds:2});
function reply(content = 'finished', calls = [], withUsage = true, reasoning) {
  const delta = {role:'assistant', ...(content === null ? {} : {content}), ...(reasoning ? {reasoning_content:reasoning} : {}), ...(calls.length ? {tool_calls:calls.map(([name,args],index)=>({index,id:`call-${index}`,type:'function',function:{name,arguments:JSON.stringify(args)}}))} : {})};
  const chunks = [{id:'fixture-response',model:'fixture-backend',choices:[{index:0,delta,finish_reason:null}]},
    {id:'fixture-response',model:'fixture-backend',choices:[{index:0,delta:{},finish_reason:calls.length?'tool_calls':'stop'}],...(withUsage ? {usage:{prompt_tokens:11,completion_tokens:5,total_tokens:16}} : {})}];
  return new Response(chunks.map(chunk=>'data: '+JSON.stringify(chunk)+'\n\n').join('')+'data: [DONE]\n\n', {headers:{'content-type':'text/event-stream'}});
}
async function scenario(t, sequence, overrides = {}) {
  assert.ok(python, 'Set ENACTIVE_TEST_PYTHON to a Python with the official mcp package');
  const dir = await mkdtemp(join(tmpdir(),'pi-host-test-'));
  t.after(()=>rm(dir,{recursive:true,force:true}));
  const log = join(dir,'calls.jsonl'), pid = join(dir,'pid');
  const payloads = [], events = [];
  let index = 0;
  const fetch = async (_url, init) => {
    payloads.push(JSON.parse(init.body));
    const item = sequence[index++];
    return typeof item === 'function' ? item(init) : item;
  };
  const mcpConfig = {command:resolve(python),args:[fixture,log,pid],cwd:dir,enabled:true,required:true,enabled_tools:['observe','mutate','integer'],startup_timeout_sec:5,tool_timeout_sec:2,default_tools_approval_mode:'never',tools:{}};
  const options = {configuration:route(), mcpConfig, context:'Frozen player guide', prompt:'Offline mission', model:model.id, effort:'off', timeoutSeconds:10, env:{OFFLINE_TEST_KEY:'fixture-key', UNRELATED_HOST_SECRET:'must-not-inherit'}, fetch, onEvent:event=>events.push(event), ...overrides};
  if (overrides.fixtureStartupDelay !== undefined) mcpConfig.args.push(String(overrides.fixtureStartupDelay));
  if (overrides.enabledTools) mcpConfig.enabled_tools=overrides.enabledTools;
  if (overrides.fixtureToolTimeoutSeconds) mcpConfig.tool_timeout_sec=overrides.fixtureToolTimeoutSeconds;
  const running = runHost(options);
  try { await overrides.synchronize?.({log}); }
  catch (error) { await running; throw error; }
  const result = await running;
  let calls=[]; try { calls=(await readFile(log,'utf8')).trim().split('\n').filter(Boolean).map(JSON.parse); } catch {}
  const childPid = Number(await readFile(pid,'utf8'));
  assert.throws(()=>process.kill(childPid,0), {code:'ESRCH'}, 'owned MCP child must exit before settlement');
  return {result,payloads,events,calls};
}
test('route is closed, graphical, finite and model/effort exact', ()=>{
  assert.doesNotThrow(()=>validateConfiguration(route(),model.id,'off'));
  for (const change of [{schema:'old'}, {unknown:true}, {max_requests:Infinity}, {api_key_env:'bad-key'}, {model:{...model,input:['text']}}, {model:{...model,headers:{authorization:'secret'}}}]) {
    assert.throws(()=>validateConfiguration({...route(),...change},model.id,'off'));
  }
  assert.throws(()=>validateConfiguration(route(),'other','off'));
  assert.throws(()=>validateConfiguration(route(),model.id,'low'));
});
for (const fail of [false,true]) test(`actual provider payload preserves full text, PNG and known error=${fail}`, async t=>{
  const {result,payloads,events,calls} = await scenario(t,[reply(null,[['observe',{fail}]]),reply()]);
  assert.equal(result.ok,true);
  assert.equal(calls.length,1);
  assert.deepEqual(payloads[0].tools.map(t=>t.function.name), ['observe','mutate','integer']);
  assert.equal(payloads[0].tools[2].function.parameters.properties.value.type,'integer');
  assert.equal(payloads[0].max_completion_tokens,model.maxTokens);
  const serialized = JSON.stringify(payloads[1]);
  assert.ok(serialized.includes('x'.repeat(30001)));
  assert.ok(serialized.includes(`data:image/png;base64,${png}`));
  assert.ok(serialized.includes('original_collection'));
  const text = payloads[1].messages.filter(m=>m.role==='tool').map(m=>m.content).join('\n');
  assert.equal(text.includes('MCP isError: true'),fail);
  assert.equal(text.split('original_collection').length,2, 'structured content must not duplicate text');
  assert.equal(events.find(e=>e.type==='tool-result').result.isError,fail);
  assert.equal(events.filter(e=>e.type==='request-start').length,2);
  assert.deepEqual(events.filter(e=>e.type==='request-start').map(e=>e.payload),payloads,
    'retained request JSON must match actual provider bodies, including schemas, history and images');
  assert.ok(events.every(e=>typeof e.monotonic_ms==='number' && typeof e.wall_time==='string'));
  assert.ok(!JSON.stringify(events).includes('fixture-key'));
  assert.equal(events.find(event=>event.type==='response-backend').backend_model,'fixture-backend');
  const {payload,...secondRequest}=events.filter(event=>event.type==='request-start')[1];
  t.diagnostic(JSON.stringify({sample:'offline-synthetic-SSE+official-MCP',requests:result.requests,host_ms:events.at(-1).monotonic_ms,second_request_content:secondRequest}));
});
test('coerced arguments are refused with zero dispatch, then deliberate correction succeeds',async t=>{
  const {result,calls,payloads,events}=await scenario(t,[reply(null,[['integer',{value:'3'}]]),reply(null,[['integer',{value:3}]]),reply()]);
  assert.equal(result.ok,true);
  assert.deepEqual(calls,[{tool:'integer',value:3}]);
  assert.ok(JSON.stringify(payloads[1]).includes('MCP input not sent'));
  assert.equal(events.filter(event=>event.type==='tool-refused').length,1);
});
test('request trace retains actual forwarded assistant reasoning without transport secrets',async t=>{
  const reasoning='Retained synthetic reasoning before an observation.';
  const {result,payloads,events}=await scenario(t,[reply(null,[['observe',{fail:false}]],true,reasoning),reply()]);
  assert.equal(result.ok,true);
  const trace=events.filter(e=>e.type==='request-start');
  assert.deepEqual(trace.map(e=>e.payload),payloads);
  assert.equal(trace[1].payload.messages.find(m=>m.role==='assistant').reasoning_content,reasoning);
  assert.ok(!JSON.stringify(trace).includes('fixture-key'));
  assert.ok(!JSON.stringify(trace).includes('UNRELATED_HOST_SECRET'));
});
test('optional null normalization is refused without dispatch',async t=>{
  const {result,calls,events}=await scenario(t,[reply(null,[['mutate',{mode:'ok',index:null}]]),reply()]);
  assert.equal(result.ok,true);assert.equal(calls.length,0);
  assert.equal(events.find(event=>event.type==='tool-refused').reason,'tool-arguments-changed');
});
test('sequential batches retain ordering and isolate child environment',async t=>{
  const {result,calls}=await scenario(t,[reply(null,[['mutate',{mode:'ok',index:1}],['mutate',{mode:'ok',index:2}]]),reply()]);
  assert.equal(result.ok,true);
  assert.deepEqual(calls.map(c=>[c.index,c.phase]),[[1,'start'],[1,'end'],[2,'start'],[2,'end']]);
  assert.equal(calls[0].secret_inherited,false);
});
test('transport loss suppresses queued mutation and subsequent inference',async t=>{
  const {result,calls,payloads}=await scenario(t,[reply(null,[['mutate',{mode:'drop',index:1}],['mutate',{mode:'ok',index:2}]]),reply()]);
  assert.equal(result.ok,false);
  assert.equal(payloads.length,1);
  assert.deepEqual(calls.map(c=>c.index),[1]);
});
test('request maximum is finite and exits unsuccessful if continuation needed',async t=>{
  const configuration=route(); configuration.max_requests=1;
  const {result,payloads}=await scenario(t,[reply(null,[['observe',{}]]),reply()],{configuration});
  assert.equal(result.ok,false); assert.equal(result.reason,'request-limit'); assert.equal(payloads.length,1);
});
test('provider errors are nonzero without leaking exception or key',async t=>{
  const {result,events}=await scenario(t,[()=>{throw new Error('fixture-key private upstream details');}]);
  assert.equal(result.ok,false); assert.equal(result.reason,'provider-error');
  assert.ok(!JSON.stringify({result,events}).includes('fixture-key'));
});
test('request deadline aborts actual provider stream',async t=>{
  const configuration=route(); configuration.request_timeout_seconds=.05;
  const {result}=await scenario(t,[init=>new Promise((_,reject)=>init.signal.addEventListener('abort',()=>reject(new Error('aborted')),{once:true}))],{configuration});
  assert.equal(result.ok,false); assert.equal(result.reason,'request-timeout');
});
test('host deadline interrupts an actually started tool and closes its child',async t=>{
  // Real initialization cannot consume the controlled deadline. The outer
  // Python watchdog and this real-timer poll still bound a broken fixture.
  t.mock.timers.enable({apis:['setTimeout']});
  const controller=new AbortController();
  const {result,calls}=await scenario(t,[reply(null,[['mutate',{mode:'wait'}]])],{
    timeoutSeconds:10,fixtureToolTimeoutSeconds:30,signal:controller.signal,
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

test('frozen MCP config rejects disabled and malformed fields', ()=>{
  const valid={command:'python',args:[],cwd:'/',enabled:true,enabled_tools:['observe'],startup_timeout_sec:1,tool_timeout_sec:1};
  assert.doesNotThrow(()=>validateMcpConfiguration(valid));
  for (const change of [{enabled:false},{required:'yes'},{args:'bad'},{enabled_tools:['observe','observe']},{tool_timeout_sec:NaN},{tools:{observe:false}},{ambient:1}]) {
    assert.throws(()=>validateMcpConfiguration({...valid,...change}));
  }
});

test('real production MCP discovery forwards exact current nested schemas only', async ()=>{
  const { execFile } = await import('node:child_process');
  const { promisify } = await import('node:util');
  const root=fileURLToPath(new URL('../../../',import.meta.url));
  const {stdout}=await promisify(execFile)(python,['-c','import json; from harness.player_tools import tool_specs; print(json.dumps({s.name:s.schema for s in tool_specs()}))'],{cwd:root,maxBuffer:INPUT_LIMIT_BYTES});
  const expected=JSON.parse(stdout), payloads=[], events=[];
  const chosen=['enactive_skill','enactive_result','enactive_snapshot'];
  const result=await runHost({configuration:route(),mcpConfig:{command:resolve(python),args:['-m','harness.player_mcp'],cwd:root,enabled:true,enabled_tools:chosen,startup_timeout_sec:5,tool_timeout_sec:1},context:'Frozen context',prompt:'Do not call tools.',model:model.id,effort:'off',timeoutSeconds:10,env:{OFFLINE_TEST_KEY:'fixture-key'},fetch:async(_url,init)=>{payloads.push(JSON.parse(init.body));return reply();},onEvent:e=>events.push(e)});
  assert.equal(result.ok,true);
  assert.deepEqual(payloads[0].tools.map(tool=>tool.function.name),chosen);
  for(const tool of payloads[0].tools) assert.deepEqual(tool.function.parameters,expected[tool.function.name]);
  assert.ok(payloads[0].messages[0].content.includes('Software assigns request IDs'));
  assert.throws(()=>process.kill(events.find(e=>e.type==='mcp-connected').child_pid,0),{code:'ESRCH'});
});

test('transport onError latches immediately before any pending-call rejection',async t=>{
  const {result,calls,payloads}=await scenario(t,[reply(null,[['mutate',{mode:'malformed',index:1}],['mutate',{mode:'ok',index:2}]]),reply()]);
  assert.equal(result.ok,false);assert.equal(result.reason,'mcp-transport-error');
  assert.deepEqual(calls.map(call=>call.index),[1]);assert.equal(payloads.length,1);
});
test('host deadline covers stalled MCP initialization and closes child',async t=>{
  const {result,payloads}=await scenario(t,[reply()],{timeoutSeconds:1,fixtureStartupDelay:30});
  assert.equal(result.ok,false);assert.equal(result.reason,'host-timeout');assert.equal(payloads.length,0);
});
test('missing allowlisted tool fails before provider call and closes child',async t=>{
  const {result,payloads}=await scenario(t,[reply()],{enabledTools:['missing_tool']});
  assert.equal(result.ok,false);assert.equal(result.reason,'missing-required-tools');assert.equal(payloads.length,0);
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

test('absent provider usage remains unknown instead of zero',async t=>{
  const {result,events}=await scenario(t,[reply('finished',[],false)]);
  assert.equal(result.ok,true);
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
