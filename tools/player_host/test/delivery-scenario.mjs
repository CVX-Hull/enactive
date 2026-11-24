import { appendFile, mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PassThrough } from 'node:stream';
import { runHost } from '../host.mjs';
import { model, route, reply, realDelay, article, fact, position } from './host-scenario.mjs';

/** The scenario's store as version `version`; its articles are revised at that version, never later than it. */
export const knowledge = (version = 'v2') => ({schema:'delivered-knowledge/3',version,commit:'c'.repeat(40),repository_id:'d'.repeat(40),
  coverage:{schema:'curator-coverage/2',session:'s01',actor:null,last_step:4},
  articles:[
    article('article-a',{revision:`article-a@${version}`,title:'A subject',lead:'A useful first lead.',body:[{text:'First claim.',facts:['fact-a']}],
      links:[{rel:'see_also',target:'article-b'}],last_confirmed:position(1)}),
    article('article-b',{revision:`article-b@${version}`,title:'B subject',lead:'A useful later lead.',body:[{text:'Second claim.',facts:['fact-b']}],
      backlinks:[{rel:'see_also',source:'article-a'}],last_confirmed:position(2)})],
  facts:[fact('fact-a',{text:'First claim.',cited_by_articles:['article-a'],seen:position(1)}),
    fact('fact-b',{text:'Second claim.',cited_by_articles:['article-b'],seen:position(2)}),
    fact('fact-alone',{subject:'Unfiled subject',text:'An unfiled claim.',seen:position(3)})],
  history:{replaced:{},ended:[],retracted:[]}});

/** Make records `from` and `to` of `value` contradict each other as a valid file states it: one `contradicts` link
 * and its backlink, each in the other's `contradicted_by`, and both contested. The two must have equal or
 * incomparable compatible scopes, so the pair conflicts rather than one shadowing the other; an article citing
 * either must then be marked contested too. */
export function contest(value, from, to) {
  const byId = id => [...value.articles, ...value.facts].find(item => item.id === id);
  const source = byId(from), target = byId(to);
  source.links.push({rel:'contradicts',target:to});
  target.backlinks.push({rel:'contradicts',source:from});
  source.contradicted_by.push(to);
  target.contradicted_by.push(from);
  source.lifecycle_state = target.lifecycle_state = 'contested';
  return value;
}

export function recallReply(ids, cost = .002, finishReason = 'stop') {
  return recallTextReply(JSON.stringify({articles:ids}), cost, finishReason);
}

export function recallTextReply(text, cost = .002, finishReason = 'stop', provider) {
  const chunks = [{id:'recall',model:'recall-fixture',provider,choices:[{index:0,delta:{role:'assistant',content:text},finish_reason:finishReason}],
    usage:{prompt_tokens:11,completion_tokens:5,total_tokens:16,...(cost === null ? {} : {cost})}}];
  return new Response(chunks.map(c => 'data: '+JSON.stringify(c)+'\n\n').join('')+'data: [DONE]\n\n',
    {headers:{'content-type':'text/event-stream'}});
}

/** A version listed for the scenario's running actor as the driver lists it: the file under `knowledge/`, then one
 * whole `knowledge-update-entry/1` line. `change` makes the faults a test needs: other `data` in the file, no file
 * (`skipFile`), other `entry` fields, a raw `line`, or a line still without its newline (`partial`). */
export async function listUpdate(directory, value, change = {}) {
  const actor = directory+'/actors/001';
  await mkdir(actor+'/knowledge',{recursive:true});
  const data = JSON.stringify(value);
  if (!change.skipFile) await writeFile(`${actor}/knowledge/${value.version}.json`,change.data ?? data);
  const entry = {schema:'knowledge-update-entry/1',version:value.version,commit:value.commit,repository_id:value.repository_id,
    file:`knowledge/${value.version}.json`,sha256:createHash('sha256').update(data).digest('hex'),coverage:value.coverage,...change.entry};
  await appendFile(actor+'/knowledge-updates.jsonl',(change.line ?? JSON.stringify(entry))+(change.partial ? '' : '\n'));
  return entry;
}

export async function deliveryScenario(directory, overrides = {}) {
  const value = overrides.knowledge ?? knowledge();
  const actor = directory+'/actors/001';
  await mkdir(actor,{recursive:true});
  const path = directory+'/delivered-knowledge.json';
  if (!overrides.preserveKnowledgeFile) await writeFile(path,JSON.stringify(value));
  const configuration = route();
  configuration.recall = {model:{...structuredClone(model),id:'recall-fixture'},every:1,unpriced_request_usd:'0.2',endpoint_costs:null};
  Object.assign(configuration,overrides.configuration);
  const events = [], payloads = [];
  let player = 0, recall = 0;
  const control = new PassThrough();
  const workspace = await mkdtemp(join(directory,'enactive-player-fixture-'));
  try {
    const result = await runHost({configuration,knowledge:value,
      knowledgeUpdates:overrides.knowledgeUpdates ? actor+'/knowledge-updates.jsonl' : null,
      updateReadTimeoutMs:overrides.updateReadTimeoutMs,finishReserveUsd:overrides.finishReserveUsd ?? '0.5',
      session:'a'.repeat(32),actorId:'3'.repeat(32),pendingControlId:overrides.pendingControlId ?? null,control,
      context:'Frozen stand-in guide',prompt:'Inspect the receiver stand-in.',model:model.id,effort:'off',timeoutSeconds:10,
      env:{OFFLINE_TEST_KEY:'stand-in-only'},
      mcpConfig:{command:process.env.ENACTIVE_TEST_PYTHON,
        args:[fileURLToPath(new URL('./delivery-mcp.py',import.meta.url)),path,'--stdio','--workspace',workspace,'--actor-id','3'.repeat(32)],
        cwd:fileURLToPath(new URL('../../../',import.meta.url)),enabled:true,required:true,
        enabled_tools:overrides.enabledTools ?? ['computer_input','player_knowledge_read','player_knowledge_query'],startup_timeout_sec:5,tool_timeout_sec:2},
      fetch:async (_url,init) => {
        const payload = JSON.parse(init.body);payloads.push(payload);
        if (payload.model === 'recall-fixture') {
          recall++;
          if (overrides.recallFetch) return overrides.recallFetch(recall,init);
          return recallReply(recall === 1 ? ['article-a'] : recall === 2 ? ['article-b'] : []);
        }
        player++;
        if (overrides.playerFetch) return overrides.playerFetch(player,init);
        // MCP round trips give the concurrent recall time to finish, without awaiting it in the host.
        await realDelay(10);
        if (player === 2) return reply(null,[['player_knowledge_read',{id_or_title:'article-b'}]]);
        if (player <= 4) return reply(null,[['computer_input',{actions:[{type:'key',key:'x',modifiers:[]}]}]]);
        return reply('Stand-in finished');
      },onEvent:event => {events.push(event);overrides.onEvent?.(event,control,configuration);}});
    await writeFile(actor+'/host.jsonl',events.map(e => JSON.stringify(e)+'\n').join(''));
    return {result,events,payloads,configuration};
  } finally {
    await rm(workspace,{recursive:true,force:true});
  }
}
