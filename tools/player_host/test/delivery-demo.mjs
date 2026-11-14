// Offline demonstration; writes only the explicitly supplied temporary package.
import { execFileSync } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve, join } from 'node:path';
import { deliveryScenario, knowledge } from './delivery-scenario.mjs';

const directory=resolve(process.argv[2]);
if (!process.argv[2]) throw new Error('Supply an owned temporary output directory');
await mkdir(directory,{recursive:true});
// The Python exporter makes the frozen data and private unit record; the application saw only delivered data.
const full=knowledge();
await writeFile(join(directory,'full-input.json'),JSON.stringify(full));
const python=process.env.ENACTIVE_TEST_PYTHON;
execFileSync(python,['-c',
  'import json,sys; from pathlib import Path; from tools.knowledge_export import export; p=Path(sys.argv[1]); export(p,json.loads((p/"full-input.json").read_text()))',directory]);
const digest=async name => createHash('sha256').update(await readFile(join(directory,name))).digest('hex');
await writeFile(join(directory,'manifest.json'),JSON.stringify({schema:'campaign-run/7',session:'a'.repeat(32),
  files:{'delivered-knowledge.json':await digest('delivered-knowledge.json')},
  private_files:{'knowledge-full.json':await digest('private/knowledge-full.json'),'units.json':await digest('private/units.json')}}));
const {result,events}=await deliveryScenario(directory,{preserveKnowledgeFile:true});
if (!result.ok) throw new Error(JSON.stringify(result));
const measure=join(directory,'memory-measure','stand-in');
const output=execFileSync(python,['-m','tools.memory_measure','facts',measure,'--runs',directory],{encoding:'utf8'});
const facts=JSON.parse(await readFile(join(measure,'judged-facts.json'),'utf8'));
if (facts.schema !== 'judged-facts/1') throw new Error('Builder failed');
console.log(JSON.stringify({result:result.reason,briefings:events.filter(e => e.type === 'knowledge-delivery' && e.kind === 'briefing').length,
  reminders:events.filter(e => e.type === 'knowledge-delivery' && e.kind === 'reminder').length,
  silences:events.filter(e => e.type === 'knowledge-recall' && e.status === 'silence').length,
  reads:events.filter(e => e.type === 'tool-result' && e.tool === 'player_knowledge_read').length,
  recall_costs:events.filter(e => e.type === 'response-complete' && e.request_role === 'recall').map(e => e.counted_cost_usd),
  spent_usd:events.at(-1).spent_usd,facts:join(measure,'judged-facts.json')},null,2));
console.log(output.trim());
