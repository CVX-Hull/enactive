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
import { compactSourceIds, coverageEntry, cutBriefing, cutMarker, CUT_BRIEFING_ARTICLES, CUT_BRIEFING_CHARS,
  CUT_BRIEFING_FACTS, CUT_BRIEFING_SNIPPET_CHARS, validateKnowledge } from '../knowledge.mjs';
import { knowledge, listUpdate, recallReply } from './delivery-scenario.mjs';
import { actorId, article, fact, model, png, position, realDelay, reply, route, sessionId, usageRecord } from './host-scenario.mjs';

const tokenCut = {high_mark:20_000, low_mark:2_600, min_free:1};
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

async function play(t, playerFetch, {contextCut = imageCut, maxImages = 2, block = 1, onEvent} = {}) {
  const dir = await mkdtemp(join(tmpdir(), 'player-context-cut-'));
  t.after(() => rm(dir, {recursive:true, force:true}));
  const actor = join(dir, 'actors', '001'), list = join(actor, 'knowledge-updates.jsonl');
  await mkdir(actor, {recursive:true});
  const configuration = {...route(), context_cut:contextCut, max_context_images:maxImages, context_image_block:block};
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

test('a high-mark cut delivers a bounded briefing, clears stale usage and warning, and keeps the new prefix stable', async t => {
  const {events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 4) await publish(publication(3));
    if (n >= 7) return reply();
    return observe(n, 1, [3, 4].includes(n) ? 97_000 : n === 5 ? 12_345 : 16);
  }, {contextCut:tokenCut, maxImages:12});
  const start = events.find(event => event.type === 'host-start');
  assert.deepEqual([start.schema, start.telemetry_version, start.context_cut], ['player-host/11', 11, tokenCut]);
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
      knowledge_version:'v1', source_id_prefix:`${sessionId}-`, source_ids:['1..3']}),
    'END CONTEXT CUT',
    'To inspect any omitted frame again, read its source_id (combining any source_id_prefix and expanding any start..end range) with player_source.',
  ]);
  const briefings = events.filter(event => event.type === 'knowledge-delivery' && event.kind === 'briefing');
  assert.deepEqual(briefings.map(event => [event.receiving_player_request_id, event.recall_request_id, event.article_ids, event.index_ids]),
    [['request-1', 'recall-1', ['article-a'], ['article-b', 'fact-alone']], ['request-5', null, ['article-a', 'article-b'], ['fact-alone']]]);
  const briefing = briefings.at(-1);
  const data = JSON.parse(briefing.text.split('\n')[1]);
  assert.deepEqual([data.leads.map(lead => lead.id), data.index, data.unlisted_entries],
    [['article-a', 'article-b'], [{id:'fact-alone', title:'Unfiled subject', index:'An unfiled claim'}], 0]);
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
  const marker5 = JSON.parse(markerText(payloads[4]).split('\n')[1]);
  assert.deepEqual([marker5.source_id_prefix, marker5.source_ids], [`${sessionId}-`, ['1..3']]);
});

test('the image trigger fires only at a new block eviction, so a cut replaces an eviction instead of following it', async t => {
  // Peak 3, block 2: the projection first omits two images at four (request-5), then four at six (request-7).
  const {events, payloads} = await play(t, async (n, {publish}) => {
    if (n === 5) await publish(publication(3));
    return n === 8 ? reply() : observe(n);
  }, {maxImages:3, block:2});
  assert.deepEqual(cutEvents(events).map(event => [event.request_id, event.outcome, event.reason, event.triggers]),
    [['request-5', 'held-back', 'uncovered', ['image_peak']], ['request-7', 'cut', undefined, ['image_peak']],
      ['request-8', 'held-back', 'uncovered', ['image_peak']]]);
  const omitted = id => events.find(event => event.type === 'context-image-projection' && event.request_id === id).omitted_images;
  assert.deepEqual(['request-4', 'request-5', 'request-6', 'request-7', 'request-8'].map(omitted), [0, 2, 2, 0, 2]);
  // Coverage that arrives between evictions waits for the next one: request-6 extends request-5 byte for byte.
  assert.equal(JSON.stringify(payloads[5].messages.slice(0, payloads[4].messages.length)), JSON.stringify(payloads[4].messages));
  const manifest = id => events.find(event => event.type === 'context-manifest' && event.request_id === id);
  assert.equal(manifest('request-6').reused_prefix_parts, manifest('request-5').part_count);
  const cut = cutEvents(events)[1];
  assert.deepEqual([cut.removed_turns, cut.images_before, cut.images_after], [3, 6, 3]);
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
  const kept = [0, 1, 2, ...Array.from({length:CUT_BRIEFING_ARTICLES - 3}, (_, n) => n + 6)].map(n => `article-${n}`);
  assert.deepEqual([small.kind, small.recall_request_id, small.article_ids, data.leads.map(lead => lead.id)],
    ['briefing', null, kept, kept]);
  assert.deepEqual(data.leads[0], {id:'article-0', title:'Article 0', lead:'Lead 0. More detail.'});
  const recent = Array.from({length:CUT_BRIEFING_FACTS}, (_, n) => `fact-${n + 5}`);
  assert.deepEqual([small.index_ids, data.index[0], data.unlisted_entries],
    [recent, {id:'fact-5', title:'Fact 5', index:'Standalone claim 5'}, 3 + 5]);
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
  assert.deepEqual(data.leads.map(lead => lead.id), ['article-0', 'article-1', 'article-2', 'article-3']);
  for (const row of [...data.leads.map(lead => lead.lead), ...data.index.map(row => row.index)]) {
    assert.equal(row.length, CUT_BRIEFING_SNIPPET_CHARS);
    assert.ok(row.endsWith('…'));
  }
  // The newest facts fill what is left; every article and fact not shown is counted.
  const listed = data.index.map(row => row.id);
  assert.ok(listed.length > 0 && listed.length < CUT_BRIEFING_FACTS, `${listed.length} index lines`);
  assert.deepEqual(listed, Array.from({length:listed.length}, (_, n) => `fact-${30 - listed.length + n}`));
  assert.equal(data.unlisted_entries, 5 + 30 - data.leads.length - listed.length);
  assert.deepEqual([bounded.article_ids, bounded.index_ids], [data.leads.map(lead => lead.id), listed]);

  // Edge cases: an empty store and a store whose only article cannot fit are bounded too.
  const empty = cutBriefing({...knowledge(), articles:[], facts:[]});
  assert.deepEqual([payload(empty).leads, payload(empty).index, payload(empty).unlisted_entries], [[], [], 0]);
  const lone = cutBriefing({...knowledge(), articles:[articles[4]], facts:[filed[4]]});
  assert.ok(size(lone) <= CUT_BRIEFING_CHARS);
  assert.deepEqual([payload(lone).leads, payload(lone).unlisted_entries], [[], 1]);
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
    unverified_branch:true, needs_review:true, condition_unverified:true};
  const articles = Array.from({length:CUT_BRIEFING_ARTICLES + 8}, (_, n) => article(`article-${n}`, {...flagged,
    title:`Article ${n}`, lead:`${'L'.repeat(200)}.`, body:[{text:`Claim ${n}.`, facts:[`filed-${n}`]}], last_confirmed:position(n)}));
  const filed = articles.map((_, n) => fact(`filed-${n}`, {...flagged, cited_by_articles:[`article-${n}`], seen:position(n)}));
  const standalone = Array.from({length:CUT_BRIEFING_FACTS + 8}, (_, n) => fact(`fact-${n}`, {...flagged,
    subject:`Fact ${n}`, text:`${'F'.repeat(200)}.`, seen:position(n)}));
  const bounded = cutBriefing(validateKnowledge({...knowledge(), articles, facts:[...filed, ...standalone]}));
  const text = bounded.text.split('\n')[1], data = JSON.parse(text);
  assert.ok(text.length <= CUT_BRIEFING_CHARS, `payload ${text.length} chars`);
  assert.ok(data.leads.length > 0 && data.index.length > 0 && data.unlisted_entries > 0, 'the cap, not the counts, bounds it');
  for (const entry of [...data.leads, ...data.index])
    assert.deepEqual(entry.status, ['contested', 'unverified_branch', 'needs_review', 'condition_unverified']);
  // Without the markers the same store fits more entries: the cap counted the added bytes.
  const plain = cutBriefing({...knowledge(), articles:articles.map(a => article(a.id, {...a, ...flaggedOff})),
    facts:[...filed, ...standalone].map(f => fact(f.id, {...f, ...flaggedOff}))});
  const plainData = JSON.parse(plain.text.split('\n')[1]);
  assert.ok(plainData.unlisted_entries < data.unlisted_entries);
  assert.ok([...plainData.leads, ...plainData.index].every(entry => !Object.hasOwn(entry, 'status')));
});
const flaggedOff = {scope:{game:'example'}, branch_relation:null, lifecycle_state:'active', unverified_branch:false,
  needs_review:false, condition_unverified:false};

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
  const marker12 = JSON.parse(markerText(payloads[11]).split('\n')[1]);
  assert.deepEqual([marker12.source_id_prefix, marker12.source_ids], [`${sessionId}-`, ['1..10']]);
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
