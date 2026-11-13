import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { projectToolResultForTelemetry } from '../host.mjs';
import { png, model, route, reply, scenario } from './host-scenario.mjs';

for (const fail of [false,true]) test(`actual provider payload preserves full text, PNG and known error=${fail}`, async t=>{
  const {result,payloads,events,calls} = await scenario(t,[reply(null,[['observe',{fail}]]),reply()]);
  assert.equal(result.ok,true);
  assert.equal(calls.length,1);
  assert.deepEqual(payloads[0].tools.map(t=>t.function.name), ['observe','mutate','integer','player_finish']);
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
  assert.equal(events.find(e=>e.type==='host-start').telemetry_version,4);
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
  assert.equal(result.finalText,visible.slice(0,8192));
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
  // The validator's own wording comes first, unchanged; the narrowed diagnostic names only the selected branch.
  const [own,narrowed]=first.split('\n\nThe errors above check every intent branch and may name another one. ');
  assert.match(own,/intent.entry.value/);
  assert.ok(narrowed.startsWith('For the selected intent.entry_type='));
  assert.ok(!narrowed.includes('intent.entry.value'));
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
