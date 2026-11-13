import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { payloadManifestParts, projectImageContext } from '../host.mjs';
import { png, model, route, reply, rateLimit, scenario } from './host-scenario.mjs';

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

test('known context overflow prevents fetch and capacity warning has no experimental countdown',async t=>{
  const configuration={...route(),model:{...model,contextWindow:6000},context_reserve_tokens:5800};
  const first=await scenario(t,[reply()],{configuration});
  assert.equal(first.result.ok,true);
  assert.ok(JSON.stringify(first.payloads[0]).includes('Host context capacity is approaching'));
  // Without a handoff tool the warning names no successor; with one it offers the handoff.
  assert.ok(JSON.stringify(first.payloads[0]).includes('no successor actor is available'));
  assert.ok(!JSON.stringify(first.payloads[0]).includes('Request the existing player_handoff'));
  const withHandoff=await scenario(t,[reply()],{configuration,enabledTools:['mutate','player_handoff','computer_result']});
  assert.ok(JSON.stringify(withHandoff.payloads[0]).includes('Request the existing player_handoff'));
  const overflow={...configuration,model:{...model,contextWindow:2000},context_reserve_tokens:1500};
  const second=await scenario(t,[reply()],{configuration:overflow,context:'x'.repeat(10000)});
  assert.equal(second.result.reason,'context-capacity');assert.equal(second.payloads.length,0);
});
test('missing or underreported provider usage cannot bypass the context heuristic floor',async t=>{
  // The cost is reported in both cases, so the run reaches the next context estimate; only the token counts are missing.
  for(const reported of [{cost:0.000038},true]) await t.test(String(reported===true),async sub=>{
    const configuration={...route(),model:{...model,contextWindow:9000},context_reserve_tokens:1024};
    const {result,payloads,events}=await scenario(sub,[reply(null,[['observe',{}]],reported),reply()],{configuration});
    assert.equal(result.reason,'context-capacity');assert.equal(payloads.length,1);
    const estimate=events.filter(event=>event.type==='context-estimate').at(-1);
    assert.ok(estimate.tokens>=estimate.heuristic_tokens);assert.equal(estimate.exact,false);
  });
});

// ---- context-manifest: exact ordered per-request parts as digests, delta-encoded ----
const sha=value=>createHash('sha256').update(value).digest('hex');
const sourceTools=['observe','mutate','integer','observe_source'];
/** Rebuild every request's full ordered part list and omitted set from the delta events alone. */
function replayManifests(manifests) {
  const lists=new Map(),omitted=new Map();
  for(const manifest of manifests) {
    const base=manifest.base_request_id;
    const prefix=base===null?[]:lists.get(base);
    assert.ok(prefix,`base ${base} must be an earlier manifest`);
    assert.ok(manifest.reused_prefix_parts<=prefix.length);
    const parts=[...prefix.slice(0,manifest.reused_prefix_parts),...manifest.parts];
    assert.equal(parts.length,manifest.part_count);
    assert.deepEqual(parts.map(part=>part.index),parts.map((_,index)=>index),'indexes are positions');
    lists.set(manifest.request_id,parts);
    omitted.set(manifest.request_id,manifest.omitted_image_indexes??(base===null?[]:omitted.get(base)));
  }
  return {lists,omitted};
}
/** Independent expectation from the actual sent payload: [role, kind, bytes, sha256] in order. */
function sentParts(payload) {
  const rows=[];
  for(const message of payload.messages) {
    const role=message.role,tool=role==='tool';
    for(const key of ['reasoning_content','reasoning','reasoning_text']) if(message[key]) rows.push([role,'reasoning',Buffer.byteLength(message[key]),sha(message[key])]);
    const kind=tool?'tool_result_text':'text';
    if(typeof message.content==='string') rows.push([role,kind,Buffer.byteLength(message.content),sha(message.content)]);
    else for(const part of message.content??[]) {
      if(part.type==='text') rows.push([role,kind,Buffer.byteLength(part.text),sha(part.text)]);
      else {const bytes=Buffer.from(part.image_url.url.split(',')[1],'base64');rows.push([role,'image',bytes.length,sha(bytes)]);}
    }
    for(const call of message.tool_calls??[]) rows.push([role,'tool_call',Buffer.byteLength(JSON.stringify(call)),sha(JSON.stringify(call))]);
  }
  return rows;
}
const sourceReplies=(count,prefix='c')=>Array.from({length:count},(_,turn)=>reply(null,[['observe_source',{n:turn+1}]],true,undefined,`${prefix}${turn+1}`));
function checkManifests({events,payloads}) {
  const manifests=events.filter(event=>event.type==='context-manifest');
  const starts=events.filter(event=>event.type==='request-start');
  assert.deepEqual(manifests.map(event=>event.request_id),starts.map(event=>event.request_id),'one manifest per HTTP attempt');
  assert.equal(manifests.length,payloads.length);
  // Emitted after request-start and before the fetch for the same attempt.
  for(const manifest of manifests) {
    const at=events.indexOf(manifest);
    assert.equal(events[at-1].type==='provider-retry'||events[at-1].type==='request-start',true);
    assert.equal(events[at-1].request_id,manifest.request_id);
    assert.deepEqual([events[at+1].type,events[at+1].request_id],['request-fetch-start',manifest.request_id]);
  }
  const {lists,omitted}=replayManifests(manifests);
  const projections=events.filter(event=>event.type==='context-image-projection');
  let projectionIndex=-1,lastLogical;
  for(const [index,manifest] of manifests.entries()) {
    const parts=lists.get(manifest.request_id);
    const sentOnly=parts.filter(part=>part.state!=='omitted');
    assert.deepEqual(sentOnly.map(part=>[part.role,part.kind,part.bytes,part.sha256]),sentParts(payloads[index]),`request ${index+1} replays exactly`);
    // A retry attempt shares its logical request's projection.
    const logical=starts[index].logical_request_id;
    if(logical!==lastLogical) projectionIndex++;
    lastLogical=logical;
    const projection=projections[projectionIndex];
    const omittedParts=parts.filter(part=>part.state==='omitted');
    assert.deepEqual(omitted.get(manifest.request_id),parts.flatMap((part,at)=>part.state==='omitted'?[at]:[]));
    // The projection previews at most 16 omissions; the manifest lists every one.
    assert.deepEqual(omittedParts.slice(0,16).map(part=>({tool_call_id:part.tool_call_id,image_index:part.image_index,sha256:part.sha256})),projection.omissions);
    assert.equal(omittedParts.length,projection.omitted_images);
    assert.equal(parts.filter(part=>part.kind==='image'&&part.state==='sent').length,projection.retained_images);
    for(const part of omittedParts) {
      const text=payloads[index].messages.find(message=>message.tool_call_id===part.tool_call_id).content;
      assert.ok(text.includes(`SHA256=${part.sha256}`)&&text.includes('Historical pixels omitted'));
    }
    for(const part of parts.filter(part=>part.kind==='image')) {
      const turn=Number(part.tool_call_id.match(/\d+/)[0]);
      assert.equal(part.sha256,sha(`fixture-image-${turn}`));
      assert.equal(part.bytes,`fixture-image-${turn}`.length);
      assert.equal(part.source_id,`${'a'.repeat(32)}-${turn}`);
    }
    for(const part of parts.filter(part=>part.kind==='tool_result_text'||part.kind==='tool_call')) assert.equal(part.tool,'observe_source');
  }
  // Privacy: digests, sizes and identities only; never bodies or pixels.
  const serialized=JSON.stringify(manifests);
  for(const forbidden of ['Frozen player guide','Offline mission','MCP server instructions','player-computer-result','Historical pixels',Buffer.from('fixture-image-1').toString('base64'),'base64,','image_url'])
    assert.ok(!serialized.includes(forbidden),forbidden);
  for(const manifest of manifests) for(const part of manifest.parts) assert.deepEqual(Object.keys(part).filter(key=>['text','content','data','url','arguments'].includes(key)),[]);
  return {manifests,lists,omitted};
}
test('context manifest replays the exact ordered parts of every request, retry and eviction',async t=>{
  const configuration=route();configuration.max_context_images=2;configuration.max_requests=12;
  const sequence=[...sourceReplies(2),rateLimit(),reply(null,[['observe_source',{n:3}]],true,undefined,'c3'),
    reply(null,[['observe_source',{n:4}]],true,undefined,'c4'),reply(null,[['observe_source',{n:5}]],true,'Historical thinking','c5'),reply()];
  const observed=await scenario(t,sequence,{configuration,enabledTools:sourceTools});
  assert.equal(observed.result.ok,true);
  assert.equal(observed.payloads.length,7,'six logical requests plus one retried attempt');
  const {manifests,lists}=checkManifests(observed);
  // The retried attempt has an identical body, so its manifest reuses the whole previous list.
  const retried=manifests[3];
  assert.equal(retried.base_request_id,manifests[2].request_id);
  assert.equal(retried.reused_prefix_parts,retried.part_count);assert.deepEqual(retried.parts,[]);
  assert.equal(manifests[0].base_request_id,null);assert.equal(manifests[0].reused_prefix_parts,0);
  // Eviction really happened and each omitted image is a listed part, not only a count.
  assert.ok(manifests.some(manifest=>manifest.omitted_image_indexes?.length>0));
  assert.ok(lists.get(manifests.at(-1).request_id).some(part=>part.state==='omitted'));
  assert.ok(lists.get(manifests.at(-1).request_id).some(part=>part.kind==='reasoning'));
  assert.equal(JSON.stringify(manifests).includes('Historical thinking'),false);
  // The omitted set is carried only when it changes.
  assert.ok(manifests.some(manifest=>!('omitted_image_indexes' in manifest)&&manifest.base_request_id!==null));
  // Earlier telemetry is retained unchanged.
  assert.ok(observed.events.some(event=>event.type==='context-image-projection'&&event.omitted_images>0&&event.omissions.length>0));
});
test('context manifest stays small over a long image history',async t=>{
  const configuration=route();configuration.max_context_images=8;configuration.context_image_block=4;configuration.max_requests=40;
  const turns=30;
  const observed=await scenario(t,[...sourceReplies(turns),reply()],{configuration,enabledTools:sourceTools});
  assert.equal(observed.result.ok,true);assert.equal(observed.payloads.length,turns+1);
  const {manifests,lists}=checkManifests(observed);
  const sizes=manifests.map(manifest=>Buffer.byteLength(JSON.stringify({type:'context-manifest',...manifest})));
  const evictions=manifests.filter(manifest=>manifest.omitted_image_indexes!==undefined).length;
  assert.ok(evictions>=5);
  // Steady requests append only their new turn.
  const steady=manifests.flatMap((manifest,index)=>index>0&&!('omitted_image_indexes' in manifest)?[sizes[index]]:[]);
  assert.ok(Math.max(...steady)<=1200,`steady manifest bytes ${Math.max(...steady)}`);
  const total=sizes.reduce((sum,size)=>sum+size,0);
  assert.ok(total/manifests.length<=2500,`average manifest bytes ${total/manifests.length}`);
  // A full listing per request would be far larger than the deltas.
  const full=[...lists.values()].reduce((sum,parts)=>sum+JSON.stringify(parts).length,0);
  assert.ok(total*3<full,`delta ${total} vs full ${full}`);
  console.log(`manifest bytes: steady max ${Math.max(...steady)}, steady avg ${Math.round(steady.reduce((a,b)=>a+b,0)/steady.length)}, eviction max ${Math.max(...sizes)}, average ${Math.round(total/sizes.length)}, total ${total}, full-listing ${full}, parts ${lists.get(manifests.at(-1).request_id).length}`);
});
test('payload manifest never lists bodies and tolerates an unattributable image list',()=>{
  const payload={messages:[{role:'developer',content:'secret system'},
    {role:'user',content:[{type:'text',text:'secret mission'},{type:'image_url',image_url:{url:'data:image/png;base64,'+png}}]}]};
  const parts=payloadManifestParts(payload,[],new Map());
  assert.deepEqual(parts.map(part=>[part.role,part.kind]),[['system','text'],['user','text'],['user','image']]);
  assert.equal(parts[2].sha256,sha(Buffer.from(png,'base64')));assert.equal(parts[2].state,'sent');
  assert.equal('tool_call_id' in parts[2],false);
  assert.ok(!JSON.stringify(parts).includes('secret'));
});
