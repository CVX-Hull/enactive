import test from 'node:test';
import assert from 'node:assert/strict';
import { validateConfiguration } from '../host.mjs';
import { model, route, usageRecord, reply, rateLimit, scenario } from './host-scenario.mjs';

test('route is closed, graphical, finite and model/effort exact', ()=>{
  assert.doesNotThrow(()=>validateConfiguration(route(),model.id,'off'));
  for (const change of [{schema:'old'}, {unknown:true}, {max_requests:Infinity}, {api_key_env:'bad-key'}, {model:{...model,input:['text']}}, {model:{...model,headers:{authorization:'secret'}}}]) {
    assert.throws(()=>validateConfiguration({...route(),...change},model.id,'off'));
  }
  assert.throws(()=>validateConfiguration(route(),'other','off'));
  assert.throws(()=>validateConfiguration(route(),model.id,'low'));
  for (const old of ['pi-player-host/1','pi-player-host/2','pi-player-host/3','pi-player-host/5','player-host/0','player-host/1','player-host/2','player-host/3','player-host/4'])
    assert.throws(()=>validateConfiguration({...route(),schema:old},model.id,'off'));
  // The dollar limit and the bound for a request with no cost record are plain decimal text; a number,
  // an exponent, a sign, a non-finite word or a limit of zero is refused, and so is leaving either out.
  for (const value of [undefined,null,1,0.5,'','0','0.0','-1','+1','1e3','1.','.5','01','NaN','Infinity','1,000',' 1']) {
    assert.throws(()=>validateConfiguration({...route(),spend_limit_usd:value},model.id,'off'),undefined,`limit ${value}`);
  }
  // The bound is above zero too: a zero bound would count a failed request as free.
  for (const value of [undefined,null,0,0.25,'','0','0.000','-0.25','1e-3','NaN','Infinity']) {
    assert.throws(()=>validateConfiguration({...route(),unpriced_request_usd:value},model.id,'off'),undefined,`bound ${value}`);
  }
  assert.doesNotThrow(()=>validateConfiguration({...route(),spend_limit_usd:'0.01',unpriced_request_usd:'0.000000000000000001'},model.id,'off'));
  for (const service_tier of [undefined,null,true,1,'flex','auto','',{},[]]) {
    assert.throws(()=>validateConfiguration({...route(),service_tier},model.id,'off'));
  }
  assert.doesNotThrow(()=>validateConfiguration({...route(),service_tier:'priority'},model.id,'off'));
  for (const value of [undefined,0,-1,1.5,true,'2',NaN,Infinity,Number.MAX_SAFE_INTEGER+1]) {
    assert.throws(()=>validateConfiguration({...route(),max_context_images:value},model.id,'off'));
  }
  const missing=route();delete missing.max_context_images;
  assert.throws(()=>validateConfiguration(missing,model.id,'off'));
  for (const value of [undefined,0,-1,1.5,true,'2',NaN,5,Number.MAX_SAFE_INTEGER+1]) {
    assert.throws(()=>validateConfiguration({...route(),context_image_block:value},model.id,'off'));
  }
  assert.doesNotThrow(()=>validateConfiguration({...route(),context_image_block:4},model.id,'off'));
  const unblocked=route();delete unblocked.context_image_block;
  assert.throws(()=>validateConfiguration(unblocked,model.id,'off'),'an old /2-shaped route without a block is rejected');
  for (const value of [undefined,null,0,1023,100000,Infinity,1.1,true,'4096'])
    assert.throws(()=>validateConfiguration({...route(),context_reserve_tokens:value},model.id,'off'));
});

test('OpenRouter uses maintained routing and reasoning serializers with explicit standard tier on every attempt',async t=>{
  const configuration=route();
  configuration.model={...configuration.model,provider:'openrouter',baseUrl:'https://openrouter.ai/api/v1',reasoning:true,
    thinkingLevelMap:{medium:'medium'},compat:{...configuration.model.compat,supportsReasoningEffort:true,
      thinkingFormat:'openrouter',openRouterRouting:{only:['fireworks/us'],order:['fireworks/us'],allow_fallbacks:false,require_parameters:true}}};
  configuration.recall.model=structuredClone(configuration.model);
  assert.doesNotThrow(()=>validateConfiguration(configuration,model.id,'medium'));
  for (const baseUrl of ['http://openrouter.ai/api/v1','https://other.invalid/api/v1','https://openrouter.ai/v1']) {
    assert.throws(()=>validateConfiguration({...configuration,model:{...configuration.model,baseUrl}},model.id,'medium'));
  }
  for(const change of [{allow_fallbacks:true},{require_parameters:false},{only:['fireworks/us','baseten']},
      {order:['baseten']},{only:[99],order:[99]},{unknown:true}]) {
    const invalid=structuredClone(configuration);Object.assign(invalid.model.compat.openRouterRouting,change);
    assert.throws(()=>validateConfiguration(invalid,model.id,'medium'));
  }
  const priority={...configuration,service_tier:'priority'};
  assert.throws(()=>validateConfiguration(priority,model.id,'medium'));
  const missing=structuredClone(configuration);delete missing.model.compat.openRouterRouting;
  assert.throws(()=>validateConfiguration(missing,model.id,'medium'));
  const result=await scenario(t,[rateLimit(),reply()],{configuration,effort:'medium'});
  assert.equal(result.result.ok,true);assert.equal(result.payloads.length,2);
  for(const payload of result.payloads) {
    assert.deepEqual(payload.provider,configuration.model.compat.openRouterRouting);
    assert.deepEqual(payload.reasoning,{effort:'medium'});
    assert.equal(payload.reasoning_effort,undefined);assert.equal(payload.service_tier,'default');
  }
  assert.deepEqual(result.payloads[0],result.payloads[1]);
  assert.deepEqual(result.events.find(e=>e.type==='host-start').provider_routing,configuration.model.compat.openRouterRouting);
});

test('frozen serving tier uses the SDK payload hook and reports only observed stream echoes',async t=>{
  const withTier=tier=>new Response([
    {model:'fixture-backend',service_tier:tier,choices:[{index:0,delta:{role:'assistant',content:'done'},finish_reason:null}]},
    {model:'fixture-backend',service_tier:tier,choices:[{index:0,delta:{},finish_reason:'stop'}],usage:usageRecord},
  ].map(chunk=>'data: '+JSON.stringify(chunk)+'\n\n').join('')+'data: [DONE]\n\n',{headers:{'content-type':'text/event-stream'}});
  const ordinary=await scenario(t,[withTier('default'),reply()]);
  assert.equal(ordinary.result.ok,true);
  assert.equal(Object.hasOwn(ordinary.payloads[0],'service_tier'),false);
  assert.equal(ordinary.events.find(e=>e.type==='host-start').requested_service_tier,'default');
  const comparable=payload=>JSON.parse(JSON.stringify(payload).replace(
    /Host decision time remaining at this snapshot: ([0-9]+\.[0-9]{3}) seconds\./g,
    (_match,seconds)=>{
      assert.ok(Number(seconds)>0 && Number(seconds)<=10,'actual original host decision horizon');
      return 'Host decision time remaining at this snapshot: <measured> seconds.';
    }));
  for(const echo of ['priority','default',undefined,'fixture-key private tier']) {
    const configuration={...route(),service_tier:'priority'};
    const actual=await scenario(t,[withTier(echo),reply()],{configuration});
    assert.equal(actual.result.ok,true);
    assert.deepEqual(comparable(actual.payloads[0]),{...comparable(ordinary.payloads[0]),service_tier:'priority'});
    assert.equal(actual.events.find(e=>e.type==='host-start').requested_service_tier,'priority');
    const tiers=actual.events.filter(e=>e.type==='response-service-tier');
    assert.deepEqual(tiers.map(e=>[e.request_id,e.applied_service_tier]),['priority','default'].includes(echo)?[['request-1',echo]]:[]);
    assert.equal(actual.payloads.length,2,'plain text needs a separate direct finish call');
    assert.ok(!JSON.stringify(actual.events).includes('fixture-key private tier'));
  }
});
