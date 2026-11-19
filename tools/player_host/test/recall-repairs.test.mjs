// R-OVERSPEND / R-REGRESSION: exact admission, lifecycle and selection regressions.
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import OpenAI from 'openai';
import { recallRefusal } from '../host.mjs';
import { knowledgeIndex, selection } from '../knowledge.mjs';
import { deliveryScenario, knowledge, recallReply } from './delivery-scenario.mjs';
import { model, reply } from './host-scenario.mjs';

async function scenario(t, options) {
  const dir=await mkdtemp(join(tmpdir(),'recall-repairs-'));
  t.after(()=>rm(dir,{recursive:true,force:true}));
  return deliveryScenario(dir,options);
}

test('both admission phases include the player in-flight bound in the finish reserve',()=>{
  const state={hasUnits:true,disabled:false,ending:false,stopping:false,
    spent:[1n,1],playerInFlight:true,playerBound:[2n,1],reserve:[3n,1],recallBound:[2n,1],limit:[8n,1]};
  for (const phase of ['preparation','fetch']) {
    assert.equal(recallRefusal(state),'finish-reserve',phase);
    assert.equal(recallRefusal({...state,playerInFlight:false}),null,phase);
    assert.equal(recallRefusal({...state,limit:[8000000000000000001n,19]}),null,phase);
  }
});

test('reminder fetch refuses the finish reserve in flight and later recall remains enabled',{timeout:30000},async t=>{
  let releaseReminder, completeReminder, startLaterReminder, prepared=0, playerPrepared=0, reminderResults=0;
  const reminderGate=new Promise(resolve=>{releaseReminder=resolve;});
  const reminderComplete=new Promise(resolve=>{completeReminder=resolve;});
  const laterReminderStarted=new Promise(resolve=>{startLaterReminder=resolve;});
  const prepareRequest=OpenAI.prototype.prepareRequest;
  // Delay SDK preparation, before the host fetch wrapper checks fresh admission
  // state. Let the next player fetch start, then release the reminder to fetch.
  t.mock.method(OpenAI.prototype,'prepareRequest',async function(request,context) {
    await prepareRequest.call(this,request,context);
    if(context.options.body.model==='recall-fixture' && ++prepared===2) await reminderGate;
    // Let the later reminder fetch while no player bound is in flight.
    if(context.options.body.model==='fixture-model' && ++playerPrepared===3) await laterReminderStarted;
  });
  const {result,events}=await scenario(t,{configuration:{spend_limit_usd:'0.9'},finishReserveUsd:'0.5',
    recallFetch:()=>recallReply(['article-a'],0),
    playerFetch:async n=>{
      if(n===1) return reply(null,[['computer_input',{actions:[{type:'key',key:'x',modifiers:[]}]}]],
        {prompt_tokens:11,completion_tokens:5,total_tokens:16,cost:0.1});
      if(n===3) return reply('Done');
      assert.equal(prepared,2,'the reminder passed its pre-check and reached SDK preparation');
      releaseReminder();
      await reminderComplete;
      return reply(null,[['computer_input',{actions:[{type:'key',key:'x',modifiers:[]}]}]],
        {prompt_tokens:11,completion_tokens:5,total_tokens:16,cost:0});
    },onEvent:e=>{
      if(e.type==='knowledge-recall' && e.kind==='reminder') {
        completeReminder();
        if(++reminderResults>1 && e.status==='not-made')startLaterReminder();
      }
      if(e.type==='request-start' && e.request_id==='recall-2')startLaterReminder();
    }});
  assert.equal(result.reason,'task_complete');
  const refusal=events.find(e=>e.type==='knowledge-recall' && e.kind==='reminder');
  assert.equal(refusal.status,'not-made');assert.equal(refusal.reason,'finish-reserve');
  assert.ok(!Object.hasOwn(refusal,'request_id'));
  assert.ok(!Object.hasOwn(refusal,'reply_text'));
  assert.ok(!Object.hasOwn(refusal,'reply_omitted_bytes'));
  assert.equal(events.filter(e=>e.type==='request-start' && e.request_role==='recall').length,2);
  assert.ok(events.some(e=>e.type==='knowledge-recall' && e.request_id==='recall-2' && e.status==='selected'));
  const index=events.indexOf(refusal);
  assert.ok(events.slice(0,index).some(e=>e.type==='request-start' && e.request_id==='request-2'));
  assert.ok(events.slice(index+1).some(e=>e.type==='response-complete' && e.request_id==='request-2'));
});

test('provider failure before recall fetch disables later reminders without starting an attempt',async t=>{
  let prepared=0;
  const prepareRequest=OpenAI.prototype.prepareRequest;
  t.mock.method(OpenAI.prototype,'prepareRequest',async function(request,context) {
    if(context.options.body.model==='recall-fixture') {
      prepared++;
      throw new Error('fixture SDK preparation failure');
    }
    return prepareRequest.call(this,request,context);
  });
  const {result,events}=await scenario(t,{recallFetch:()=>assert.fail('recall fetch must not start')});
  assert.equal(result.reason,'task_complete');
  const briefing=events.find(e=>e.type==='knowledge-recall' && e.kind==='briefing');
  assert.equal(briefing.status,'not-made');assert.equal(briefing.reason,'provider-failure');
  assert.ok(!Object.hasOwn(briefing,'request_id'));
  assert.ok(!Object.hasOwn(briefing,'reply_text'));
  assert.ok(!Object.hasOwn(briefing,'reply_omitted_bytes'));
  const reminders=events.filter(e=>e.type==='knowledge-recall' && e.kind==='reminder');
  assert.ok(reminders.length>0);
  assert.ok(reminders.every(e=>e.status==='not-made' && e.reason==='disabled'));
  assert.equal(prepared,1);
  assert.equal(events.filter(e=>e.type==='request-start' && e.request_role==='recall').length,0);
});

test('finish reserve refuses before preparing recall and leaves enough budget to finish',async t=>{
  let armed=false,reads=0;
  const recallModel={...structuredClone(model),id:'recall-fixture'};
  Object.defineProperty(recallModel,'api',{enumerable:true,get(){if(armed)reads++;return model.api;}});
  const {result,events}=await scenario(t,{configuration:{spend_limit_usd:'0.8',
    recall:{model:recallModel,every:1,unpriced_request_usd:'0.2'}},
    finishReserveUsd:'0.65',
    onEvent:e=>{if(e.type==='mcp-connected')armed=true;if(e.type==='settled')armed=false;},playerFetch:()=>reply('Done')});
  assert.equal(reads,0,'the pre-check must not enter recall preparation');
  assert.equal(result.reason,'task_complete');
  const refusal=events.find(e=>e.type==='knowledge-recall');
  assert.equal(refusal.reason,'finish-reserve');assert.ok(!Object.hasOwn(refusal,'request_id'));
});

test('unstarted recall preparation consumes no attempt or request id and cannot stop the player prematurely',async t=>{
  let armed=false;
  const recallModel={...structuredClone(model),id:'recall-fixture'};
  Object.defineProperty(recallModel,'maxTokens',{enumerable:true,get(){if(armed)throw new Error('fixture preparation failure');return model.maxTokens;}});
  const {result,events}=await scenario(t,{configuration:{recall:{model:recallModel,every:1,unpriced_request_usd:'0.2'}},
    onEvent:e=>{if(e.type==='mcp-connected')armed=true;if(e.type==='settled')armed=false;},
    playerFetch:n=>n===1?reply(null,[['player_knowledge_read',{id_or_title:'article-a'}]]):reply('Done')});
  assert.equal(result.reason,'task_complete');assert.equal(result.requests,2);
  assert.deepEqual(events.filter(e=>e.type==='request-start').map(e=>e.request_id),['request-1','request-2']);
  assert.ok(events.filter(e=>e.type==='knowledge-recall').every(e=>!Object.hasOwn(e,'request_id')));
});

test('normal finish aborts and counts an in-flight recall without a stop event',async t=>{
  let aborted=false;
  const {result,events}=await scenario(t,{recallFetch:(n,init)=>n===1?recallReply(['article-a']):new Promise((_resolve,reject)=>{
    init.signal.addEventListener('abort',()=>{aborted=true;reject(new Error('fixture aborted'));},{once:true});
  })});
  assert.equal(result.reason,'task_complete');assert.equal(aborted,true);
  assert.ok(events.every(e=>e.type!=='abort'));
  const cost=events.find(e=>e.type==='response-complete'&&e.request_id==='recall-2');
  assert.equal(cost.counted_cost_usd,null);assert.equal(events.at(-1).unpriced_recall_requests,1);
  assert.equal(events.find(e=>e.type==='knowledge-recall'&&e.request_id==='recall-2').reason,'actor-ended');
});

test('handoff also aborts and counts the actor\'s in-flight recall',async t=>{
  let aborted=false;
  const {result,events}=await scenario(t,{enabledTools:['computer_input','player_handoff'],
    playerFetch:n=>n===1?reply(null,[['computer_input',{actions:[{type:'key',key:'x',modifiers:[]}]}]])
      :reply(null,[['player_handoff',{summary:'Retain the fixture context'}]]),
    recallFetch:(n,init)=>n===1?recallReply(['article-a']):new Promise((_resolve,reject)=>{
      init.signal.addEventListener('abort',()=>{aborted=true;reject(new Error('fixture aborted'));},{once:true});
    })});
  assert.equal(result.reason,'handoff');assert.equal(aborted,true);
  assert.equal(events.find(e=>e.type==='response-complete'&&e.request_id==='recall-2').counted_cost_usd,null);
  assert.equal(events.find(e=>e.type==='knowledge-recall'&&e.request_id==='recall-2').reason,'actor-ended');
});

for (const kind of ['unknown-selection','length']) test(`valid provider cost survives ${kind}`,async t=>{
  const {result,events}=await scenario(t,{recallFetch:()=>recallReply(kind==='length'?['article-a']:['unknown'],.003,
    kind==='length'?'length':'stop')});
  assert.equal(result.reason,'task_complete');
  const cost=events.find(e=>e.type==='response-complete'&&e.request_role==='recall');
  assert.equal(cost.counted_cost_usd,'0.003');assert.equal(cost.reported_cost_usd,'0.003');
  assert.equal(cost.cost_counted_as,'provider-reported');assert.equal(events.at(-1).unpriced_recall_requests,0);
  assert.equal(cost.usage_available,true);assert.equal(cost.usage.input,11);
  assert.equal(cost.stop_reason,kind==='length'?'length':'stop');
  if(kind==='length') {
    assert.equal(events.filter(e=>e.type==='request-start' && e.request_role==='recall').length,1);
    assert.ok(events.some(e=>e.type==='knowledge-recall' && e.reason==='disabled'));
  }
});

test('selection deduplicates article id/title and delivers standalone fact text as a lead',async t=>{
  const {result,events}=await scenario(t,{recallFetch:()=>recallReply(['article-a','A subject','fact-alone'])});
  assert.equal(result.ok,true);
  const briefing=events.find(e=>e.type==='knowledge-delivery'&&e.kind==='briefing');
  assert.deepEqual(briefing.article_ids,['article-a']);assert.deepEqual(briefing.fact_ids,['fact-a','fact-alone']);
  const data=JSON.parse(briefing.text.split('\n')[1]);
  assert.equal(data.leads.length,2);assert.equal(data.leads[1].lead,'An unfiled claim.');
  assert.deepEqual(briefing.index_ids,['article-b']);
});

test('recall accepts exactly the delivered index ids and titles',()=>{
  const value=knowledge();
  const message=ids=>({content:[{type:'text',text:JSON.stringify({articles:ids})}]});
  for(const row of knowledgeIndex(value)) for(const name of [row.id,row.title]) {
    assert.deepEqual(selection(message([name]),value).map(item=>item.id),[row.id]);
  }
  for(const name of ['fact-a','fact-b','unknown-id','Unknown title']) {
    assert.throws(()=>selection(message([name]),value),/invalid-recall-selection/,name);
  }
  assert.deepEqual(selection(message(['article-a','A subject']),value).map(item=>item.id),['article-a']);
});

for(const id of ['article-a','fact-alone','A subject','Unfiled subject']) test(`recall refuses a repeated selection entry: ${id}`,()=>{
  const message={content:[{type:'text',text:JSON.stringify({articles:[id,id]})}]};
  assert.throws(()=>selection(message,knowledge()),/invalid-recall-selection/);
});
