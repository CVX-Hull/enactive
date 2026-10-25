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
const fixture=fileURLToPath(new URL('server.py',import.meta.url));
async function cli(t, handle, extraEnv = {}) {
  const dir=await mkdtemp(join(tmpdir(),'pi-host-cli-'));
  t.after(()=>rm(dir,{recursive:true,force:true}));
  const server=createServer(handle); server.listen(0,'127.0.0.1'); await once(server,'listening');
  t.after(()=>{server.closeAllConnections();server.close();});
  const model={id:'fixture',name:'fixture',api:'openai-completions',provider:'fixture',baseUrl:`http://127.0.0.1:${server.address().port}/v1`,input:['text','image'],reasoning:false,cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:10000,maxTokens:100};
  const route={schema:'pi-player-host/1',model,api_key_env:'CLI_FIXTURE_KEY',max_requests:1,request_timeout_seconds:5};
  const mcp={command:resolve(python),args:[fixture,join(dir,'log'),join(dir,'pid')],cwd:dir,enabled:true,required:true,enabled_tools:['observe'],startup_timeout_sec:3,tool_timeout_sec:1};
  const paths={route:join(dir,'route.json'),mcp:join(dir,'mcp.json'),context:join(dir,'context.txt'),final:join(dir,'final.txt')};
  await Promise.all([writeFile(paths.route,JSON.stringify(route)),writeFile(paths.mcp,JSON.stringify(mcp)),writeFile(paths.context,'Frozen player guide'),writeFile(paths.final,'reserved')]);
  const child=spawn(process.execPath,[runner,'--config',paths.route,'--mcp-config',paths.mcp,'--context',paths.context,'--model','fixture','--effort','off','--timeout-seconds','10','-o',paths.final],{env:{PATH:process.env.PATH,CLI_FIXTURE_KEY:'sentinel-private-key',...extraEnv},stdio:['pipe','pipe','pipe']});
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
