import test from 'node:test';
import assert from 'node:assert/strict';
import { McpClient } from '@earendil-works/pi-mcp';
import { reply, scenario, handoffArgs, handoffTools, handoffId, sessionId, actorId, collectArgs } from './host-scenario.mjs';

test('completed handoff fences later batch inputs and ends even after an earlier ordinary tool',async t=>{
  const {result,payloads,calls,events}=await scenario(t,[reply('not a final gameplay report',[
    ['mutate',{mode:'ok',index:1}],['player_handoff',handoffArgs],['mutate',{mode:'ok',index:2}]
  ])],{enabledTools:handoffTools});
  assert.deepEqual(result,{ok:true,reason:'handoff',requests:1,finalText:'',control_id:null});
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
  assert.equal(result.reason,'task_complete');assert.equal(result.requests,2);
  assert.equal(events.filter(e=>e.type==='handoff').length,0);
});
test('proven nonadmission cannot arm settlement of another issuance',async t=>{
  const {result,events}=await scenario(t,[reply(null,[['player_handoff',{...handoffArgs,mode:'not-admitted'}]]),
    reply(null,[['computer_result',collectArgs]]),reply()],{enabledTools:handoffTools});
  assert.equal(result.reason,'task_complete');assert.equal(result.requests,3);
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
    assert.equal(result.reason,'task_complete');assert.equal(result.requests,2);
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
    assert.equal(result.ok,true);assert.equal(result.reason,'task_complete');assert.equal(result.requests,3);
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
  assert.equal(result.reason,'task_complete');assert.equal(result.requests,3);
  assert.equal(events.filter(e=>e.type==='handoff').length,0);
});
test('first actual MCP text owns the handoff receipt even when extra text follows',async t=>{
  const {result}=await scenario(t,[reply(null,[['player_handoff',{mode:'extra-text'}]])],{enabledTools:handoffTools});
  assert.equal(result.reason,'handoff');assert.equal(result.requests,1);
});
