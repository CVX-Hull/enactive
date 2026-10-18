/* Execute the production viewer against delayed image decoding, without a browser dependency. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const elements = new Map();
function element(id) {
  if (elements.has(id)) return elements.get(id);
  const classes = new Set();
  const node = {id, value: '', dataset: {}, hidden: false, textContent: '',
    classList: {add: x => classes.add(x), toggle: (x, yes) => yes ? classes.add(x) : classes.delete(x), contains: x => classes.has(x)},
    replaceWith: other => elements.set(id, other), replaceChildren() {}, append() {}, addEventListener() {}};
  elements.set(id, node);
  return node;
}
const pending = [];
const requests = [];
const sendButtons = [element('action-send'), element('key-send'), element('walk-send')];
class DeferredImage {
  decode() { return new Promise((resolve, reject) => pending.push({resolve, reject})); }
  replaceWith(other) { elements.set('frame', other); }
}
const context = vm.createContext({Image: DeferredImage, document: {
  getElementById: element, querySelector: () => ({content: 'test-token'}),
  querySelectorAll: selector => selector === '.send' ? sendButtons : [], createElement: () => element(Symbol()), activeElement: null
}, fetch: (url, options) => new Promise((resolve, reject) => requests.push({url, options, resolve, reject})), setTimeout() {}});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8'), context);
const run = source => vm.runInContext(source, context);
function render(revision, frame, changes = {}) {
  context.input = {connection: 'fresh', age_ms: 0, pause_requested: false, frozen: false,
    latency_ms: 10, goal: '', events: [], state: {protocol: 3, boundary: {kind: 'normal_play', id: 'b-normal', control_generation: 0, recovery_operations: [], interrupt_request_id: null}, timestamp_ms: Date.now(), session: 'test', revision, frame,
      frame_ok: true, status: 'ready', actions: [], ...changes}};
  run('render(input)');
}
const tick = () => new Promise(setImmediate);
function boundary(kind, generation = 1, owner = null) {
  return {kind, id: `boundary-${kind}-${generation}`, control_generation: generation,
    recovery_operations: {activity_poll: ['request_interrupt'], interrupt_confirmation: ['answer_interrupt'],
      debug_prompt: ['continue_debug_once']}[kind] || [], interrupt_request_id: owner};
}
function request(url, kind) {
  const index = requests.findIndex(item => item.url === url && (!kind || JSON.parse(item.options.body).kind === kind));
  assert.notEqual(index, -1, `Missing request ${url} ${kind || ''}`);
  return requests.splice(index, 1)[0];
}
async function reply(item, result, ok = true) { item.resolve({ok, status: ok ? 200 : 409, json: async () => result}); await tick(); }
async function statusReply() { await reply(request('/api/status'), context.input); }
async function decode() { pending.shift().resolve(); await new Promise(setImmediate); }
(async () => {
  render(1, 'frame-1-1-1.png');
  assert.throws(() => run('authority()'), /Wait for/);
  await decode();
  assert.equal(run('authority().expected_revision'), 1);
  element('key').value = 'x';
  render(2, 'frame-1-1-2.png');
  assert.throws(() => run('authority()'), /Wait for/);
  await decode();
  assert.equal(element('key').value, '');
  assert.equal(run('authority().expected_revision'), 2);

  context.input.run_lease = {task_id: 'task', execution_epoch: 0, owner: 'waypoint player', session: 'test'};
  run('render(input)');
  assert.match(element('control-state').textContent, /RUN OWNED.*waypoint player/);
  assert.ok(sendButtons.every(button => button.disabled));
  assert.equal(element('resume').disabled, true);
  assert.equal(element('observe').disabled, false);
  assert.equal(element('pause').disabled, false);
  const countBeforeLeaseInput = requests.length;
  for (const kind of ['action', 'key', 'walk', 'resume']) await run(`command('${kind}')`);
  assert.equal(requests.length, countBeforeLeaseInput, 'leased viewer must not submit ordinary input');
  assert.match(element('error').textContent, /Pause to take over/);
  context.input.run_lease = null;
  context.input.pause_requested = true;
  run('render(input)');
  assert.equal(element('control-state').textContent, 'PAUSED');
  assert.ok(sendButtons.every(button => button.disabled), 'revoked lease does not imply resumed input');
  context.input.pause_requested = false;
  run('render(input)');

  render(3, 'frame-1-1-3.png');
  render(4, 'frame-1-1-3.png', {status: 'dispatched', frame_ok: false});
  await decode();
  assert.throws(() => run('authority()'), /Wait for/);
  assert.equal(element('frame-shell').classList.contains('stale'), true);
  assert.match(element('frame-note').textContent, /DISPATCHED/);

  render(5, 'frame-1-1-5.png');
  render(6, 'frame-1-1-6.png');
  await decode(); // Obsolete image may not replace the last displayed frame.
  assert.equal(run('displayed.revision'), 3);
  await decode();
  assert.equal(run('authority().expected_revision'), 6);
  for (const kind of ['activity_poll', 'debug_prompt', 'unsupported', 'interrupt_confirmation']) {
    render(7, `frame-${kind}.png`, {boundary: {kind}});
    await decode();
    assert.throws(() => run('authority()'), /native control/);
    assert.match(element('category').textContent, new RegExp(kind.replaceAll('_', ' ').toUpperCase()));
  }
  render(8, 'frame-menu.png', {boundary: {kind: 'menu'}});
  await decode();
  assert.equal(run('authority().expected_revision'), 8);
  render(9, 'frame-old.png', {protocol: 2});
  await decode();
  assert.throws(() => run('authority()'), /native control/);
  // Same revision/frame cannot transfer boundary or generation authority after native takeover.
  const activity = boundary('activity_poll');
  render(10, 'activity.png', {boundary: activity});
  assert.equal(element('recovery-interrupt').hidden, true);
  await decode();
  assert.equal(element('recovery-interrupt').disabled, false);
  assert.equal(run('JSON.stringify(recoveryAuthority("request_interrupt"))'),
    JSON.stringify({expected_session: 'test', expected_control_generation: 1}));
  for (const change of [{boundary: {...activity, id: 'another'}},
    {boundary: {...activity, control_generation: 2}}, {session: 'another-session'},
    {frame_ok: false}, {timestamp_ms: Date.now() - 4000}]) {
    render(10, 'activity.png', {boundary: activity, ...change});
    assert.throws(() => run('recoveryAuthority("request_interrupt")'), /current recovery frame/);
    assert.equal(element('recovery-interrupt').hidden, true);
    assert.doesNotMatch(element('frame-note').textContent, /^FRESH/);
  }

  render(11, 'bad-decode.png', {boundary: activity});
  pending.shift().reject(new Error('bad PNG'));
  await tick();
  assert.equal(element('recovery-interrupt').hidden, true);
  assert.match(element('error').textContent, /could not be loaded/);
  render(11, 'bad-decode.png', {boundary: activity});
  assert.match(element('error').textContent, /could not be loaded/);
  await decode();

  // An old successful decode after takeover cannot authorize a recovery.
  render(12, 'old-decode.png', {boundary: activity});
  render(12, 'old-decode.png', {boundary: boundary('activity_poll', 2)});
  await decode();
  assert.equal(element('recovery-interrupt').hidden, true);
  render(12, 'takeover.png', {boundary: boundary('activity_poll', 2)});
  await decode();
  assert.equal(element('recovery-interrupt').disabled, false);

  render(13, 'question.png', {boundary: boundary('interrupt_confirmation', 3, 'interrupt-owner')});
  await decode();
  assert.equal(element('recovery-yes').hidden, false);
  const answer = JSON.parse(run('JSON.stringify(recoveryAuthority("answer_interrupt", "YES"))'));
  assert.deepEqual(answer, {expected_session: 'test', expected_control_generation: 3,
    expected_boundary_id: 'boundary-interrupt_confirmation-3', expected_revision: 13,
    expected_frame: 'question.png', interrupt_request_id: 'interrupt-owner', choice: 'YES'});
  render(13, 'question.png', {boundary: boundary('interrupt_confirmation', 3, 'different-owner')});
  assert.throws(() => run('recoveryAuthority("answer_interrupt", "YES")'), /current recovery frame/);
  render(14, 'generic-yesno.png', {boundary: boundary('menu', 4)});
  await decode();
  assert.equal(element('recovery-yes').hidden, true);
  render(15, 'unowned.png', {boundary: boundary('interrupt_confirmation', 4)});
  await decode();
  assert.equal(element('recovery-yes').hidden, true);
  render(16, 'no-advertisement.png', {boundary: {...activity, recovery_operations: []}});
  await decode();
  assert.equal(element('recovery-interrupt').hidden, true);

  // Recovery and Pause can run while the ordinary command promise is unresolved.
  requests.length = 0; // Initial poll is deliberately unresolved in this fixture.
  render(17, 'normal-before-activity.png');
  await decode();
  run('void command("key", {key: "x", ...authority()})');
  const ordinary = request('/api/command', 'key');
  assert.equal(run('gameplayBusy'), true);
  render(18, 'active-pending.png', {boundary: activity});
  context.input.pending = {id: 'gameplay-id'};
  context.input.unknown_outcomes = [{status: 'unknown', request: {id: 'old-gameplay'}}];
  run('render(input)');
  await decode();
  assert.equal(element('recovery-interrupt').disabled, false);
  run('void recover("request_interrupt")');
  const recoveryRequest = request('/api/recovery', 'request_interrupt');
  assert.deepEqual(JSON.parse(recoveryRequest.options.body), {kind: 'request_interrupt',
    expected_session: 'test', expected_control_generation: 1});
  assert.equal(run('gameplayBusy && recoveryBusy'), true);
  assert.equal(element('pause').disabled, false);
  assert.equal(element('observe').disabled, false);
  await run('recover("request_interrupt")');
  assert.equal(requests.filter(item => item.url === '/api/recovery').length, 0);
  run('void command("pause")');
  const pause = request('/api/command', 'pause');
  await reply(pause, {status: 'pause_requested'});
  await statusReply();
  assert.equal(run('gameplayBusy && recoveryBusy'), true);
  const unknown = {status: 'unknown', id: 'control-id', error: 'Delivery unknown', retirement: 'claimed'};
  context.input.control_pending = {id: 'control-id'};
  context.input.control_unknown_outcomes = [{request: {id: 'control-id'}, status: 'unknown'}];
  await reply(recoveryRequest, unknown, false);
  await statusReply();
  assert.deepEqual(JSON.parse(element('recovery-result').textContent), unknown);
  assert.match(element('error').textContent, /Delivery unknown/);
  assert.match(element('gameplay-evidence').textContent, /gameplay-id/);
  assert.match(element('recovery-evidence').textContent, /control-id/);
  assert.match(element('gameplay-pending').textContent, /1 retained unknown/);
  assert.match(element('recovery-pending').textContent, /1 retained unknown/);
  assert.equal(element('observe').disabled, false);
  assert.equal(element('pause').disabled, false);

  // A fresh frame/passive status cannot clear unresolved control or resume play.
  render(19, 'pending-fresh.png', {boundary: activity});
  context.input.control_pending = {id: 'control-id'};
  run('render(input)');
  await decode();
  assert.equal(element('recovery-interrupt').disabled, true);
  assert.equal(element('resume').disabled, true);
  run('recoveryNeedsObserve = false'); // Simulate reload: durable server slot still blocks recovery.
  run('render(input)');
  assert.equal(element('recovery-interrupt').disabled, true);
  assert.throws(() => run('recoveryAuthority("request_interrupt")'), /unresolved/);
  run('recoveryNeedsObserve = true');
  context.input.control_pending = null;
  run('render(input)');
  assert.equal(element('recovery-interrupt').disabled, true);
  run('void command("observe")');
  const observe = request('/api/command', 'observe');
  await reply(observe, {status: 'ready'});
  await statusReply();
  assert.equal(element('recovery-interrupt').disabled, false);
  assert.equal(run('gameplayBusy'), true);
  await reply(ordinary, {status: 'unknown', id: 'gameplay-id', error: 'Original input unknown'}, false);
  await statusReply();
  assert.equal(run('gameplayBusy'), false);
  assert.deepEqual(JSON.parse(element('recovery-result').textContent), unknown);
  assert.match(element('error').textContent, /Original input unknown/);
  assert.match(element('error').textContent, /Delivery unknown/);
  assert.equal(requests.length, 0); // No automatic answer, retry, resume or observe.

  render(20, 'debug.png', {boundary: boundary('debug_prompt', 5)});
  await decode();
  const debug = JSON.parse(run('JSON.stringify(recoveryAuthority("continue_debug_once"))'));
  assert.equal(debug.expected_frame, 'debug.png');
  assert.equal(debug.expected_boundary_id, 'boundary-debug_prompt-5');
  assert.equal(element('recovery-debug').disabled, false);
  // An earlier Observe must not clear a newer recovery uncertainty.
  run('void command("observe")');
  const earlierObserve = request('/api/command', 'observe');
  // A lost response stays unknown until explicit observation, even if status reports no slot.
  run('void recover("continue_debug_once")');
  request('/api/recovery', 'continue_debug_once').reject(new Error('Connection lost'));
  await tick();
  await statusReply();
  assert.equal(run('recoveryNeedsObserve'), true);
  assert.match(element('recovery-result').textContent, /unknown/);
  assert.equal(element('pause').disabled, false);
  assert.equal(requests.length, 0);
  await reply(earlierObserve, {status: 'ready'});
  await statusReply();
  assert.equal(run('recoveryNeedsObserve'), true);
  assert.equal(element('recovery-debug').disabled, true);
  // Reload reads the two channels from status rather than merging their identities.
  run('recoveryResult = null; recoveryNeedsObserve = false');
  context.input.pending = {id: 'restored-gameplay'};
  context.input.control_pending = {id: 'restored-control'};
  context.input.unknown_outcomes = [{status: 'unknown', request: {id: 'old-gameplay'}}];
  context.input.control_unknown_outcomes = [{status: 'unknown', request: {id: 'old-control'}}];
  context.input.events = [{timestamp_ms: Date.now(), request: {kind: 'continue_debug_once'}, outcome: unknown}];
  run('render(input)');
  assert.match(element('gameplay-evidence').textContent, /restored-gameplay/);
  assert.match(element('recovery-evidence').textContent, /restored-control/);
  assert.match(element('recovery-result').textContent, /Delivery unknown/);
  assert.equal(element('recovery-debug').disabled, true);
  console.log('Viewer regressions passed: exact decoded authority, takeover/owner/stale/capture guards, independent requests and Pause, explicit reconciliation and retained uncertainty.');
})().catch(error => { console.error(error); process.exitCode = 1; });
