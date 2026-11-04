import test from 'node:test';
import assert from 'node:assert/strict';
import { Type } from '@earendil-works/pi-ai';
import { runToolCall } from '@earendil-works/pi-agent-core';
import { createValidationFeedback, exampleValue, FIX_LINE } from '../validation-feedback.mjs';

const schema = {type:'object', additionalProperties:false,
  required:['mode', 'count', 'note', 'tags', 'extra_reason'], properties:{
    mode:{type:'string', enum:['fast', 'slow']},
    count:{type:'integer', minimum:1, maximum:5},
    note:{type:'string', minLength:1, maxLength:20},
    tags:{type:'array', items:{type:'string', minLength:1, maxLength:8}, maxItems:2},
    extra_reason:{type:'string', minLength:0, maxLength:50}}};
const good = {mode:'fast', count:2, note:'ok', tags:[], extra_reason:''};
const call = (id='bad', args={...good, mode:'warp', count:9}) => ({type:'toolCall', id, name:'level_tool', arguments:args});
const assistant = (...calls) => ({role:'assistant', content:calls});
async function refusal(toolCall, parameters=schema, execute=async()=>({content:[{type:'text',text:'executed'}]})) {
  const tool={name:'level_tool',parameters:Type.Unsafe(parameters),execute};
  const result=await runToolCall(toolCall,{tools:[tool],context:{tools:[tool]},assistantMessage:assistant(toolCall)});
  return {tool, message:{role:'toolResult',toolCallId:toolCall.id,toolName:toolCall.name,
    isError:result.isError,content:result.result.content,
    ...(result.durationMs===undefined?{}:{durationMs:result.durationMs})}};
}
const covered = {names:['level_tool'], terminal:['level_tool']};
function freeze(value) {
  if (value && typeof value==='object') { Object.values(value).forEach(freeze);Object.freeze(value); }
}

test('a minimal valid example is built from the schema alone', () => {
  assert.deepEqual(exampleValue(schema), {mode:'fast', count:1, note:'<note>', tags:[], extra_reason:''});
  assert.equal(exampleValue({type:'string', minLength:2, maxLength:3}, 'name'), '<na');
  assert.deepEqual(exampleValue({type:'array', minItems:1, items:{type:'string', enum:['a']}}), ['a']);
});

test('a real SDK refusal gains field paths, allowed values, a truncated received value, an example and the fix line, stable across history',async()=>{
  const bad=call('bad', {mode:'warp', count:9, note:'n'.repeat(300), tags:['aa', 'bb', 'cc'], rogue:1});
  let dispatched=0;
  const {tool,message}=await refusal(bad,schema,async()=>{dispatched++;});
  assert.equal(dispatched,0);
  const originals=[assistant(bad),message];const before=structuredClone(originals);freeze(originals);
  const events=[];const project=createValidationFeedback([tool],event=>events.push(event),covered);
  const first=project(originals)[1].content[0].text;
  assert.ok(first.startsWith('Validation failed for tool "level_tool":\n'));
  assert.ok(first.includes('- mode: must be one of "fast", "slow"; received "warp"'),first);
  assert.match(first,/- count: .*maximum 5\); received 9/);
  const note=/- note: .*received (".*)/.exec(first)[1];
  assert.ok(note.length<150&&note.includes('182 more characters'),note);
  assert.match(first,/- tags: .*maxItems 2.*received \["aa","bb","cc"\]/);
  assert.ok(first.includes('- extra_reason: required property is missing'),first);
  assert.ok(first.includes('unknown properties "rogue" are not allowed'),first);
  assert.ok(!first.includes('schema is false'));
  assert.ok(first.includes('Valid example call: level_tool {"mode":"fast","count":1,"note":"<note>","tags":[],"extra_reason":""}'),first);
  assert.ok(first.endsWith(`\n${FIX_LINE}`));
  assert.equal(events.length,1);assert.equal(events[0].original_result,message);assert.equal(events[0].tool,'level_tool');
  const later=[...originals,assistant({type:'toolCall',id:'other',name:'observe',arguments:{}}),
    {role:'toolResult',toolCallId:'other',toolName:'observe',content:[{type:'text',text:'later'}],durationMs:0}];
  assert.equal(project(later)[1].content[0].text,first);
  assert.equal(events.length,1,'same canonical refusal is diagnosed and traced once');
  assert.deepEqual(originals,before);
  const accepted=await refusal(call('fixed',good),schema,async()=>({content:[{type:'text',text:'accepted'}]}));
  assert.equal(accepted.message.isError,false);
});

test('the fix line is only for terminal tools, and an uncovered tool keeps the SDK text',async()=>{
  const bad=call();const {tool,message}=await refusal(bad);
  const plain=createValidationFeedback([tool],()=>{},{names:['level_tool'],terminal:[]})([assistant(bad),message])[1].content[0].text;
  assert.ok(plain.includes('Valid example call')&&!plain.includes('abstaining'));
  const history=[assistant(bad),message];
  assert.equal(createValidationFeedback([tool],()=>assert.fail())(history),history);
  assert.equal(createValidationFeedback([tool],()=>assert.fail(),{names:['other']})(history),history);
});

test('parser, executed, unknown and ambiguous history keep their original errors',async()=>{
  const bad=call();const {tool,message}=await refusal(bad);
  const events=[];const project=createValidationFeedback([tool],e=>events.push(e),covered);
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

test('a refusal with no recoverable field keeps its original text',async()=>{
  // Unexpected SDK-looking history with valid arguments must retain its original
  // error rather than invent a cause. This is a synthetic fallback case.
  const valid=call('valid',good);
  const {tool,message}=await refusal(valid);assert.equal(message.isError,false);
  delete message.durationMs;message.isError=true;
  message.content=[{type:'text',text:'Validation failed for tool "level_tool":\nunknown upstream cause'}];
  const original=[assistant(valid),message];
  assert.equal(createValidationFeedback([tool],()=>assert.fail(),covered)(original),original);
});

// The recorder's flat schema: an array of enum items, an optional-length string, a bounded number and a 4-item source list.
const episodeSchema = {type:'object', additionalProperties:false,
  required:['attempted', 'observation_status', 'changed', 'confidence', 'sources'], properties:{
    attempted:{type:'string', minLength:1, maxLength:1024},
    observation_status:{type:'array', items:{type:'string', enum:['seen', 'not_yet', 'contradicted']}, maxItems:8},
    changed:{type:'string', minLength:0, maxLength:1024},
    confidence:{type:'number', minimum:0, maximum:1},
    sources:{type:'array', items:{type:'string', minLength:1, maxLength:128}, maxItems:4}}};

test('a recorder refusal names the failing array item, the enum, the bound and the note, and ends with the fix line', async()=>{
  const bad=call('bad', {attempted:'a', observation_status:['seen', 'maybe'], changed:'', confidence:2, sources:['1', '2', '3', '4', '5']});
  const {tool,message}=await refusal(bad,episodeSchema);
  const project=createValidationFeedback([tool],()=>{},{...covered,notes:{level_tool:'Note: empty observation_status is valid only without a subgoal.'}});
  const text=project([assistant(bad),message])[1].content[0].text;
  assert.ok(text.includes('must be one of "seen", "not_yet", "contradicted"; received "maybe"'),text);
  assert.match(text,/- confidence: .*maximum 1\); received 2/);
  assert.match(text,/- sources: .*maxItems 4\); received \["1","2","3","4","5"\]/);
  assert.ok(text.includes('Valid example call: level_tool {"attempted":"<attempted>","observation_status":[],"changed":"","confidence":0,"sources":[]}\nNote: empty observation_status'),text);
  assert.ok(text.endsWith(`\n${FIX_LINE}`));
  const sparse=call('sparse', {attempted:'a'});
  const gap=await refusal(sparse,episodeSchema);
  const gaps=createValidationFeedback([gap.tool],()=>{},covered)([assistant(sparse),gap.message])[1].content[0].text;
  for (const name of ['observation_status', 'changed', 'confidence', 'sources']) assert.ok(gaps.includes(`- ${name}: required property is missing`),gaps);
});
