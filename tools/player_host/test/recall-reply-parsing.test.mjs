// R-REGRESSION / R-OVERSPEND: reply-shape delivery,
// retained model text and exactly-once accounting through the actual host.
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { selection } from '../knowledge.mjs';
import { deliveryScenario, knowledge, recallReply, recallTextReply } from './delivery-scenario.mjs';
import { model } from './host-scenario.mjs';

async function scenario(t, options) {
  const dir = await mkdtemp(join(tmpdir(), 'recall-reply-parsing-'));
  t.after(() => rm(dir, {recursive:true, force:true}));
  const result = await deliveryScenario(dir, options);
  const starts = result.events.filter(e => e.type === 'request-start' && e.request_role === 'recall');
  for (const start of starts) {
    const completions = result.events.filter(e => e.type === 'response-complete' && e.request_id === start.request_id);
    assert.equal(completions.length, 1, `${start.request_id} completes once`);
    const recall = result.events.find(e => e.type === 'knowledge-recall' && e.request_id === start.request_id);
    assert.ok(result.events.indexOf(completions[0]) < result.events.indexOf(recall));
  }
  const costs = result.events.filter(e => e.type === 'response-complete');
  assert.equal(result.events.at(-1).requests, costs.length);
  assert.ok(Math.abs(Number(result.events.at(-1).spent_usd)
    - costs.reduce((sum, e) => sum + Number(e.counted_cost_usd), 0)) < 1e-12);
  return result;
}

const replyShapes = [
  {name:'json fence', text:'```json\n{"articles":["article-a"]}\n```', status:'selected'},
  {name:'sentence before object', text:'Here are the relevant articles:\n{"articles":["article-a"]}', detail:'not-json'},
  {name:'empty selection', text:'{"articles":[]}', status:'silence'},
  {name:'unknown id', text:'{"articles":["unknown-id"]}', detail:'unknown-entry'},
  {name:'two objects', text:'{"articles":[]}\n{"articles":["article-a"]}', detail:'not-json'},
  {name:'two fences', text:'```json\n{"articles":[]}\n```\n```json\n{"articles":[]}\n```', detail:'not-json'},
];

for (const shape of replyShapes) test(`host records and accounts for recall reply: ${shape.name}`, async t => {
  const {result, events} = await scenario(t, {recallFetch:n => n === 1 ? recallTextReply(shape.text) : recallReply(['article-b'])});
  assert.equal(result.ok, true);
  const event = events.find(e => e.type === 'knowledge-recall' && e.request_id === 'recall-1');
  assert.equal(event.status, shape.status ?? 'failure');
  assert.equal(event.reply_text, shape.text);
  assert.equal(event.reply_omitted_bytes, 0);
  if (shape.detail) {
    assert.equal(event.reason, 'invalid-recall-selection');
    assert.equal(event.selection_error, shape.detail);
    assert.ok(!Object.hasOwn(event, 'error_name'));
    const briefing = events.find(e => e.type === 'knowledge-delivery' && e.kind === 'briefing');
    assert.deepEqual(briefing.article_ids, []);
    assert.deepEqual(briefing.index_ids, ['article-a', 'article-b', 'fact-alone']);
  }
  assert.ok(events.some(e => e.type === 'request-start' && e.request_id === 'recall-2'), 'later reminder is requested');
  assert.ok(events.some(e => e.type === 'knowledge-recall' && e.kind === 'reminder' && e.status === 'selected'));
});

test('an invalid reminder delivers nothing and does not disable later reminders', async t => {
  const text = 'Relevant leads: {"articles":["article-b"]}';
  const {events} = await scenario(t, {recallFetch:n => n === 2 ? recallTextReply(text) : recallReply(['article-a'])});
  const failed = events.find(e => e.type === 'knowledge-recall' && e.request_id === 'recall-2');
  assert.equal(failed.selection_error, 'not-json');
  assert.equal(failed.reply_text, text);
  assert.ok(events.every(e => !(e.type === 'knowledge-delivery' && e.recall_request_id === 'recall-2')));
  assert.ok(events.some(e => e.type === 'knowledge-recall' && e.request_id === 'recall-3' && e.status === 'selected'));
});

for (const provider of ['fixture', 'openrouter']) test(`${provider} recall payload has the stable index prefix and provider-specific format`, async t => {
  const tags = ['fixture', 'fixture/secondary'];
  const endpoint_costs = provider === 'openrouter' ? Object.fromEntries(tags.map(tag => [tag, {...model.cost}])) : null;
  const routeModel = {...structuredClone(model), provider,
    ...(provider === 'openrouter' ? {baseUrl:'https://openrouter.ai/api/v1',
      compat:{...model.compat, openRouterRouting:{only:tags, order:[...tags], allow_fallbacks:false, require_parameters:true}}} : {})};
  const {result, payloads, events} = await scenario(t, {configuration:{model:routeModel, endpoint_costs,
    recall:{model:{...routeModel, id:'recall-fixture'}, every:1, unpriced_request_usd:'0.2',endpoint_costs}},
    recallFetch:n => recallTextReply('{"articles":["article-b"]}', .002, 'stop',
      n === 1 ? 'Secondary Endpoint' : n === 2 ? 'stand-in-only private provider' : undefined)});
  assert.equal(result.ok, true);
  const completions = events.filter(e => e.type === 'response-complete' && e.request_role === 'recall');
  assert.equal(completions[0].reported_provider, 'Secondary Endpoint');
  for (const completion of completions.slice(1)) assert.equal(completion.reported_provider, null);
  const recalls = payloads.filter(p => p.model === 'recall-fixture');
  assert.ok(recalls.length >= 2);
  // The stable prefix is the system prompt and a user message holding only the index; the request's kind,
  // its first message or recent calls and the latest screen follow in a second user message.
  const prefix = p => JSON.stringify(p.messages.slice(0, 2));
  for (const [i, payload] of recalls.entries()) {
    assert.deepEqual(payload.messages.map(m => m.role), ['system', 'user', 'user']);
    assert.equal(prefix(payload), prefix(recalls[0]), 'the cacheable prefix is byte-identical across recalls of one version');
    const [indexText, requestText] = payload.messages.slice(1).map(m => m.content.find(p => p.type === 'text').text);
    assert.deepEqual(Object.keys(JSON.parse(indexText)), ['index']);
    assert.equal(payload.messages[1].content.length, 1);
    assert.deepEqual(Object.keys(JSON.parse(requestText)), ['kind', i === 0 ? 'first_message' : 'recent_calls', 'already_in_context']);
  }
  assert.notEqual(JSON.stringify(recalls[0].messages[2]), JSON.stringify(recalls[1].messages[2]), 'only the request changes');
  assert.ok(recalls[0].messages[0].content.startsWith('Choose relevant leads'), 'the recall instructions reach the provider');
  for (const payload of recalls) {
    if (provider === 'openrouter') {
      assert.deepEqual(payload.provider, routeModel.compat.openRouterRouting);
      assert.deepEqual(payload.response_format, {type:'json_schema',
        json_schema:{name:'recall_selection', strict:true, schema:{type:'object',
          properties:{articles:{type:'array', items:{type:'string'}}}, required:['articles'], additionalProperties:false}}});
    }
    else assert.ok(!Object.hasOwn(payload, 'response_format'));
  }
  for (const payload of payloads.filter(p => p.model !== 'recall-fixture')) assert.ok(!Object.hasOwn(payload, 'response_format'));
});

test('recall telemetry bounds UTF-8 reply text without changing the parsed reply', async t => {
  const value = knowledge();
  value.articles[0].title = '😀';
  const text = ' '.repeat(8176) + JSON.stringify({articles:[value.articles[0].title]});
  const {events} = await scenario(t, {knowledge:value, recallFetch:() => recallTextReply(text)});
  const event = events.find(e => e.type === 'knowledge-recall' && e.request_id === 'recall-1');
  assert.equal(event.status, 'selected');
  assert.equal(Buffer.byteLength(event.reply_text), 8190);
  assert.equal(event.reply_text, text.slice(0, 8190));
  assert.equal(event.reply_omitted_bytes, Buffer.byteLength(text) - 8190);
  assert.ok(!event.reply_text.includes('\ufffd'));
});

test('unexpected selection errors retain their name and do not complete or charge twice', async t => {
  const value = knowledge();
  const {events} = await scenario(t, {knowledge:value, onEvent:event => {
    if (event.type === 'response-complete' && event.request_id === 'recall-1') {
      const lead = value.articles[0].lead;
      Object.defineProperty(value.articles[0], 'lead', {configurable:true, get() {
        Object.defineProperty(this, 'lead', {configurable:true, writable:true, value:lead});
        throw new TypeError('fixture selection failure');
      }});
    }
  }});
  const failure = events.find(e => e.type === 'knowledge-recall' && e.request_id === 'recall-1');
  assert.equal(failure.reason, 'recall-failed');
  assert.equal(failure.error_name, 'TypeError');
  assert.equal(failure.reply_text, '{"articles":["article-a"]}');
  assert.ok(!Object.hasOwn(failure, 'stack'));
  assert.equal(events.filter(e => e.type === 'request-start' && e.request_role === 'recall').length, 1);
});

test('selection joins text parts, ignores reasoning and accepts one untagged or json fence', () => {
  for (const text of [' {"articles":["article-a"]} \n', '```\n{"articles":["article-a"]}\n```',
    ' \n```json\r\n{"articles":["article-a"]}\r\n```\n ']) {
    const mid = Math.floor(text.length / 2);
    const message = {content:[{type:'text', text:text.slice(0, mid)}, {type:'thinking', thinking:'private'},
      {type:'text', text:text.slice(mid)}]};
    assert.deepEqual(selection(message, knowledge()).map(a => a.id), ['article-a']);
  }
});

test('an exact id selects its own entry even when another entry has that text as its title', () => {
  // R-REGRESSION (#946): the index was searched for id or title in one pass, so an earlier entry titled with a
  // later entry's id was selected in its place.
  const value = knowledge();
  value.articles[0].title = 'article-b';
  const pick = ids => selection({content:[{type:'text', text:JSON.stringify({articles:ids})}]}, value).map(a => a.id);
  assert.deepEqual(pick(['article-b']), ['article-b']);
  // A title still names its entry when no id matches it.
  assert.deepEqual(pick(['B subject']), ['article-b']);
});

test('invalid selections always expose the machine reason instead of a SyntaxError', () => {
  for (const [text, detail] of [
    ['', 'not-json'], ['{', 'not-json'], ['```js\n{"articles":[]}\n```', 'not-json'],
    ['```json\n{"articles":[]}\n```\nDone.', 'not-json'],
    ['[]', 'not-one-object'], ['null', 'not-one-object'], ['"text"', 'not-one-object'],
    ['{}', 'wrong-keys'], ['{"articles":null}', 'wrong-keys'], ['{"articles":[],"extra":true}', 'wrong-keys'],
    ['{"articles":["article-a","article-a"]}', 'repeated-entry'], ['{"articles":[42]}', 'unknown-entry'],
  ]) assert.throws(() => selection({content:[{type:'text', text}]}, knowledge()),
    {name:'Error', message:'invalid-recall-selection', detail});
});
