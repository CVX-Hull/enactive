import test from 'node:test';
import assert from 'node:assert/strict';
import { Type } from '@earendil-works/pi-ai';
import { runToolCall } from '@earendil-works/pi-agent-core';
import { createValidationFeedback } from '../validation-feedback.mjs';

const schema = {type:'object', additionalProperties:false, required:['intent'], properties:{intent:{anyOf:[
  {type:'object', additionalProperties:false, required:['entry_type','entry'], properties:{entry_type:{const:'claim'},
    entry:{type:'object', required:['value'], properties:{value:{type:'number'}}}}},
  {type:'object', additionalProperties:false, required:['entry_type','entry'], properties:{entry_type:{const:'work'},
    entry:{type:'object', required:['stage','subject'], additionalProperties:false, properties:{
      stage:{type:'string', maxLength:128}, subject:{type:'string', pattern:'^[A-Za-z0-9][A-Za-z0-9_-]*$'},
      optional:{type:'string'}}}}}
]}}};
const call = (id='bad', entry={stage:'x'.repeat(224), subject:'small cardboard box'}) =>
  ({type:'toolCall', id, name:'remember', arguments:{intent:{entry_type:'work', entry}}});
const assistant = (...calls) => ({role:'assistant', content:calls});
async function refusal(toolCall, parameters=schema, execute=async()=>({content:[{type:'text',text:'executed'}]})) {
  const tool={name:'remember',parameters:Type.Unsafe(parameters),execute};
  const result=await runToolCall(toolCall,{tools:[tool],context:{tools:[tool]},assistantMessage:assistant(toolCall)});
  return {tool, message:{role:'toolResult',toolCallId:toolCall.id,toolName:toolCall.name,
    isError:result.isError,content:result.result.content,
    ...(result.durationMs===undefined?{}:{durationMs:result.durationMs})}};
}
function freeze(value) {
  if (value && typeof value==='object') { Object.values(value).forEach(freeze);Object.freeze(value); }
}

test('real SDK refusal gains accurate branch feedback, stable across later history without changing canonical data',async()=>{
  const bad=call();let dispatched=0;
  const {tool,message}=await refusal(bad,schema,async()=>{dispatched++;});
  assert.equal(dispatched,0);
  assert.ok(message.content[0].text.includes('intent.entry.value'),'reproduce the unrelated Claim-branch error');
  const originals=[assistant(bad),message];const before=structuredClone(originals);freeze(originals);
  const events=[];const project=createValidationFeedback([tool],event=>events.push(event));
  const first=project(originals);
  assert.match(first[1].content[0].text,/entry.stage: must not have more than 128/);
  assert.match(first[1].content[0].text,/entry.subject: must match pattern/);
  assert.ok(!first[1].content[0].text.includes('intent.entry.value'));
  assert.equal(events.length,1);assert.equal(events[0].original_result,message);
  const later=[...originals,assistant({type:'toolCall',id:'other',name:'observe',arguments:{}}),
    {role:'toolResult',toolCallId:'other',toolName:'observe',content:[{type:'text',text:'later'}],durationMs:0}];
  assert.equal(project(later)[1].content[0].text,first[1].content[0].text);
  assert.equal(project([...later,{role:'assistant',content:[{type:'text',text:'done'}]}])[1].content[0].text,
    first[1].content[0].text);
  assert.equal(events.length,1,'same canonical refusal is diagnosed and traced once');
  assert.deepEqual(originals,before);assert.deepEqual(tool.parameters,Type.Unsafe(schema));
  const fixed=call('fixed',{stage:'partial pickup',subject:'small_cardboard_box'});
  const accepted=await refusal(fixed,schema,async()=>{dispatched++;return {content:[{type:'text',text:'accepted'}]};});
  assert.equal(accepted.message.isError,false);assert.equal(dispatched,1);
  assert.ok(Object.hasOwn(accepted.message,'durationMs'));
});

test('parser, executed, unknown and ambiguous history keep their original errors',async()=>{
  const bad=call();const {tool,message}=await refusal(bad);
  const events=[];const project=createValidationFeedback([tool],e=>events.push(e));
  for (const [c,r] of [
    [{...bad,argumentsError:'incomplete JSON'},message],
    [bad,{...message,durationMs:0}],
    [bad,{...message,durationMs:undefined}],
    [{...bad,name:'unknown'},message],
    [bad,{...message,toolName:'other'}],
    [bad,{...message,content:[...message.content,{type:'text',text:'other'}]}],
    [bad,{...message,content:[{type:'text',text:'MCP isError: true\n'+message.content[0].text}]}],
  ]) {
    const history=[assistant(c),r];assert.equal(project(history),history);
  }
  for (const history of [[assistant(bad,bad),message], [assistant(bad),message,message],
    [message], [assistant(bad,call('unfinished')),message]]) assert.equal(project(history),history);
  assert.equal(events.length,0);
  // An earlier ambiguous build must not poison a later uniquely paired build.
  assert.notEqual(project([assistant(bad),message])[1].content[0].text,message.content[0].text);
});

test('missing discriminator names the valid values; ambiguous one and a passing narrowed check preserve full SDK refusal',async()=>{
  // A discriminator that names no branch gets the valid values instead of any branch's errors.
  for (const [intent,got] of [[{entry:{stage:'long'}},'nothing'],[{entry_type:'unknown',entry:{stage:'long'}},'"unknown"']]) {
    const c={...call(),arguments:{intent}};const {tool,message}=await refusal(c);
    const events=[];const projected=createValidationFeedback([tool],e=>events.push(e))([assistant(c),message]);
    const text=projected[1].content[0].text;
    assert.ok(text.includes('intent.entry_type must be one of "claim", "work"')&&text.includes(`(got ${got})`));
    assert.ok(text.includes('Valid intent.entry_type shapes: claim {entry_type, entry}; work {entry_type, entry}.'));
    assert.ok(!text.includes('intent.entry.value'));assert.equal(events.length,1);
  }
  const duplicate=structuredClone(schema);duplicate.properties.intent.anyOf.push(duplicate.properties.intent.anyOf[1]);
  const c=call();const duplicated=await refusal(c,duplicate);const history=[assistant(c),duplicated.message];
  assert.equal(createValidationFeedback([duplicated.tool],()=>assert.fail())(history),history);
  // Unexpected SDK-looking history with valid arguments must retain its original
  // error rather than invent a cause. This is a synthetic fallback case.
  const valid=call('valid',{stage:'short',subject:'box'});
  const {tool,message}=await refusal(valid);assert.equal(message.isError,false);
  delete message.durationMs;message.isError=true;
  message.content=[{type:'text',text:'Validation failed for tool "remember":\nunknown upstream cause'}];
  const original=[assistant(valid),message];
  assert.equal(createValidationFeedback([tool],()=>assert.fail())(original),original);
});

test('selected diagnostics retain constraints surrounding the intent union',async()=>{
  const constrained=structuredClone(schema);constrained.properties.intent.maxProperties=1;
  const c=call('surrounding',{stage:'short',subject:'box'});
  const {tool,message}=await refusal(c,constrained);assert.equal(message.isError,true);
  const projected=createValidationFeedback([tool],()=>{})([assistant(c),message]);
  assert.match(projected[1].content[0].text,/intent: must not have more than 1 properties/);
  assert.deepEqual(tool.parameters,Type.Unsafe(constrained));
});

test('any discriminated union argument is narrowed, not only the memory intent',async()=>{
  const parameters={type:'object',additionalProperties:false,required:['proposal'],properties:{proposal:{anyOf:[
    {type:'object',additionalProperties:false,required:['action','record_id'],properties:{action:{const:'keep'},record_id:{type:'string',minLength:1}}},
    {type:'object',additionalProperties:false,required:['action','outcome'],properties:{action:{const:'close'},outcome:{enum:['achieved','failed']}}}]}}};
  const c={type:'toolCall',id:'p',name:'remember',arguments:{proposal:{action:'close',outcome:'revised'}}};
  const {tool,message}=await refusal(c,parameters);assert.equal(message.isError,true);
  const events=[];const text=createValidationFeedback([tool],e=>events.push(e))([assistant(c),message])[1].content[0].text;
  assert.ok(text.startsWith('Selected proposal.action="close".\n')&&text.includes('proposal.outcome')&&!text.includes('record_id: '));
  assert.ok(text.includes('Valid proposal.action shapes: keep {action, record_id}; close {action, outcome}.'));
  assert.deepEqual(events[0].selected,{property:'proposal',key:'action',value:'close'});
});
