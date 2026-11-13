import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile, rm, unlink } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PassThrough } from 'node:stream';
import { createHash } from 'node:crypto';
import { runHost } from '../host.mjs';

const python = process.env.ENACTIVE_TEST_PYTHON;
const root = fileURLToPath(new URL('../../../', import.meta.url));
const fixture = join(root, 'tests/fixtures/recorded_player_mcp.py');
// Real, decoded 1x1 PNGs. These bytes stand in for originals, never live captures.
const originals = [
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNg5xYGAABCACYnFfaDAAAAAElFTkSuQmCC',
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGMQ10wEAAD8AKK9A+X6AAAAAElFTkSuQmCC',
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGPwlC0EAAGKANhV9g3rAAAAAElFTkSuQmCC',
].map(encoded=>Buffer.from(encoded,'base64'));
const sha256 = data => createHash('sha256').update(data).digest('hex');
const model = {id:'recorded-offline-model',name:'Offline fixture',api:'openai-completions',provider:'fixture',
  baseUrl:'https://fixture.invalid/v1',reasoning:false,input:['text','image'],
  cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:1000000,maxTokens:1024,
  compat:{supportsDeveloperRole:false,supportsStore:false,supportsUsageInStreaming:true}};
const configuration = () => ({schema:'player-host/4',service_tier:'default',model:structuredClone(model),
  api_key_env:'OFFLINE_TEST_KEY',max_requests:2,spend_limit_usd:'100',unpriced_request_usd:'0.25',max_context_images:30,context_image_block:1,
  context_reserve_tokens:4096,request_timeout_seconds:2});
const finish = ['player_finish',{disposition:'task_complete',report:'Recorded assessment reply',source_ids:[],control_id:null}];
const proposal = ['computer_input',{actions:[{type:'key',key:'x',modifiers:[]}]}];

// Same maintained SDK mocking pattern as host-scenario.mjs: scripted Responses,
// injected fetch and real MCP stdio. There is no listener or provider parser.
function reply(calls) {
  const delta = {role:'assistant',tool_calls:calls.map(([name,args],index)=>({index,id:`recorded-${index}`,
    type:'function',function:{name,arguments:JSON.stringify(args)}}))};
  const chunks = [
    {id:'recorded-response',model:'offline-backend',choices:[{index:0,delta,finish_reason:null}]},
    {id:'recorded-response',model:'offline-backend',choices:[{index:0,delta:{},finish_reason:'tool_calls'}],
      usage:{prompt_tokens:11,completion_tokens:5,total_tokens:16,cost:0.000038}},
  ];
  return new Response(chunks.map(chunk=>'data: '+JSON.stringify(chunk)+'\n\n').join('')+'data: [DONE]\n\n',
    {headers:{'content-type':'text/event-stream'}});
}
const rateLimit = () => new Response(JSON.stringify({error:{type:'rate_limit_error',message:'Offline retry fixture'}}),
  {status:429,headers:{'content-type':'application/json','retry-after-ms':'0'}});

async function makePacket(dir, count) {
  await mkdir(join(dir,'sources'));
  const sources = Array.from({length:count},(_,index)=>({schema:'computer-source/1',
    source_id:`${'a'.repeat(32)}-${index+1}`,session:'a'.repeat(32),capture_id:index+1,
    sha256:sha256(originals[index%originals.length]),media_type:'image/png',presented_ms:1700+index,received_wall:1234.5+index,
    width:1,height:1,window_width:40,window_height:20,viewport:[0,0,1,1]}));
  for (const [index,source] of sources.entries())
    await writeFile(join(dir,'sources',source.source_id+'.png'),originals[index%originals.length]);
  const packet = {current_source_id:sources.at(-1).source_id,sources};
  await writeFile(join(dir,'packet.json'),JSON.stringify(packet));
  return packet;
}

async function scenario(t, sequence, {count=3, damage}={}) {
  assert.ok(python,'Set ENACTIVE_TEST_PYTHON to the project Python with maintained MCP/Pillow');
  const dir = await mkdtemp(join(tmpdir(),'recorded-player-test-'));
  t.after(()=>rm(dir,{recursive:true,force:true}));
  const packet = await makePacket(dir,count);
  const packetPath = join(dir,'packet.json'), log = join(dir,'calls.jsonl'), pid = join(dir,'pid');
  if (damage) await damage({packet,packetPath,dir});
  const expected = JSON.parse(execFileSync(resolve(python),['-c',
    'import json; from harness.player_tools import tool_specs; print(json.dumps(tool_specs()))'],
    {cwd:root,env:{PATH:process.env.PATH ?? '/usr/bin:/bin',LANG:'C.UTF-8'},encoding:'utf8'}));
  const priorSentinel = process.env.RECORDED_PLAYER_TEST_SENTINEL;
  process.env.RECORDED_PLAYER_TEST_SENTINEL = 'harmless-offline-presence-test';
  t.after(()=>{
    if (priorSentinel === undefined) delete process.env.RECORDED_PLAYER_TEST_SENTINEL;
    else process.env.RECORDED_PLAYER_TEST_SENTINEL = priorSentinel;
  });
  const payloads=[], bodies=[], events=[];
  const result = await runHost({session:'2'.repeat(32),actorId:'3'.repeat(32),pendingControlId:null,
    control:new PassThrough(),configuration:configuration(),mcpConfig:{
      command:resolve(python),args:[fixture,'--packet',packetPath,'--log',log,'--pid',pid],cwd:dir,
      enabled:true,required:true,enabled_tools:Object.keys(expected),startup_timeout_sec:5,tool_timeout_sec:2,
      default_tools_approval_mode:'never',tools:{}},
    context:'Frozen offline player guide',prompt:'Inspect the retained recorded views through tools, then propose a control choice.',
    model:model.id,effort:'off',timeoutSeconds:10,
    env:{OFFLINE_TEST_KEY:'offline-test-value',RECORDED_PLAYER_TEST_SENTINEL:'harmless-offline-presence-test'},
    fetch:async(_url,init)=>{
      bodies.push(init.body);payloads.push(JSON.parse(init.body));
      assert.ok(payloads.length<=2,'never enter a third fetch, including retries');
      assert.ok(sequence.length>=payloads.length,'no unplanned provider attempt');
      return sequence[payloads.length-1];
    },onEvent:event=>events.push(event)});
  const child = Number(await readFile(pid,'utf8'));
  assert.throws(()=>process.kill(child,0),{code:'ESRCH'},'owned fixture must be absent before host settlement');
  const entries = (await readFile(log,'utf8')).trim().split('\n').map(JSON.parse);
  assert.deepEqual(entries[0],{event:'startup',test_sentinel_inherited:false});
  assert.ok(!JSON.stringify(entries).includes('offline-test-value'));
  assert.ok(!JSON.stringify(entries).includes('harmless-offline-presence-test'));
  const calls = entries.slice(1);
  assert.ok(calls.every(call=>!call.proposal || (call.refusal && !call.read)));
  const starts = events.filter(event=>event.type==='request-start');
  assert.equal(starts.length,payloads.length);
  for (const [index,event] of starts.entries()) {
    assert.equal(event.payload_sha256,sha256(bodies[index]));
    assert.equal(event.payload_bytes,Buffer.byteLength(bodies[index]));
  }
  return {result,packet,payloads,events,calls,expected};
}

function continuationImages(payload) {
  return payload.messages.flatMap(message=>Array.isArray(message.content)?message.content:[])
    .filter(part=>part.type==='image_url');
}

test('actual host keeps current schemas and all 30 original images, refusing proposal then exhausting two requests',async t=>{
  const {result,packet,payloads,events,calls,expected} = await scenario(t,[
    reply([['computer_observe',{}]]),reply([proposal])],{count:30});
  assert.deepEqual(result,{ok:false,reason:'request-limit',requests:2,finalText:'',control_id:null});
  assert.equal(payloads.length,2);
  const tools = payloads[0].tools.map(tool=>tool.function);
  assert.equal(tools.length,Object.keys(expected).length+1,'host alone adds direct finish');
  for (const [name,[description,parameters]] of Object.entries(expected)) {
    const actual = tools.find(tool=>tool.name===name);
    assert.equal(actual.description,description);
    assert.deepEqual(actual.parameters,parameters);
  }
  assert.ok(tools.some(tool=>tool.name==='player_finish'));
  assert.equal(continuationImages(payloads[0]).length,0);
  const images = continuationImages(payloads[1]);
  assert.equal(images.length,30,'SDK grows the complete retained multi-image continuation');
  for (const [index,image] of images.entries()) {
    const bytes = Buffer.from(image.image_url.url.split(',')[1],'base64');
    assert.deepEqual(bytes,originals[index%originals.length]);
    assert.equal(sha256(bytes),packet.sources[index].sha256);
  }
  const observed = events.find(event=>event.type==='tool-result' && event.tool==='computer_observe').result;
  assert.deepEqual(observed.content.filter(part=>part.type==='text').slice(1).map(part=>JSON.parse(part.text).source),packet.sources);
  assert.equal(observed.content.filter(part=>part.type==='image_reference').length,30);
  assert.deepEqual(observed.content.filter(part=>part.type==='image_reference').map(part=>part.sha256),
    packet.sources.map(source=>source.sha256));
  assert.deepEqual(calls.map(call=>[call.name,call.read,Boolean(call.refusal)]),[
    ['computer_observe',true,false],['computer_input',false,true]]);
  assert.deepEqual(calls[1].arguments,proposal[1]);
  assert.equal(events.filter(event=>event.type==='player-finish').length,0);
  const completed = events.filter(event=>event.type==='response-complete');
  assert.equal(completed.length,2);
  assert.ok(completed.every(event=>event.usage_available && event.usage.totalTokens===16));
});

test('proposal and direct finish in the second response retain actual successful host disposition',async t=>{
  const {result,payloads,calls,events} = await scenario(t,[reply([['computer_observe',{}]]),reply([proposal,finish])]);
  assert.equal(result.ok,true);
  assert.equal(result.reason,'task_complete');
  assert.equal(result.requests,2);
  assert.equal(result.finalText,finish[1].report);
  assert.equal(continuationImages(payloads[1]).length,3);
  assert.deepEqual(calls.map(call=>call.name),['computer_observe','computer_input']);
  assert.ok(calls[1].proposal && calls[1].refusal && !calls[1].read);
  assert.equal(events.filter(event=>event.type==='player-finish').length,1);
});

test('exact member source read grows only its original image continuation',async t=>{
  const source_id = 'a'.repeat(32)+'-2';
  const {result,payloads,events,calls,packet} = await scenario(t,[reply([['player_source',{source_id}]]),reply([finish])]);
  assert.equal(result.ok,true);
  assert.equal(result.requests,2);
  assert.equal(continuationImages(payloads[1]).length,1);
  assert.equal(continuationImages(payloads[1])[0].image_url.url,'data:image/png;base64,'+originals[1].toString('base64'));
  const observed = events.find(event=>event.type==='tool-result').result;
  assert.deepEqual(JSON.parse(observed.content[1].text),{historical:true,selected_current:false,source:packet.sources[1]});
  assert.deepEqual(calls.map(call=>[call.name,call.arguments,call.read]),[['player_source',{source_id},true]]);
});

test('retry is charged inside the same two-attempt cap; observation without image continuation stays incomplete',async t=>{
  const {result,payloads,events,calls} = await scenario(t,[rateLimit(),reply([['computer_observe',{}]])]);
  assert.equal(result.ok,false);
  assert.equal(result.reason,'request-limit');
  assert.equal(result.requests,2);
  assert.equal(payloads.length,2);
  assert.deepEqual(payloads[0],payloads[1],'retry is the same pre-observation request');
  assert.ok(payloads.every(payload=>continuationImages(payload).length===0));
  assert.ok(events.some(event=>event.type==='provider-retry' && event.stage==='started'));
  assert.deepEqual(calls.map(call=>call.name),['computer_observe']);
  assert.ok(events.find(event=>event.type==='tool-result').result.content.some(part=>part.type==='image_reference'));
});

test('early direct finish preserves actual completion and missing observation facts',async t=>{
  const {result,payloads,calls} = await scenario(t,[reply([finish])]);
  assert.equal(result.ok,true);
  assert.equal(result.reason,'task_complete');
  assert.equal(result.requests,1);
  assert.equal(payloads.length,1);
  assert.equal(calls.length,0);
  assert.equal(continuationImages(payloads[0]).length,0);
});

for (const damage of ['missing','forged']) test(`${damage} packet fails before any provider request and closes owned fixture`,async t=>{
  const {result,payloads,calls} = await scenario(t,[],{damage:async({packet,packetPath})=>{
    if (damage==='missing') await unlink(packetPath);
    else {
      packet.sources[0].sha256='0'.repeat(64);
      await writeFile(packetPath,JSON.stringify(packet));
    }
  }});
  assert.equal(result.ok,false);
  assert.equal(result.requests,0);
  assert.equal(payloads.length,0);
  assert.equal(calls.length,0);
});
