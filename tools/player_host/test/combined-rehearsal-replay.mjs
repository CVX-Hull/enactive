// Offline end-to-end player-host/12 + player-knowledge/3 rehearsal driven by tests/test_wave4c_combined_rehearsal.py.
// Runs the real Node host (`tools/player_host/host.mjs`) over the real Python MCP (`delivery-mcp.py`) against a
// real exported `delivered-knowledge/3` file, exercising:
// - `player-host/12` (`telemetry_version: 12`) & bounded briefing;
// - `player_knowledge_query` (`bm25_1hop` + `_fold` -> compact `player-knowledge/3` hits);
// - `player_knowledge_read` (casefolded title read);
// - reminder recall with `already_in_context` deduplication;
// - `context_cut` hysteresis + best-effort `k = E` fallback (`cut_result: "best_effort"`) + ephemeral `recent_intents`;
// - halving `tail-notice`;
// - `"undelivered"` live knowledge update on a retryable failure followed by delivered update;
// - `spend-reserve-reached` handshake followed by orderly `ending` control and `player_finish`.
// Not a `node --test` file.
import { appendFile, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { deliveryScenario, listUpdate, recallReply } from './delivery-scenario.mjs';
import { reply } from './host-scenario.mjs';

const usage = prompt => ({ prompt_tokens: prompt, completion_tokens: 40, total_tokens: prompt + 40 });

const [dirArg, updateArg] = process.argv.slice(2);
if (!dirArg || !updateArg) throw new Error('Usage: combined-rehearsal-replay.mjs DIRECTORY UPDATE_JSON');
const directory = resolve(dirArg);
const knowledge = JSON.parse(await readFile(join(directory, 'delivered-knowledge.json'), 'utf8'));
const updateKnowledge = JSON.parse(await readFile(resolve(updateArg), 'utf8'));
const updatesFile = join(directory, 'actors', '001', 'knowledge-updates.jsonl');
const session = 'a'.repeat(32);
const actorId = '3'.repeat(32);

const recallPayloads = [];
const playerPayloads = [];
let controlSent = false;
const completedOps = [];
const stopControlId = 'b'.repeat(32);

const coverageLine = (operationId, version) => JSON.stringify({
  schema: 'coverage-update-entry/1', session, actor_id: actorId, operation_id: operationId, version, restored: false,
}) + '\n';

const { result, events } = await deliveryScenario(directory, {
  knowledge,
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
  recallFetch: (n, init) => {
    const payload = JSON.parse(init.body);
    recallPayloads.push(payload);
    // First recall is briefing -> select 'water-purification'; later reminders observe already_in_context -> silence.
    return recallReply(n === 1 ? ['water-purification'] : [], 0.001);
  },
  playerFetch: async (n, init) => {
    const payload = JSON.parse(init.body);
    playerPayloads.push(payload);
    // Request 1: query with morphological variant ("purifying waters") + casefolded title read + input.
    if (n === 1) {
      return reply(null, [
        ['player_knowledge_query', { query: 'purifying waters', intent: 'Search purification knowledge' }],
        ['player_knowledge_read', { id_or_title: 'WATER PURIFICATION', intent: 'Read full water article' }],
        ['computer_input', { actions: [{ type: 'key', key: 'x', modifiers: [] }], intent: 'Inspect shelter supplies' }],
      ], { ...usage(2500), cost: 0.05 });
    }
    // Request 2: second input turn; crosses 50% of work budget ($1.10) -> triggers halving `tail-notice` (`spend-limit`).
    if (n === 2) {
      return reply(null, [
        ['computer_input', { actions: [{ type: 'key', key: 'y', modifiers: [] }], intent: 'Boil river water at stove' }],
      ], { ...usage(7000), cost: 0.60 });
    }
    // Request 3: two computer_inputs have completed; append coverage through op 2 BEFORE returning
    // so refreshUpdates() adopts it before request 4 -> triggers `cut_result: "best_effort"` + `recent_intents`!
    if (n === 3) {
      const coveredOp = completedOps[1];
      if (!coveredOp) throw new Error('Expected two completed operations before request 3');
      await appendFile(updatesFile, coverageLine(coveredOp, knowledge.version));
      return reply(null, [
        ['computer_input', { actions: [{ type: 'key', key: 'z', modifiers: [] }], intent: 'Check clean water container' }],
      ], { ...usage(8000), cost: 0.05 });
    }
    // Request 4: post-cut turn! List live update v3 and stay inside ordinary budget so request 5 delivers v3.
    if (n === 4) {
      await listUpdate(directory, updateKnowledge);
      return reply(null, [
        ['computer_input', { actions: [{ type: 'key', key: 'w', modifiers: [] }], intent: 'Adopt updated water knowledge' }],
      ], { ...usage(3200), cost: 0.05 });
    }
    // Request 5: delivers v3 update (`outcome: "delivered"`) and crosses ordinary work budget -> `spend-reserve-reached`!
    if (n === 5) {
      return reply(null, [
        ['computer_input', { actions: [{ type: 'key', key: 's', modifiers: [] }], intent: 'Prepare to save and close' }],
      ], { ...usage(3200), cost: 0.45 });
    }
    // Request 6: after `spend-reserve-reached` + orderly `orderly_stop` control -> finish cleanly.
    return reply(null, [
      ['player_finish', {
        disposition: 'external_stop_complete',
        control_id: stopControlId,
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
        schema: 'player-control/1', id: stopControlId, session, actor_id: actorId, type: 'orderly_stop',
      }) + '\n');
    }
  },
});

// Second real actor (`002`): receives a live v3 update superseded mid-flight by `orderly_stop`,
// producing a real `knowledge-delivery` (`kind: "update"`, `outcome: "undelivered"`) followed by `delivered`.
const actor2Root = join(directory, '_actor2_stage');
await mkdir(actor2Root, { recursive: true });
await writeFile(join(actor2Root, 'delivered-knowledge.json'), JSON.stringify(knowledge));
let actor2Control = null;
const stopControlId2 = 'c'.repeat(32);
const { events: events2 } = await deliveryScenario(actor2Root, {
  knowledge,
  preserveKnowledgeFile: true,
  knowledgeUpdates: true,
  enabledTools: ['computer_input'],
  recallFetch: () => recallReply([], 0.001),
  playerFetch: async (n, init) => {
    if (n === 1) {
      await listUpdate(actor2Root, updateKnowledge);
      return reply(null, [['computer_input', { actions: [{ type: 'key', key: 'x', modifiers: [] }] }]], { ...usage(1200), cost: 0.01 });
    }
    if (n === 2) {
      // Trigger orderly_stop while request-2 (carrying v3 update) is in flight -> host aborts & emits `undelivered`!
      setTimeout(() => actor2Control?.write(JSON.stringify({
        schema: 'player-control/1', id: stopControlId2, session, actor_id: actorId, type: 'orderly_stop',
      }) + '\n'), 20);
      await new Promise((_res, rej) => {
        init.signal?.addEventListener('abort', () => rej(new DOMException('Aborted', 'AbortError')), { once: true });
      });
    }
    return reply(null, [['player_finish', {
      disposition: 'external_stop_complete', control_id: stopControlId2, report: 'Stopped after undelivered update.', source_ids: [],
    }]], { ...usage(1200), cost: 0.01 });
  },
  onEvent: (_event, control) => { actor2Control = control; },
});
const actor2Id = '4'.repeat(32);
await mkdir(join(directory, 'actors', '002'), { recursive: true });
await writeFile(
  join(directory, 'actors', '002', 'host.jsonl'),
  events2.map(e => JSON.stringify(e).replaceAll(actorId, actor2Id) + '\n').join(''),
);
await writeFile(join(directory, 'actors', '002', 'delivered-knowledge.json'), JSON.stringify(knowledge));
await rm(actor2Root, { recursive: true, force: true });

const allUpdates = [...events, ...events2].filter(e => e.type === 'knowledge-delivery' && e.kind === 'update');
const summary = {
  ok: result.ok,
  reason: result.reason,
  host: events.find(e => e.type === 'host-start'),
  recall_count: recallPayloads.length,
  reminder_has_already_in_context: recallPayloads.slice(1).some(p => JSON.stringify(p.messages).includes('already_in_context')),
  cuts: events.filter(e => e.type === 'context-cut'),
  tail_notices: events.filter(e => e.type === 'tail-notice'),
  spend_reserves: events.filter(e => e.type === 'spend-reserve-reached'),
  updates: allUpdates,
  cut_prompt_has_recent_intents: playerPayloads.some(p => JSON.stringify(p.messages).includes('recent_intents')),
};
await writeFile(join(directory, 'rehearsal-summary.json'), JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify(summary));
