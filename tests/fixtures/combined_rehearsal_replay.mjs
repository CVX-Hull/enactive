// Offline end-to-end player-host/13 + player-knowledge/4 rehearsal driven by tests/test_wave4c_combined_rehearsal.py.
// Kept under tests/fixtures/ (outside tools/player_host/test/) so bare `node --test` does not execute this CLI.
// Runs two real Node hosts (`actors/001` with actorId `33..33`, `actors/002` with actorId `44..44`) in place over
// the real Python MCP (`delivery-mcp.py`) against a real exported `delivered-knowledge/4` file, with zero post-hoc
// trace rewriting.
import { appendFile, readFile, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { deliveryScenario, listUpdate } from '../../tools/player_host/test/delivery-scenario.mjs';
import { reply } from '../../tools/player_host/test/host-scenario.mjs';

const usage = prompt => ({ prompt_tokens: prompt, completion_tokens: 40, total_tokens: prompt + 40 });

const [dirArg, updateArg] = process.argv.slice(2);
if (!dirArg || !updateArg) throw new Error('Usage: combined_rehearsal_replay.mjs DIRECTORY UPDATE_JSON');
const directory = resolve(dirArg);
const knowledge = JSON.parse(await readFile(join(directory, 'delivered-knowledge.json'), 'utf8'));
const updateKnowledge = JSON.parse(await readFile(resolve(updateArg), 'utf8'));
const updatesFile = join(directory, 'actors', '001', 'knowledge-updates.jsonl');
const session = 'a'.repeat(32);
const actorId1 = '3'.repeat(32);
const actorId2 = '4'.repeat(32);

const playerPayloads = [];
let controlSent = false;
const completedOps = [];
const stopControlId1 = 'b'.repeat(32);

const coverageLine = (operationId, version) => JSON.stringify({
  schema: 'coverage-update-entry/1', session, actor_id: actorId1, operation_id: operationId, version, restored: false,
}) + '\n';

const { result: result1, events: events1 } = await deliveryScenario(directory, {
  knowledge,
  actorDir: '001',
  actorId: actorId1,
  preserveKnowledgeFile: true,
  knowledgeUpdates: true,
  enabledTools: ['computer_input', 'computer_observe', 'player_knowledge_query', 'player_knowledge_read'],
  finishReserveUsd: '0.50',
  spendReserveWaitMs: 2000,
  configuration: {
    spend_limit_usd: '2.00',
    unpriced_request_usd: '0.20',
    context_cut: { high_mark: 6000, low_mark: 1, min_free: 2 },
  },
  playerFetch: async (n, init) => {
    const payload = JSON.parse(init.body);
    playerPayloads.push(payload);
    if (n === 1) {
      return reply(null, [
        ['player_knowledge_query', { query: 'purifying waters', intent: 'Search purification knowledge' }],
        ['player_knowledge_read', { id_or_title: 'WATER PURIFICATION', intent: 'Read full water article' }],
        ['player_agenda', {
          op: 'upsert',
          id: 'boil-water',
          title: 'Boil river water in shelter stove',
          status: 'active',
          refs: ['water-purification'],
          intent: 'Track water purification thread across cuts',
        }],
        ['computer_input', { actions: [{ type: 'key', key: 'x', modifiers: [] }], intent: 'Inspect shelter supplies' }],
      ], { ...usage(2500), cost: 0.05 });
    }
    if (n === 2) {
      return reply(null, [
        ['computer_input', { actions: [{ type: 'key', key: 'y', modifiers: [] }], intent: 'Boil river water at stove' }],
      ], { ...usage(7000), cost: 0.60 });
    }
    if (n === 3) {
      const coveredOp = completedOps[1];
      if (!coveredOp) throw new Error('Expected two completed operations before request 3');
      await appendFile(updatesFile, coverageLine(coveredOp, knowledge.version));
      return reply(null, [
        ['computer_input', { actions: [{ type: 'key', key: 'z', modifiers: [] }], intent: 'Check clean water container' }],
      ], { ...usage(8000), cost: 0.05 });
    }
    if (n === 4) {
      await listUpdate(directory, updateKnowledge, { actorDir: '001' });
      return reply(null, [
        ['computer_input', { actions: [{ type: 'key', key: 'w', modifiers: [] }], intent: 'Adopt updated water knowledge' }],
      ], { ...usage(3200), cost: 0.05 });
    }
    if (n === 5) {
      return reply(null, [
        ['computer_input', { actions: [{ type: 'key', key: 's', modifiers: [] }], intent: 'Prepare to save and close' }],
      ], { ...usage(3200), cost: 0.45 });
    }
    return reply(null, [
      ['player_finish', {
        disposition: 'external_stop_complete',
        control_id: stopControlId1,
        report: 'Completed rehearsal stop cleanly.',
        source_ids: [],
        intent: 'Close rehearsal cleanly',
      }],
    ], { ...usage(2000), cost: 0.02 });
  },
  onEvent: (event, control) => {
    if (event.type === 'tool-result' && event.tool === 'computer_input') {
      const opId = event.result?.structuredContent?.operation_id;
      if (opId) completedOps.push(opId);
    }
    if (event.type === 'spend-reserve-reached' && !controlSent) {
      controlSent = true;
      control.write(JSON.stringify({
        schema: 'player-control/1', id: stopControlId1, session, actor_id: actorId1, type: 'orderly_stop',
      }) + '\n');
    }
  },
});

// Second real actor (`actors/002`, real actorId `44..44`) runs in place with its own update log & files:
// its live v3 update is carried on request-2 when the upstream returns a non-retryable HTTP 500, producing a real
// `knowledge-delivery` (`kind: "update"`, `outcome: "undelivered"`) and settling honestly as `provider-error`.
const { result: result2, events: events2 } = await deliveryScenario(directory, {
  knowledge,
  actorDir: '002',
  actorId: actorId2,
  preserveKnowledgeFile: true,
  knowledgeUpdates: true,
  enabledTools: ['computer_input'],
  playerFetch: async n => {
    if (n === 1) {
      await listUpdate(directory, updateKnowledge, { actorDir: '002' });
      return reply(null, [['computer_input', { actions: [{ type: 'key', key: 'x', modifiers: [] }] }]], { ...usage(1200), cost: 0.01 });
    }
    return new Response(JSON.stringify({ error: { message: 'non-retryable stand-in error' } }),
      { status: 500, headers: { 'content-type': 'application/json' } });
  },
});

const summary = {
  actor1: { ok: result1.ok, reason: result1.reason },
  actor2: { ok: result2.ok, reason: result2.reason },
  host1: events1.find(e => e.type === 'host-start'),
  host2: events2.find(e => e.type === 'host-start'),
  cuts: events1.filter(e => e.type === 'context-cut'),
  tail_notices: events1.filter(e => e.type === 'tail-notice'),
  spend_reserves: events1.filter(e => e.type === 'spend-reserve-reached'),
  actor1_updates: events1.filter(e => e.type === 'knowledge-delivery' && e.kind === 'update'),
  actor2_updates: events2.filter(e => e.type === 'knowledge-delivery' && e.kind === 'update'),
  agenda_events: events1.filter(e => e.type === 'player-agenda'),
  cut_prompt_has_recent_intents: playerPayloads.some(p => JSON.stringify(p.messages).includes('recent_intents')),
  cut_prompt_has_agenda: playerPayloads.some(p => JSON.stringify(p.messages).includes('boil-water')),
};
await writeFile(join(directory, 'rehearsal-summary.json'), JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify(summary));
