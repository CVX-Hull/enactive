// Shared offline fixtures for the runHost test files in this directory: the frozen
// route, synthetic provider responses and `scenario`, which runs one host against
// an owned Python MCP child. Not a test file itself; `node --test` runs each
// `*.test.mjs` here in its own process, so nothing in this module is shared state.
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PassThrough } from 'node:stream';
import { createHash } from 'node:crypto';
import { runHost } from '../host.mjs';

const realSetTimeout = globalThis.setTimeout;
const realDelay = ms => new Promise(resolve=>realSetTimeout(resolve,ms));
const python = process.env.ENACTIVE_TEST_PYTHON;
const fixture = fileURLToPath(new URL('../../../tests/fixtures/player_host_mcp.py', import.meta.url));
const png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ioAAAAASUVORK5CYII=';
const model = { id: 'fixture-model', name: 'Offline fixture', api: 'openai-completions', provider: 'fixture', baseUrl: 'https://fixture.invalid/v1', reasoning: false, input: ['text', 'image'], cost: {input:0, output:0, cacheRead:0, cacheWrite:0}, contextWindow: 100000, maxTokens: 1024, compat: { supportsDeveloperRole:false, supportsStore:false, supportsUsageInStreaming:true } };
const route = () => ({schema:'player-host/3',context_reserve_tokens:4096,service_tier:'default', model:structuredClone(model), api_key_env:'OFFLINE_TEST_KEY', max_requests:4, max_context_images:4, context_image_block:1, request_timeout_seconds:2});
function reply(content = 'finished', calls = [], withUsage = true, reasoning, callPrefix = 'call') {
  if (!calls.length && content !== null) calls = [['player_finish',{disposition:'task_complete',report:content.slice(0,8192),source_ids:[],control_id:null}]];
  const delta = {role:'assistant', ...(content === null ? {} : {content}), ...(reasoning ? {reasoning_content:reasoning} : {}), ...(calls.length ? {tool_calls:calls.map(([name,args],index)=>({index,id:`${callPrefix}-${index}`,type:'function',function:{name,arguments:JSON.stringify(args)}}))} : {})};
  const chunks = [{id:'fixture-response',model:'fixture-backend',choices:[{index:0,delta,finish_reason:null}]},
    {id:'fixture-response',model:'fixture-backend',choices:[{index:0,delta:{},finish_reason:calls.length?'tool_calls':'stop'}],...(withUsage ? {usage:withUsage === true ? {prompt_tokens:11,completion_tokens:5,total_tokens:16} : withUsage} : {})}];
  return new Response(chunks.map(chunk=>'data: '+JSON.stringify(chunk)+'\n\n').join('')+'data: [DONE]\n\n', {headers:{'content-type':'text/event-stream'}});
}
function rateLimit(error = {type:'rate_limit_error', message:'Rate limit exceeded'}, headers = {}) {
  return new Response(JSON.stringify({error}), {status:429,
    headers:{'content-type':'application/json', 'retry-after-ms':'0', ...headers}});
}
async function scenario(t, sequence, overrides = {}) {
  assert.ok(python, 'Set ENACTIVE_TEST_PYTHON to a Python with the official mcp package');
  const dir = await mkdtemp(join(tmpdir(),'pi-host-test-'));
  t.after(()=>rm(dir,{recursive:true,force:true}));
  const log = join(dir,'calls.jsonl'), pid = join(dir,'pid');
  const payloads = [], bodies = [], events = [];
  let index = 0;
  const fetch = async (_url, init) => {
    bodies.push(init.body);
    payloads.push(JSON.parse(init.body));
    const item = sequence[index++];
    return typeof item === 'function' ? item(init) : item;
  };
  const mcpConfig = {command:resolve(python),args:[fixture,log,pid],cwd:dir,enabled:true,required:true,enabled_tools:['observe','mutate','integer'],startup_timeout_sec:5,tool_timeout_sec:2,default_tools_approval_mode:'never',tools:{}};
  const options = {session:'2'.repeat(32),actorId:'3'.repeat(32),pendingControlId:null,control:new PassThrough(),configuration:route(), mcpConfig, context:'Frozen player guide', prompt:'Offline mission', model:model.id, effort:'off', timeoutSeconds:10, env:{OFFLINE_TEST_KEY:'fixture-key', UNRELATED_HOST_SECRET:'must-not-inherit'}, fetch, ...overrides,
    onEvent:event=>{events.push(event);overrides.onEvent?.(event);}};
  if (overrides.fixtureStartupDelay !== undefined) mcpConfig.args.push(String(overrides.fixtureStartupDelay));
  if (overrides.enabledTools) mcpConfig.enabled_tools=overrides.enabledTools;
  if (overrides.fixtureToolTimeoutSeconds) mcpConfig.tool_timeout_sec=overrides.fixtureToolTimeoutSeconds;
  overrides.controlReady?.(options.control);
  const running = runHost(options);
  let settled=false;
  void running.then(()=>{settled=true;},()=>{settled=true;});
  const drainCleanupClock=async()=>{
    if(!overrides.advanceCleanupTimers)return;
    const until=Date.now()+5000;
    while(!settled && Date.now()<until) {
      await realDelay(10);
      if(!settled)overrides.advanceCleanupTimers();
    }
    assert.ok(settled,'mocked cleanup timers must settle within five real seconds');
  };
  try {
    await overrides.synchronize?.({log});
    if(overrides.advanceCleanupTimers) {
      // The original work tick must already have stopped the host. Pumping
      // cleanup afterward cannot conceal a renewed or missing work deadline.
      assert.equal(events.find(event=>event.type==='abort')?.reason,overrides.expectedAbort);
    }
  } catch (error) { await drainCleanupClock();await running;throw error; }
  await drainCleanupClock();
  const result = await running;
  let calls=[]; try { calls=(await readFile(log,'utf8')).trim().split('\n').filter(Boolean).map(JSON.parse); } catch {}
  const childPid = Number(await readFile(pid,'utf8'));
  assert.throws(()=>process.kill(childPid,0), {code:'ESRCH'}, 'owned MCP child must exit before settlement');
  assertRequestMetadata(events, bodies);
  return {result,payloads,bodies,events,calls};
}
function assertRequestMetadata(events, bodies) {
  const starts=events.filter(event=>event.type==='request-start');
  assert.equal(starts.length,bodies.length);
  for(const [index,event] of starts.entries()) {
    assert.equal(event.payload_sha256,createHash('sha256').update(bodies[index]).digest('hex'));
    assert.equal(event.payload_bytes,Buffer.byteLength(bodies[index]));
    assert.equal(event.message_count,JSON.parse(bodies[index]).messages.length);
    for(const key of ['payload','messages','prompt','history','reasoning','reasoning_content']) assert.equal(Object.hasOwn(event,key),false);
  }
}

function eventStream(text) {
  return new Response(text, {headers:{'content-type':'text/event-stream'}});
}

const handoffArgs = {ids:[],summary:'Retain current context'};
const handoffTools = ['mutate','player_handoff','computer_result'];
const handoffId = '1'.repeat(32);
const sessionId = '2'.repeat(32);
const actorId = '3'.repeat(32);
const collectArgs = {operation_id:handoffId};

export { realDelay, python, fixture, png, model, route, reply, rateLimit, scenario, assertRequestMetadata, eventStream,
  handoffArgs, handoffTools, handoffId, sessionId, actorId, collectArgs };
