import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { once } from 'node:events';

const python=process.env.ENACTIVE_TEST_PYTHON;
const runner=fileURLToPath(new URL('../run.mjs',import.meta.url));
const fixture=fileURLToPath(new URL('../../../tests/fixtures/player_host_mcp.py',import.meta.url));
async function cli(t, handle, extraEnv = {}, enabledTools = ['observe']) {
  const dir=await mkdtemp(join(tmpdir(),'pi-host-cli-'));
  t.after(()=>rm(dir,{recursive:true,force:true}));
  const server=createServer(handle); server.listen(0,'127.0.0.1'); await once(server,'listening');
  t.after(()=>{server.closeAllConnections();server.close();});
  const model={id:'fixture',name:'fixture',api:'openai-completions',provider:'fixture',baseUrl:`http://127.0.0.1:${server.address().port}/v1`,input:['text','image'],reasoning:false,cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:10000,maxTokens:100};
  const route={schema:'player-host/4',role:'actor',intent_tail_bytes:null,service_tier:'default',model,api_key_env:'CLI_FIXTURE_KEY',max_requests:1,max_context_images:4,context_image_block:1,request_timeout_seconds:5};
  const mcp={command:resolve(python),args:[fixture,join(dir,'log'),join(dir,'pid')],cwd:dir,enabled:true,required:true,enabled_tools:enabledTools,startup_timeout_sec:3,tool_timeout_sec:1};
  const paths={route:join(dir,'route.json'),mcp:join(dir,'mcp.json'),context:join(dir,'context.txt'),final:join(dir,'final.txt')};
  await Promise.all([writeFile(paths.route,JSON.stringify(route)),writeFile(paths.mcp,JSON.stringify(mcp)),writeFile(paths.context,'Frozen player guide'),writeFile(paths.final,'reserved')]);
  const child=spawn(process.execPath,[runner,'run','--config',paths.route,'--mcp-config',paths.mcp,'--context',paths.context,'--model','fixture','--effort','off','--timeout-seconds','10','-o',paths.final],{env:{PATH:process.env.PATH,CLI_FIXTURE_KEY:'sentinel-private-key',...extraEnv},stdio:['pipe','pipe','pipe']});
  t.after(()=>{if(child.exitCode===null) child.kill('SIGKILL');});
  let stdout='',stderr='';child.stdout.on('data',chunk=>stdout+=chunk);child.stderr.on('data',chunk=>stderr+=chunk);
  child.stdin.end('Offline mission');
  const finished=once(child,'exit');
  return {child,finished,paths,dir,read:()=>({events:stdout.trim().split('\n').filter(Boolean).map(JSON.parse),stderr})};
}
for(const signal of ['SIGINT','SIGTERM']) test(`CLI ${signal} exits nonzero and closes actual MCP child`,async t=>{
  let received;
  const request=new Promise(resolve=>received=resolve);
  const run=await cli(t,()=>received());
  await request;
  const mcpPid=Number(await readFile(join(run.dir,'pid'),'utf8'));
  run.child.kill(signal);
  const [code,exitSignal]=await run.finished;
  assert.equal(code,1);assert.equal(exitSignal,null);
  assert.throws(()=>process.kill(mcpPid,0),{code:'ESRCH'});
  assert.equal(await readFile(run.paths.final,'utf8'),'reserved');
  assert.equal(run.read().events.at(-1).reason,'cancelled');
  assert.equal(run.read().stderr,'');
});
test('CLI provider API error exits nonzero and redacts response detail',async t=>{
  const run=await cli(t,(_req,res)=>{res.writeHead(403,{'content-type':'application/json'});res.end(JSON.stringify({error:{message:'sentinel-private-key should never escape',type:'forbidden'}}));});
  const [code]=await run.finished;
  assert.equal(code,1);
  assert.equal(run.read().events.at(-1).reason,'provider-error');
  assert.ok(!JSON.stringify(run.read()).includes('sentinel-private-key'));
  assert.equal(await readFile(run.paths.final,'utf8'),'reserved');
});
test('CLI writes the driver-reserved final path only after terminal success',async t=>{
  const run=await cli(t,(_req,res)=>{res.writeHead(200,{'content-type':'text/event-stream'});res.end('data: '+JSON.stringify({id:'fixture',model:'fixture-backend',choices:[{index:0,delta:{role:'assistant',content:'final answer'},finish_reason:'stop'}]})+'\n\ndata: [DONE]\n\n');});
  const [code]=await run.finished;
  assert.equal(code,0);assert.equal(await readFile(run.paths.final,'utf8'),'final answer\n');
  const sink=run.read().events.at(-1).event_output;
  assert.ok(sink.events>0&&sink.bytes>0);
  assert.ok(sink.json_ms>=0&&sink.enqueue_ms>=0);
});

for(const name of ['OPENAI_LOG','OPENAI_CUSTOM_HEADERS','OPENAI_ORG_ID','OPENAI_PROJECT_ID']) test(`CLI refuses ambient SDK ${name} without inference or secret output`, async t=>{
  let requests=0;
  const run=await cli(t,()=>{requests++;},{[name]:'sentinel-ambient-private-value'});
  const [code]=await run.finished;
  assert.equal(code,1);assert.equal(requests,0);
  assert.equal(run.read().events.at(-1).reason,'ambient-provider-configuration');
  assert.ok(!JSON.stringify(run.read()).includes('sentinel-ambient-private-value'));
  assert.equal(run.read().stderr,'');
});

test('CLI completed handoff exits zero, leaves the reserved final path unchanged and sends no extra HTTP request',async t=>{
  let requests=0;
  const args={};
  const run=await cli(t,(_req,res)=>{
    requests++;res.writeHead(200,{'content-type':'text/event-stream'});
    res.end('data: '+JSON.stringify({id:'fixture',model:'fixture-backend',choices:[{index:0,delta:{role:'assistant',tool_calls:[{index:0,id:'handoff-call',type:'function',function:{name:'player_handoff',arguments:JSON.stringify(args)}}]},finish_reason:'tool_calls'}]})+'\n\ndata: [DONE]\n\n');
  },{},['player_handoff']);
  const [code]=await run.finished;
  assert.equal(code,0);assert.equal(requests,1);
  assert.equal(run.read().events.at(-1).reason,'handoff');
  assert.equal(await readFile(run.paths.final,'utf8'),'reserved');
  const pid=Number(await readFile(join(run.dir,'pid'),'utf8'));
  assert.throws(()=>process.kill(pid,0),{code:'ESRCH'});
});

async function modeRun(t, args) {
  const child=spawn(process.execPath,[runner,...args],{env:{PATH:process.env.PATH},stdio:['ignore','pipe','pipe']});
  t.after(()=>{if(child.exitCode===null) child.kill('SIGKILL');});
  let stdout='',stderr='';child.stdout.on('data',chunk=>stdout+=chunk);child.stderr.on('data',chunk=>stderr+=chunk);
  const [code]=await once(child,'exit');
  return {code,stdout,stderr};
}
async function validateFiles(t, mutate = ()=>{}) {
  const dir=await mkdtemp(join(tmpdir(),'pi-host-validate-'));
  t.after(()=>rm(dir,{recursive:true,force:true}));
  const model={id:'fixture',name:'fixture',api:'openai-completions',provider:'fixture',baseUrl:'http://127.0.0.1:1/v1',input:['text','image'],reasoning:false,cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:10000,maxTokens:100};
  const route={schema:'player-host/4',role:'actor',intent_tail_bytes:null,service_tier:'default',model,api_key_env:'CLI_FIXTURE_KEY',max_requests:1,max_context_images:4,context_image_block:1,request_timeout_seconds:5};
  const mcp={command:resolve(python),args:[fixture],cwd:dir,enabled:true,required:true,enabled_tools:['observe'],startup_timeout_sec:3,tool_timeout_sec:1};
  mutate(route,mcp);
  const paths={route:join(dir,'route.json'),mcp:join(dir,'mcp.json')};
  await Promise.all([writeFile(paths.route,JSON.stringify(route)),writeFile(paths.mcp,JSON.stringify(mcp))]);
  return ['validate','--config',paths.route,'--mcp-config',paths.mcp,'--model','fixture','--effort','off'];
}
test('CLI validate accepts the route and MCP table silently without a credential',async t=>{
  const result=await modeRun(t,await validateFiles(t));
  assert.equal(result.code,0);assert.equal(result.stdout,'');
});
test('CLI validate refuses an old route schema, a disabled MCP table and repeated or missing flags',async t=>{
  for (const mutate of [route=>{route.schema='pi-player-host/4';},(_route,mcp)=>{mcp.enabled=false;}]) {
    const result=await modeRun(t,await validateFiles(t,mutate));
    assert.equal(result.code,1);assert.equal(result.stdout,'');
  }
  const good=await validateFiles(t);
  assert.equal((await modeRun(t,[...good,'--effort','off'])).code,1);
  assert.equal((await modeRun(t,good.slice(0,-2))).code,1);
  assert.equal((await modeRun(t,['validate'])).code,1);
});
test('CLI requires a leading mode word and settles unsuccessfully without one',async t=>{
  const files=await validateFiles(t);
  for (const args of [[],files.slice(1),['unknown',...files.slice(1)]]) {
    const result=await modeRun(t,args);
    assert.equal(result.code,1);
    const last=result.stdout.trim().split('\n').filter(Boolean).map(JSON.parse).at(-1);
    assert.equal(last.type,'settled');assert.equal(last.ok,false);assert.equal(last.reason,'invalid-arguments');
  }
});
