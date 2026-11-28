// Offline replay of one actor's live knowledge updates through the real host, with a scripted provider and
// the real application over MCP. It reads the driver's files as a host does and writes only the supplied owned
// directory, which holds `delivered-knowledge.json` (the actor's frozen version) and `actors/001/` with the
// actor's `knowledge-updates.jsonl` and `knowledge/`. Prints one JSON line: how the host settled and every
// update and cut event it recorded. Used by tests/live_curator_stand_in_run.py; not a `node --test` file.
import { readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { deliveryScenario } from './delivery-scenario.mjs';
import { reply } from './host-scenario.mjs';

const [path, flag, cut, ...extra] = process.argv.slice(2);
if (!path || extra.length || (flag !== undefined && (flag !== '--context-cut' || cut === undefined)))
  throw new Error('Usage: live-update-replay.mjs DIRECTORY [--context-cut JSON]');
const directory = resolve(path);
const knowledge = JSON.parse(await readFile(join(directory,'delivered-knowledge.json'),'utf8'));
const input = () => reply(null,[['computer_input',{actions:[{type:'key',key:'x',modifiers:[]}]}]]);
const {result,events} = await deliveryScenario(directory,{knowledge,preserveKnowledgeFile:true,knowledgeUpdates:true,
  configuration:{context_cut:cut === undefined ? null : JSON.parse(cut)},
  playerFetch:n => n < 3 ? input() : reply('Replay finished')});
const field = (event, names) => Object.fromEntries(names.filter(name => name in event).map(name => [name,event[name]]));
console.log(JSON.stringify({ok:result.ok,reason:result.reason,
  host:field(events.find(e => e.type === 'host-start'),['schema','telemetry_version']),
  updates:events.filter(e => ['knowledge-delivery','knowledge-undelivered'].includes(e.type) && e.kind === 'update')
    .map(e => field(e,['type','outcome','version','previous_version','coverage','reason','receiving_player_request_id',
      'delta','delivered_knowledge_schema'])),
  cuts:events.filter(e => e.type === 'context-cut').map(({wall_time,monotonic_ms,...event}) => event)}));
