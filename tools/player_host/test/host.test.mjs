import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { McpClient } from '@earendil-works/pi-mcp';
import { runHost, validateConfiguration, validateMcpConfiguration, projectImageContext, projectToolResultForTelemetry, INPUT_LIMIT_BYTES,
  INTENT_LABEL, boundedText, formatIntentTail, levelCommitEvent, levelAbstainEvent, changedFields } from '../host.mjs';

const realSetTimeout = globalThis.setTimeout;
const realDelay = ms => new Promise(resolve=>realSetTimeout(resolve,ms));
const python = process.env.ENACTIVE_TEST_PYTHON;
const fixture = fileURLToPath(new URL('../../../tests/fixtures/player_host_mcp.py', import.meta.url));
const png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ioAAAAASUVORK5CYII=';
const model = { id: 'fixture-model', name: 'Offline fixture', api: 'openai-completions', provider: 'fixture', baseUrl: 'https://fixture.invalid/v1', reasoning: false, input: ['text', 'image'], cost: {input:0, output:0, cacheRead:0, cacheWrite:0}, contextWindow: 100000, maxTokens: 1024, compat: { supportsDeveloperRole:false, supportsStore:false, supportsUsageInStreaming:true } };
const route = () => ({schema:'player-host/5',role:'actor',intent_tail_bytes:null,service_tier:'default', model:structuredClone(model), api_key_env:'OFFLINE_TEST_KEY', max_requests:4, max_context_images:4, context_image_block:1, request_timeout_seconds:2});
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
  if (overrides.intentFixture !== undefined) await writeFile(join(dir,'intent.json'), overrides.intentFixture);
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
  for (const old of ['pi-player-host/1','pi-player-host/2','pi-player-host/3','pi-player-host/5','player-host/0','player-host/1','player-host/2','player-host/3','player-host/4','player-host/6'])
    assert.throws(()=>validateConfiguration({...route(),schema:old},model.id,'off'));
  for (const change of [{role:undefined},{role:'lead'},{intent_tail_bytes:undefined},{intent_tail_bytes:63},
    {intent_tail_bytes:4097},{intent_tail_bytes:1.5},{role:'level',intent_tail_bytes:1024}])
    assert.throws(()=>validateConfiguration({...route(),...change},model.id,'off'));
  for (const change of [{intent_tail_bytes:64},{intent_tail_bytes:4096},{role:'level'}])
    validateConfiguration({...route(),...change},model.id,'off');
  for (const service_tier of [undefined,null,true,1,'flex','auto','',{},[]]) {
    assert.throws(()=>validateConfiguration({...route(),service_tier},model.id,'off'));
  }
  assert.doesNotThrow(()=>validateConfiguration({...route(),service_tier:'priority'},model.id,'off'));
  for (const value of [undefined,0,-1,1.5,true,'2',NaN,Infinity,Number.MAX_SAFE_INTEGER+1]) {
    assert.throws(()=>validateConfiguration({...route(),max_context_images:value},model.id,'off'));
  }
  const missing=route();delete missing.max_context_images;
  assert.throws(()=>validateConfiguration(missing,model.id,'off'));
  for (const value of [undefined,0,-1,1.5,true,'2',NaN,5,Number.MAX_SAFE_INTEGER+1]) {
    assert.throws(()=>validateConfiguration({...route(),context_image_block:value},model.id,'off'));
  }
  assert.doesNotThrow(()=>validateConfiguration({...route(),context_image_block:4},model.id,'off'));
  const unblocked=route();delete unblocked.context_image_block;
  assert.throws(()=>validateConfiguration(unblocked,model.id,'off'),'an old /2-shaped route without a block is rejected');
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
  const projected=projectImageContext(messages,1,1);
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
  const projected=projectImageContext(messages,2,1);
  assert.equal(projected.summary.omitted_images,18);
  assert.equal(projected.summary.omissions.length,16);
  assert.equal(projected.summary.omitted_provenance_entries,2);
  assert.equal(projected.messages[1].content[0].text,'keep source-history');
  assert.ok(projected.messages[1].content[18].text.includes('image_index=17'));
  assert.deepEqual(projected.messages[1].content.slice(-2),images.slice(-2));
  assert.deepEqual(messages[1].content.slice(1),images);
});

// One tool result per turn, each with `perTurn` images; the latest batch is protected.
function imageHistory(turns, perTurn = 1) {
  const messages=[];
  for (let turn=0; turn<turns; turn++) {
    messages.push({role:'assistant',content:[{type:'toolCall',id:`t${turn}`,name:'observe',arguments:{}}]});
    messages.push({role:'toolResult',toolCallId:`t${turn}`,content:[{type:'text',text:`frame ${turn}`},
      ...Array.from({length:perTurn},(_,index)=>({type:'image',mimeType:'image/png',data:Buffer.from(`image-${turn}-${index}`).toString('base64')}))]});
  }
  return messages;
}
const pixels=projection=>projection.messages.flatMap(message=>Array.isArray(message.content)?message.content:[]).filter(part=>part.type==='image').length;
test('block eviction omits whole blocks of the oldest images at count boundaries only',()=>{
  // max 39, block 10: the derived minimum is 30, so retained pixels cycle 30..39.
  for (const [n,omitted] of [[39,0],[40,10],[41,10],[49,10],[50,20],[59,20],[60,30]]) {
    const projection=projectImageContext(imageHistory(n),39,10);
    assert.equal(projection.summary.omitted_images,omitted,`n=${n}`);
    assert.equal(pixels(projection),n-omitted);
    assert.equal(projection.summary.context_image_block,10);
  }
});
test('block 1 is byte-identical to omitting exactly the overflow',()=>{
  for (const n of [1,30,31,45]) {
    const messages=imageHistory(n);
    const projection=projectImageContext(messages,30,1);
    assert.equal(projection.summary.omitted_images,Math.max(0,n-30));
    const expected=structuredClone(messages);let seen=0;
    for (const message of expected) for (const [index,part] of message.content.entries()) {
      if (part.type!=='image' || seen++ >= Math.max(0,n-30)) continue;
      const sha256=createHash('sha256').update(Buffer.from(part.data,'base64')).digest('hex');
      message.content[index]={type:'text',text:`Historical pixels omitted from this request by frozen image policy; toolCallId=${message.toolCallId}; image_index=0; SHA256=${sha256}. Pixels were not reread; this marker grants no authority or source-read proof.`};
    }
    assert.equal(JSON.stringify(projection.messages),JSON.stringify(expected),`n=${n}`);
  }
});
test('consecutive requests within a block share a byte-identical serialized prefix',()=>{
  const serial=n=>projectImageContext(imageHistory(n,3),39,10).messages.map(message=>JSON.stringify(message));
  // Three images per turn under 39/10: whole blocks go only at 42, 51 and 60 images.
  const stable=[];
  for (let n=14; n<=20; n++) {
    const previous=serial(n-1), current=serial(n);
    stable.push(JSON.stringify(current.slice(0,previous.length))===JSON.stringify(previous));
  }
  assert.deepEqual(stable,[false,true,true,false,true,true,false]);
});
test('a whole block never reaches into the protected latest batch',()=>{
  // 3 historical images plus a protected batch of 38 under max 39, block 10: overflow 2 rounds to 10, capped at 3.
  const messages=[...imageHistory(3),{role:'assistant',content:[{type:'toolCall',id:'batch',name:'observe',arguments:{}}]},
    {role:'toolResult',toolCallId:'batch',content:Array.from({length:38},(_,index)=>({type:'image',mimeType:'image/png',data:Buffer.from(`batch-${index}`).toString('base64')}))}];
  const projection=projectImageContext(messages,39,10);
  assert.equal(projection.summary.blocked,false);assert.equal(projection.summary.protected_images,38);
  assert.equal(projection.summary.omitted_images,3);assert.equal(pixels(projection),38);
  assert.equal(projectImageContext(messages,37,10).summary.blocked,true,'protected over the peak still blocks');
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
test('the frozen block reaches the actual serializer and its telemetry',async t=>{
  const configuration=route();configuration.max_context_images=2;configuration.context_image_block=2;
  const {result,payloads,events}=await scenario(t,[
    reply(null,[['observe',{}],['observe',{}]],true,undefined,'old'),
    reply(null,[['observe',{}],['integer',{value:7}]],true,undefined,'current'),
    reply(null,[['observe',{}]],true,undefined,'newest'),reply()],{configuration});
  assert.equal(result.ok,true);
  const imageCount=payload=>payload.messages.flatMap(message=>Array.isArray(message.content)?message.content:[])
    .filter(part=>part.type==='image_url').length;
  // Three images overflow by one, so a whole block of two goes; four overflow by two, still one block.
  assert.deepEqual(payloads.map(imageCount),[0,2,1,2]);
  const projections=events.filter(event=>event.type==='context-image-projection');
  assert.deepEqual(projections.map(event=>[event.omitted_images,event.context_image_block]),[[0,2],[0,2],[2,2],[2,2]]);
  assert.equal(events.find(event=>event.type==='host-start').context_image_block,2);
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
test('an actor keeps the SDK validation refusal text unchanged; only a level gets field feedback',async t=>{
  const bad={snapshot_id:'fixture-snapshot',intent:{entry_type:'work',entry:{stage:'x'.repeat(244),available:[{subject:'small cardboard box'}]}}};
  const {result,payloads,events}=await scenario(t,[reply(null,[['fixture_remember',bad]],true,undefined,'bad'),reply()],
    {configuration:{...route(),max_requests:3},enabledTools:['fixture_remember']});
  assert.equal(result.ok,true);
  const text=payloads[1].messages.find(m=>m.role==='tool'&&m.tool_call_id==='bad-0').content;
  assert.match(text,/^Validation failed for tool "fixture_remember":/);
  assert.ok(!text.includes('Valid example call')&&!text.includes('abstaining'));
  assert.equal(events.filter(e=>e.type==='tool-validation-feedback').length,0);
});

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
  const {stdout}=await promisify(execFile)(python,['-c','import json; from harness.player_tools import HOST_TOOLS, PROFILES, tool_specs; specs=tool_specs(); print(json.dumps({name:{"schema":specs[name][1],"description":specs[name][0]} for name in PROFILES["flat"] if name not in HOST_TOOLS}))'],{cwd:productionRoot,maxBuffer:INPUT_LIMIT_BYTES});
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
  assert.deepEqual(handoff.parameters.required,[]);
  assert.deepEqual(Object.keys(handoff.parameters.properties),[]);
  assert.ok(chosen.includes('computer_result')&&chosen.includes('player_result'));
  assert.ok(chosen.every(name=>!name.startsWith('enactive_')));
  assert.ok(payloads[0].messages[0].content.includes('Only basic computer control is authoritative'));
  assert.throws(()=>process.kill(events.find(e=>e.type==='mcp-connected').child_pid,0),{code:'ESRCH'});
});

test('actor intent tail is a host-internal custodian read that the model never sees as a tool', async ()=>{
  const chosen=['computer_observe','computer_input','computer_result','player_result'], payloads=[], events=[];
  const result=await runHost({configuration:{...route(),intent_tail_bytes:256},mcpConfig:productionMcp(chosen),
    context:'Frozen current player guide',prompt:'Do not call tools.',model:model.id,effort:'off',
    timeoutSeconds:10,env:{OFFLINE_TEST_KEY:'fixture-key'},
    fetch:async(_url,init)=>{payloads.push(JSON.parse(init.body));return reply();},onEvent:e=>events.push(e)});
  assert.equal(result.ok,true);
  assert.ok(payloads[0].tools.every(tool=>tool.function.name!=='player_intent'));
  const tail=JSON.stringify(payloads[0].messages.at(-1));
  assert.ok(tail.includes('Current intent (software-published') && tail.includes('No committed intent.'));
  const event=events.find(e=>e.type==='intent-tail');
  assert.equal(event.available,true);assert.equal(event.record_id,null);assert.equal(event.request_id,'request-1');
  const refused=await runHost({configuration:route(),mcpConfig:productionMcp([...chosen,'player_intent']),
    context:'Frozen current player guide',prompt:'Do not call tools.',model:model.id,effort:'off',
    timeoutSeconds:10,env:{OFFLINE_TEST_KEY:'fixture-key'},fetch:async()=>reply(),onEvent:()=>{}});
  assert.equal(refused.ok,false);assert.equal(refused.reason,'host-internal-tool-enabled');
});

test('intent tail formatting is bounded, labelled and honest about failure and age', ()=>{
  const value={schema:'player-intent/1',record:{record_id:'r1',text:'Reach the door é'.repeat(20),sources:['s1'],
    expected_observations:['adjacent door'],status:'open',confidence:0.4},
    age:{seconds:12.34,inputs_since_commit:3,inputs_by_this_actor:7,same_actor:true,same_session:true}};
  const tail=formatIntentTail(value,128);
  assert.ok(tail.text.startsWith(INTENT_LABEL+'\n') && tail.surfaced_bytes<=128 && tail.omitted_bytes>0);
  assert.ok(tail.text.includes('bytes omitted by the frozen intent bound') && !tail.text.includes('�'));
  const full=formatIntentTail(value,4096);
  assert.equal(full.omitted_bytes,0);assert.ok(full.text.includes('Age: 3 inputs since commit; 12.3 seconds; this session'));
  const earlier=formatIntentTail({...value,age:{...value.age,inputs_since_commit:null,same_actor:false,same_session:false}},4096);
  assert.ok(earlier.text.includes('7 inputs by this actor; committed for an earlier actor') && earlier.text.includes('an earlier session'));
  assert.ok(formatIntentTail(null,256).text.includes('Unavailable: the intent read failed or was malformed'));
  assert.equal(boundedText('ééé',3).text,'é');
});

const terminalTools=['player_level_keep','player_level_replace','player_level_close','player_level_abstain'];
const levelTools=['player_log_read',...terminalTools];
const levelRoute={...route(),role:'level'};
const keepCall=['player_level_keep',{reason:'Still valid',sources:[]}];
const replaceCall=['player_level_replace',{text:'x',expected_observations:[],status:'open',confidence:0.5,sources:[],previous_outcome:'none',previous_reason:''}];
const closeCall=['player_level_close',{outcome:'achieved',reason:'Done',sources:[]}];
const abstainCall=['player_level_abstain',{reason_code:'other',reason:'Nothing to act on',sources:[]}];
const rejectedReplace=['player_level_replace',{...replaceCall[1],previous_outcome:'bogus'}];
const blankAbstain=['player_level_abstain',{...abstainCall[1],reason:' '}];
const readCall=['player_log_read',{after:0,limit:5}];
const levelScenario=(t,sequence,max_requests=route().max_requests)=>
  scenario(t,sequence,{configuration:{...levelRoute,max_requests},enabledTools:levelTools});
const toolNames=payload=>payload.tools.map(tool=>tool.function.name);

test('a level pass requires a tool call on every request and an actor does not', async t=>{
  const level=await levelScenario(t,[reply(null,[abstainCall])]);
  assert.equal(level.payloads[0].tool_choice,'required');
  const actor=await scenario(t,[reply()]);
  assert.equal(Object.hasOwn(actor.payloads[0],'tool_choice'),false);
});

test('a level pass ends on a replace and emits one level-pass and level-commit', async t=>{
  const {result,events,payloads}=await levelScenario(t,[reply(null,[readCall,replaceCall])]);
  assert.equal(result.ok,true);assert.equal(result.reason,'completed');assert.equal(payloads.length,1);
  assert.equal(events.filter(e=>e.type==='level-pass').length,1);
  const [commit]=events.filter(e=>e.type==='level-commit');
  assert.deepEqual([commit.action,commit.inputs_since,commit.record_ids],['replace',1,['7'.repeat(32)]]);
  assert.equal(events.some(e=>e.type==='intent-tail'||e.type==='level-abstain'),false);
});

for (const [name,call,action] of [['keep',keepCall,'keep'],['close',closeCall,'close']]) {
  test(`a level pass ends on a discarded ${name}`, async t=>{
    const {result,events,payloads}=await levelScenario(t,[reply(null,[call])]);
    assert.equal(result.ok,true);assert.equal(payloads.length,1);
    const [discard]=events.filter(e=>e.type==='level-discard');
    assert.deepEqual([discard.action,discard.inputs_since],[action,11]);
  });
}

test('a level pass ends on a valid abstain and emits level-abstain with its code and reason', async t=>{
  const {result,events,payloads}=await levelScenario(t,[reply(null,[abstainCall])]);
  assert.equal(result.ok,true);assert.equal(payloads.length,1);
  const [abstain]=events.filter(e=>e.type==='level-abstain');
  assert.deepEqual([abstain.reason_code,abstain.reason,abstain.request_id,typeof abstain.tool_call_id],['other','Nothing to act on','request-1','string']);
  assert.equal(events.some(e=>e.type==='level-commit'||e.type==='level-discard'),false);
});

test('a rejected terminal call does not end the pass, and a later call after the ending one is refused', async t=>{
  const {result,events,payloads}=await levelScenario(t,[
    reply(null,[rejectedReplace]),
    reply(null,[blankAbstain]),
    reply(null,[replaceCall,abstainCall])]);
  assert.equal(result.ok,true);assert.equal(payloads.length,3);
  assert.deepEqual(events.filter(e=>e.type.startsWith('level-')&&e.type!=='level-pass'&&e.type!=='level-reserved-request'&&e.type!=='level-terminal-call').map(e=>e.type),['level-commit']);
  const refused=events.find(e=>e.type==='tool-refused');
  assert.deepEqual([refused.tool,refused.reason,refused.dispatched],['player_level_abstain','level-ended',false]);
});

test('a level pass that ends without a terminal call fails as level-no-proposal', async t=>{
  for (const sequence of [[reply('I propose a subgoal')],[reply(null,[readCall]),reply('Committed.')]]) {
    const {result,events}=await levelScenario(t,sequence);
    assert.equal(result.ok,false);assert.equal(result.reason,'level-no-proposal');
    assert.equal(events.find(e=>e.type==='abort').reason,'level-no-proposal');
  }
  const rejected=await levelScenario(t,[reply(null,[rejectedReplace]),reply('Sorry.')]);
  assert.equal(rejected.result.reason,'level-no-proposal');
});

test('a failure latched in a level pass keeps its own reason rather than level-no-proposal', async t=>{
  const limited=await levelScenario(t,[reply(null,[readCall]),reply(null,[abstainCall])],1);
  assert.equal(limited.result.ok,false);assert.equal(limited.result.reason,'request-limit');
  const timeout=await scenario(t,[init=>new Promise((_,reject)=>init.signal.addEventListener('abort',()=>reject(new Error('aborted')),{once:true}))],{configuration:{...levelRoute,request_timeout_seconds:.05},enabledTools:levelTools});
  assert.equal(timeout.result.ok,false);assert.notEqual(timeout.result.reason,'level-no-proposal');
  assert.equal(timeout.result.reason,'request-timeout');
});

test('the last two requests of a level pass offer only the terminal tools and say so', async t=>{
  const {result,events,payloads}=await levelScenario(t,[
    reply(null,[readCall]),reply(null,[readCall]),reply(null,[rejectedReplace]),reply(null,[replaceCall])],4);
  assert.equal(result.ok,true);assert.equal(payloads.length,4);
  assert.deepEqual(toolNames(payloads[0]),levelTools);
  assert.deepEqual(toolNames(payloads[1]),levelTools);
  assert.deepEqual(toolNames(payloads[2]),terminalTools);
  assert.deepEqual(toolNames(payloads[3]),terminalTools);
  for (const payload of payloads) assert.equal(payload.tool_choice,'required');
  const status=payload=>JSON.stringify(payload.messages.at(-1));
  assert.ok(!status(payloads[1]).includes('offers only the pass-ending tools'));
  assert.ok(status(payloads[2]).includes('Remaining allowance including this request: 2.')&&status(payloads[2]).includes('offers only the pass-ending tools'));
  assert.deepEqual(events.filter(e=>e.type==='level-reserved-request').map(e=>e.request_id),['request-3','request-4']);
});

test('an actor is never restricted to terminal tools, and a pass of two requests or fewer is terminal-only', async t=>{
  const actor=await scenario(t,[reply(null,[['observe',{}]]),reply(null,[['observe',{}]]),reply()],{configuration:{...route(),max_requests:3}});
  assert.ok(actor.payloads.every(payload=>toolNames(payload).length===3));
  assert.equal(actor.events.some(e=>e.type==='level-reserved-request'),false);
  const short=await levelScenario(t,[reply(null,[replaceCall])],2);
  assert.deepEqual(toolNames(short.payloads[0]),terminalTools);
});

test('a terminal call refused on the last allowed request settles as level-final-refusal, not request-limit', async t=>{
  const {result,events,payloads}=await levelScenario(t,[reply(null,[readCall]),reply(null,[blankAbstain]),reply(null,[rejectedReplace])],3);
  assert.equal(payloads.length,3);assert.equal(result.ok,false);assert.equal(result.reason,'level-final-refusal');
  assert.equal(events.find(e=>e.type==='abort').reason,'level-final-refusal');
  assert.equal(events.at(-1).reason,'level-final-refusal');
  // A refused terminal call with budget left is repaired by the next request instead.
  const repaired=await levelScenario(t,[reply(null,[readCall]),reply(null,[blankAbstain]),reply(null,[abstainCall])],3);
  assert.equal(repaired.result.ok,true);
  // The last request used by an ordinary tool is still a request-limit.
  const limited=await levelScenario(t,[reply(null,[readCall]),reply(null,[readCall]),reply(null,[readCall])],3);
  assert.equal(limited.result.reason,'request-limit');
});

test('a terminal call whose transport is lost ends the pass as level-uncertain, with its identity and no further dispatch', async t=>{
  const lost=['player_level_close',{outcome:'achieved',reason:'lost transport',sources:[]}];
  const {result,events,payloads,calls}=await levelScenario(t,[reply(null,[readCall,lost,abstainCall]),reply(null,[abstainCall])]);
  assert.equal(result.ok,false);assert.equal(result.reason,'level-uncertain');assert.equal(payloads.length,1);
  const [uncertain]=events.filter(e=>e.type==='level-uncertain');
  assert.deepEqual([uncertain.tool,uncertain.identity,uncertain.request_id,typeof uncertain.tool_call_id],['player_level_close','1'.repeat(32),'request-1','string']);
  assert.equal(events.some(e=>['level-commit','level-discard','level-abstain'].includes(e.type)),false);
  const refused=events.find(e=>e.type==='tool-refused');
  assert.deepEqual([refused.tool,refused.reason,refused.dispatched],['player_level_abstain','level-ended',false]);
  assert.equal(events.find(e=>e.type==='abort').reason,'level-uncertain');
  assert.equal(events.at(-1).reason,'level-uncertain');
  assert.deepEqual(calls.map(c=>c.tool),['player_log_read','player_level_close']);
});

test('reserved requests are logical requests: a provider retry never changes its request\'s declarations, and attempts bring the window forward', async t=>{
  // Logical request 1 is retried once (two attempts), so only two HTTP attempts remain when logical request 2 starts:
  // the window opens by attempts there, and the terminal-only declarations still appear before the budget ends.
  const shifted=await levelScenario(t,[serverError(502),reply(null,[readCall]),reply(null,[readCall]),reply(null,[rejectedReplace])],4);
  assert.equal(shifted.result.reason,'level-final-refusal');assert.equal(shifted.payloads.length,4);
  assert.deepEqual(shifted.payloads.map(toolNames),[levelTools,levelTools,terminalTools,terminalTools]);
  assert.deepEqual(shifted.events.filter(e=>e.type==='level-reserved-request').map(e=>[e.logical_request_id,e.request_id]),
    [['request-2','request-3'],['request-3','request-4']]);
  // One numbering: the logical count, shared by every attempt of a request, in request-start and level-reserved-request.
  assert.deepEqual(shifted.events.filter(e=>e.type==='request-start').map(e=>[e.request_id,e.logical_request_id]),
    [['request-1','request-1'],['request-2','request-1'],['request-3','request-2'],['request-4','request-3']]);
  assert.ok(JSON.stringify(shifted.payloads[2].messages.at(-1)).includes('offers only the pass-ending tools'));
  assert.equal(JSON.stringify(shifted.payloads[1].messages.at(-1)).includes('offers only the pass-ending tools'),false);
  // A retry of a reserved logical request resends the same terminal-only declarations.
  const retried=await levelScenario(t,[reply(null,[readCall]),serverError(502),reply(null,[abstainCall])],3);
  assert.equal(retried.result.ok,true);assert.equal(retried.payloads.length,3);
  assert.deepEqual(retried.payloads.map(toolNames),[levelTools,terminalTools,terminalTools]);
  assert.deepEqual(retried.events.filter(e=>e.type==='level-reserved-request').map(e=>e.logical_request_id),['request-2']);
  assert.equal(JSON.stringify(retried.payloads[1].tools),JSON.stringify(retried.payloads[2].tools));
  assert.ok(JSON.stringify(retried.payloads[2].messages.at(-1)).includes('offers only the pass-ending tools'));
});

test('a non-terminal call on a reserved request is refused without dispatch, with the tools to call and the fix line', async t=>{
  const {result,events,payloads,calls}=await levelScenario(t,[reply(null,[readCall],true,undefined,'read'),reply(null,[abstainCall])],2);
  assert.equal(result.ok,true);assert.equal(payloads.length,2);
  assert.deepEqual(calls.map(c=>c.tool),['player_level_abstain']);
  const [refused]=events.filter(e=>e.type==='tool-refused');
  assert.deepEqual([refused.tool,refused.reason,refused.dispatched],['player_log_read','level-reserved',false]);
  const message=payloads[1].messages.find(m=>m.role==='tool'&&m.tool_call_id==='read-0').content;
  assert.ok(message.includes('player_log_read is not offered on this request and was not run')&&message.includes(terminalTools.join(', ')),message);
  assert.ok(message.endsWith('Fix the call and resend it; abstaining is not the remedy for a fixable call.'),message);
  // The refusal does not end the pass: the next request's terminal call does.
  assert.equal(events.some(e=>e.type==='level-abstain'),true);
});

test('every terminal call is traced, with unparseable arguments flagged and no tool-start', async t=>{
  const raw=(name,args)=>new Response([{id:'r',model:'fixture-backend',choices:[{index:0,delta:{role:'assistant',tool_calls:[{index:0,id:'raw-0',type:'function',function:{name,arguments:args}}]},finish_reason:null}]},
    {id:'r',model:'fixture-backend',choices:[{index:0,delta:{},finish_reason:'tool_calls'}],usage:{prompt_tokens:11,completion_tokens:5,total_tokens:16}}]
    .map(chunk=>'data: '+JSON.stringify(chunk)+'\n\n').join('')+'data: [DONE]\n\n',{headers:{'content-type':'text/event-stream'}});
  const {result,events,calls}=await levelScenario(t,[raw('player_level_abstain','{"reason_code":"other",'),reply(null,[readCall,blankAbstain,abstainCall],true,undefined,'ok')]);
  assert.equal(result.ok,true);
  const traced=events.filter(e=>e.type==='level-terminal-call').map(e=>[e.request_id,e.tool_call_id,e.tool,e.arguments_error]);
  assert.deepEqual(traced,[['request-1','raw-0','player_level_abstain',true],['request-2','ok-1','player_level_abstain',false],['request-2','ok-2','player_level_abstain',false]]);
  const started=events.filter(e=>e.type==='tool-start').map(e=>e.tool_call_id);
  assert.equal(started.includes('raw-0'),false);
  // The blank abstain was dispatched (the custodian rejects it); the unparseable one never was.
  assert.deepEqual(calls.map(c=>c.tool),['player_log_read','player_level_abstain','player_level_abstain']);
});

test('a terminal call whose arguments the SDK changed is refused naming the field, with the fix line', async t=>{
  const coerced=['player_level_replace',{...replaceCall[1],confidence:'0.5'}];
  const {result,calls,payloads,events}=await levelScenario(t,[reply(null,[coerced],true,undefined,'c'),reply(null,[replaceCall])]);
  assert.equal(result.ok,true);assert.deepEqual(calls.map(c=>c.tool),['player_level_replace']);
  assert.equal(events.find(e=>e.type==='tool-refused').reason,'tool-arguments-changed');
  const message=payloads[1].messages.find(m=>m.role==='tool'&&m.tool_call_id==='c-0').content;
  assert.ok(message.includes('MCP input not sent')&&message.includes('player_level_replace')&&message.includes('field confidence'),message);
  assert.ok(message.endsWith('Fix the call and resend it; abstaining is not the remedy for a fixable call.'),message);
  assert.deepEqual(changedFields({a:1,b:{c:[1],d:2}},{a:1,b:{c:[2],d:3}}),['b.c','b.d']);
});

test('production level schemas: a refused call names each field, the rule, the allowed values, a received value and an example', async ()=>{
  const bad={text:'t'.repeat(3000),expected_observations:'one',status:'open',confidence:3,record_id:'r1',
    previous_outcome:'done',previous_reason:''};
  const payloads=[], events=[];
  const sequence=[reply(null,[['player_level_replace',bad]],true,undefined,'bad'),reply(null,[['player_level_abstain',{reason_code:'other'}]],true,undefined,'bad2'),reply()];
  const result=await runHost({configuration:{...levelRoute,max_requests:8},mcpConfig:productionMcp(levelTools),
    context:'Frozen current player guide',prompt:'Level pass.',model:model.id,effort:'off',timeoutSeconds:20,env:{OFFLINE_TEST_KEY:'fixture-key'},
    fetch:async(_url,init)=>{payloads.push(JSON.parse(init.body));return sequence[payloads.length-1] ?? reply();},onEvent:e=>events.push(e)});
  // Nothing was valid, so no call reached the custodian and the pass ends without a terminal call.
  assert.equal(result.reason,'level-no-proposal');assert.equal(events.filter(e=>e.type==='tool-start').length,0);
  const first=payloads.at(-1).messages.find(m=>m.role==='tool'&&m.tool_call_id==='bad-0').content;
  assert.match(first,/^Validation failed for tool "player_level_replace":/);
  assert.ok(first.includes('- previous_outcome: must be one of "none", "achieved", "failed", "abandoned", "revised"; received "done"'),first);
  assert.match(first,/- confidence: .*maximum 1.*received 3/);
  assert.match(first,/- expected_observations: .*received "one"/);
  assert.match(first,/- sources: required property is missing/);
  assert.ok(first.includes('unknown properties "record_id" are not allowed'),first);
  const received=/- text: .*received (".*)/.exec(first)[1];
  assert.ok(received.length<200&&received.includes('more characters'),'received values are truncated to 120 characters');
  assert.ok(first.includes('Valid example call: player_level_replace {"text":"<text>"'),first);
  assert.ok(first.includes('"previous_outcome":"none","previous_reason":""'),first);
  assert.ok(first.endsWith('Fix the call and resend it; abstaining is not the remedy for a fixable call.'),first);
  assert.ok(first.includes('In this example previous_outcome is "none"')&&first.includes('valid only when there is no current subgoal'),first);
  assert.ok(!first.includes('schema is false'));
  const second=payloads.at(-1).messages.find(m=>m.role==='tool'&&m.tool_call_id==='bad2-0').content;
  assert.ok(second.includes('- reason: required property is missing')&&second.includes('- sources: required property is missing'),second);
  assert.ok(second.includes('Valid example call: player_level_abstain {"reason_code":"insufficient_evidence","reason":"<reason>","sources":[]}'),second);
  assert.equal(events.filter(e=>e.type==='tool-validation-feedback').length,2);
  assert.ok(payloads[0].tools.every(tool=>!JSON.stringify(tool.function.parameters).includes('"const"')));
});

test('a level-role host without the level tools fails before any provider request', async t=>{
  const {result,payloads}=await scenario(t,[reply()],{configuration:{...route(),role:'level'},enabledTools:['observe']});
  assert.equal(result.ok,false);assert.equal(result.reason,'missing-required-tools');assert.equal(payloads.length,0);
});

for (const [name,intentFixture] of [['a failed read','error'],['an unexpected shape',
    JSON.stringify({schema:'player-intent/1',record:{record_id:'r',text:'x',sources:'not-a-list'},age:{}})]]) {
  test(`an intent tail after ${name} shows Unavailable and the actor continues`, async t=>{
    const {result,payloads,events}=await scenario(t,[reply(null,[['observe',{}]]),reply()],
      {configuration:{...route(),intent_tail_bytes:256},enabledTools:['observe'],intentFixture});
    assert.equal(result.ok,true);assert.equal(payloads.length,2);
    for (const payload of payloads) assert.ok(JSON.stringify(payload.messages.at(-1)).includes('Unavailable: the intent read failed or was malformed'));
    assert.deepEqual(events.filter(e=>e.type==='intent-tail').map(e=>e.available),[false,false]);
  });
}

test('level commit telemetry distinguishes commits, discards and local tool errors', ()=>{
  const result=value=>({content:[{type:'text',text:JSON.stringify(value)}]});
  const committed=levelCommitEvent(result({schema:'player-level-commit/3',status:'committed',action:'replace',reason:null,position:4,
    inputs_since:1,staleness_inputs:10,records:[{id:'w1'}],kept:[]}));
  assert.deepEqual(committed,{type:'level-commit',action:'replace',reason:null,position:4,inputs_since:1,staleness_inputs:10,record_ids:['w1'],kept:[]});
  for (const action of ['keep','close'])
    assert.equal(levelCommitEvent(result({schema:'player-level-commit/3',status:'committed',action,reason:null,position:4,
      inputs_since:1,staleness_inputs:10,records:[],kept:[]})).action,action);
  assert.equal(levelCommitEvent(result({schema:'player-level-commit/3',status:'discarded',action:'keep',reason:'stale',position:4,
    inputs_since:12,staleness_inputs:10,records:[],kept:[]})).type,'level-discard');
  assert.equal(levelCommitEvent({...result({schema:'player-level-commit/3',status:'committed',action:'keep'}),isError:true}),null);
  assert.equal(levelCommitEvent({content:[{type:'text',text:'{'}]}),null);
  assert.equal(levelCommitEvent(result({schema:'player-error/1'})),null);
  for (const old of ['player-level-commit/1','player-level-commit/2'])
    assert.equal(levelCommitEvent(result({schema:old,status:'committed',action:'keep'})),null);
  assert.equal(levelCommitEvent(result({schema:'player-level-commit/3',status:'committed',action:'bogus'})),null);
});

test('level abstain telemetry needs a valid abstain result with its reason code and never a local tool error', ()=>{
  const result=value=>({content:[{type:'text',text:JSON.stringify(value)}]});
  const ok={schema:'player-level-abstain/2',status:'abstained',reason_code:'no_change_needed',reason:'No evidence'};
  assert.deepEqual(levelAbstainEvent(result(ok)),{type:'level-abstain',reason_code:'no_change_needed',reason:'No evidence'});
  assert.equal(levelAbstainEvent({...result(ok),isError:true}),null);
  assert.equal(levelAbstainEvent(result({...ok,reason:''})),null);
  assert.equal(levelAbstainEvent(result({...ok,reason_code:undefined})),null);
  for (const old of ['player-level-abstain/0','player-level-abstain/1'])
    assert.equal(levelAbstainEvent(result({...ok,schema:old})),null);
  assert.equal(levelAbstainEvent({content:[{type:'text',text:'{'}]}),null);
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
  const partial=()=>new Response(new ReadableStream({start(c){
    c.enqueue(new TextEncoder().encode('data: '+JSON.stringify({choices:[{index:0,delta:{role:'assistant',content:'par'},finish_reason:null}]})+'\n\n'));
    c.error(new Error('fixture-key reset after headers'));
  }}),{headers:{'content-type':'text/event-stream'}});
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
      return reply(null,[['computer_observe',{}],['player_handoff',{}],['computer_observe',{}]]);
    },onEvent:e=>events.push(e)});
  assert.deepEqual(result,{ok:true,reason:'handoff',requests:1,finalText:''});
  assertRequestMetadata(events,bodies);
  assert.deepEqual(events.filter(e=>e.type==='tool-start').map(e=>e.tool),['computer_observe','player_handoff']);
  const value=JSON.parse(events.find(e=>e.type==='tool-result'&&e.tool==='player_handoff').result.content[0].text);
  assert.equal(value.schema,'computer-operation/1');assert.equal(value.status,'sealed');
  assert.equal(value.handoff.schema,'player-handoff/2');assert.equal(value.handoff.grants_authority,false);
  const event=events.find(e=>e.type==='handoff');
  assert.equal(event.handoff_id,value.operation_id);assert.equal(event.session,value.session);
  assert.equal(event.actor_id,value.actor_id);assert.equal(event.context_id,value.handoff.context_id);
  assert.equal(event.context_sha256,value.handoff.context_sha256);assert.equal(event.grants_authority,false);
  assert.deepEqual(events.filter(e=>e.type==='tool-refused').map(e=>[e.tool,e.reason,e.dispatched]),[['computer_observe','handoff',false]]);
  assert.throws(()=>process.kill(events.find(e=>e.type==='mcp-connected').child_pid,0),{code:'ESRCH'});
});

const handoffArgs = {};
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
