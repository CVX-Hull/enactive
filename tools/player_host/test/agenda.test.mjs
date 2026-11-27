import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { McpClient } from '@earendil-works/pi-mcp';
import { reply, realDelay } from './host-scenario.mjs';
import { deliveryScenario, knowledge, listUpdate } from './delivery-scenario.mjs';
import { AGENDA_SCHEMA, AGENDA_MAX_BYTES, AGENDA_CUT_HEADROOM, AGENDA_MAX_ACTIVE, AGENDA_MAX_THREADS, AGENDA_MAX_SUB_ITEMS,
  AGENDA_MAX_REFS, AGENDA_TOMBSTONE_CUTS, emptyAgenda, validateAgenda, advanceAgendaCut,
  agendaForPrompt, agendaQueryText, agendaRefSet, applyAgendaTool } from '../agenda.mjs';

const earned = new Set(['fact-one', 'live-1']);
const apply = (agenda, args) => applyAgendaTool(agenda, args, earned);
const thread = (id, status = 'active') => ({id, status, title:'Check progress', created_at_cut:0, updated_at_cut:0});
const add = (agenda, fields = {}) => apply(agenda, {op:'upsert', id:'task', status:'active', title:'Make progress', ...fields}).agenda;

test('the closed agenda enforces fields, Unicode code points, stamps, and active and total limits', () => {
  assert.deepEqual(emptyAgenda(), {schema:AGENDA_SCHEMA, cut_count:0, threads:[]});
  assert.equal(validateAgenda({...emptyAgenda(), threads:[{...thread('emoji'), title:'😀'.repeat(120)}]}).threads.length, 1);
  for (const edit of [
    {id:'bad\n'}, {title:' '}, {title:'😀'.repeat(121)}, {status:'unknown'}, {status:'dropped'},
    {created_at_cut:1}, {updated_at_cut:1}, {notes:' '.repeat(10)}, {stop_when:'x'.repeat(161)},
    {refs:['fact-one', 'fact-one']}, {refs:Array.from({length:AGENDA_MAX_REFS + 1}, (_, i) => String(i))},
    {sub_items:[{text:'Nested', done:false, sub_items:[]}]}, {sub_items:[{text:'Missing done'}]},
    {sub_items:Array.from({length:AGENDA_MAX_SUB_ITEMS + 1}, () => ({text:'Check', done:false}))}, {authority:true},
  ]) assert.throws(() => validateAgenda({...emptyAgenda(), threads:[{...thread('task'), ...edit}]}), /invalid-agenda/, JSON.stringify(edit));
  for (const cut_count of [-1, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(() => validateAgenda({...emptyAgenda(), cut_count}), /invalid-agenda/);
  }
  for (const [cap, status] of [[AGENDA_MAX_ACTIVE, 'paused'], [AGENDA_MAX_THREADS, 'done']]) {
    const threads = Array.from({length:cap}, (_, i) => thread(`task-${i}`,status));
    validateAgenda({...emptyAgenda(), threads});
    assert.throws(() => validateAgenda({...emptyAgenda(), threads:[...threads, thread('extra', status)]}), /invalid-agenda/);
  }
  assert.throws(() => validateAgenda({...emptyAgenda(), threads:[thread('task'), thread('task')]}), /invalid-agenda/);
});

test('writes are atomic, evidence grounded, and limited to 3072 UTF-8 bytes', () => {
  const before = add(emptyAgenda(), {refs:['fact-one'], stop_when:'When the player decides'});
  const saved = structuredClone(before);
  assert.throws(() => add(before, {refs:['invented']}), /unearned ref "invented"/);
  assert.throws(() => apply(before, {op:'upsert', id:'task', updated_at_cut:3}), /invalid-agenda/);
  assert.throws(() => apply(before, {op:'set_status', id:'unknown', status:'done'}), /invalid-agenda/);
  assert.throws(() => apply(before, {op:'read', title:'Extra'}), /invalid-agenda/);
  const large = {title:'😀'.repeat(120), notes:'😀'.repeat(240), stop_when:'😀'.repeat(160)};
  const one = add(before, large);
  const next = {op:'upsert', id:'next', status:'active', ...large};
  assert.throws(() => apply(one, next), new RegExp(String(AGENDA_MAX_BYTES)));
  const same = apply(before, {op:'read'});
  assert.equal(same.agenda, before);
  assert.equal(same.changed, false);
  assert.deepEqual(before, saved);
});

test('cuts stamp updates mechanically and retire tombstones after two cuts', () => {
  let agenda = add(emptyAgenda(), {refs:['fact-one'], notes:'first notes'});
  agenda = advanceAgendaCut(agenda);
  agenda = apply(agenda, {op:'set_status', id:'task', status:'dropped', drop_reason:'Player decided', sub_items:[{text:'Read', done:true}]}).agenda;
  agenda = add(agenda, {id:'keep', status:'paused', title:'Other approach', refs:['live-1']});
  assert.deepEqual(agenda.threads.map(row => [row.id, row.created_at_cut, row.updated_at_cut]), [['task',0,1], ['keep',1,1]]);
  assert.deepEqual([...agendaRefSet(agenda)], ['live-1']);
  assert.match(agendaQueryText(agenda), /Other approach/);
  assert.doesNotMatch(agendaQueryText(agenda), /first notes/);
  assert.equal(agendaForPrompt(agenda).threads[0].created_at_cut, undefined);
  for (let i = 1; i < AGENDA_TOMBSTONE_CUTS; i++) {
    agenda = advanceAgendaCut(agenda);
    assert.equal(agenda.threads.length, 2);
  }
  assert.deepEqual(apply(agenda, {op:'clear_completed'}).agenda.threads.map(thread => thread.id), ['keep']);
  agenda = advanceAgendaCut(agenda);
  assert.equal(agenda.cut_count, 1 + AGENDA_TOMBSTONE_CUTS);
  assert.deepEqual(agenda.threads.map(thread => thread.id), ['keep']);
});

async function deliveryDirectory(t) {
  const dir = await mkdtemp(join(tmpdir(), 'player-agenda-'));
  t.after(() => rm(dir, {recursive:true, force:true}));
  return dir;
}

test('host-local agenda earns evidence from delivered knowledge, carried state, and source read results', async t => {
  const agenda = applyAgendaTool(emptyAgenda(), {op:'upsert', id:'carried', status:'paused', title:'Earlier work',
    refs:['carried-1']}, new Set(['carried-1'])).agenda;
  t.mock.method(McpClient.prototype, 'connect', async () => {});
  t.mock.method(McpClient.prototype, 'close', async () => {});
  t.mock.method(McpClient.prototype, 'listTools', async () => [{name:'player_source',
    inputSchema:{type:'object', properties:{intent:{type:'string'}, source_id:{type:'string'}}}}]);
  t.mock.method(McpClient.prototype, 'callTool', async (_name, args) => {
    const status = args.source_id === 'observed-1' ? 'available' : 'unavailable';
    return {content:[{type:'text', text:JSON.stringify({schema:'player-source-read/2', status, source_id:args.source_id})}]};
  });
  const upsert = refs => ['player_agenda', {op:'upsert', id:'progress', title:'Keep the evidence', status:'active', refs}];
  const {result, events, payloads} = await deliveryScenario(await deliveryDirectory(t), {
    agenda, knowledge:knowledge(), enabledTools:['player_source'],
    playerFetch:n => n === 1 ? reply(null, [
      ['player_source', {source_id:'observed-1'}], ['player_source', {source_id:'unknown-1'}],
      upsert(['unknown-1']), upsert(['observed-1', 'carried-1', 'article-a', 'fact-b']),
    ]) : reply(),
  });
  assert.equal(result.ok, true);
  assert.deepEqual(result.agenda.threads.at(-1).refs, ['observed-1', 'carried-1', 'article-a', 'fact-b']);
  assert.equal(events.filter(event => event.type === 'player-agenda').length, 1);
  const refusal = payloads[1].messages.find(message => message.tool_call_id === 'call-2');
  assert.match(JSON.stringify(refusal.content), /unearned ref.*unknown-1/);
});

test('the MCP tool list cannot shadow player_agenda', async t => {
  t.mock.method(McpClient.prototype, 'connect', async () => {});
  t.mock.method(McpClient.prototype, 'close', async () => {});
  t.mock.method(McpClient.prototype, 'listTools', async () => ['observe','player_agenda'].map(name => ({
    name, inputSchema:{type:'object'},
  })));
  const {result, payloads} = await deliveryScenario(await deliveryDirectory(t), {enabledTools:['observe']});
  assert.equal(result.reason, 'missing-required-tools');
  assert.equal(payloads.length, 0);
});

test('tool writes reserve cut headroom so advanceAgendaCut never overflows across digit growth', () => {
  let agenda = {...emptyAgenda(), cut_count:999, threads:[]};
  for (let i = 0; i < 6; i++) {
    agenda = applyAgendaTool(agenda, {op:'upsert', id:`t-${i}`, status:'active', title:'x'.repeat(120),
      notes:'y'.repeat(240)}, new Set()).agenda;
  }
  const probe = {op:'upsert', id:'fit', status:'active', title:'a', notes:'b'};
  const baseBytes = Buffer.byteLength(JSON.stringify(applyAgendaTool(agenda, probe, new Set()).agenda));
  const fill = (AGENDA_MAX_BYTES - AGENDA_CUT_HEADROOM) - baseBytes;
  assert.ok(fill > 0 && fill < 240);
  const full = applyAgendaTool(agenda, {...probe, notes:'b' + 'z'.repeat(fill)}, new Set()).agenda;
  assert.equal(Buffer.byteLength(JSON.stringify(full)), AGENDA_MAX_BYTES - AGENDA_CUT_HEADROOM);
  assert.throws(() => applyAgendaTool(agenda, {...probe, notes:'b' + 'z'.repeat(fill + 1)}, new Set()),
    /tool headroom/);
  const advanced = advanceAgendaCut(full);
  assert.equal(advanced.cut_count, 1000);
  assert.ok(Buffer.byteLength(JSON.stringify(advanced)) <= AGENDA_MAX_BYTES);
});

test('host-local agenda and affects_agenda stay in live prompts and never leak into knowledge telemetry', async t => {
  const dir = await deliveryDirectory(t);
  const secretTitle = 'Secret agenda task title';
  const agenda = applyAgendaTool(emptyAgenda(), {op:'upsert', id:'secret-task', status:'active',
    title:secretTitle, refs:['fact-alone']}, new Set(['fact-alone'])).agenda;
  const v3 = knowledge('v3');
  v3.facts.pop();
  v3.history.ended = ['fact-alone'];
  const {result, events, payloads} = await deliveryScenario(dir, {
    agenda, knowledge:knowledge('v2'), knowledgeUpdates:true,
    playerFetch:async n => {
      if (n === 1) {
        await listUpdate(dir, v3);
        await realDelay(1200);
        return reply(null, [['computer_input', {actions:[{type:'key', key:'x', modifiers:[]}]}]]);
      }
      return reply();
    },
  });
  assert.equal(result.ok, true, result.reason);
  const textOf = content => typeof content === 'string'
    ? content
    : (content ?? []).filter(part => part.type === 'text').map(part => part.text).join('');
  const openingPrompt = textOf(payloads[0].messages[1].content);
  const [knowledgePart, agendaPart] = openingPrompt.split('BEGIN PLAYER AGENDA');
  assert.ok(agendaPart && agendaPart.includes(secretTitle), 'live opening prompt includes separate agenda block');
  assert.ok(!knowledgePart.includes(secretTitle), 'BEGIN FALLIBLE KNOWLEDGE never embeds agenda');
  const secondTexts = payloads[1].messages.map(message => textOf(message.content)).join('\n');
  assert.ok(secondTexts.includes('"affects_agenda":true'), 'live update marks agenda impact');
  const knowledgeEvents = events.filter(event => event.type === 'knowledge-delivery' || event.type === 'knowledge-undelivered');
  assert.equal(knowledgeEvents.length, 2);
  for (const event of knowledgeEvents) {
    const serialized = JSON.stringify(event);
    assert.ok(!serialized.includes(secretTitle), `agenda title leaked in ${event.kind}`);
    assert.ok(!serialized.includes('affects_agenda'), `affects_agenda leaked in ${event.kind}`);
  }
});
