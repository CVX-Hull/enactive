// R-OVERSPEND / R-REGRESSION: exact admission, lifecycle and selection regressions.
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { recallRefusal } from '../host.mjs';
import { deliveryScenario, recallReply } from './delivery-scenario.mjs';
import { model, reply } from './host-scenario.mjs';

async function scenario(t, options) {
  const dir=await mkdtemp(join(tmpdir(),'recall-repairs-'));
  t.after(()=>rm(dir,{recursive:true,force:true}));
  return deliveryScenario(dir,options);
}

test('both admission phases include the player in-flight bound in the finish reserve',()=>{
  const state={hasUnits:true,disabled:false,ending:false,stopping:false,recalls:1,recallMax:5,requests:1,max:10,
    spent:[1n,1],playerInFlight:true,playerBound:[2n,1],reserve:[3n,1],limit:[6n,1]};
  for (const phase of ['preparation','fetch']) {
    assert.equal(recallRefusal(state),'finish-reserve',phase);
    assert.equal(recallRefusal({...state,playerInFlight:false}),null,phase);
    assert.equal(recallRefusal({...state,limit:[6000000000000000001n,19]}),null,phase);
  }
});

test('attempt-limit pre-check refuses before preparing the recall model and reserves the last attempt',async t=>{
  let armed=false,reads=0;
  const recallModel={...structuredClone(model),id:'recall-fixture'};
  Object.defineProperty(recallModel,'api',{enumerable:true,get(){if(armed)reads++;return model.api;}});
  const {result,events}=await scenario(t,{configuration:{max_requests:1,
    recall:{model:recallModel,every:1,max_requests:10,unpriced_request_usd:'0.2'}},
    onEvent:e=>{if(e.type==='mcp-connected')armed=true;if(e.type==='settled')armed=false;},playerFetch:()=>reply('Done')});
  assert.equal(reads,0,'the pre-check must not enter recall preparation');
  assert.equal(result.reason,'task_complete');
  const refusal=events.find(e=>e.type==='knowledge-recall');
  assert.equal(refusal.reason,'attempt-limit');assert.ok(!Object.hasOwn(refusal,'request_id'));
});

test('unstarted recall preparation consumes no attempt or request id and cannot stop the player prematurely',async t=>{
  let armed=false;
  const recallModel={...structuredClone(model),id:'recall-fixture'};
  Object.defineProperty(recallModel,'maxTokens',{enumerable:true,get(){if(armed)throw new Error('fixture preparation failure');return model.maxTokens;}});
  const {result,events}=await scenario(t,{configuration:{max_requests:2,
    recall:{model:recallModel,every:1,max_requests:10,unpriced_request_usd:'0.2'}},
    onEvent:e=>{if(e.type==='mcp-connected')armed=true;if(e.type==='settled')armed=false;},
    playerFetch:n=>n===1?reply(null,[['player_knowledge_read',{id_or_title:'article-a'}]]):reply('Done')});
  assert.equal(result.reason,'task_complete');assert.equal(result.requests,2);
  assert.deepEqual(events.filter(e=>e.type==='request-start').map(e=>e.request_id),['request-1','request-2']);
  assert.ok(events.filter(e=>e.type==='knowledge-recall').every(e=>!Object.hasOwn(e,'request_id')));
});

for (const limit of ['total','recall']) test(`fetch re-checks the ${limit} attempt allowance after preparation`,async t=>{
  let armed=false,configuration;
  const recallModel={...structuredClone(model),id:'recall-fixture'};
  Object.defineProperty(recallModel,'maxTokens',{enumerable:true,get(){
    if(armed) {
      if(limit==='total')configuration.max_requests=1;
      else configuration.recall.max_requests=0;
    }
    return model.maxTokens;
  }});
  const {result,events}=await scenario(t,{configuration:{max_requests:2,
    recall:{model:recallModel,every:1,max_requests:10,unpriced_request_usd:'0.2'}},
    onEvent:(e,_control,c)=>{configuration=c;if(e.type==='mcp-connected')armed=true;if(e.type==='settled')armed=false;},
    playerFetch:()=>reply('Done')});
  assert.equal(result.reason,'task_complete');
  assert.ok(events.every(e=>!(e.type==='request-start'&&e.request_role==='recall')));
  const refusal=events.find(e=>e.type==='knowledge-recall');
  assert.equal(refusal.reason,limit==='total'?'attempt-limit':'allowance');
  assert.ok(!Object.hasOwn(refusal,'request_id'));
});

test('a reminder leaves the last attempt for a normal player finish',async t=>{
  const {result,events}=await scenario(t,{configuration:{max_requests:3},
    playerFetch:n=>n===1?reply(null,[['computer_input',{actions:[{type:'key',key:'x',modifiers:[]}]}]]):reply('Done')});
  assert.equal(result.reason,'task_complete');assert.equal(result.requests,3);
  assert.deepEqual(events.filter(e=>e.type==='request-start').map(e=>e.request_id),['recall-1','request-1','request-2']);
});

test('normal finish aborts and counts an in-flight recall without a stop event',async t=>{
  let aborted=false;
  const {result,events}=await scenario(t,{recallFetch:(n,init)=>n===1?recallReply(['article-a']):new Promise((_resolve,reject)=>{
    init.signal.addEventListener('abort',()=>{aborted=true;reject(new Error('fixture aborted'));},{once:true});
  })});
  assert.equal(result.reason,'task_complete');assert.equal(aborted,true);
  assert.ok(events.every(e=>e.type!=='abort'));
  const cost=events.find(e=>e.type==='response-complete'&&e.request_id==='recall-2');
  assert.equal(cost.counted_cost_usd,'0.2');assert.equal(events.at(-1).unpriced_recall_requests,1);
});

test('handoff also aborts and counts the actor\'s in-flight recall',async t=>{
  let aborted=false;
  const {result,events}=await scenario(t,{enabledTools:['computer_input','player_handoff'],
    playerFetch:n=>n===1?reply(null,[['computer_input',{actions:[{type:'key',key:'x',modifiers:[]}]}]])
      :reply(null,[['player_handoff',{ids:[],summary:'Retain the fixture context'}]]),
    recallFetch:(n,init)=>n===1?recallReply(['article-a']):new Promise((_resolve,reject)=>{
      init.signal.addEventListener('abort',()=>{aborted=true;reject(new Error('fixture aborted'));},{once:true});
    })});
  assert.equal(result.reason,'handoff');assert.equal(aborted,true);
  assert.equal(events.find(e=>e.type==='response-complete'&&e.request_id==='recall-2').counted_cost_usd,'0.2');
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
