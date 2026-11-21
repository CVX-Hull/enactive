// Offline replay of one actor's live knowledge updates through the real host, with a scripted provider and
// the real application over MCP. It reads the driver's files as a host does and writes only the supplied owned
// directory, which holds `delivered-knowledge.json` (the actor's frozen version) and `actors/001/` with the
// actor's `knowledge-updates.jsonl` and `knowledge/`. Prints one JSON line: how the host settled and every
// update event it recorded. Used by tests/live_curator_stand_in_run.py; not a `node --test` file.
import { readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { deliveryScenario, recallReply } from './delivery-scenario.mjs';
import { reply } from './host-scenario.mjs';

if (!process.argv[2]) throw new Error('Supply an owned directory holding delivered-knowledge.json and actors/001');
const directory = resolve(process.argv[2]);
const knowledge = JSON.parse(await readFile(join(directory,'delivered-knowledge.json'),'utf8'));
const input = () => reply(null,[['computer_input',{actions:[{type:'key',key:'x',modifiers:[]}]}]]);
const {result,events} = await deliveryScenario(directory,{knowledge,preserveKnowledgeFile:true,knowledgeUpdates:true,
  recallFetch:() => recallReply([]),playerFetch:n => n < 3 ? input() : reply('Replay finished')});
const field = (event, names) => Object.fromEntries(names.filter(name => name in event).map(name => [name,event[name]]));
console.log(JSON.stringify({ok:result.ok,reason:result.reason,
  host:field(events.find(e => e.type === 'host-start'),['schema','telemetry_version']),
  updates:events.filter(e => ['knowledge-delivery','knowledge-undelivered'].includes(e.type) && e.kind === 'update')
    .map(e => field(e,['type','outcome','version','previous_version','coverage','reason','receiving_player_request_id',
      'article_ids','fact_ids','index_ids','removed_ids','delivered_knowledge_schema'])),
  recalls:events.filter(e => e.type === 'knowledge-recall').map(e => field(e,['kind','status','reason','version']))}));
