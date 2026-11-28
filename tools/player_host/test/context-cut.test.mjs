// R-REGRESSION: an incomplete or invalid coverage prefix must never discard
// uncovered operations, and a cut must still produce a usable player request.
import test from 'node:test';
import assert from 'node:assert/strict';
import { appendFile, mkdir, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { PassThrough } from 'node:stream';
import { McpClient } from '@earendil-works/pi-mcp';
import { emptyAgenda, applyAgendaTool } from '../agenda.mjs';
import { runHost, validateConfiguration } from '../host.mjs';
import { compactSourceIds, coverageEntry, cutBriefing, cutMarker, CUT_BRIEFING_ARTICLES, CUT_BRIEFING_CHARS,
  CUT_BRIEFING_FACTS, CUT_BRIEFING_SNIPPET_CHARS, validateKnowledge } from '../knowledge.mjs';
import { contest, knowledge, listUpdate } from './delivery-scenario.mjs';
import { actorId, article, fact, model, png, position, realDelay, reply, route, sessionId, usageRecord } from './host-scenario.mjs';

const tokenCut = {high_mark:60_000, low_mark:2_600, min_free:1};
const imageCut = {high_mark:90_000, low_mark:80_000, min_free:1};
const operationId = n => n.toString(16).padStart(32, '0');
const sourceId = n => `${sessionId}-${n}`;
const publication = (n, version = 'v1') => ({schema:'coverage-update-entry/1', session:sessionId, actor_id:actorId,
  operation_id:operationId(n), version, restored:false});
const restoration = {...publication(0), actor_id:null, operation_id:null, version:null, restored:true};
const usage = tokens => ({...usageRecord, prompt_tokens:tokens - 5, total_tokens:tokens});

test('the current route requires a closed context cut policy for the player model only', () => {
  const base = route();
  const validate = config => validateConfiguration(config, model.id, 'off');
  assert.equal(validate(base).context_cut, null);
  assert.deepEqual(validate({...base, context_cut:tokenCut}).context_cut, tokenCut);
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

test('compactSourceIds and cutMarker losslessly compact runs and factor out a shared prefix', () => {
  assert.deepEqual(compactSourceIds([]), []);
  assert.deepEqual(compactSourceIds(['s-0001']), ['s-0001']);
  assert.deepEqual(compactSourceIds(['s-0001', 's-0002', 's-0003', 's-0005', 's-0006', 'custom', 's-9', 's-10', 's-011']),
    ['s-0001..0003', 's-0005..0006', 'custom', 's-9..10', 's-011']);
  const factored = JSON.parse(cutMarker({removedTurns:4, coveredThroughOperationId:operationId(4), knowledgeVersion:'v1',
    sourceIds:[`${sessionId}-10`, `${sessionId}-13`, `${sessionId}-14`, `${sessionId}-20`]}).split('\n')[1]);
  assert.deepEqual([factored.source_id_prefix, factored.source_ids], [`${sessionId}-`, ['10', '13..14', '20']]);
});

const observe = (n, count = 1, tokens = 16) => reply(null,
  Array.from({length:count}, () => ['computer_observe', {}]), usage(tokens), undefined, `turn-${n}`);
const messageText = message => typeof message.content === 'string' ? message.content
  : (message.content ?? []).filter(part => part.type === 'text').map(part => part.text).join('');
const markerText = payload => payload.messages.map(messageText).find(text => text.startsWith('BEGIN CONTEXT CUT'));
const cutEvents = events => events.filter(event => event.type === 'context-cut');

async function play(t, playerFetch, {contextCut = imageCut, maxImages = 2, block = 1, onEvent, agenda, routeOverrides} = {}) {
  const dir = await mkdtemp(join(tmpdir(), 'player-context-cut-'));
  t.after(() => rm(dir, {recursive:true, force:true}));
  const actor = join(dir, 'actors', '001'), list = join(actor, 'knowledge-updates.jsonl');
  await mkdir(actor, {recursive:true});
  const configuration = {...route(), context_cut:contextCut, max_context_images:maxImages, context_image_block:block, ...routeOverrides};
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
  const result = await runHost({configuration, agenda, knowledge:knowledge('v1'), knowledgeUpdates:list,
    session:sessionId, actorId, pendingControlId:null, control, finishReserveUsd:'0',
    context:'Frozen player guide', prompt:'Offline mission', model:model.id, effort:'off', timeoutSeconds:15,
    env:{OFFLINE_TEST_KEY:'fixture-only'}, mcpConfig:{command:process.execPath, args:[], cwd:dir,
      enabled:true, required:true, enabled_tools:['computer_observe'], startup_timeout_sec:2, tool_timeout_sec:2},
    fetch:async (_url, init) => {
      const payload = JSON.parse(init.body);
      payloads.push(payload);
      return playerFetch(payloads.length, {dir, publish, appendCoverage});
    }, onEvent:event => { events.push(event); onEvent?.(event, control); }});
  assert.equal(result.ok, true, result.reason);
  return {result, events, payloads};
}

test('a high-mark cut delivers a bounded briefing, clears stale usage and warning, and keeps the new prefix stable', async t => {
  const {events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 4) await publish(publication(3));
    if (n >= 7) return reply();
    return observe(n, 1, [3, 4].includes(n) ? 95_000 : n === 5 ? 12_345 : 16);
  }, {contextCut:tokenCut, maxImages:12});
  const start = events.find(event => event.type === 'host-start');
  assert.deepEqual([start.schema, start.telemetry_version, start.context_cut], ['player-host/13', 13, tokenCut]);
  assert.ok(start.unsupported_features.includes('compaction'));
  const [held, cut] = cutEvents(events);
  assert.equal(cutEvents(events).length, 2);
  assert.deepEqual([held.request_id, held.outcome, held.reason], ['request-4', 'held-back', 'uncovered']);
  assert.deepEqual([cut.request_id, cut.outcome, cut.triggers, cut.removed_turns, cut.cumulative_removed_turns],
    ['request-5', 'cut', ['high_mark'], 3, 3]);
  assert.equal(cut.source_ids_count, 3);
  assert.ok(cut.tokens_before > 95_000);
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
    JSON.stringify({grants_authority:false, removed_turns:3, uncovered_turns:0, covered_through_operation_id:operationId(3),
      knowledge_version:'v1', source_id_prefix:`${sessionId}-`, source_ids:['1..3'], recent_intents:['State the fixture action']}),
    'END CONTEXT CUT',
    'To inspect any omitted frame again, read its source_id (combining any source_id_prefix and expanding any start..end range) with player_source.',
  ]);
  const briefings = events.filter(event => event.type === 'knowledge-delivery' && event.kind === 'briefing');
  assert.deepEqual(briefings.map(event => [event.receiving_player_request_id, event.article_ids, event.index_ids]),
    [['request-1', ['article-b', 'article-a'], ['fact-alone']], ['request-5', ['article-b', 'article-a'], ['fact-alone']]]);
  const briefing = briefings.at(-1);
  const data = JSON.parse(briefing.text.split('\n')[1]);
  assert.deepEqual([data.leads.map(lead => lead.id), data.index, data.unlisted_entries],
    [['article-b', 'article-a'], [{id:'fact-alone', title:'Unfiled subject', index:'An unfiled claim'}], 0]);
  assert.equal(messageText(after.messages[1]), 'Offline mission\n\n' + briefing.text);
  assert.ok(events.filter(event => event.type === 'request-start').every(event => event.request_role === 'player'));

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
  const marker5 = JSON.parse(markerText(payloads[4]).split('\n')[1]);
  assert.deepEqual([marker5.source_id_prefix, marker5.source_ids], [`${sessionId}-`, ['1..3']]);
});

test('armed image pressure retries when coverage arrives between block evictions', async t => {
  const {events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 5) await publish(publication(3));
    return n === 8 ? reply() : observe(n);
  }, {maxImages:3, block:2});
  assert.deepEqual(cutEvents(events).map(event => [event.request_id, event.outcome, event.reason, event.triggers]),
    [['request-5', 'held-back', 'uncovered', ['image_peak']], ['request-6', 'cut', undefined, ['image_peak']],
      ['request-8', 'held-back', 'uncovered', ['image_peak']]]);
  const omitted = id => events.find(event => event.type === 'context-image-projection' && event.request_id === id).omitted_images;
  assert.deepEqual(['request-4', 'request-5', 'request-6', 'request-7', 'request-8'].map(omitted), [0, 2, 0, 0, 2]);
  assert.ok(markerText(payloads[5]));
  const cut = cutEvents(events)[1];
  assert.deepEqual([cut.removed_turns, cut.images_before, cut.images_after], [3, 5, 2]);
});

test('an image cut leaves a block of headroom, so the next request extends the cut prefix without eviction', async t => {
  // Peak 3, block 2: request-5 holds four images and would omit a block. Coverage through turn 3 lets the cut
  // reach its target of one image (3 - 2), so requests 6 and 7 add images without another cut or eviction.
  const {events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 4) await publish(publication(3));
    return n === 7 ? reply() : observe(n);
  }, {maxImages:3, block:2});
  assert.deepEqual(cutEvents(events).map(event => [event.request_id, event.outcome, event.triggers, event.removed_turns,
    event.images_before, event.images_after]), [['request-5', 'cut', ['image_peak'], 3, 4, 1]]);
  const omitted = id => events.find(event => event.type === 'context-image-projection' && event.request_id === id).omitted_images;
  assert.deepEqual(['request-5', 'request-6', 'request-7'].map(omitted), [0, 0, 0]);
  const manifest = id => events.find(event => event.type === 'context-manifest' && event.request_id === id);
  for (const [previous, next] of [[5, 6], [6, 7]]) {
    assert.equal(manifest(`request-${next}`).reused_prefix_parts, manifest(`request-${previous}`).part_count);
    assert.equal(JSON.stringify(payloads[next - 1].messages.slice(0, payloads[previous - 1].messages.length)),
      JSON.stringify(payloads[previous - 1].messages));
  }
});

test('a cut briefing is bounded: recent articles as leads and recent standalone facts as index lines', () => {
  // Delivered order is not recency: the first three articles are the most recently confirmed.
  const articles = Array.from({length:CUT_BRIEFING_ARTICLES + 3}, (_, n) => article(`article-${n}`, {title:`Article ${n}`,
    lead:`Lead ${n}. More detail.`, body:[{text:`Claim ${n}.`, facts:[`filed-${n}`]}],
    last_confirmed:position(n < 3 ? 10_000 + n : n)}));
  const filed = articles.map((_, n) => fact(`filed-${n}`, {text:`Claim ${n}.`, cited_by_articles:[`article-${n}`], seen:position(n)}));
  const store = count => ({...knowledge(), articles, facts:[...filed, ...Array.from({length:count}, (_, n) =>
    fact(`fact-${n}`, {subject:`Fact ${n}`, text:`Standalone claim ${n}. Detail.`, seen:position(n)}))]});
  const small = cutBriefing(store(CUT_BRIEFING_FACTS + 5));
  const data = JSON.parse(small.text.split('\n')[1]);
  const kept = [2, 1, 0, ...Array.from({length:CUT_BRIEFING_ARTICLES - 3}, (_, n) => CUT_BRIEFING_ARTICLES + 2 - n)].map(n => `article-${n}`);
  assert.deepEqual([small.kind, small.article_ids, data.leads.map(lead => lead.id)],
    ['briefing', kept, kept]);
  assert.deepEqual(data.leads[0], {id:'article-2', title:'Article 2', lead:'Lead 2. More detail.'});
  const recent = Array.from({length:CUT_BRIEFING_FACTS}, (_, n) => `fact-${CUT_BRIEFING_FACTS + 4 - n}`);
  assert.deepEqual([small.index_ids, data.index[0], data.unlisted_entries],
    [recent, {id:'fact-28', title:'Fact 28', index:'Standalone claim 28'}, 3 + 5]);
  const large = cutBriefing(store(5_000));
  assert.equal(JSON.parse(large.text.split('\n')[1]).unlisted_entries, 3 + 5_000 - CUT_BRIEFING_FACTS);
  assert.ok(large.text.length < small.text.length * 1.1, 'the briefing does not grow with the store');
});

test('a cut briefing stays within its serialized size cap however long the entries are', () => {
  const payload = briefing => JSON.parse(briefing.text.split('\n')[1]);
  const size = briefing => briefing.text.split('\n')[1].length;
  const huge = 100_000;
  // Five valid articles with 100 KB leads, the newest titled too long to fit even clipped, and thirty standalone
  // facts of 100 KB with no sentence break, so their index lines are 100 KB before clipping.
  const articles = Array.from({length:5}, (_, n) => article(`article-${n}`, {title:n === 4 ? 'T'.repeat(CUT_BRIEFING_CHARS) : `Article ${n}`,
    lead:'L'.repeat(huge), body:[{text:`Claim ${n}.`, facts:[`filed-${n}`]}], last_confirmed:position(n)}));
  const filed = articles.map((_, n) => fact(`filed-${n}`, {text:`Claim ${n}.`, cited_by_articles:[`article-${n}`], seen:position(n)}));
  const standalone = Array.from({length:30}, (_, n) => fact(`fact-${n}`, {subject:`Fact ${n}`, text:'F'.repeat(huge), seen:position(n)}));
  const store = {...knowledge(), articles, facts:[...filed, ...standalone]};
  assert.ok(JSON.stringify(store).length > 30 * huge, 'the store itself is megabytes');
  const bounded = cutBriefing(store), data = payload(bounded);
  assert.ok(size(bounded) <= CUT_BRIEFING_CHARS, `payload ${size(bounded)} chars`);
  assert.deepEqual(data.leads.map(lead => lead.id), ['article-4', 'article-3', 'article-2', 'article-1', 'article-0']);
  for (const row of [...data.leads.map(lead => lead.lead), ...data.index.map(row => row.index)]) {
    assert.equal(row.length, CUT_BRIEFING_SNIPPET_CHARS);
    assert.ok(row.endsWith('…'));
  }
  // The newest facts fill what is left; every article and fact not shown is counted.
  const listed = data.index.map(row => row.id);
  assert.ok(listed.length > 0 && listed.length < CUT_BRIEFING_FACTS, `${listed.length} index lines`);
  assert.deepEqual(listed, Array.from({length:listed.length}, (_, n) => `fact-${29 - n}`));
  assert.equal(data.unlisted_entries, 5 + 30 - data.leads.length - listed.length);
  assert.deepEqual([bounded.article_ids, bounded.index_ids], [data.leads.map(lead => lead.id), listed]);

  // Edge cases: an empty store and a store whose only article needs clipping are bounded too.
  const empty = cutBriefing({...knowledge(), articles:[], facts:[]});
  assert.deepEqual([payload(empty).leads, payload(empty).index, payload(empty).unlisted_entries], [[], [], 0]);
  const lone = cutBriefing({...knowledge(), articles:[articles[4]], facts:[filed[4]]});
  assert.ok(size(lone) <= CUT_BRIEFING_CHARS);
  assert.deepEqual([lone.article_ids, payload(lone).unlisted_entries], [['article-4'], 0]);
  assert.ok(payload(lone).leads[0].title.endsWith('…'));
  const single = cutBriefing({...knowledge(), articles:[articles[0]], facts:[filed[0]]});
  assert.deepEqual([payload(single).leads.map(lead => lead.lead.length), payload(single).unlisted_entries],
    [[CUT_BRIEFING_SNIPPET_CHARS], 0]);
  const giantEnvelope = cutBriefing({...knowledge(),
    coverage:{schema:'curator-coverage/2', session:`s1${'0'.repeat(CUT_BRIEFING_CHARS)}`, actor:null, last_step:null},
    articles:[], facts:[]});
  assert.ok(size(giantEnvelope) <= CUT_BRIEFING_CHARS, `oversized coverage payload ${size(giantEnvelope)} chars`);
  assert.deepEqual([payload(giantEnvelope).coverage, payload(giantEnvelope).leads, payload(giantEnvelope).unlisted_entries],
    [null, [], 0]);
});

// Evidence gate 10 (cut and cache): the status markers are counted against the cap.
test('a cut briefing whose entries carry every status marker stays within its cap', () => {
  const flagged = {scope:{game:'example', world:null}, branch_relation:'unknown', lifecycle_state:'contested',
    unverified_branch:true, needs_review:true};
  const articles = Array.from({length:CUT_BRIEFING_ARTICLES + 8}, (_, n) => article(`article-${n}`, {...flagged,
    title:`Article ${n}`, lead:`${'L'.repeat(200)}.`, body:[{text:`Claim ${n}.`, facts:[`filed-${n}`]}], last_confirmed:position(n)}));
  const filed = articles.map((_, n) => fact(`filed-${n}`, {...flagged, cited_by_articles:[`article-${n}`], seen:position(n)}));
  const standalone = Array.from({length:CUT_BRIEFING_FACTS + 8}, (_, n) => fact(`fact-${n}`, {...flagged,
    subject:`Fact ${n}`, text:`${'F'.repeat(200)}.`, seen:position(n)}));
  const store = {...knowledge(), articles, facts:[...filed, ...standalone]};
  // Each fact is contested by a real peer of equal scope, and each article inherits `contested` from its fact.
  for (const group of [filed, standalone])
    for (let n = 0; n < group.length; n += 2) contest(store, group[n].id, group[n + 1].id);
  const bounded = cutBriefing(validateKnowledge(store));
  const text = bounded.text.split('\n')[1], data = JSON.parse(text);
  assert.ok(text.length <= CUT_BRIEFING_CHARS, `payload ${text.length} chars`);
  assert.ok(data.leads.length > 0 && data.index.length > 0 && data.unlisted_entries > 0, 'the cap, not the counts, bounds it');
  for (const entry of [...data.leads, ...data.index])
    assert.deepEqual(entry.status, ['contested', 'unverified_branch', 'needs_review']);
  // Without the markers the same store fits more entries: the cap counted the added bytes.
  const plain = cutBriefing(validateKnowledge({...knowledge(), articles:articles.map(a => article(a.id, {...a, ...flaggedOff})),
    facts:[...filed, ...standalone].map(f => fact(f.id, {...f, ...flaggedOff}))}));
  const plainData = JSON.parse(plain.text.split('\n')[1]);
  assert.ok(plainData.unlisted_entries < data.unlisted_entries);
  assert.ok([...plainData.leads, ...plainData.index].every(entry => !Object.hasOwn(entry, 'status')));
});
const flaggedOff = {scope:{game:'example'}, branch_relation:null, lifecycle_state:'active', unverified_branch:false,
  needs_review:false, links:[], backlinks:[], contradicted_by:[]};

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
    return n === 5 ? reply() : observe(n, 1, 2500);
  }, {maxImages:1});
  assert.deepEqual(cutEvents(events).map(event => [event.request_id, event.outcome, event.reason, event.covered_through_operation_id]),
    [['request-3', 'cut', undefined, operationId(1)]]);
  assert.equal(markerText(payloads[4]), markerText(payloads[2]));
});

test('a clipped update can join a cut and use the verified coverage for the adopted version', async t => {
  const {events, payloads} = await play(t, async (n, {dir, publish}) => {
    if (n === 3) {
      const huge = knowledge();
      huge.articles[0].lead = 'x'.repeat(600_000);
      await listUpdate(dir, huge);
      await publish(publication(1), publication(2, 'v2'), {...publication(2), session:actorId},
        {...publication(2), actor_id:sessionId});
    }
    return n === 4 ? reply() : observe(n, 1, 9000);
  });
  assert.ok(!events.some(event => event.type === 'knowledge-delivery' && event.reason === 'invalid-entry'));
  const [cut] = cutEvents(events);
  assert.deepEqual([cut.request_id, cut.outcome, cut.knowledge_version, cut.covered_through_operation_id, cut.removed_turns],
    ['request-4', 'cut', 'v2', operationId(2), 2]);
  const marker = JSON.parse(markerText(payloads[3]).split('\n')[1]);
  assert.equal(marker.changes_since.article_changes[0].id, 'article-a');
  assert.ok(marker.changes_since.article_changes[0].lead.endsWith('…'));
  assert.equal(marker.uncovered_turns, 0);
  assert.equal(cut.uncovered_turns, 0);
});

test('cut markers diff from the previous briefing even after mid-segment delivery, and carry committed agenda', async t => {
  let agenda = applyAgendaTool(emptyAgenda(), {op:'upsert', id:'evidence', status:'active', title:'Carry evidence',
    refs:['fact-alone']}, new Set(['fact-alone'])).agenda;
  agenda = applyAgendaTool(agenda, {op:'upsert', id:'finished', status:'done', title:'Earlier work'}, new Set()).agenda;
  const v2 = knowledge('v2'), v3 = knowledge('v3');
  for (const value of [v2, v3]) {
    value.facts.pop();
    value.history.ended.push('fact-alone');
  }
  v3.articles[0].body[0].text = 'Changed claim under the same lead.';
  const {result, events, payloads} = await play(t, async (n, {dir, publish}) => {
    if (n === 1) { await listUpdate(dir, v2); await realDelay(1200); }
    if (n === 2) await publish(publication(1, 'v2'));
    if (n === 3) { await listUpdate(dir, v3); await publish(publication(2, 'v3')); }
    return n === 4 ? reply() : observe(n, 1, 4000);
  }, {agenda, maxImages:1});
  assert.deepEqual(events.filter(event => event.type === 'knowledge-delivery' && event.kind === 'update')
    .map(event => [event.outcome, event.previous_version, event.version]), [['delivered', 'v1', 'v2']]);
  const first = JSON.parse(markerText(payloads[2]).split('\n')[1]);
  const second = JSON.parse(markerText(payloads[3]).split('\n')[1]);
  assert.deepEqual([first.changes_since.from_version, first.changes_since.to_version], ['v1', 'v2']);
  assert.deepEqual(first.changes_since.corrections, [{old_id:'fact-alone', reason:'ended', by:[], affects_agenda:true}]);
  assert.deepEqual([first.agenda.cut_count, first.agenda.threads.length], [1, 2]);
  assert.deepEqual([second.changes_since.from_version, second.changes_since.to_version], ['v2', 'v3']);
  assert.equal(second.changes_since.claim_updates[0].text, 'Changed claim under the same lead.');
  assert.equal(second.changes_since.corrections, undefined);
  assert.deepEqual([second.agenda.cut_count, second.agenda.threads.map(thread => thread.id)], [2, ['evidence']]);
  assert.deepEqual(result.agenda.threads.map(thread => thread.id), ['evidence']);
  assert.ok(!payloads[2].messages.some(message => messageText(message).startsWith('BEGIN FALLIBLE KNOWLEDGE UPDATE')));
  assert.deepEqual(cutEvents(events).map(event => event.uncovered_turns), [0, 0]);
});

test('cut leaves an earlier agenda-related ending visible when the replacement omits it, then retires it on the next cut', async t => {
  const agenda = applyAgendaTool(emptyAgenda(), {op:'upsert', id:'evidence', status:'active', title:'Carry evidence',
    refs:['fact-alone']}, new Set(['fact-alone'])).agenda;
  const v2 = knowledge('v2'), v3 = knowledge('v3'), v4 = knowledge('v4');
  v2.facts.pop();
  v2.history.ended = ['fact-alone'];
  v4.articles[0].lead = 'Updated lead for cut two.';
  const {payloads} = await play(t, async (n, {dir, publish}) => {
    if (n === 1) { await listUpdate(dir, v2); await realDelay(1200); }
    if (n === 2) { await listUpdate(dir, v3); await publish(publication(1, 'v3')); }
    if (n === 3) { await listUpdate(dir, v4); await publish(publication(2, 'v4')); }
    return n === 4 ? reply() : observe(n, 1, 4000);
  }, {agenda, maxImages:1});
  const marker1 = JSON.parse(markerText(payloads[2]).split('\n')[1]);
  assert.equal(marker1.changes_since, undefined);
  assert.ok(payloads[2].messages.some(message => messageText(message).startsWith('BEGIN FALLIBLE KNOWLEDGE UPDATE (v2)')));
  assert.ok(!payloads[3].messages.some(message => messageText(message).startsWith('BEGIN FALLIBLE KNOWLEDGE UPDATE (v2)')));
});

test('strict-fit rescue still succeeds when a carried agenda is already at the exact 3072-byte ceiling', async t => {
  const threads = Array.from({length:6}, (_, i) => ({
    id:`t-${i}`, status:'active', title:'x'.repeat(120), notes:'y'.repeat(240), created_at_cut:0, updated_at_cut:0,
  }));
  const base = {schema:'player-agenda-continuation/1', cut_count:9, threads:[...threads, {
    id:'pad', status:'active', title:'a', notes:'b', created_at_cut:0, updated_at_cut:0,
  }]};
  const extra = 3072 - Buffer.byteLength(JSON.stringify(base));
  assert.ok(extra > 0 && extra < 240);
  base.threads[6].notes = 'b' + 'z'.repeat(extra);
  assert.equal(Buffer.byteLength(JSON.stringify(base)), 3072);
  const {result, events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 2) await publish(publication(1));
    return n === 3 ? reply() : observe(n, 1, n === 2 ? 98_000 : 16);
  }, {agenda:base, maxImages:12, contextCut:{low_mark:95_000, high_mark:99_900, min_free:10}});
  assert.equal(result.ok, true);
  assert.deepEqual(cutEvents(events).map(event => [event.outcome, event.cut_result]), [['cut', 'rescue']]);
  assert.equal(result.agenda.cut_count, 9);
  assert.ok(markerText(payloads[2]));
});

test('an accepted orderly stop fences new cuts and remains visible after an earlier cut', async t => {
  const command = {schema:'player-control/1', type:'orderly_stop', id:'c'.repeat(32), session:sessionId, actor_id:actorId};
  const {events, payloads, result} = await play(t, async (n, {publish}) => {
    if (n === 2) await publish(publication(1));
    if (n === 3) await publish(publication(2));
    return n === 4 ? reply(null, [['player_finish', {disposition:'external_stop_complete', report:'Stopped',
      source_ids:[], control_id:command.id}]]) : observe(n, 1, 2500);
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
    return observe(n, 1, [3, 4, 5].includes(n) ? 95_000 : 16);
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
  const result = await runHost({configuration, knowledge:knowledge('v1'), knowledgeUpdates:list,
    session:sessionId, actorId, pendingControlId:null, control:new PassThrough(), finishReserveUsd:'0',
    context:'Frozen player guide', prompt:'Offline mission', model:model.id, effort:'off', timeoutSeconds:15,
    env:{OFFLINE_TEST_KEY:'fixture-only'}, mcpConfig:{command:process.execPath, args:[], cwd:dir,
      enabled:true, required:true, enabled_tools:['computer_observe'], startup_timeout_sec:2, tool_timeout_sec:2},
    fetch:async (_url, init) => {
      const payload = JSON.parse(init.body);
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
  const marker12 = JSON.parse(markerText(payloads[11]).split('\n')[1]);
  assert.deepEqual([marker12.source_id_prefix, marker12.source_ids], [`${sessionId}-`, ['1..10']]);
});

test('handoff succeeds after a cut and cut briefing emits knowledge-undelivered if spend stops before fetch', async t => {
  const dir = await mkdtemp(join(tmpdir(), 'player-context-cut-handoff-'));
  t.after(() => rm(dir, {recursive:true, force:true}));
  const actor = join(dir, 'actors', '001'), list = join(actor, 'knowledge-updates.jsonl');
  await mkdir(actor, {recursive:true});
  const configuration = {...route(), context_cut:imageCut, max_context_images:1};
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
  const result = await runHost({configuration, knowledge:knowledge('v1'), knowledgeUpdates:list,
    session:sessionId, actorId, pendingControlId:null, control:new PassThrough(), finishReserveUsd:'0',
    context:'Frozen player guide', prompt:'Offline mission', model:model.id, effort:'off', timeoutSeconds:15,
    env:{OFFLINE_TEST_KEY:'fixture-only'}, mcpConfig:{command:process.execPath, args:[], cwd:dir,
      enabled:true, required:true, enabled_tools:['computer_observe', 'player_handoff'], startup_timeout_sec:2, tool_timeout_sec:2},
    fetch:async (_url, init) => {
      const payload = JSON.parse(init.body);
      reqs++;
      if (reqs === 2) { await appendFile(list, JSON.stringify(publication(1)) + '\n'); await realDelay(1200); }
      return reqs === 3 ? reply(null, [['player_handoff', {}]]) : observe(reqs, 1, 2500);
    }, onEvent:event => events.push(event)});
  assert.deepEqual([result.ok, result.reason], [true, 'handoff']);
  assert.deepEqual(cutEvents(events).map(c => [c.request_id, c.outcome]), [['request-3', 'cut']]);
  assert.ok(events.some(e => e.type === 'handoff' && e.handoff_id === handoffOp));

  // Verify an unplaced cut briefing when the spend limit stops the next fetch.
  const dir2 = await mkdtemp(join(tmpdir(), 'player-context-cut-undelivered-'));
  t.after(() => rm(dir2, {recursive:true, force:true}));
  const actor2 = join(dir2, 'actors', '001'), list2 = join(actor2, 'knowledge-updates.jsonl');
  await mkdir(actor2, {recursive:true});
  const config2 = {...route(), spend_limit_usd:'0.002', unpriced_request_usd:'0.001', context_cut:imageCut, max_context_images:1};
  operations = 0;
  const events2 = [];
  let reqs2 = 0;
  const res2 = await runHost({configuration:config2, knowledge:knowledge('v1'), knowledgeUpdates:list2,
    session:sessionId, actorId, pendingControlId:null, control:new PassThrough(), finishReserveUsd:'0',
    context:'Frozen player guide', prompt:'Offline mission', model:model.id, effort:'off', timeoutSeconds:15,
    env:{OFFLINE_TEST_KEY:'fixture-only'}, mcpConfig:{command:process.execPath, args:[], cwd:dir2,
      enabled:true, required:true, enabled_tools:['computer_observe'], startup_timeout_sec:2, tool_timeout_sec:2},
    fetch:async (_url, init) => {
      const payload = JSON.parse(init.body);
      reqs2++;
      if (reqs2 === 2) { await appendFile(list2, JSON.stringify(publication(1)) + '\n'); await realDelay(1200); }
      return reply(null, [['computer_observe', {}]], {...usage(2500), cost:reqs2 === 2 ? 0.002 : 0.0005});
    }, onEvent:event => events2.push(event)});
  assert.deepEqual([res2.ok, res2.reason], [false, 'spend-limit']);
  assert.ok(events2.some(e => e.type === 'context-cut' && e.outcome === 'cut' && e.request_id === 'request-3'));
  assert.ok(events2.some(e => e.type === 'knowledge-undelivered' && e.kind === 'briefing' && e.reason === 'actor-ended'));
});

test('strict-fit rescue cuts a covered turn below min_free and independent of high_mark', async t => {
  const {events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 2) await publish(publication(1));
    return n === 3 ? reply() : observe(n, 1, n === 2 ? 98_000 : 16);
  }, {maxImages:12, contextCut:{low_mark:95_000, high_mark:99_900, min_free:10}});
  const [cut] = cutEvents(events);
  assert.deepEqual([cut.request_id, cut.outcome, cut.cut_result, cut.triggers, cut.removed_turns],
    ['request-3', 'cut', 'rescue', [], 1]);
  assert.ok(cut.tokens_before + model.maxTokens >= model.contextWindow);
  assert.ok(cut.tokens_after + model.maxTokens < model.contextWindow && cut.tokens_after < cut.tokens_before);
  assert.ok(markerText(payloads[2]));
});

test('best effort cuts the largest fit prefix when no prefix reaches the low mark', async t => {
  const {events} = await play(t, async (n, {publish}) => {
    if (n === 4) await publish(publication(3));
    return n === 5 ? reply() : observe(n, 1, n >= 3 ? 8000 : 16);
  }, {maxImages:12, contextCut:{low_mark:1, high_mark:7000, min_free:2}});
  assert.deepEqual(cutEvents(events).map(event => [event.outcome, event.cut_result, event.removed_turns, event.covered_through_operation_id]),
    [['held-back', undefined, undefined, null], ['cut', 'best_effort', 3, operationId(3)]]);
  const cut = cutEvents(events).at(-1);
  assert.ok(cut.tokens_after - cut.briefing_tokens > 1);
  assert.ok(cut.tokens_after < cut.tokens_before);
});

test('cut markers accumulate distinct committed intents with the most recent occurrence last', async t => {
  const clipped = 'x'.repeat(158) + '😀' + 'tail';
  const intents = ['inspect', 'collect', 'inspect', clipped, 'plan', 'confirm', 'route', 'inspect'];
  const {payloads} = await play(t, async (n, {publish}) => {
    if (n === 5) await publish(publication(8));
    if (n === 9) await publish(publication(16));
    if (n === 10) return reply();
    const intent = intents[n - 1] ?? 'latest protected';
    return reply(null, [['computer_observe', {intent}], ['computer_observe', {intent:'malformed\nintent'}]],
      usage([5, 9].includes(n) ? 13_000 : 16), undefined, `turn-${n}`);
  }, {maxImages:30, contextCut:{low_mark:1, high_mark:12_000, min_free:2}});
  const markers = [payloads[5], payloads[9]].map(payload => JSON.parse(markerText(payload).split('\n')[1]));
  assert.deepEqual(markers.map(marker => marker.recent_intents), [
    ['collect', 'inspect', 'x'.repeat(158) + '…'],
    ['x'.repeat(158) + '…', 'plan', 'confirm', 'route', 'inspect'],
  ]);
});

test('tiered uncovered-cut fallback holds between high_mark and uncovered ceiling, cuts uncovered above ceiling, and heals when coverage catches up', async t => {
  // high_mark=20_000 -> uncoveredHighMark=ceil(20_000 * 5 / 3)=33_334.
  const agenda = applyAgendaTool(emptyAgenda(), {op:'upsert', id:'survive', status:'active', title:'Keep playing',
    refs:['fact-alone']}, new Set(['fact-alone'])).agenda;
  const {events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 6) await publish(publication(5));
    if (n === 7) return reply();
    // n=3 (request-4): 25_000 > high_mark but <= 33_334 -> holds back uncovered!
    // n=4 (request-5): 40_000 > 33_334 with 0 coverage -> tiered uncovered cut!
    // n=6 (request-7): coverage catches up through op 5, pressure 40_000 -> covered cut heals uncovered_turns to 0!
    const tok = n === 3 ? 25_000 : n === 4 ? 40_000 : n === 6 ? 40_000 : 16;
    return reply(null, [['computer_observe', {intent:`step-${n}`}]], usage(tok), undefined, `turn-${n}`);
  }, {agenda, maxImages:12, contextCut:{high_mark:20_000, low_mark:5_000, min_free:2}});
  const cuts = cutEvents(events);
  assert.deepEqual(cuts.map(c => [c.request_id, c.outcome, c.reason ?? c.cut_result, c.covered_through_operation_id, c.uncovered_turns]), [
    ['request-4', 'held-back', 'uncovered', null, undefined],
    ['request-5', 'cut', 'target', null, 2],
    ['request-7', 'cut', 'target', operationId(5), 0],
  ]);
  const uncovBanner = markerText(payloads[4]).split('\n');
  assert.ok(uncovBanner[0].includes('(some not yet curator-covered)'));
  const uncovData = JSON.parse(uncovBanner[1]);
  assert.deepEqual([uncovData.removed_turns, uncovData.uncovered_turns, uncovData.covered_through_operation_id,
    uncovData.source_id_prefix, uncovData.source_ids, uncovData.recent_intents, uncovData.agenda.threads.map(th => th.id)],
    [2, 2, null, `${sessionId}-`, ['1..2'], ['step-1', 'step-2'], ['survive']]);
  const healedBanner = markerText(payloads[6]).split('\n');
  assert.ok(healedBanner[0].includes('older curator-covered turns omitted'));
  assert.equal(JSON.parse(healedBanner[1]).uncovered_turns, 0);
});

test('hard-fit rescue drops uncovered turns when zero coverage exists instead of stopping on context-capacity', async t => {
  const {result, events, payloads} = await play(t, async n => {
    if (n === 3) return reply();
    return observe(n, 1, n === 2 ? 98_500 : 16);
  }, {maxImages:12, contextCut:{low_mark:95_000, high_mark:99_000, min_free:10}});
  assert.equal(result.ok, true);
  const [cut] = cutEvents(events);
  assert.deepEqual([cut.request_id, cut.outcome, cut.cut_result, cut.covered_through_operation_id, cut.removed_turns, cut.uncovered_turns],
    ['request-3', 'cut', 'rescue', null, 1, 1]);
  const marker = JSON.parse(markerText(payloads[2]).split('\n')[1]);
  assert.deepEqual([marker.removed_turns, marker.uncovered_turns, marker.covered_through_operation_id, marker.source_ids],
    [1, 1, null, [`${sessionId}-1`]]);
});

test('restore invalidation and orderly_stop still fence uncovered-cut fallback', async t => {
  const {events} = await play(t, async (n, {publish}) => {
    if (n === 2) await publish(restoration);
    if (n === 5) return reply();
    return observe(n, 1, n >= 3 ? 60_000 : 16);
  }, {maxImages:12, contextCut:{high_mark:20_000, low_mark:5_000, min_free:2}});
  assert.equal(cutEvents(events).length, 0);

  const command = {schema:'player-control/1', type:'orderly_stop', id:'c'.repeat(32), session:sessionId, actor_id:actorId};
  const {events:stopEvents, result} = await play(t, async n => {
    if (n === 4) return reply(null, [['player_finish', {disposition:'external_stop_complete', report:'Stopped',
      source_ids:[], control_id:command.id}]]);
    return observe(n, 1, n >= 3 ? 60_000 : 16);
  }, {maxImages:12, contextCut:{high_mark:20_000, low_mark:5_000, min_free:2}, onEvent:(event, control) => {
    if (event.type === 'tool-result' && event.request_id === 'request-2') control.write(JSON.stringify(command) + '\n');
  }});
  assert.equal(result.reason, 'external_stop_complete');
  assert.equal(cutEvents(stopEvents).length, 0);
});
