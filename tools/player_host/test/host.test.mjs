import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { McpClient } from '@earendil-works/pi-mcp';
import { runHost, validateConfiguration, validateMcpConfiguration, projectImageContext, projectToolResultForTelemetry, INPUT_LIMIT_BYTES } from '../host.mjs';

const realSetTimeout = globalThis.setTimeout;
const realDelay = ms => new Promise(resolve=>realSetTimeout(resolve,ms));
const python = process.env.ENACTIVE_TEST_PYTHON;
const fixture = fileURLToPath(new URL('server.py', import.meta.url));
const png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ioAAAAASUVORK5CYII=';
const model = { id: 'fixture-model', name: 'Offline fixture', api: 'openai-completions', provider: 'fixture', baseUrl: 'https://fixture.invalid/v1', reasoning: false, input: ['text', 'image'], cost: {input:0, output:0, cacheRead:0, cacheWrite:0}, contextWindow: 100000, maxTokens: 1024, compat: { supportsDeveloperRole:false, supportsStore:false, supportsUsageInStreaming:true } };
const route = () => ({schema:'pi-player-host/4',service_tier:'default', model:structuredClone(model), api_key_env:'OFFLINE_TEST_KEY', max_requests:4, max_context_images:4, request_timeout_seconds:2});
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
  const payloads = [], bodies = [], events = [];
  let index = 0;
  const fetch = async (_url, init) => {
    bodies.push(init.body);
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
  let settled=false;
  void running.then(()=>{settled=true;},()=>{settled=true;});
  const drainCleanupClock=async()=>{
    if(!overrides.advanceCleanupTimers)return;
    const until=Date.now()+5000;
    while(!settled && Date.now()<until) {
      await realDelay(10);
      if(!settled)overrides.advanceCleanupTimers();
    }
    assert.ok(settled,'mocked cleanup timers must settle within five real seconds');
  };
  try {
    await overrides.synchronize?.({log});
    if(overrides.advanceCleanupTimers) {
      // The original work tick must already have stopped the host. Pumping
      // cleanup afterward cannot conceal a renewed or missing work deadline.
      assert.equal(events.find(event=>event.type==='abort')?.reason,overrides.expectedAbort);
    }
  } catch (error) { await drainCleanupClock();await running;throw error; }
  await drainCleanupClock();
  const result = await running;
  let calls=[]; try { calls=(await readFile(log,'utf8')).trim().split('\n').filter(Boolean).map(JSON.parse); } catch {}
  const childPid = Number(await readFile(pid,'utf8'));
  assert.throws(()=>process.kill(childPid,0), {code:'ESRCH'}, 'owned MCP child must exit before settlement');
  assertRequestMetadata(events, bodies);
  return {result,payloads,bodies,events,calls};
}
function assertRequestMetadata(events, bodies) {
  const starts=events.filter(event=>event.type==='request-start');
  assert.equal(starts.length,bodies.length);
  for(const [index,event] of starts.entries()) {
    assert.equal(event.payload_sha256,createHash('sha256').update(bodies[index]).digest('hex'));
    assert.equal(event.payload_bytes,Buffer.byteLength(bodies[index]));
    assert.equal(event.message_count,JSON.parse(bodies[index]).messages.length);
    for(const key of ['payload','messages','prompt','history','reasoning','reasoning_content']) assert.equal(Object.hasOwn(event,key),false);
  }
}
test('route is closed, graphical, finite and model/effort exact', ()=>{
  assert.doesNotThrow(()=>validateConfiguration(route(),model.id,'off'));
  for (const change of [{schema:'old'}, {unknown:true}, {max_requests:Infinity}, {api_key_env:'bad-key'}, {model:{...model,input:['text']}}, {model:{...model,headers:{authorization:'secret'}}}]) {
    assert.throws(()=>validateConfiguration({...route(),...change},model.id,'off'));
  }
  assert.throws(()=>validateConfiguration(route(),'other','off'));
  assert.throws(()=>validateConfiguration(route(),model.id,'low'));
  assert.throws(()=>validateConfiguration({...route(),schema:'pi-player-host/1'},model.id,'off'));
  assert.throws(()=>validateConfiguration({...route(),schema:'pi-player-host/2'},model.id,'off'));
  assert.throws(()=>validateConfiguration({...route(),schema:'pi-player-host/3'},model.id,'off'));
  for (const service_tier of [undefined,null,true,1,'flex','auto','',{},[]]) {
    assert.throws(()=>validateConfiguration({...route(),service_tier},model.id,'off'));
  }
  assert.doesNotThrow(()=>validateConfiguration({...route(),service_tier:'priority'},model.id,'off'));
  for (const value of [undefined,0,-1,1.5,true,'2',NaN,Infinity,Number.MAX_SAFE_INTEGER+1]) {
    assert.throws(()=>validateConfiguration({...route(),max_context_images:value},model.id,'off'));
  }
  const missing=route();delete missing.max_context_images;
  assert.throws(()=>validateConfiguration(missing,model.id,'off'));
});

test('OpenRouter uses maintained routing and reasoning serializers with explicit standard tier on every attempt',async t=>{
  const configuration=route();
  configuration.model={...configuration.model,provider:'openrouter',baseUrl:'https://openrouter.ai/api/v1',reasoning:true,
    thinkingLevelMap:{medium:'medium'},compat:{...configuration.model.compat,supportsReasoningEffort:true,
      thinkingFormat:'openrouter',openRouterRouting:{only:['fireworks/us'],order:['fireworks/us'],allow_fallbacks:false,require_parameters:true}}};
  assert.doesNotThrow(()=>validateConfiguration(configuration,model.id,'medium'));
  for (const baseUrl of ['http://openrouter.ai/api/v1','https://other.invalid/api/v1','https://openrouter.ai/v1']) {
    assert.throws(()=>validateConfiguration({...configuration,model:{...configuration.model,baseUrl}},model.id,'medium'));
  }
  for(const change of [{allow_fallbacks:true},{require_parameters:false},{only:['fireworks/us','baseten']},
      {order:['baseten']},{only:[99],order:[99]},{unknown:true}]) {
    const invalid=structuredClone(configuration);Object.assign(invalid.model.compat.openRouterRouting,change);
    assert.throws(()=>validateConfiguration(invalid,model.id,'medium'));
  }
  const priority={...configuration,service_tier:'priority'};
  assert.throws(()=>validateConfiguration(priority,model.id,'medium'));
  const missing=structuredClone(configuration);delete missing.model.compat.openRouterRouting;
  assert.throws(()=>validateConfiguration(missing,model.id,'medium'));
  const result=await scenario(t,[rateLimit(),reply()],{configuration,effort:'medium'});
  assert.equal(result.result.ok,true);assert.equal(result.payloads.length,2);
  for(const payload of result.payloads) {
    assert.deepEqual(payload.provider,configuration.model.compat.openRouterRouting);
    assert.deepEqual(payload.reasoning,{effort:'medium'});
    assert.equal(payload.reasoning_effort,undefined);assert.equal(payload.service_tier,'default');
  }
  assert.deepEqual(result.payloads[0],result.payloads[1]);
  assert.deepEqual(result.events.find(e=>e.type==='host-start').provider_routing,configuration.model.compat.openRouterRouting);
});

test('frozen serving tier uses the SDK payload hook and reports only observed stream echoes',async t=>{
  const withTier=tier=>new Response([
    {model:'fixture-backend',service_tier:tier,choices:[{index:0,delta:{role:'assistant',content:'done'},finish_reason:null}]},
    {model:'fixture-backend',service_tier:tier,choices:[{index:0,delta:{},finish_reason:'stop'}]},
  ].map(chunk=>'data: '+JSON.stringify(chunk)+'\n\n').join('')+'data: [DONE]\n\n',{headers:{'content-type':'text/event-stream'}});
  const ordinary=await scenario(t,[withTier('default')]);
  assert.equal(ordinary.result.ok,true);
  assert.equal(Object.hasOwn(ordinary.payloads[0],'service_tier'),false);
  assert.equal(ordinary.events.find(e=>e.type==='host-start').requested_service_tier,'default');
  const comparable=payload=>JSON.parse(JSON.stringify(payload).replace(
    /Host decision time remaining at this snapshot: ([0-9]+\.[0-9]{3}) seconds\./g,
    (_match,seconds)=>{
      assert.ok(Number(seconds)>0 && Number(seconds)<=10,'actual original host decision horizon');
      return 'Host decision time remaining at this snapshot: <measured> seconds.';
    }));
  for(const echo of ['priority','default',undefined,'fixture-key private tier']) {
    const configuration={...route(),service_tier:'priority'};
    const actual=await scenario(t,[withTier(echo)],{configuration});
    assert.equal(actual.result.ok,true);
    assert.deepEqual(comparable(actual.payloads[0]),{...comparable(ordinary.payloads[0]),service_tier:'priority'});
    assert.equal(actual.events.find(e=>e.type==='host-start').requested_service_tier,'priority');
    const tiers=actual.events.filter(e=>e.type==='response-service-tier');
    assert.deepEqual(tiers.map(e=>[e.request_id,e.applied_service_tier]),['priority','default'].includes(echo)?[['request-1',echo]]:[]);
    assert.equal(actual.payloads.length,1,'missing or fallback echo cannot retry inference');
    assert.ok(!JSON.stringify(actual.events).includes('fixture-key private tier'));
  }
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

test('actual serializer retains projected history while telemetry omits reasoning and image bytes',async t=>{
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
  assert.ok(originalResults.every(event=>event.result.content.some(part=>part.type==='image_reference' && part.bytes===Buffer.from(png,'base64').length)));
  assert.ok(originalResults.every(event=>!JSON.stringify(event).includes('Historical pixels omitted')));
  assert.ok(!JSON.stringify(events).includes(reasoning));
  assert.ok(!JSON.stringify(events).includes(png));
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
  assert.ok(!JSON.stringify(events).includes(png));
  const image=events.find(e=>e.type==='tool-result').result.content.find(part=>part.type==='image_reference');
  assert.deepEqual(image,{type:'image_reference',media_type:'image/png',bytes:Buffer.from(png,'base64').length,
    sha256:createHash('sha256').update(Buffer.from(png,'base64')).digest('hex'),image_index:0});
  assert.ok(events.every(e=>typeof e.monotonic_ms==='number' && typeof e.wall_time==='string'));
  assert.ok(!JSON.stringify(events).includes('fixture-key'));
  assert.equal(events.find(event=>event.type==='response-backend').backend_model,'fixture-backend');
  const secondRequest=events.filter(event=>event.type==='request-start')[1];
  t.diagnostic(JSON.stringify({sample:'offline-synthetic-SSE+official-MCP',requests:result.requests,host_ms:events.at(-1).monotonic_ms,second_request_content:secondRequest}));
});
test('coerced arguments are refused with zero dispatch, then deliberate correction succeeds',async t=>{
  const {result,calls,payloads,events}=await scenario(t,[reply(null,[['integer',{value:'3'}]]),reply(null,[['integer',{value:3}]]),reply()]);
  assert.equal(result.ok,true);
  assert.deepEqual(calls,[{tool:'integer',value:3}]);
  assert.ok(JSON.stringify(payloads[1]).includes('MCP input not sent'));
  assert.equal(events.filter(event=>event.type==='tool-refused').length,1);
});
test('request metadata hashes exact serialized bodies without retaining forwarded private reasoning or secrets',async t=>{
  const reasoning='Private synthetic reasoning before an observation.';
  const {result,payloads,events}=await scenario(t,[reply('Visible plan',[['observe',{fail:false}]],true,reasoning),reply()]);
  assert.equal(result.ok,true);
  const trace=events.filter(e=>e.type==='request-start');
  assert.equal(payloads[1].messages.find(m=>m.role==='assistant').reasoning_content,reasoning);
  assert.ok(JSON.stringify(payloads[1]).includes(png));
  assert.equal(events.find(e=>e.type==='host-start').telemetry_version,2);
  assert.deepEqual(events.filter(e=>e.type==='assistant-text').map(e=>[e.text,e.omitted_bytes]),[['Visible plan',0],['finished',0]]);
  for(const secret of [reasoning,png,'fixture-key','UNRELATED_HOST_SECRET','Frozen player guide','Offline mission']) {
    assert.ok(!JSON.stringify(events).includes(secret));
  }
  assert.ok(trace.every(e=>e.text_bytes>0&&e.payload_bytes>0));
});
test('tool telemetry projection preserves text, structured data and canonical MCP objects',()=>{
  const result={content:[{type:'text',text:'actual game JSON'},
    {type:'image',mimeType:'image/png',data:png},{type:'image',mimeType:'image/png',data:png}],
    structuredContent:{actual:'structured game JSON'},isError:true};
  const original=structuredClone(result);
  const freeze=value=>{if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}};
  freeze(result);
  const projected=projectToolResultForTelemetry(result);
  assert.deepEqual(result,original);
  assert.deepEqual(projected.content[0],original.content[0]);
  assert.deepEqual(projected.structuredContent,original.structuredContent);
  assert.equal(projected.isError,true);
  assert.deepEqual(projected.content.slice(1).map(part=>part.image_index),[0,1]);
  assert.ok(!JSON.stringify(projected).includes(png));
});
test('assistant narration is bounded by UTF8 bytes and excludes thinking parts',async t=>{
  const visible='a'.repeat(8191)+'思'.repeat(5);
  const {result,events}=await scenario(t,[reply(visible,[],true,'private-thinking-sentinel')]);
  assert.equal(result.finalText,visible);
  const narration=events.find(e=>e.type==='assistant-text');
  assert.equal(narration.text,'a'.repeat(8191));
  assert.equal(narration.omitted_bytes,15);
  assert.ok(Buffer.byteLength(narration.text)<=8192);
  assert.ok(!JSON.stringify(events).includes('private-thinking-sentinel'));
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
  const {result,payloads,events}=await scenario(t,[reply(null,[['observe',{}]]),reply()],{configuration});
  assert.equal(result.ok,false); assert.equal(result.reason,'request-limit'); assert.equal(payloads.length,1);
  assert.equal(events.find(event=>event.type==='abort').response_progress.scope,'last-http-attempt');
});
test('fixture union schema refusal gives stable precise feedback, explicit correction dispatches, MCP errors stay intact',async t=>{
  const entry={stage:'x'.repeat(244),available:[{subject:'small cardboard box'}]};
  const bad={snapshot_id:'fixture-snapshot',intent:{entry_type:'work',entry}};
  const fixed=structuredClone(bad);fixed.intent.entry.stage='partial';
  fixed.intent.entry.available[0].subject='small_cardboard_box';
  const mcpError=structuredClone(fixed);mcpError.intent.entry.stage='mcp-error';
  const configuration=route();configuration.max_requests=6;
  const {result,calls,payloads,events}=await scenario(t,[
    reply(null,[['fixture_remember',bad]],true,undefined,'bad'),
    reply(null,[['fixture_remember',fixed]],true,undefined,'fixed'),
    reply(null,[['observe',{}]],true,undefined,'later'),
    reply(null,[['fixture_remember',mcpError]],true,undefined,'mcp-error'),reply()
  ],{configuration,enabledTools:['fixture_remember','observe']});
  assert.equal(result.ok,true);
  assert.deepEqual(calls.filter(c=>c.tool==='fixture_remember').map(c=>c.intent),[fixed.intent,mcpError.intent]);
  const first=payloads[1].messages.find(m=>m.role==='tool'&&m.tool_call_id==='bad-0').content;
  assert.match(first,/entry.stage: must not have more than 128/);
  assert.match(first,/entry.available.0.subject: must match pattern/);
  assert.ok(!first.includes('intent.entry.value'));
  for(const payload of payloads.slice(2)) {
    assert.equal(payload.messages.find(m=>m.role==='tool'&&m.tool_call_id==='bad-0').content,first);
  }
  const diagnostics=events.filter(e=>e.type==='tool-validation-feedback');assert.equal(diagnostics.length,1);
  assert.match(diagnostics[0].original_result.content[0].text,/intent.entry.value/);
  assert.equal(diagnostics[0].projected_text,first);
  const actualMcpError=payloads[4].messages.find(m=>m.role==='tool'&&m.tool_call_id==='mcp-error-0').content;
  assert.match(actualMcpError,/MCP isError: true/);assert.match(actualMcpError,/fixture MCP refusal/);
  assert.deepEqual(payloads[0].tools,payloads[4].tools,'the actual full schema remains stable');
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
  assert.equal(b.content_bytes,8);assert.equal(b.reasoning_bytes,0);assert.equal(b.tool_argument_bytes,0);
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
    {choices:[{index:0,delta:{reasoning_text:'z',content:'ok'},finish_reason:'stop'}]}];
  const body=chunks.map(chunk=>'data: '+JSON.stringify(chunk)+'\n\n').join('')+'data: [DONE]\n\n';
  const {result,events}=await scenario(t,[new Response(body,{headers:{'content-type':'text/event-stream'}})]);
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
  assert.equal(b.provider_events,2);assert.equal(b.content_bytes,2);assert.equal(b.tool_argument_bytes,0);
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

test('frozen MCP config rejects disabled and malformed fields', ()=>{
  const valid={command:'python',args:[],cwd:'/',enabled:true,enabled_tools:['observe'],startup_timeout_sec:1,tool_timeout_sec:1};
  assert.doesNotThrow(()=>validateMcpConfiguration(valid));
  for (const change of [{enabled:false},{required:'yes'},{args:'bad'},{enabled_tools:['observe','observe']},{tool_timeout_sec:NaN},{tools:{observe:false}},{ambient:1}]) {
    assert.throws(()=>validateMcpConfiguration({...valid,...change}));
  }
});

const root=fileURLToPath(new URL('../../../',import.meta.url));
const productionRoot=process.env.ENACTIVE_TEST_PRODUCTION_ROOT ?? root;
function productionMcp(enabled_tools) {
  return {command:resolve(python),args:[join(productionRoot,'tests/player_service_fixture.py'),'--stdio'],
    cwd:productionRoot,enabled:true,enabled_tools,startup_timeout_sec:5,tool_timeout_sec:2};
}
test('real production MCP discovery forwards all exact current actor-only tool schemas', async ()=>{
  const { execFile } = await import('node:child_process');
  const { promisify } = await import('node:util');
  const {stdout}=await promisify(execFile)(python,['-c','import json; from harness.player_tools import tool_specs; print(json.dumps({name:{"schema":schema,"description":description} for name,(description,schema) in tool_specs().items()}))'],{cwd:productionRoot,maxBuffer:INPUT_LIMIT_BYTES});
  const expected=JSON.parse(stdout), payloads=[], bodies=[], events=[];
  const chosen=Object.keys(expected);
  assert.equal(chosen.length,14);
  const result=await runHost({configuration:route(),mcpConfig:productionMcp(chosen),
    context:'Frozen current player guide',prompt:'Do not call tools.',model:model.id,effort:'off',
    timeoutSeconds:10,env:{OFFLINE_TEST_KEY:'fixture-key'},
    fetch:async(_url,init)=>{bodies.push(init.body);payloads.push(JSON.parse(init.body));return reply();},onEvent:e=>events.push(e)});
  assert.equal(result.ok,true);
  assertRequestMetadata(events,bodies);
  assert.deepEqual(payloads[0].tools.map(tool=>tool.function.name),chosen);
  for(const tool of payloads[0].tools) {
    assert.deepEqual(tool.function.parameters,expected[tool.function.name].schema);
    assert.equal(tool.function.description,expected[tool.function.name].description);
    for(const key of ['actor_id','session','token']) assert.equal(Object.hasOwn(tool.function.parameters.properties,key),false);
  }
  const handoff=payloads[0].tools.find(tool=>tool.function.name==='player_handoff').function;
  assert.deepEqual(handoff.parameters.required,['ids','summary']);
  assert.ok(chosen.includes('computer_result')&&chosen.includes('player_result'));
  assert.ok(chosen.every(name=>!name.startsWith('enactive_')));
  assert.ok(payloads[0].messages[0].content.includes('Only basic computer control is authoritative'));
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
  const bad=new Response('data: '+JSON.stringify({id:'fixture-key',provider:'fixture-key',choices:[{index:0,delta:{content:'ok'},finish_reason:'stop'}]})+'\n\ndata: [DONE]\n\n',
    {headers:{'content-type':'text/event-stream','x-request-id':'fixture-key'}});
  const observed=await scenario(t,[bad]);
  assert.equal(observed.result.ok,true);
  assert.equal(observed.events.find(e=>e.type==='response-headers').provider_request_id,null);
  const progress=observed.events.find(e=>e.type==='response-complete').response_progress;
  assert.equal(progress.response_id,null);assert.equal(progress.reported_provider,null);
  assert.ok(!JSON.stringify(observed.events).includes('fixture-key'));
});

test('request budget is fresh request-only bookkeeping after unchanged history',async t=>{
  const {result,payloads}=await scenario(t,[reply(null,[['observe',{}]]),reply(null,[['observe',{}]],true,undefined,'next'),reply()]);
  assert.equal(result.ok,true);assert.equal(result.requests,3);
  const marker='Host resource status (software-generated at context construction):';
  const text=message=>typeof message.content==='string'?message.content:(message.content??[]).filter(part=>part.type==='text').map(part=>part.text).join('\n');
  for(const [index,payload] of payloads.entries()) {
    const notes=payload.messages.filter(message=>text(message).startsWith(marker));
    assert.equal(notes.length,1,'prior bookkeeping must not accumulate into canonical history');
    assert.equal(payload.messages.at(-1),notes[0]);assert.equal(notes[0].role,'user');
    assert.ok(text(notes[0]).includes(`charged before this request: ${index}/4.`));
    assert.match(text(notes[0]),/Host decision time remaining at this snapshot: \d+\.\d{3} seconds/);
    assert.ok(text(notes[0]).includes(`including this request: ${4-index}.`));
    assert.ok(text(notes[0]).includes('not a human task, gameplay evidence, source-read proof, authority or a latency/quality metric'));
    assert.deepEqual(payload.messages[0],payloads[0].messages[0]);
    assert.deepEqual(payload.messages[1],payloads[0].messages[1]);
    assert.deepEqual(payload.tools,payloads[0].tools);
  }
  assert.deepEqual(payloads[2].messages.filter(message=>message.role==='tool').map(message=>message.tool_call_id),['call-0','next-0']);
  assert.ok(!text(payloads[0].messages[1]).includes(marker),'original mission remains intact');
});

test('eligible 429 consumes a separate attempt with identical context and one tool execution',async t=>{
  const {result,events,payloads,calls}=await scenario(t,[
    rateLimit({type:'rate_limit_error',message:'Rate limited; fixture-key private upstream text'}),
    reply(null,[['mutate',{mode:'ok',index:1}]]),reply()]);
  assert.equal(result.ok,true);assert.equal(result.requests,3);
  assert.deepEqual(payloads[0],payloads[1]);
  const note=payload=>{
    const content=payload.messages.at(-1).content;
    return typeof content==='string'?content:content.map(part=>part.text??'').join('\n');
  };
  assert.ok(note(payloads[0]).includes('charged before this request: 0/4.'));
  assert.ok(note(payloads[0]).includes('An eligible retry can consume another attempt'));
  assert.ok(note(payloads[2]).includes('charged before this request: 2/4.'));
  assert.ok(note(payloads[2]).includes('including this request: 2.'));
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
  const {result,payloads,calls}=await scenario(t,[new Response(new ReadableStream({start(c){
    c.enqueue(new TextEncoder().encode(first));c.error(new Error('fixture-key private stream failure'));
  }}),{headers:{'content-type':'text/event-stream'}}),reply()]);
  assert.equal(result.reason,'provider-error');assert.equal(payloads.length,1);assert.equal(calls.length,0);
});

test('production MCP preserves actual source JSON and PNG through Pi while event images are references',async()=>{
  const payloads=[],bodies=[],events=[];
  const result=await runHost({configuration:route(),mcpConfig:productionMcp(['computer_observe','player_source']),
    context:'Offline current pixel fixture',prompt:'Read actual source pixels.',model:model.id,
    effort:'off',timeoutSeconds:10,env:{OFFLINE_TEST_KEY:'fixture-key'},
    fetch:async(_url,init)=>{
      bodies.push(init.body);payloads.push(JSON.parse(init.body));
      if(payloads.length===1)return reply(null,[['computer_observe',{}]]);
      if(payloads.length===2) {
        const operation=JSON.parse(events.find(e=>e.type==='tool-result').result.content[0].text);
        return reply(null,[['player_source',{source_id:operation.source.source_id}]],true,undefined,'read');
      }
      return reply();
    },onEvent:e=>events.push(e)});
  assert.equal(result.ok,true);assert.equal(payloads.length,3);
  assertRequestMetadata(events,bodies);
  const original=JSON.parse(events.find(e=>e.type==='tool-result').result.content[0].text);
  assert.equal(original.schema,'computer-operation/1');assert.equal(original.status,'completed');
  assert.equal(original.source.schema,'computer-source/1');
  assert.equal(original.source.width,4);assert.equal(original.source.height,4);
  const images=payloads[2].messages.flatMap(message=>Array.isArray(message.content)?message.content:[])
    .filter(part=>part.type==='image_url');
  assert.equal(images.length,2);
  assert.equal(images[0].image_url.url,images[1].image_url.url);
  const pngBytes=Buffer.from(images[0].image_url.url.split(',')[1],'base64');
  assert.equal(createHash('sha256').update(pngBytes).digest('hex'),original.source.sha256);
  const references=events.filter(e=>e.type==='tool-result').flatMap(e=>e.result.content)
    .filter(part=>part.type==='image_reference');
  assert.equal(references.length,2);
  assert.ok(references.every(part=>part.bytes===pngBytes.length&&part.sha256===original.source.sha256));
  assert.ok(!JSON.stringify(events).includes(pngBytes.toString('base64')));
  assert.throws(()=>process.kill(events.find(e=>e.type==='mcp-connected').child_pid,0),{code:'ESRCH'});
});
test('production MCP sealed handoff settles after earlier ordinary tool without followup inference or dispatch',async()=>{
  const payloads=[],bodies=[],events=[];
  const result=await runHost({configuration:route(),mcpConfig:productionMcp(['computer_observe','player_handoff']),
    context:'Offline current actor handoff fixture',prompt:'Retain unfinished context and hand off.',
    model:model.id,effort:'off',timeoutSeconds:10,env:{OFFLINE_TEST_KEY:'fixture-key'},
    fetch:async(_url,init)=>{
      bodies.push(init.body);payloads.push(JSON.parse(init.body));
      return reply(null,[['computer_observe',{}],['player_handoff',{ids:[],summary:'synthetic unfinished work'}],['computer_observe',{}]]);
    },onEvent:e=>events.push(e)});
  assert.deepEqual(result,{ok:true,reason:'handoff',requests:1,finalText:''});
  assertRequestMetadata(events,bodies);
  assert.deepEqual(events.filter(e=>e.type==='tool-start').map(e=>e.tool),['computer_observe','player_handoff']);
  const value=JSON.parse(events.find(e=>e.type==='tool-result'&&e.tool==='player_handoff').result.content[0].text);
  assert.equal(value.schema,'computer-operation/1');assert.equal(value.status,'sealed');
  assert.equal(value.handoff.schema,'player-handoff/1');assert.equal(value.handoff.grants_authority,false);
  const event=events.find(e=>e.type==='handoff');
  assert.equal(event.handoff_id,value.operation_id);assert.equal(event.session,value.session);
  assert.equal(event.actor_id,value.actor_id);assert.equal(event.context_id,value.handoff.context_id);
  assert.equal(event.context_sha256,value.handoff.context_sha256);assert.equal(event.grants_authority,false);
  assert.deepEqual(events.filter(e=>e.type==='tool-refused').map(e=>[e.tool,e.reason,e.dispatched]),[['computer_observe','handoff',false]]);
  assert.throws(()=>process.kill(events.find(e=>e.type==='mcp-connected').child_pid,0),{code:'ESRCH'});
});

const handoffArgs = {ids:[],summary:'Retain current context'};
const handoffTools = ['mutate','player_handoff','computer_result'];
const handoffId = '1'.repeat(32);
const sessionId = '2'.repeat(32);
const actorId = '3'.repeat(32);
const collectArgs = {operation_id:handoffId};

test('completed handoff fences later batch inputs and ends even after an earlier ordinary tool',async t=>{
  const {result,payloads,calls,events}=await scenario(t,[reply('not a final gameplay report',[
    ['mutate',{mode:'ok',index:1}],['player_handoff',handoffArgs],['mutate',{mode:'ok',index:2}]
  ])],{enabledTools:handoffTools});
  assert.deepEqual(result,{ok:true,reason:'handoff',requests:1,finalText:''});
  assert.equal(payloads.length,1);
  assert.deepEqual(calls.filter(c=>c.tool==='mutate').map(c=>[c.phase,c.index]),[['start',1],['end',1]]);
  assert.equal(events.filter(e=>e.type==='handoff').length,1);
  const receipt=events.find(e=>e.type==='tool-result'&&e.tool==='player_handoff').result;
  assert.equal(JSON.parse(receipt.content[0].text).handoff.operation_id,handoffId);
  assert.deepEqual(events.filter(e=>e.type==='tool-refused').map(e=>[e.tool,e.reason,e.dispatched]),[['mutate','handoff',false]]);
});
test('direct handoff settles without another model turn',async t=>{
  const {result,calls}=await scenario(t,[reply(null,[['player_handoff',handoffArgs]])],{enabledTools:handoffTools});
  assert.equal(result.reason,'handoff');assert.equal(result.ok,true);assert.equal(result.requests,1);
  assert.deepEqual(calls.map(c=>c.tool),['player_handoff']);
});
test('only this host pending or uncertain handoff can settle through collection',async t=>{
  for(const mode of ['pending','transport-uncertain']) await t.test(mode,async sub=>{
    const {result,calls}=await scenario(sub,[
      reply(null,[['player_handoff',{...handoffArgs,mode}]]),
      reply(null,[['computer_result',collectArgs]])
    ],{enabledTools:handoffTools});
    assert.equal(result.reason,'handoff');assert.equal(result.ok,true);assert.equal(result.requests,2);
    assert.deepEqual(calls.map(c=>c.tool),['player_handoff','computer_result']);
  });
});
test('a fresh successor can inspect issuance without ending its host',async t=>{
  const {result,events}=await scenario(t,[
    reply(null,[['computer_result',collectArgs]]),reply()
  ],{enabledTools:handoffTools});
  assert.equal(result.reason,'completed');assert.equal(result.requests,2);
  assert.equal(events.filter(e=>e.type==='handoff').length,0);
});
test('proven nonadmission cannot arm settlement of another issuance',async t=>{
  const {result,events}=await scenario(t,[reply(null,[['player_handoff',{...handoffArgs,mode:'not-admitted'}]]),
    reply(null,[['computer_result',collectArgs]]),reply()],{enabledTools:handoffTools});
  assert.equal(result.reason,'completed');assert.equal(result.requests,3);
  assert.equal(events.filter(e=>e.type==='handoff').length,0);
});
test('ordinary plain-text collection errors preserve explicit correction',async t=>{
  const {result}=await scenario(t,[
    reply(null,[['player_handoff',{...handoffArgs,mode:'pending'}]]),
    reply(null,[['computer_result',{...collectArgs,mode:'plain-error'}]]),
    reply(null,[['computer_result',collectArgs]])
  ],{enabledTools:handoffTools});
  assert.equal(result.reason,'handoff');assert.equal(result.requests,3);
});
test('refused and pending handoffs allow a new explicit model decision',async t=>{
  for(const mode of ['refused','pending','error']) await t.test(mode,async sub=>{
    const {result,events}=await scenario(sub,[reply(null,[['player_handoff',{...handoffArgs,mode}]]),reply()],{enabledTools:handoffTools});
    assert.equal(result.reason,'completed');assert.equal(result.requests,2);
    assert.equal(events.filter(e=>e.type==='handoff').length,0);
  });
});
test('incoherent claimed handoffs stop before another input or provider request',async t=>{
  for(const mode of ['foreign','old','legacy','context','actor','operation','session','authority','sealed-wall','malformed']) await t.test(mode,async sub=>{
    const {result,calls,payloads}=await scenario(sub,[reply(null,[['player_handoff',{...handoffArgs,mode}],['mutate',{mode:'ok'}]])],{enabledTools:handoffTools});
    assert.equal(result.ok,false);assert.equal(result.reason,'invalid-handoff-receipt');
    assert.equal(payloads.length,1);assert.deepEqual(calls.map(c=>c.tool),['player_handoff']);
  });
});
test('reading a different operation cannot settle this host pending handoff',async t=>{
  for(const args of [{operation_id:'4'.repeat(32)},{operation_id:'unrelated'}]) await t.test(args.operation_id,async sub=>{
    const {result,events}=await scenario(sub,[reply(null,[['player_handoff',{...handoffArgs,mode:'pending'}]]),
      reply(null,[['computer_result',args]]),reply()],{enabledTools:handoffTools});
    assert.equal(result.ok,true);assert.equal(result.reason,'completed');assert.equal(result.requests,3);
    assert.equal(events.filter(e=>e.type==='handoff').length,0);
  });
});
test('cancellation dominates an otherwise coherent handoff',async t=>{
  const controller=new AbortController();
  const {result,events}=await scenario(t,[reply(null,[['player_handoff',handoffArgs]])],{
    enabledTools:handoffTools,signal:controller.signal,onEvent:e=>{if(e.type==='handoff')controller.abort();}});
  assert.equal(events.filter(e=>e.type==='handoff').length,1);
  assert.equal(result.ok,false);assert.equal(result.reason,'cancelled');assert.equal(result.finalText,'');
});
test('owned cleanup failure dominates handoff settlement',async t=>{
  const original=McpClient.prototype.close;
  McpClient.prototype.close=async function(){await original.call(this);throw new Error('fixture cleanup failure');};
  try {
    const {result}=await scenario(t,[reply(null,[['player_handoff',handoffArgs]])],{enabledTools:handoffTools});
    assert.equal(result.ok,false);assert.equal(result.reason,'mcp-cleanup-failed');assert.equal(result.finalText,'');
  } finally {McpClient.prototype.close=original;}
});

test('handoff event contains only immutable actor context bindings and no authority',async t=>{
  const {events}=await scenario(t,[reply(null,[['player_handoff',handoffArgs]])],{enabledTools:handoffTools});
  const {type,wall_time,monotonic_ms,request_id,tool_call_id,...event}=events.find(e=>e.type==='handoff');
  assert.deepEqual(event,{session:sessionId,actor_id:actorId,handoff_id:handoffId,
    context_id:'4'.repeat(32),context_sha256:'5'.repeat(64),grants_authority:false});
});
test('matching original collection rejects different session actor or nested operation bindings',async t=>{
  for(const mode of ['session','actor','operation','foreign','old','legacy']) await t.test(mode,async sub=>{
    const {result,calls,payloads}=await scenario(sub,[
      reply(null,[['player_handoff',{mode:'pending'}]]),
      reply(null,[['computer_result',{...collectArgs,mode}],['mutate',{mode:'ok'}]])
    ],{enabledTools:handoffTools});
    assert.equal(result.reason,'invalid-handoff-receipt');assert.equal(payloads.length,2);
    assert.deepEqual(calls.map(c=>c.tool),['player_handoff','computer_result']);
  });
});
test('one pending original handoff cannot be replaced by another direct receipt',async t=>{
  const {result,calls,payloads}=await scenario(t,[reply(null,[['player_handoff',{mode:'pending'}]]),
    reply(null,[['player_handoff',{mode:'another-pending'}],['mutate',{mode:'ok'}]])],{enabledTools:handoffTools});
  assert.equal(result.reason,'invalid-handoff-receipt');assert.equal(payloads.length,2);
  assert.deepEqual(calls.map(c=>c.tool),['player_handoff','player_handoff']);
});
test('isError handoff cannot establish a pending origin even when it carries a sealed receipt',async t=>{
  const {result,events}=await scenario(t,[reply(null,[['player_handoff',{mode:'error'}]]),
    reply(null,[['computer_result',collectArgs]]),reply()],{enabledTools:handoffTools});
  assert.equal(result.reason,'completed');assert.equal(result.requests,3);
  assert.equal(events.filter(e=>e.type==='handoff').length,0);
});
test('first actual MCP text owns the handoff receipt even when extra text follows',async t=>{
  const {result}=await scenario(t,[reply(null,[['player_handoff',{mode:'extra-text'}]])],{enabledTools:handoffTools});
  assert.equal(result.reason,'handoff');assert.equal(result.requests,1);
});
