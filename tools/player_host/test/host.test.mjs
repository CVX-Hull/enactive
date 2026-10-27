import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { runHost, validateConfiguration, validateMcpConfiguration, projectImageContext, INPUT_LIMIT_BYTES } from '../host.mjs';

const realSetTimeout = globalThis.setTimeout;
const realDelay = ms => new Promise(resolve=>realSetTimeout(resolve,ms));
const python = process.env.ENACTIVE_TEST_PYTHON;
const fixture = fileURLToPath(new URL('server.py', import.meta.url));
const png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ioAAAAASUVORK5CYII=';
const model = { id: 'fixture-model', name: 'Offline fixture', api: 'openai-completions', provider: 'fixture', baseUrl: 'https://fixture.invalid/v1', reasoning: false, input: ['text', 'image'], cost: {input:0, output:0, cacheRead:0, cacheWrite:0}, contextWindow: 100000, maxTokens: 1024, compat: { supportsDeveloperRole:false, supportsStore:false, supportsUsageInStreaming:true } };
const route = () => ({schema:'pi-player-host/2', model:structuredClone(model), api_key_env:'OFFLINE_TEST_KEY', max_requests:4, max_context_images:4, request_timeout_seconds:2});
function reply(content = 'finished', calls = [], withUsage = true, reasoning, callPrefix = 'call') {
  const delta = {role:'assistant', ...(content === null ? {} : {content}), ...(reasoning ? {reasoning_content:reasoning} : {}), ...(calls.length ? {tool_calls:calls.map(([name,args],index)=>({index,id:`${callPrefix}-${index}`,type:'function',function:{name,arguments:JSON.stringify(args)}}))} : {})};
  const chunks = [{id:'fixture-response',model:'fixture-backend',choices:[{index:0,delta,finish_reason:null}]},
    {id:'fixture-response',model:'fixture-backend',choices:[{index:0,delta:{},finish_reason:calls.length?'tool_calls':'stop'}],...(withUsage ? {usage:{prompt_tokens:11,completion_tokens:5,total_tokens:16}} : {})}];
  return new Response(chunks.map(chunk=>'data: '+JSON.stringify(chunk)+'\n\n').join('')+'data: [DONE]\n\n', {headers:{'content-type':'text/event-stream'}});
}
function rateLimit(error = {type:'rate_limit_error', message:'Rate limit exceeded'}, headers = {}) {
  return new Response(JSON.stringify({error}), {status:429,
    headers:{'content-type':'application/json', 'retry-after-ms':'0', ...headers}});
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
  const options = {configuration:route(), mcpConfig, context:'Frozen player guide', prompt:'Offline mission', model:model.id, effort:'off', timeoutSeconds:10, env:{OFFLINE_TEST_KEY:'fixture-key', UNRELATED_HOST_SECRET:'must-not-inherit'}, fetch, ...overrides,
    onEvent:event=>{events.push(event);overrides.onEvent?.(event);}};
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
  assert.throws(()=>validateConfiguration({...route(),schema:'pi-player-host/1'},model.id,'off'));
  for (const value of [undefined,0,-1,1.5,true,'2',NaN,Infinity,Number.MAX_SAFE_INTEGER+1]) {
    assert.throws(()=>validateConfiguration({...route(),max_context_images:value},model.id,'off'));
  }
  const missing=route();delete missing.max_context_images;
  assert.throws(()=>validateConfiguration(missing,model.id,'off'));
});

test('image projection copies canonical messages and protects the entire latest tool batch',()=>{
  const image={type:'image',mimeType:'image/png',data:png};
  const messages=[{role:'assistant',content:[{type:'toolCall',id:'old',name:'observe',arguments:{}}]},
    {role:'toolResult',toolCallId:'old',content:[image,{type:'text',text:'source-old'}]},
    {role:'assistant',content:[{type:'thinking',thinking:'keep reasoning'},
      {type:'toolCall',id:'current-image',name:'observe',arguments:{}},
      {type:'toolCall',id:'current-text',name:'integer',arguments:{value:1}}]},
    {role:'toolResult',toolCallId:'current-image',content:[image]},
    {role:'toolResult',toolCallId:'current-text',content:[{type:'text',text:'source-current'}]}];
  const original=structuredClone(messages);
  const freeze=value=>{if(value && typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}};
  freeze(messages);
  const projected=projectImageContext(messages,1);
  assert.deepEqual(messages,original);
  assert.notEqual(projected.messages,messages);
  assert.notEqual(projected.messages[3].content,messages[3].content);
  assert.deepEqual(projected.messages.slice(2),original.slice(2));
  assert.equal(projected.summary.protected_images,1);
  assert.equal(projected.summary.omitted_images,1);
  const marker=projected.messages[1].content[0];
  assert.equal(marker.type,'text');
  assert.ok(marker.text.includes('toolCallId=old'));
  assert.ok(marker.text.includes('image_index=0'));
  assert.ok(marker.text.includes(createHash('sha256').update(Buffer.from(png,'base64')).digest('hex')));
  assert.ok(marker.text.includes('no authority'));
});

test('projection omits individual historical images and bounds provenance previews',()=>{
  const images=Array.from({length:20},(_,index)=>({type:'image',mimeType:'image/png',
    data:Buffer.from(`historical-${index}`).toString('base64')}));
  const messages=[{role:'assistant',content:[{type:'toolCall',id:'history',name:'observe',arguments:{}}]},
    {role:'toolResult',toolCallId:'history',content:[{type:'text',text:'keep source-history'},...images]},
    {role:'assistant',content:[{type:'toolCall',id:'current',name:'integer',arguments:{value:1}}]},
    {role:'toolResult',toolCallId:'current',content:[{type:'text',text:'current result'}]}];
  const projected=projectImageContext(messages,2);
  assert.equal(projected.summary.omitted_images,18);
  assert.equal(projected.summary.omissions.length,16);
  assert.equal(projected.summary.omitted_provenance_entries,2);
  assert.equal(projected.messages[1].content[0].text,'keep source-history');
  assert.ok(projected.messages[1].content[18].text.includes('image_index=17'));
  assert.deepEqual(projected.messages[1].content.slice(-2),images.slice(-2));
  assert.deepEqual(messages[1].content.slice(1),images);
});

test('actual serializer caps newest history images while retaining text, reasoning, pairs and original traces',async t=>{
  const configuration=route();configuration.max_context_images=2;
  const reasoning='Full historical reasoning is retained.';
  const {result,payloads,events,calls}=await scenario(t,[
    reply(null,[['observe',{}],['observe',{}]],true,reasoning,'old'),
    reply(null,[['observe',{}],['integer',{value:7}]],true,reasoning,'current'),
    reply(null,[['observe',{}]],true,reasoning,'newest'),reply()],{configuration});
  assert.equal(result.ok,true);assert.equal(result.requests,4);assert.equal(calls.length,5);
  const imageCount=payload=>payload.messages.flatMap(message=>Array.isArray(message.content)?message.content:[])
    .filter(part=>part.type==='image_url').length;
  assert.deepEqual(payloads.map(imageCount),[0,2,2,2]);
  for(const payload of payloads.slice(2)) {
    const assistants=payload.messages.filter(message=>message.role==='assistant');
    const callIds=assistants.flatMap(message=>message.tool_calls?.map(call=>call.id)??[]);
    assert.deepEqual(payload.messages.filter(message=>message.role==='tool').map(message=>message.tool_call_id),callIds);
    assert.ok(assistants.every(message=>message.reasoning_content===reasoning));
    assert.equal(JSON.stringify(payload).split('x'.repeat(30001)).length-1,callIds.length-1);
    assert.ok(JSON.stringify(payload).includes('source-1'));
  }
  const thirdTools=payloads[2].messages.filter(message=>message.role==='tool');
  assert.ok(thirdTools[0].content.includes('toolCallId=old-0'));
  assert.ok(!thirdTools[1].content.includes('Historical pixels omitted'));
  assert.ok(!thirdTools[2].content.includes('Historical pixels omitted'));
  assert.equal(thirdTools.at(-1).tool_call_id,'current-1');
  const projections=events.filter(event=>event.type==='context-image-projection');
  assert.deepEqual(projections.map(event=>event.omitted_images),[0,0,1,2]);
  assert.equal(projections[2].protected_images,1,'text-only last result must not hide current batch images');
  assert.deepEqual(projections[3].omissions.map(item=>item.tool_call_id),['old-0','old-1']);
  const originalResults=events.filter(event=>event.type==='tool-result' && event.tool==='observe');
  assert.equal(originalResults.length,4);
  assert.ok(originalResults.every(event=>event.result.content.some(part=>part.type==='image' && part.data===png)));
  assert.ok(originalResults.every(event=>!JSON.stringify(event).includes('Historical pixels omitted')));
  assert.deepEqual(events.filter(event=>event.type==='request-start').map(event=>event.payload),payloads);
  assert.equal(events.find(event=>event.type==='host-start').max_context_images,2);
});

test('oversized current batch stops without charging or sending its next request',async t=>{
  const configuration=route();configuration.max_context_images=1;
  const {result,payloads,events,calls}=await scenario(t,[
    reply(null,[['observe',{}],['observe',{}],['integer',{value:9}]],true,undefined,'oversized'),
    reply(null,[['mutate',{mode:'ok',index:99}]],true,undefined,'never-sent')],{configuration});
  assert.equal(result.ok,false);assert.equal(result.reason,'context-image-limit');
  assert.equal(result.requests,1);assert.equal(payloads.length,1);
  assert.deepEqual(calls.map(call=>call.tool),['observe','observe','integer']);
  assert.equal(events.filter(event=>event.type==='request-start').length,1);
  const projection=events.filter(event=>event.type==='context-image-projection').at(-1);
  assert.equal(projection.protected_images,2);assert.equal(projection.blocked,true);
  assert.equal(projection.omitted_images,0);
  assert.ok(!events.some(event=>event.type==='tool-start' && event.tool==='mutate'));
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
  const {stdout}=await promisify(execFile)(python,['-c','import json; from harness.player_tools import tool_specs; print(json.dumps({s.name:{"schema":s.schema,"description":s.description} for s in tool_specs()}))'],{cwd:root,maxBuffer:INPUT_LIMIT_BYTES});
  const expected=JSON.parse(stdout), payloads=[], events=[];
  // The current deciding profile excludes lead admission and the advisory role.
  const chosen=Object.keys(expected).filter(name=>name!=='enactive_start'&&!name.startsWith('enactive_reflect_'));
  assert.equal(chosen.length,16);
  const context=await readFile(join(root,'docs/player-guide.md'),'utf8');
  const result=await runHost({configuration:route(),mcpConfig:{command:resolve(python),args:['-m','harness.player_mcp'],cwd:root,enabled:true,enabled_tools:chosen,startup_timeout_sec:5,tool_timeout_sec:1},context,prompt:'Do not call tools.',model:model.id,effort:'off',timeoutSeconds:10,env:{OFFLINE_TEST_KEY:'fixture-key'},fetch:async(_url,init)=>{payloads.push(JSON.parse(init.body));return reply();},onEvent:e=>events.push(e)});
  assert.equal(result.ok,true);
  assert.deepEqual(payloads[0].tools.map(tool=>tool.function.name),chosen);
  for(const tool of payloads[0].tools) {
    assert.deepEqual(tool.function.parameters,expected[tool.function.name].schema);
    assert.equal(tool.function.description,expected[tool.function.name].description);
  }
  const skill=payloads[0].tools.find(tool=>tool.function.name==='enactive_skill').function;
  const published=JSON.parse(skill.description.split('\nProgram result schema: ')[1].split('\n')[0]);
  assert.deepEqual(published.required,['status','state','input','reason']);
  assert.equal(JSON.stringify(payloads[0]).split('Program result schema: ').length-1,1);
  const direct=skill.parameters.properties.intent.anyOf.find(branch=>branch.properties.skill_kind.const==='direct');
  const directClick=direct.properties.goal.properties.input.anyOf.find(branch=>branch.properties.type.const==='click');
  assert.ok(directClick.required.includes('geometry'));
  const programClick=published.then.properties.input.anyOf.find(branch=>branch.properties.type.const==='click');
  assert.ok(!programClick.required.includes('geometry'));
  assert.equal(programClick.properties.geometry,undefined);
  assert.ok(payloads[0].messages[0].content.startsWith(context));
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

test('eligible 429 consumes a separate attempt with identical context and one tool execution',async t=>{
  const {result,events,payloads,calls}=await scenario(t,[
    rateLimit({type:'rate_limit_error',message:'Rate limited; fixture-key private upstream text'}),
    reply(null,[['mutate',{mode:'ok',index:1}]]),reply()]);
  assert.equal(result.ok,true);assert.equal(result.requests,3);
  assert.deepEqual(payloads[0],payloads[1]);
  const starts=events.filter(e=>e.type==='request-start');
  assert.deepEqual(starts.map(e=>e.request_id),['request-1','request-2','request-3']);
  assert.deepEqual(starts.map(e=>e.payload),payloads);
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
  for (const headers of [{'x-should-retry':'false'},{'retry-after-ms':'6000'}]) await t.test(JSON.stringify(headers),async sub=>{
    const {result,payloads,events}=await scenario(sub,[rateLimit(undefined,headers),reply()]);
    assert.equal(result.reason,'provider-error');assert.equal(result.requests,1);assert.equal(payloads.length,1);
    assert.equal(events.filter(e=>e.type==='response-complete').length,1);
  });
});
test('malformed and oversized refusal bodies cannot authorize a retry',async t=>{
  for (const body of ['not JSON',JSON.stringify({error:{message:'Rate limit '+ 'x'.repeat(17000)}})]) await t.test(String(body.length),async sub=>{
    const {result,payloads}=await scenario(sub,[new Response(body,{status:429}),reply()]);
    assert.equal(result.reason,'provider-error');assert.equal(result.requests,1);assert.equal(payloads.length,1);
  });
});
test('request timeout and cancellation interrupt backoff without a second attempt',async t=>{
  for (const cancel of [false,true]) await t.test(String(cancel),async sub=>{
    const configuration=route();configuration.request_timeout_seconds=.1;
    const controller=new AbortController();
    const {result,payloads,events}=await scenario(sub,[()=>{
      if(cancel) setTimeout(()=>controller.abort(),20);
      return rateLimit(undefined,{'retry-after-ms':'1000'});
    },reply()],{configuration,signal:controller.signal});
    assert.equal(result.reason,cancel?'cancelled':'request-timeout');
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
  const {result,payloads}=await scenario(t,[rateLimit(undefined,{'retry-after-ms':'4000'}),reply()],{timeoutSeconds:2});
  assert.equal(result.reason,'host-timeout');assert.equal(payloads.length,1);
});
test('a partial provider stream is never retried and cannot dispatch its tool',async t=>{
  const first='data: '+JSON.stringify({choices:[{index:0,delta:{role:'assistant',tool_calls:[{index:0,id:'partial',type:'function',function:{name:'mutate',arguments:'{"mode":"ok"}'}}]},finish_reason:null}]})+'\n\n';
  const {result,payloads,calls}=await scenario(t,[new Response(new ReadableStream({start(c){
    c.enqueue(new TextEncoder().encode(first));c.error(new Error('fixture-key private stream failure'));
  }}),{headers:{'content-type':'text/event-stream'}}),reply()]);
  assert.equal(result.reason,'provider-error');assert.equal(payloads.length,1);assert.equal(calls.length,0);
});

test('rendered marker literals survive production MCP presentation and actual Pi serialization',async()=>{
  const root=fileURLToPath(new URL('../../../',import.meta.url));
  const payloads=[],events=[];
  const responses=[reply(null,[['enactive_snapshot',{}]]),reply()];
  const result=await runHost({configuration:route(),mcpConfig:{command:resolve(python),
    args:['-m','tests.test_player_tools','--stdio-fixture'],cwd:root,enabled:true,
    enabled_tools:['enactive_snapshot'],startup_timeout_sec:5,tool_timeout_sec:2},
    context:'Offline marker presentation fixture',prompt:'Read one snapshot.',model:model.id,
    effort:'off',timeoutSeconds:10,env:{OFFLINE_TEST_KEY:'fixture-key'},
    fetch:async(_url,init)=>{payloads.push(JSON.parse(init.body));return responses.shift();},
    onEvent:e=>events.push(e)});
  assert.equal(result.ok,true);assert.equal(payloads.length,2);
  const tool=payloads[1].messages.find(message=>message.role==='tool');
  const snapshot=JSON.parse(tool.content);
  assert.deepEqual(snapshot.source.observation.ui.rows.map(row=>row.rendered_marker),['-','+',null]);
  assert.deepEqual(snapshot.source.observation.ui.rows.map(row=>row.text),['item','item','item']);
  assert.equal(snapshot.source.observation.ui.selected,'row-0');
  assert.equal(events.filter(event=>event.type==='tool-start').length,1);
  const pid=events.find(event=>event.type==='mcp-connected').child_pid;
  assert.throws(()=>process.kill(pid,0),{code:'ESRCH'});
});
