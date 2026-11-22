// R-REGRESSION: an incomplete or invalid coverage prefix must never discard
// uncovered operations, and a cut must still produce a usable player request.
import test from 'node:test';
import assert from 'node:assert/strict';
import { appendFile, mkdir, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { PassThrough } from 'node:stream';
import { McpClient } from '@earendil-works/pi-mcp';
import { runHost, validateConfiguration } from '../host.mjs';
import { compactSourceIds, coverageEntry } from '../knowledge.mjs';
import { knowledge, listUpdate, recallReply } from './delivery-scenario.mjs';
import { actorId, model, png, realDelay, reply, route, sessionId, usageRecord } from './host-scenario.mjs';

const tokenCut = {high_mark:20_000, low_mark:2_600, min_free:1};
const imageCut = {high_mark:90_000, low_mark:80_000, min_free:1};
const operationId = n => n.toString(16).padStart(32, '0');
const sourceId = n => `${sessionId}-${n}`;
const publication = (n, version = 'v1') => ({schema:'coverage-update-entry/1', session:sessionId, actor_id:actorId,
  operation_id:operationId(n), version, restored:false});
const restoration = {...publication(0), actor_id:null, operation_id:null, version:null, restored:true};
const usage = tokens => ({...usageRecord, prompt_tokens:tokens - 5, total_tokens:tokens});

test('route /10 requires a closed context cut policy for the player model only', () => {
  const base = route();
  const validate = config => validateConfiguration(config, model.id, 'off');
  assert.equal(validate(base).context_cut, null);
  assert.deepEqual(validate({...base, context_cut:tokenCut,
    recall:{...base.recall, model:{...base.recall.model, contextWindow:4096}}}).context_cut, tokenCut);
  const missing = {...base};
  delete missing.context_cut;
  assert.throws(() => validate(missing), /invalid-configuration/);
  assert.throws(() => validate({...base, schema:'player-host/9'}), /invalid-configuration/);
  for (const context_cut of [false, [], {}, {...tokenCut, high_mark:tokenCut.low_mark},
    {...tokenCut, high_mark:model.contextWindow}, {...tokenCut, low_mark:0}, {...tokenCut, low_mark:1.5},
    {...tokenCut, min_free:0}, {...tokenCut, min_free:Number.MAX_SAFE_INTEGER + 1}, {...tokenCut, extra:true}]) {
    assert.throws(() => validate({...base, context_cut}), /invalid-configuration/);
  }
});

test('coverage lines are closed and distinguish publication from restore invalidation', () => {
  for (const entry of [publication(1), restoration]) assert.deepEqual(coverageEntry(JSON.stringify(entry)), entry);
  for (const entry of [{...publication(1), schema:'coverage-update-entry/2'}, {...publication(1), extra:true},
    {...publication(1), session:'wrong'}, {...publication(1), actor_id:null}, {...publication(1), operation_id:'bad'},
    {...publication(1), version:'v0'}, {...publication(1), version:'v01'}, {...publication(1), version:'v9007199254740992'},
    {...publication(1), version:null}, {...publication(1), restored:'false'}, {...restoration, version:'v1'},
    {...restoration, actor_id:actorId}, {...restoration, operation_id:operationId(1)}]) {
    assert.equal(coverageEntry(JSON.stringify(entry)), null);
  }
  assert.equal(coverageEntry('not JSON'), null);
});

test('compactSourceIds losslessly compacts contiguous numbered runs and keeps singletons or arbitrary IDs', () => {
  assert.deepEqual(compactSourceIds([]), []);
  assert.deepEqual(compactSourceIds(['s-0001']), ['s-0001']);
  assert.deepEqual(compactSourceIds(['s-0001', 's-0002', 's-0003', 's-0005', 's-0006', 'custom', 's-9', 's-10', 's-011']),
    ['s-0001..0003', 's-0005..0006', 'custom', 's-9..10', 's-011']);
});

const observe = (n, count = 1, tokens = 16) => reply(null,
  Array.from({length:count}, () => ['computer_observe', {}]), usage(tokens), undefined, `turn-${n}`);
const messageText = message => typeof message.content === 'string' ? message.content
  : (message.content ?? []).filter(part => part.type === 'text').map(part => part.text).join('');
const markerText = payload => payload.messages.map(messageText).find(text => text.startsWith('BEGIN CONTEXT CUT'));
const cutEvents = events => events.filter(event => event.type === 'context-cut');

async function play(t, playerFetch, {contextCut = imageCut, maxImages = 2, onEvent} = {}) {
  const dir = await mkdtemp(join(tmpdir(), 'player-context-cut-'));
  t.after(() => rm(dir, {recursive:true, force:true}));
  const actor = join(dir, 'actors', '001'), list = join(actor, 'knowledge-updates.jsonl');
  await mkdir(actor, {recursive:true});
  const configuration = {...route(), context_cut:contextCut, max_context_images:maxImages};
  configuration.recall.model.id = 'recall-fixture';
  configuration.recall.every = 100;
  const control = new PassThrough();
  const events = [], payloads = [];
  let operations = 0;

  // Fixed operation and source IDs let the fixture append real update lines at
  // defined points in the transcript. Pi still builds and serializes each request.
  t.mock.method(McpClient.prototype, 'connect', async () => {});
  t.mock.method(McpClient.prototype, 'close', async () => {});
  t.mock.method(McpClient.prototype, 'listTools', async () => [{name:'computer_observe',
    inputSchema:{type:'object', properties:{intent:{type:'string'}}, required:['intent'], additionalProperties:false}}]);
  t.mock.method(McpClient.prototype, 'callTool', async () => {
    const n = ++operations;
    return {content:[{type:'text', text:`Observation ${n}`}, {type:'image', data:png, mimeType:'image/png'}],
      structuredContent:{schema:'player-computer-operation/1', kind:'observe', status:'completed',
        actor_id:actorId, session:sessionId, operation_id:operationId(n), source:{source_id:sourceId(n)}}};
  });
  const appendCoverage = (...entries) => appendFile(list, entries.map(entry => JSON.stringify(entry) + '\n').join(''));
  const publish = async (...entries) => {
    await appendCoverage(...entries);
    // Give the off-path reader a polling interval while the provider holds its response.
    await realDelay(1200);
  };
  const result = await runHost({configuration, knowledge:{...knowledge(), version:'v1'}, knowledgeUpdates:list,
    session:sessionId, actorId, pendingControlId:null, control, finishReserveUsd:'0',
    context:'Frozen player guide', prompt:'Offline mission', model:model.id, effort:'off', timeoutSeconds:15,
    env:{OFFLINE_TEST_KEY:'fixture-only'}, mcpConfig:{command:process.execPath, args:[], cwd:dir,
      enabled:true, required:true, enabled_tools:['computer_observe'], startup_timeout_sec:2, tool_timeout_sec:2},
    fetch:async (_url, init) => {
      const payload = JSON.parse(init.body);
      if (payload.model === 'recall-fixture') return recallReply(['article-a']);
      payloads.push(payload);
      return playerFetch(payloads.length, {dir, publish, appendCoverage});
    }, onEvent:event => { events.push(event); onEvent?.(event, control); }});
  assert.equal(result.ok, true, result.reason);
  return {result, events, payloads};
}

test('a high-mark cut delivers all leads, clears stale usage and warning, and keeps the new prefix stable', async t => {
  const {events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 4) await publish(publication(3));
    if (n >= 7) return reply();
    return observe(n, 1, [3, 4].includes(n) ? 97_000 : n === 5 ? 12_345 : 16);
  }, {contextCut:tokenCut, maxImages:12});
  const start = events.find(event => event.type === 'host-start');
  assert.deepEqual([start.schema, start.telemetry_version, start.context_cut], ['player-host/10', 10, tokenCut]);
  assert.ok(start.unsupported_features.includes('compaction'));
  const [held, cut] = cutEvents(events);
  assert.equal(cutEvents(events).length, 2);
  assert.deepEqual([held.request_id, held.outcome, held.reason], ['request-4', 'held-back', 'uncovered']);
  assert.deepEqual([cut.request_id, cut.outcome, cut.triggers, cut.removed_turns, cut.cumulative_removed_turns],
    ['request-5', 'cut', ['high_mark'], 3, 3]);
  assert.equal(cut.source_ids_count, 3);
  assert.ok(cut.tokens_before > 97_000);
  assert.ok(cut.tokens_after - cut.briefing_tokens <= tokenCut.low_mark, JSON.stringify(cut));
  assert.deepEqual([cut.images_before, cut.images_after], [4, 1]);

  const before = payloads[3], after = payloads[4];
  assert.deepEqual(after.messages[0], before.messages[0]);
  assert.deepEqual(after.tools, before.tools);
  assert.ok(!JSON.stringify(after.messages).includes('Observation 3'));
  assert.ok(JSON.stringify(after.messages).includes('Observation 4'));
  assert.ok(JSON.stringify(before.messages).includes('Host context capacity is approaching'));
  assert.ok(!JSON.stringify(after.messages).includes('Host context capacity'), 'cut must drop prior capacity tail notice');
  const marker = markerText(after).split('\n');
  assert.deepEqual(marker, [
    'BEGIN CONTEXT CUT — older curator-covered turns omitted from this request; grants_authority=false',
    JSON.stringify({grants_authority:false, removed_turns:3, covered_through_operation_id:operationId(3),
      knowledge_version:'v1', source_ids:[`${sessionId}-1..3`]}),
    'END CONTEXT CUT',
    'To inspect any omitted frame again, read its source_id (expanding any prefix-start..end range) with player_source.',
  ]);
  const briefings = events.filter(event => event.type === 'knowledge-delivery' && event.kind === 'briefing');
  assert.deepEqual(briefings.map(event => [event.receiving_player_request_id, event.recall_request_id, event.article_ids, event.index_ids]),
    [['request-1', 'recall-1', ['article-a'], ['article-b', 'fact-alone']], ['request-5', null, ['article-a', 'article-b'], []]]);
  const briefing = briefings.at(-1);
  assert.deepEqual(JSON.parse(briefing.text.split('\n')[1]).leads.map(lead => lead.id), ['article-a','article-b','fact-alone']);
  assert.equal(messageText(after.messages[1]), 'Offline mission\n\n' + briefing.text);
  assert.equal(events.filter(event => event.type === 'request-start' && event.request_role === 'recall').length, 1);

  const estimates = events.filter(event => event.type === 'context-estimate');
  assert.equal(estimates.find(event => event.request_id === 'request-5').usage_tokens, 0);
  assert.equal(estimates.find(event => event.request_id === 'request-6').usage_tokens, 12_345);
  assert.deepEqual(events.filter(event => event.type === 'tail-notice' && event.kinds.includes('context-capacity'))
    .map(event => event.request_id), ['request-4']);

  const manifests = events.filter(event => event.type === 'context-manifest').slice(4);
  for (let i = 1; i < manifests.length; i++) {
    assert.equal(manifests[i].reused_prefix_parts, manifests[i - 1].part_count);
    assert.ok(manifests[i].reused_prefix_parts > manifests[i - 1].reused_prefix_parts);
    const older = payloads[i + 3], newer = payloads[i + 4];
    assert.equal(JSON.stringify(newer.messages.slice(0, older.messages.length)), JSON.stringify(older.messages));
  }
});

test('image peak holds an only partly covered batch, then cuts it whole and accumulates omitted sources', async t => {
  const {events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 2) await publish(publication(1));
    if (n === 3) await publish(publication(2));
    if (n === 4) await publish(publication(3));
    return n === 5 ? reply() : observe(n, n === 1 ? 2 : 1);
  });
  const [held, first, second] = cutEvents(events);
  assert.deepEqual([held.request_id, held.reason, held.available_turns, held.covered_through_operation_id],
    ['request-3', 'uncovered', 0, operationId(1)]);
  const projection = events.find(event => event.type === 'context-image-projection' && event.request_id === 'request-3');
  assert.equal(projection.omissions.length, 1);
  assert.ok(!markerText(payloads[2]));
  assert.ok(JSON.stringify(payloads[2].messages).includes('Observation 2'));
  assert.deepEqual([first.request_id, first.triggers, first.removed_turns, first.images_after], ['request-4', ['image_peak'], 1, 2]);
  assert.deepEqual([second.request_id, second.triggers, second.cumulative_removed_turns, second.source_ids_count],
    ['request-5', ['image_peak'], 2, 3]);
  assert.deepEqual(JSON.parse(markerText(payloads[4]).split('\n')[1]).source_ids, [`${sessionId}-1..3`]);
});

test('an otherwise eligible prefix below min_free falls back to image eviction', async t => {
  const {events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 2) await publish(publication(1));
    return n === 3 ? reply() : observe(n);
  }, {contextCut:{...imageCut, min_free:2}, maxImages:1});
  const [held] = cutEvents(events);
  assert.deepEqual([held.request_id, held.reason, held.available_turns, held.min_free], ['request-3', 'below-min-free', 1, 2]);
  assert.equal(events.find(event => event.type === 'context-image-projection' && event.request_id === 'request-3').omissions.length, 1);
  assert.ok(!markerText(payloads[2]));
});

test('restore permanently disables additional cuts even if later coverage arrives', async t => {
  const {events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 2) await publish(publication(1));
    if (n === 3) await publish(restoration, publication(2));
    if (n === 4) await publish(publication(3));
    return n === 5 ? reply() : observe(n);
  }, {maxImages:1});
  assert.deepEqual(cutEvents(events).map(event => [event.request_id, event.outcome, event.reason, event.covered_through_operation_id]),
    [['request-3', 'cut', undefined, operationId(1)], ['request-4', 'held-back', 'restored', null],
      ['request-5', 'held-back', 'restored', null]]);
  assert.equal(markerText(payloads[4]), markerText(payloads[2]));
});

test('coverage from a newer version refused for capacity leaves the adopted coverage usable', async t => {
  const {events, payloads} = await play(t, async (n, {dir, publish}) => {
    if (n === 3) {
      const huge = knowledge();
      huge.articles[0].lead = 'x'.repeat(600_000);
      await listUpdate(dir, huge);
      await publish(publication(1), publication(2, 'v2'), {...publication(2), session:actorId},
        {...publication(2), actor_id:sessionId});
    }
    return n === 4 ? reply() : observe(n);
  });
  assert.ok(events.some(event => event.type === 'knowledge-delivery' && event.version === 'v2' && event.reason === 'context-capacity'));
  assert.ok(!events.some(event => event.type === 'knowledge-delivery' && event.reason === 'invalid-entry'));
  const [cut] = cutEvents(events);
  assert.deepEqual([cut.request_id, cut.outcome, cut.knowledge_version, cut.covered_through_operation_id, cut.removed_turns],
    ['request-4', 'cut', 'v1', operationId(1), 1]);
  assert.deepEqual(JSON.parse(markerText(payloads[3]).split('\n')[1]).source_ids, [sourceId(1)]);
});

test('an accepted orderly stop fences new cuts and remains visible after an earlier cut', async t => {
  const command = {schema:'player-control/1', type:'orderly_stop', id:'c'.repeat(32), session:sessionId, actor_id:actorId};
  const {events, payloads, result} = await play(t, async (n, {publish}) => {
    if (n === 2) await publish(publication(1));
    if (n === 3) await publish(publication(2));
    return n === 4 ? reply(null, [['player_finish', {disposition:'external_stop_complete', report:'Stopped',
      source_ids:[], control_id:command.id}]]) : observe(n);
  }, {maxImages:1, onEvent:(event, control) => {
    if (event.type === 'tool-result' && event.request_id === 'request-3') control.write(JSON.stringify(command) + '\n');
  }});
  assert.equal(result.reason, 'external_stop_complete');
  assert.deepEqual(cutEvents(events).map(event => [event.request_id, event.outcome]), [['request-3', 'cut']]);
  assert.ok(events.some(event => event.type === 'control-accepted' && event.control_id === command.id));
  assert.equal(markerText(payloads[3]), markerText(payloads[2]));
  assert.ok(payloads[3].messages.some(message => messageText(message).startsWith('Automation control: orderly stop requested.')
    && messageText(message).endsWith(`control_id: ${command.id}`)));
});

test('a second capacity warning after a cut re-emits the full wrap-up instruction', async t => {
  const {events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 4) await publish(publication(3));
    if (n === 6) return reply();
    return observe(n, 1, [3, 4, 5].includes(n) ? 97_000 : 16);
  }, {contextCut:tokenCut, maxImages:12});
  assert.deepEqual(events.filter(event => event.type === 'tail-notice' && event.kinds.includes('context-capacity'))
    .map(event => event.request_id), ['request-4', 'request-6']);
  assert.ok(!JSON.stringify(payloads[4].messages).includes('Host context capacity'));
  assert.ok(JSON.stringify(payloads[5].messages).includes('Host context capacity is approaching'));
  assert.ok(JSON.stringify(payloads[5].messages).includes('No text summarization or history restoration is available.'));
});

test('an unknown player-transport/2 operation in a batch prevents cutting that batch', async t => {
  const dir = await mkdtemp(join(tmpdir(), 'player-context-cut-transport-'));
  t.after(() => rm(dir, {recursive:true, force:true}));
  const actor = join(dir, 'actors', '001'), list = join(actor, 'knowledge-updates.jsonl');
  await mkdir(actor, {recursive:true});
  const configuration = {...route(), context_cut:imageCut, max_context_images:2};
  configuration.recall.model.id = 'recall-fixture';
  configuration.recall.every = 100;
  let calls = 0;
  t.mock.method(McpClient.prototype, 'connect', async () => {});
  t.mock.method(McpClient.prototype, 'close', async () => {});
  t.mock.method(McpClient.prototype, 'listTools', async () => [{name:'computer_observe',
    inputSchema:{type:'object', properties:{intent:{type:'string'}}, required:['intent'], additionalProperties:false}}]);
  t.mock.method(McpClient.prototype, 'callTool', async () => {
    calls++;
    if (calls === 2) {
      return {content:[{type:'text', text:JSON.stringify({schema:'player-transport/2', status:'unknown', reason:'timeout'})}]};
    }
    return {content:[{type:'text', text:`Observation ${calls}`}, {type:'image', data:png, mimeType:'image/png'}],
      structuredContent:{schema:'player-computer-operation/1', kind:'observe', status:'completed',
        actor_id:actorId, session:sessionId, operation_id:operationId(calls), source:{source_id:sourceId(calls)}}};
  });
  const events = [], payloads = [];
  const result = await runHost({configuration, knowledge:{...knowledge(), version:'v1'}, knowledgeUpdates:list,
    session:sessionId, actorId, pendingControlId:null, control:new PassThrough(), finishReserveUsd:'0',
    context:'Frozen player guide', prompt:'Offline mission', model:model.id, effort:'off', timeoutSeconds:15,
    env:{OFFLINE_TEST_KEY:'fixture-only'}, mcpConfig:{command:process.execPath, args:[], cwd:dir,
      enabled:true, required:true, enabled_tools:['computer_observe'], startup_timeout_sec:2, tool_timeout_sec:2},
    fetch:async (_url, init) => {
      const payload = JSON.parse(init.body);
      if (payload.model === 'recall-fixture') return recallReply(['article-a']);
      payloads.push(payload);
      const n = payloads.length;
      if (n === 2) { await appendFile(list, JSON.stringify(publication(1)) + '\n'); await realDelay(1200); }
      return n === 4 ? reply() : observe(n, n === 1 ? 2 : 1);
    }, onEvent:event => events.push(event)});
  assert.equal(result.ok, true, result.reason);
  const cuts = cutEvents(events);
  assert.ok(cuts.length >= 1 && cuts.every(c => c.outcome === 'held-back' && c.reason === 'uncovered'));
});

test('min_free 10 holds back 9 covered turns and cuts at 10 covered turns', async t => {
  const {events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 10) await publish(publication(9));
    if (n === 11) await publish(publication(10));
    if (n === 12) return reply();
    return observe(n, 1, 16);
  }, {contextCut:{high_mark:90_000, low_mark:80_000, min_free:10}, maxImages:1});
  const cuts = cutEvents(events).filter(c => ['request-11', 'request-12'].includes(c.request_id));
  assert.deepEqual(cuts.map(c => [c.request_id, c.outcome, c.reason ?? null, c.removed_turns ?? c.available_turns]),
    [['request-11', 'held-back', 'below-min-free', 9], ['request-12', 'cut', null, 10]]);
  assert.deepEqual(JSON.parse(markerText(payloads[11]).split('\n')[1]).source_ids, [`${sessionId}-1..10`]);
});

test('handoff succeeds after a cut and cut briefing emits knowledge-undelivered if spend stops before fetch', async t => {
  const dir = await mkdtemp(join(tmpdir(), 'player-context-cut-handoff-'));
  t.after(() => rm(dir, {recursive:true, force:true}));
  const actor = join(dir, 'actors', '001'), list = join(actor, 'knowledge-updates.jsonl');
  await mkdir(actor, {recursive:true});
  const configuration = {...route(), context_cut:imageCut, max_context_images:1};
  configuration.recall.model.id = 'recall-fixture';
  configuration.recall.every = 100;
  let operations = 0;
  const handoffOp = operationId(99), contextId = 'd'.repeat(32), contextSha = 'e'.repeat(64);
  t.mock.method(McpClient.prototype, 'connect', async () => {});
  t.mock.method(McpClient.prototype, 'close', async () => {});
  t.mock.method(McpClient.prototype, 'listTools', async () => [
    {name:'computer_observe', inputSchema:{type:'object', properties:{intent:{type:'string'}}, required:['intent'], additionalProperties:false}},
    {name:'player_handoff', inputSchema:{type:'object', properties:{intent:{type:'string'}}, required:['intent'], additionalProperties:false}},
  ]);
  t.mock.method(McpClient.prototype, 'callTool', async name => {
    if (name === 'player_handoff') {
      return {content:[{type:'text', text:'Handoff sealed'}],
        structuredContent:{schema:'player-computer-operation/1', kind:'handoff', status:'sealed',
          actor_id:actorId, session:sessionId, operation_id:handoffOp,
          handoff:{schema:'player-handoff/1', grants_authority:false, operation_id:handoffOp, session:sessionId,
            actor_id:actorId, context_id:contextId, context_sha256:contextSha, sealed_wall:1.5}}};
    }
    const n = ++operations;
    return {content:[{type:'text', text:`Observation ${n}`}, {type:'image', data:png, mimeType:'image/png'}],
      structuredContent:{schema:'player-computer-operation/1', kind:'observe', status:'completed',
        actor_id:actorId, session:sessionId, operation_id:operationId(n), source:{source_id:sourceId(n)}}};
  });
  const events = [];
  let reqs = 0;
  const result = await runHost({configuration, knowledge:{...knowledge(), version:'v1'}, knowledgeUpdates:list,
    session:sessionId, actorId, pendingControlId:null, control:new PassThrough(), finishReserveUsd:'0',
    context:'Frozen player guide', prompt:'Offline mission', model:model.id, effort:'off', timeoutSeconds:15,
    env:{OFFLINE_TEST_KEY:'fixture-only'}, mcpConfig:{command:process.execPath, args:[], cwd:dir,
      enabled:true, required:true, enabled_tools:['computer_observe', 'player_handoff'], startup_timeout_sec:2, tool_timeout_sec:2},
    fetch:async (_url, init) => {
      const payload = JSON.parse(init.body);
      if (payload.model === 'recall-fixture') return recallReply(['article-a']);
      reqs++;
      if (reqs === 2) { await appendFile(list, JSON.stringify(publication(1)) + '\n'); await realDelay(1200); }
      return reqs === 3 ? reply(null, [['player_handoff', {}]]) : observe(reqs);
    }, onEvent:event => events.push(event)});
  assert.deepEqual([result.ok, result.reason], [true, 'handoff']);
  assert.deepEqual(cutEvents(events).map(c => [c.request_id, c.outcome]), [['request-3', 'cut']]);
  assert.ok(events.some(e => e.type === 'handoff' && e.handoff_id === handoffOp));

  // Now verify knowledge-undelivered when spend limit stops right after cutContext queues a cut briefing.
  const dir2 = await mkdtemp(join(tmpdir(), 'player-context-cut-undelivered-'));
  t.after(() => rm(dir2, {recursive:true, force:true}));
  const actor2 = join(dir2, 'actors', '001'), list2 = join(actor2, 'knowledge-updates.jsonl');
  await mkdir(actor2, {recursive:true});
  const config2 = {...route(), spend_limit_usd:'0.002', unpriced_request_usd:'0.001', context_cut:imageCut, max_context_images:1};
  config2.recall.model.id = 'recall-fixture';
  config2.recall.every = 100;
  operations = 0;
  const events2 = [];
  let reqs2 = 0;
  const res2 = await runHost({configuration:config2, knowledge:{...knowledge(), version:'v1'}, knowledgeUpdates:list2,
    session:sessionId, actorId, pendingControlId:null, control:new PassThrough(), finishReserveUsd:'0',
    context:'Frozen player guide', prompt:'Offline mission', model:model.id, effort:'off', timeoutSeconds:15,
    env:{OFFLINE_TEST_KEY:'fixture-only'}, mcpConfig:{command:process.execPath, args:[], cwd:dir2,
      enabled:true, required:true, enabled_tools:['computer_observe'], startup_timeout_sec:2, tool_timeout_sec:2},
    fetch:async (_url, init) => {
      const payload = JSON.parse(init.body);
      if (payload.model === 'recall-fixture') return recallReply(['article-a']);
      reqs2++;
      if (reqs2 === 2) { await appendFile(list2, JSON.stringify(publication(1)) + '\n'); await realDelay(1200); }
      return reply(null, [['computer_observe', {}]], {...usageRecord, cost:reqs2 === 2 ? 0.002 : 0.0005});
    }, onEvent:event => events2.push(event)});
  assert.deepEqual([res2.ok, res2.reason], [false, 'spend-limit']);
  assert.ok(events2.some(e => e.type === 'context-cut' && e.outcome === 'cut' && e.request_id === 'request-3'));
  assert.ok(events2.some(e => e.type === 'knowledge-undelivered' && e.kind === 'briefing' && e.reason === 'actor-ended'));
});
