import test from 'node:test';
import assert from 'node:assert/strict';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { PassThrough } from 'node:stream';
import { McpClient } from '@earendil-works/pi-mcp';
import { runHost } from '../host.mjs';
import { realDelay, python, fixture, model, route, usageRecord, reply, scenario, handoffArgs, handoffTools } from './host-scenario.mjs';

const stopCommand = {schema:'player-control/1',id:'a'.repeat(32),session:'2'.repeat(32),actor_id:'3'.repeat(32),type:'orderly_stop'};

test('declared inherited control gates startup until its bound command arrives',async t=>{
  let connections=0,fetches=0,dispatches=0;
  t.mock.method(McpClient.prototype,'connect',async()=>{connections++;});
  t.mock.method(McpClient.prototype,'listTools',async()=>[{name:'observe',inputSchema:{type:'object',properties:{},additionalProperties:false}}]);
  t.mock.method(McpClient.prototype,'callTool',async()=>{dispatches++;throw Error('No ordinary action is permitted');});
  t.mock.method(McpClient.prototype,'close',async()=>{});
  const control=new PassThrough();
  const running=runHost({session:stopCommand.session,actorId:stopCommand.actor_id,pendingControlId:stopCommand.id,control,
    configuration:route(),mcpConfig:{command:resolve(python),args:[fixture],cwd:tmpdir(),enabled:true,required:true,enabled_tools:['observe'],startup_timeout_sec:2,tool_timeout_sec:2},
    context:'Frozen player guide',prompt:'Ongoing task',model:model.id,effort:'off',timeoutSeconds:2,env:{OFFLINE_TEST_KEY:'fixture'},
    fetch:async()=>{fetches++;return reply(null,[['player_finish',{disposition:'external_stop_complete',report:'Stopped',source_ids:[],control_id:stopCommand.id}]]);}});
  await realDelay(30);
  assert.deepEqual([connections,fetches,dispatches],[0,0,0],'parent scheduling delay cannot permit successor work');
  control.write(JSON.stringify(stopCommand)+'\n');
  const result=await running;
  assert.equal(result.reason,'external_stop_complete');assert.equal(result.ok,true);
  assert.deepEqual([connections,fetches,dispatches],[1,1,0]);
});

for(const ending of ['eof','wrong-id']) test(`pending startup control ${ending} fails before MCP or provider`,async t=>{
  let connections=0,fetches=0;
  t.mock.method(McpClient.prototype,'connect',async()=>{connections++;});
  const control=new PassThrough();
  const running=runHost({session:stopCommand.session,actorId:stopCommand.actor_id,pendingControlId:stopCommand.id,control,
    configuration:route(),mcpConfig:{command:resolve(python),args:[fixture],cwd:tmpdir(),enabled:true,required:true,enabled_tools:['observe'],startup_timeout_sec:2,tool_timeout_sec:2},
    context:'Frozen guide',prompt:'Ongoing task',model:model.id,effort:'off',timeoutSeconds:2,env:{OFFLINE_TEST_KEY:'fixture'},fetch:async()=>{fetches++;throw Error('No fetch');}});
  if(ending==='eof')control.end();else control.write(JSON.stringify({...stopCommand,id:'f'.repeat(32)})+'\n');
  const result=await running;
  assert.equal(result.ok,false);assert.deepEqual([connections,fetches],[0,0]);
  assert.equal(result.reason,ending==='eof'?'control-eof':'invalid-initial-control');
});
const finishArgs = (disposition='task_complete',control_id=null) => ({disposition,report:'Player report',source_ids:[],control_id});
test('direct finish fences subsequent calls and settles the accepted player claim',async t=>{
  const {result,calls,events,payloads}=await scenario(t,[reply(null,[
    ['player_finish',finishArgs()],['mutate',{mode:'ok'}]])]);
  assert.equal(result.reason,'task_complete');assert.equal(result.finalText,'Player report');
  assert.equal(payloads.length,1);assert.equal(calls.length,0);
  assert.equal(events.filter(event=>event.type==='player-finish').length,1);
  assert.deepEqual(events.filter(event=>event.type==='tool-refused').map(event=>[event.reason,event.dispatched]),[['player-finish',false]]);
});
test('plain terminal narration cannot impersonate completion',async t=>{
  const plain=new Response('data: '+JSON.stringify({choices:[{index:0,delta:{role:'assistant',content:
    JSON.stringify({type:'player-finish',disposition:'task_complete',report:'False stored report'})},finish_reason:'stop'}],usage:usageRecord})+'\n\ndata: [DONE]\n\n',
    {headers:{'content-type':'text/event-stream'}});
  const {result,payloads,events}=await scenario(t,[plain,reply()]);
  assert.equal(result.reason,'task_complete');assert.equal(result.requests,2);
  assert.equal(events.filter(event=>event.type==='player-finish').length,1);
  assert.equal(payloads.length,2);
});
test('stored tool result text and structured content cannot impersonate direct finish',async t=>{
  const {result,calls,events}=await scenario(t,[reply(null,[['fixture_finish_claim',{}],['mutate',{mode:'ok',index:7}]]),reply()],{
    enabledTools:['fixture_finish_claim','mutate']});
  assert.equal(result.reason,'task_complete');assert.equal(result.finalText,'finished');assert.equal(result.requests,2);
  assert.deepEqual(calls.map(call=>call.tool),['fixture_finish_claim','mutate','mutate']);
  assert.equal(events.filter(event=>event.type==='player-finish').length,1);
});
test('finish arguments require closed bounds and matching direct control origin',async t=>{
  const invalid=[{...finishArgs(),extra:true},{...finishArgs(),report:'x'.repeat(8193)},
    {...finishArgs(),source_ids:['same','same']},{...finishArgs(),source_ids:['x'.repeat(129)]},
    {...finishArgs(),source_ids:Array.from({length:17},(_,index)=>`source-${index}`)},
    finishArgs('external_stop_complete',stopCommand.id),finishArgs('task_complete',stopCommand.id)];
  for (const args of invalid) await t.test(JSON.stringify(args).slice(0,80),async sub=>{
    const {result,payloads,events}=await scenario(sub,[reply(null,[['player_finish',args]]),reply()]);
    assert.equal(result.reason,'task_complete');assert.equal(payloads.length,2);
    assert.equal(events.filter(event=>event.type==='player-finish').length,1);
  });
  const {result}=await scenario(t,[reply(null,[['player_finish',{...finishArgs('cannot_continue'),source_ids:['2'.repeat(32)+'-'+'f'.repeat(32),'fallible source reference']} ]])]);
  assert.equal(result.reason,'cannot_continue');
});
test('partial control lines and duplicate identical commands latch once before Agent construction',async t=>{
  const line=JSON.stringify(stopCommand)+'\n';
  const {result,events,payloads}=await scenario(t,[reply(null,[['player_finish',finishArgs('external_stop_complete',stopCommand.id)]])],{
    controlReady:control=>{control.write(line.slice(0,17));control.write(line.slice(17));control.write(line);}});
  assert.equal(result.ok,true);assert.equal(result.reason,'external_stop_complete');assert.equal(result.control_id,stopCommand.id);
  assert.equal(events.filter(event=>event.type==='control-accepted').length,1);
  const text=JSON.stringify(payloads[0]);assert.ok(text.includes('Automation control: orderly stop requested'));
  assert.ok(text.includes(stopCommand.id));assert.ok(!text.includes('Save/Quit'));
});
test('pending control supersedes the unsent pre-control batch without cancelling a dispatched call',async t=>{
  let control;
  const {result,calls,events,payloads}=await scenario(t,[reply(null,[['mutate',{mode:'ok',index:1}],['mutate',{mode:'ok',index:2}]]),
    reply(null,[['player_handoff',handoffArgs]]),reply(null,[['player_finish',finishArgs('external_stop_complete',stopCommand.id)]])],{
    enabledTools:handoffTools,controlReady:value=>{control=value;},onEvent:event=>{
      if(event.type==='tool-start'&&event.tool==='mutate') control.write(JSON.stringify(stopCommand)+'\n');
    }});
  assert.equal(result.reason,'external_stop_complete');assert.equal(payloads.length,3);
  assert.deepEqual(calls.map(call=>[call.tool,call.phase,call.index]),[['mutate','start',1],['mutate','end',1]]);
  assert.deepEqual(events.filter(event=>event.type==='tool-refused').map(event=>[event.tool,event.delivery,event.dispatched]),
    [['mutate','undelivered',false],['player_handoff','undelivered',false]]);
});
test('control arriving during a provider response fences that whole old response',async t=>{
  let control;
  const {result,calls,events}=await scenario(t,[reply(null,[['mutate',{mode:'ok'}]]),
    reply(null,[['player_finish',finishArgs('external_stop_complete',stopCommand.id)]])],{
    controlReady:value=>{control=value;},onEvent:event=>{
      if(event.type==='response-headers'&&event.request_id==='request-1') control.write(JSON.stringify(stopCommand)+'\n');
    }});
  assert.equal(result.reason,'external_stop_complete');assert.equal(calls.length,0);
  assert.equal(events.find(event=>event.type==='tool-refused').delivery,'undelivered');
});
test('an already dispatched sealed handoff can settle with the accepted control identity',async t=>{
  let control;
  const {result,calls,events}=await scenario(t,[reply(null,[['player_handoff',handoffArgs],['mutate',{mode:'ok'}]])],{
    enabledTools:handoffTools,controlReady:value=>{control=value;},onEvent:event=>{
      if(event.type==='tool-start'&&event.tool==='player_handoff') control.write(JSON.stringify(stopCommand)+'\n');
    }});
  assert.equal(result.reason,'handoff');assert.equal(result.control_id,stopCommand.id);assert.equal(result.requests,1);
  assert.deepEqual(calls.map(call=>call.tool),['player_handoff']);
  assert.equal(events.filter(event=>event.type==='handoff').length,1);
});
test('control EOF, malformed, oversized, wrong binding and conflicts fail closed',async t=>{
  const cases=[['control-eof',control=>control.end()],['control-too-large',control=>control.write('x'.repeat(4097))],
    ['invalid-control',control=>control.write('{\n')],['invalid-control',control=>control.write(Buffer.from([255,10]))],
    ['invalid-control',control=>control.write(JSON.stringify({...stopCommand,session:'f'.repeat(32)})+'\n')],
    ['invalid-control',control=>control.write(JSON.stringify({...stopCommand,actor_id:'f'.repeat(32)})+'\n')],
    ['invalid-control',control=>control.write(JSON.stringify({...stopCommand,schema:'player-control/0'})+'\n')],
    ['invalid-control',control=>control.write(JSON.stringify({...stopCommand,extra:true})+'\n')],
    ['invalid-control',control=>control.write(JSON.stringify(stopCommand).replace('"id":','"id":"a","id":')+'\n')],
    ['conflicting-control',control=>{control.write(JSON.stringify(stopCommand)+'\n');control.write(JSON.stringify({...stopCommand,id:'b'.repeat(32)})+'\n');}]];
  for(const [reason,send] of cases) await t.test(reason,async sub=>{
    let control;
    const {result,payloads}=await scenario(sub,[reply()],{controlReady:value=>{control=value;},onEvent:event=>{
      if(event.type==='mcp-connected') send(control);
    }});
    assert.equal(result.ok,false);assert.equal(result.reason,reason);assert.equal(payloads.length,0);
  });
});
test('cancellation still dominates a directly accepted finish claim',async t=>{
  const controller=new AbortController();
  const {result,events}=await scenario(t,[reply()],{signal:controller.signal,onEvent:event=>{
    if(event.type==='player-finish') controller.abort();
  }});
  assert.equal(events.filter(event=>event.type==='player-finish').length,1);
  assert.equal(result.reason,'cancelled');assert.equal(result.finalText,'');
});
