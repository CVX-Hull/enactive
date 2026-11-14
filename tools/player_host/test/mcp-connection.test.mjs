import test from 'node:test';
import assert from 'node:assert/strict';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PassThrough } from 'node:stream';
import { createHash } from 'node:crypto';
import { runHost, validateMcpConfiguration, INPUT_LIMIT_BYTES } from '../host.mjs';
import { python, model, route, reply, scenario, assertRequestMetadata } from './host-scenario.mjs';

test('frozen MCP config rejects disabled and malformed fields', ()=>{
  const valid={command:'python',args:[],cwd:'/',enabled:true,enabled_tools:['observe'],startup_timeout_sec:1,tool_timeout_sec:1};
  assert.doesNotThrow(()=>validateMcpConfiguration(valid));
  for (const change of [{enabled:false},{required:'yes'},{args:'bad'},{enabled_tools:['observe','observe']},{tool_timeout_sec:NaN},{tools:{observe:false}},{ambient:1}]) {
    assert.throws(()=>validateMcpConfiguration({...valid,...change}));
  }
});

const root=fileURLToPath(new URL('../../../',import.meta.url));
const productionRoot=process.env.ENACTIVE_TEST_PRODUCTION_ROOT ?? root;
function productionMcp(enabled_tools, actorId) {
  return {command:resolve(python),args:[join(productionRoot,'tests/player_service_fixture.py'),'--stdio',...(actorId ? ['--actor-id',actorId] : [])],
    cwd:productionRoot,enabled:true,enabled_tools,startup_timeout_sec:5,tool_timeout_sec:2};
}
test('real production MCP discovery forwards all exact current actor-only tool schemas', async ()=>{
  const { execFile } = await import('node:child_process');
  const { promisify } = await import('node:util');
  const {stdout}=await promisify(execFile)(python,['-c','import json; from harness.player_tools import tool_specs; print(json.dumps({name:{"schema":schema,"description":description} for name,(description,schema) in tool_specs().items()}))'],{cwd:productionRoot,maxBuffer:INPUT_LIMIT_BYTES});
  const expected=JSON.parse(stdout), payloads=[], bodies=[], events=[];
  const chosen=Object.keys(expected);
  assert.equal(chosen.length,16);
  const result=await runHost({knowledge:{schema:'delivered-knowledge/1',version:null,coverage:null,articles:[],facts:[]},finishReserveUsd:'0',session:'2'.repeat(32),actorId:'3'.repeat(32),pendingControlId:null,control:new PassThrough(),configuration:route(),mcpConfig:productionMcp(chosen),
    context:'Frozen current player guide',prompt:'Do not call tools.',model:model.id,effort:'off',
    timeoutSeconds:10,env:{OFFLINE_TEST_KEY:'fixture-key'},
    fetch:async(_url,init)=>{bodies.push(init.body);payloads.push(JSON.parse(init.body));return reply();},onEvent:e=>events.push(e)});
  assert.equal(result.ok,true);
  assertRequestMetadata(events,bodies);
  assert.deepEqual(payloads[0].tools.map(tool=>tool.function.name),[...chosen,'player_finish']);
  for(const tool of payloads[0].tools.filter(tool=>tool.function.name!=='player_finish')) {
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

test('production MCP preserves actual source JSON and PNG through Pi while event images are references',async()=>{
  const payloads=[],bodies=[],events=[];
  const result=await runHost({knowledge:{schema:'delivered-knowledge/1',version:null,coverage:null,articles:[],facts:[]},finishReserveUsd:'0',session:'2'.repeat(32),actorId:'3'.repeat(32),pendingControlId:null,control:new PassThrough(),configuration:route(),mcpConfig:productionMcp(['computer_observe','player_source']),
    context:'Offline current pixel fixture',prompt:'Read actual source pixels.',model:model.id,
    effort:'off',timeoutSeconds:10,env:{OFFLINE_TEST_KEY:'fixture-key'},
    fetch:async(_url,init)=>{
      bodies.push(init.body);payloads.push(JSON.parse(init.body));
      if(payloads.length===1)return reply(null,[['computer_observe',{}]]);
      if(payloads.length===2) {
        const shown=JSON.parse(events.find(e=>e.type==='tool-result').result.content[0].text);
        return reply(null,[['player_source',{source_id:shown.source_id}]],true,undefined,'read');
      }
      return reply();
    },onEvent:e=>events.push(e)});
  assert.equal(result.ok,true);assert.equal(payloads.length,3);
  assertRequestMetadata(events,bodies);
  const observed=events.find(e=>e.type==='tool-result');
  // The model reads the short result; the trace holds the full operation record beside it.
  const original=observed.result.structuredContent;
  assert.deepEqual(JSON.parse(observed.result.content[0].text),{schema:'player-computer-result/2',status:'completed',
    source_id:original.source.source_id,width:4,height:4});
  const toolMessage=payloads[1].messages.find(message=>message.role==='tool');
  const sentText=typeof toolMessage.content==='string'?toolMessage.content:toolMessage.content.filter(part=>part.type==='text').map(part=>part.text).join('');
  assert.equal(sentText,observed.result.content[0].text);
  assert.ok(!sentText.includes('receipts')&&!sentText.includes('actor_id'));
  assert.equal(original.schema,'player-computer-operation/1');assert.equal(original.status,'completed');
  assert.ok(original.receipts.length>0&&original.receipts[0].schema==='computer-receipt/2');
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
  const result=await runHost({knowledge:{schema:'delivered-knowledge/1',version:null,coverage:null,articles:[],facts:[]},finishReserveUsd:'0',session:'a'.repeat(32),actorId:'3'.repeat(32),pendingControlId:null,control:new PassThrough(),configuration:route(),mcpConfig:productionMcp(['computer_observe','player_handoff'],'3'.repeat(32)),
    context:'Offline current actor handoff fixture',prompt:'Retain unfinished context and hand off.',
    model:model.id,effort:'off',timeoutSeconds:10,env:{OFFLINE_TEST_KEY:'fixture-key'},
    fetch:async(_url,init)=>{
      bodies.push(init.body);payloads.push(JSON.parse(init.body));
      return reply(null,[['computer_observe',{}],['player_handoff',{ids:[],summary:'synthetic unfinished work'}],['computer_observe',{}]]);
    },onEvent:e=>events.push(e)});
  assert.deepEqual(result,{ok:true,reason:'handoff',requests:1,finalText:'',control_id:null});
  assertRequestMetadata(events,bodies);
  assert.deepEqual(events.filter(e=>e.type==='tool-start').map(e=>e.tool),['computer_observe','player_handoff']);
  const sealed=events.find(e=>e.type==='tool-result'&&e.tool==='player_handoff').result;
  assert.deepEqual(JSON.parse(sealed.content[0].text),{schema:'player-computer-result/2',status:'sealed'});
  const value=sealed.structuredContent;
  assert.equal(value.schema,'player-computer-operation/1');assert.equal(value.status,'sealed');
  assert.equal(value.handoff.schema,'player-handoff/1');assert.equal(value.handoff.grants_authority,false);
  const event=events.find(e=>e.type==='handoff');
  assert.equal(event.handoff_id,value.operation_id);assert.equal(event.session,value.session);
  assert.equal(event.actor_id,value.actor_id);assert.equal(event.context_id,value.handoff.context_id);
  assert.equal(event.context_sha256,value.handoff.context_sha256);assert.equal(event.grants_authority,false);
  assert.deepEqual(events.filter(e=>e.type==='tool-refused').map(e=>[e.tool,e.reason,e.dispatched]),[['computer_observe','handoff',false]]);
  assert.throws(()=>process.kill(events.find(e=>e.type==='mcp-connected').child_pid,0),{code:'ESRCH'});
});

test('production MCP foreign actor handoff cannot settle or dispatch later input',async()=>{
  const events=[];
  const result=await runHost({knowledge:{schema:'delivered-knowledge/1',version:null,coverage:null,articles:[],facts:[]},finishReserveUsd:'0',session:'a'.repeat(32),actorId:'2'.repeat(32),pendingControlId:null,control:new PassThrough(),configuration:route(),
    mcpConfig:productionMcp(['computer_observe','player_handoff'],'3'.repeat(32)),context:'Offline foreign actor fixture',
    prompt:'Retain unfinished context.',model:model.id,effort:'off',timeoutSeconds:10,env:{OFFLINE_TEST_KEY:'fixture-key'},
    fetch:async()=>reply(null,[['player_handoff',{ids:[],summary:'Foreign actor'}],['computer_observe',{}]]),onEvent:event=>events.push(event)});
  assert.equal(result.ok,false);assert.equal(result.reason,'invalid-handoff-receipt');assert.equal(result.requests,1);
  assert.deepEqual(events.filter(event=>event.type==='tool-start').map(event=>event.tool),['player_handoff']);
  assert.equal(events.filter(event=>event.type==='handoff').length,0);
  assert.throws(()=>process.kill(events.find(event=>event.type==='mcp-connected').child_pid,0),{code:'ESRCH'});
});
