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
  // The read-only objective follows saved status, including while a draft is being edited.
  const objective = element('recorded-objective-text');
  Object.defineProperty(objective, 'innerHTML', {set() { assert.fail('Recorded objective must use textContent'); }});
  assert.equal(objective.textContent, 'No objective recorded.');
  const requestsBeforeObjective = requests.length;
  const savedGoal = 'Survive the first day.\nFind shelter and preserve supplies.';
  context.input.goal = savedGoal;
  run('render(input)');
  assert.equal(objective.textContent, savedGoal);
  assert.equal(element('goal').value, savedGoal);
  context.document.activeElement = element('goal');
  element('goal').value = 'Unsaved draft: explore instead';
  context.input.goal = 'Saved objective from a later status';
  run('render(input)');
  assert.equal(objective.textContent, context.input.goal);
  assert.equal(element('goal').value, 'Unsaved draft: explore instead');
  const untrustedGoal = '<img src=x onerror="fetch(\'/api/gameplay\')">\n<script>resume()</script> & "quoted"';
  context.input.goal = untrustedGoal;
  run('render(input)');
  assert.equal(objective.textContent, untrustedGoal, 'Markup must remain literal text');
  const longGoal = 'unbroken'.repeat(200) + '\nKeep every recorded line.';
  context.input.goal = longGoal;
  run('render(input)');
  assert.equal(objective.textContent, longGoal, 'Long objectives remain fully available');
  for (const emptyGoal of ['', '  \n\t', null, undefined]) {
    context.input.goal = emptyGoal;
    run('render(input)');
    assert.equal(objective.textContent, 'No objective recorded.');
  }
  assert.equal(requests.length, requestsBeforeObjective, 'Rendering objectives must not submit any request');
  assert.equal(run('authority().expected_revision'), 1, 'Recorded text cannot change frame authority');
  context.document.activeElement = null;
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
  // The task interface retains observed authority and exact run/epoch bindings.
  function taskSnapshot(state = 'planning', changes = {}) {
    return {run_id: 'run-exact', task: {task_id: 'task-exact', distance: 2, direction: 'east',
      origin: [0, 0, 0], target: [2, 0, 0], budgets: {primitives: 8}},
      run: {state, stage_id: 'outbound-stage', execution_epoch: 4, model_id: 'external-unreported',
        configuration_id: 'external-chat-v1', lease_owner: 'waypoint player', paused: false, fresh: true,
        progress: {verified_steps: 1, displacement: [1, 0, 0]}, next_check: 'Wait for a candidate, then revalidate',
        last_public_reason: 'Planning from retained public evidence', remaining_budgets: {primitives: 7},
        evidence: [{observation_id: 'observed-1', frame_path: 'retained/frame.png', frame_sha256: 'abc123'}], ...changes},
      planner: {kind: 'external_chat', pending_request_id: 'planning-exact', deadline_ms: Date.now() + 20000, usage_known: false},
      last_receipt: {logical_action_id: 'logical-1', native_request_id: 'native-1', disposition: 'returned', reason: 'Exact receipt'}};
  }
  run('recoveryNeedsObserve = false');
  render(30, 'task-start.png');
  element('task-direction').value = 'east';
  element('task-distance').value = '2';
  assert.equal(element('task-start').disabled, true, 'task start must await matching decoded frame');
  await decode();
  assert.equal(element('task-start').disabled, false);
  run('void gameplayCommand("start")');
  const startTask = request('/api/gameplay', 'start');
  assert.deepEqual(JSON.parse(startTask.options.body), {kind: 'start', direction: 'east', distance: 2,
    expected_session: 'test', expected_revision: 30});
  assert.equal(startTask.options.headers['X-CDDA-Token'], 'test-token');
  assert.equal(run('taskBusy'), true);
  assert.equal(element('task-start').disabled, true);
  assert.equal(element('pause').disabled, false);
  run('void command("pause")');
  await reply(request('/api/command', 'pause'), {status: 'pause_requested'});
  await statusReply();
  assert.equal(run('taskBusy'), true, 'Pause must not wait for the task request');
  context.input.gameplay = taskSnapshot();
  context.input.run_lease = {owner: 'waypoint player'};
  await reply(startTask, {status: 'accepted', gameplay: context.input.gameplay});
  await statusReply();
  assert.equal(element('task-state').textContent, 'PLANNING');
  assert.match(element('task-summary').textContent, /2 tile.*east.*return/);
  assert.match(element('task-player').textContent, /external-unreported.*waiting for candidate/);
  assert.match(element('task-executor').textContent, /waypoint player/);
  assert.match(element('task-progress').textContent, /1 \/ 4 verified/);
  assert.match(element('task-evidence').textContent, /retained\/frame.png/);
  assert.match(element('task-evidence').textContent, /native-1/);
  assert.match(element('task-budgets').textContent, /original.*primitives/s);
  // A slow player stays visible while the input frame ages; status never submits work.
  context.input.state.timestamp_ms = Date.now() - 5000;
  context.input.gameplay.run.fresh = false;
  for (let index = 0; index < 4; index++) run('render(input)');
  assert.equal(element('task-state').textContent, 'PLANNING');
  assert.match(element('task-freshness').textContent, /stale/);
  assert.match(element('task-next').textContent, /revalidate/);
  assert.equal(element('task-continue').disabled, true);
  assert.equal(element('pause').disabled, false);
  assert.equal(requests.length, 0, 'slow planning status cannot start, continue, plan or retry');

  render(31, 'task-paused.png', {paused: true});
  context.input.pause_requested = true;
  context.input.gameplay = taskSnapshot('paused', {paused: true, lease_owner: null,
    last_public_reason: 'Operator paused during planning'});
  run('render(input)');
  await decode();
  assert.equal(element('task-state').textContent, 'PAUSED');
  assert.match(element('task-reason').textContent, /Operator paused/);
  assert.equal(element('task-continue').disabled, true, 'Continue must not implicitly resume native transport');
  render(32, 'task-resumed.png');
  context.input.gameplay = taskSnapshot('paused', {paused: true, lease_owner: null});
  run('render(input)');
  assert.equal(element('task-continue').disabled, true);
  await decode();
  assert.equal(element('task-continue').disabled, false);
  run('void gameplayCommand("continue")');
  const continueTask = request('/api/gameplay', 'continue');
  assert.deepEqual(JSON.parse(continueTask.options.body), {kind: 'continue', run_id: 'run-exact', execution_epoch: 4,
    expected_session: 'test', expected_revision: 32});
  await reply(continueTask, {status: 'rejected', error: 'Continuation authority is stale', gameplay: context.input.gameplay}, false);
  await statusReply();
  assert.match(element('error').textContent, /Continuation authority is stale/);
  assert.match(element('task-result').textContent, /rejected/);
  assert.equal(element('pause').disabled, false);
  assert.equal(requests.length, 0, 'rejected continuation is never retried');

  render(33, 'task-unknown.png');
  context.input.gameplay = taskSnapshot('unknown', {lease_owner: null,
    last_public_reason: 'Published action receipt unavailable; effects unknown'});
  context.input.gameplay.last_receipt.disposition = 'unknown';
  run('render(input)');
  await decode();
  assert.equal(element('task-state').textContent, 'UNKNOWN');
  assert.equal(element('task-continue').disabled, true);
  assert.match(element('task-progress').textContent, /1 \/ 4 verified/);
  assert.match(element('task-reason').textContent, /effects unknown/);
  assert.match(element('task-evidence').textContent, /unknown/);
  assert.equal(element('task-abandon').disabled, false);
  run('void gameplayCommand("abandon")');
  const abandonTask = request('/api/gameplay', 'abandon');
  assert.deepEqual(JSON.parse(abandonTask.options.body), {kind: 'abandon', run_id: 'run-exact', execution_epoch: 4});
  abandonTask.reject(new Error('Service unavailable'));
  await tick();
  await statusReply();
  assert.match(element('error').textContent, /Task response unavailable/);
  assert.equal(element('pause').disabled, false);
  assert.equal(requests.length, 0);
  render(34, 'task-completed.png');
  context.input.gameplay = taskSnapshot('completed', {lease_owner: null, paused: true,
    progress: {verified_steps: 4, displacement: [0, 0, 0]}});
  run('render(input)');
  await decode();
  assert.equal(element('task-state').textContent, 'COMPLETED');
  assert.match(element('task-progress').textContent, /4 \/ 4 verified/);
  assert.equal(element('task-start').disabled, true, 'a completed retained task must be explicitly abandoned');
  assert.equal(element('task-continue').disabled, true);
  assert.equal(element('task-abandon').disabled, false);
  assert.match(element('task-control-note').textContent, /Abandon this task before starting another/);
  const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
  assert.match(html, /<section class="recorded-objective" aria-labelledby="recorded-objective-heading">/);
  assert.match(html, /id="recorded-objective-heading"[^>]*>Recorded objective</);
  assert.match(html, /id="recorded-objective-text" tabindex="0">No objective recorded\.</);
  assert.ok(html.indexOf('id="recorded-objective-text"') < html.indexOf('id="frame-shell"'),
    'Recorded objective belongs before the native frame in document order; graphical layout needs browser acceptance');
  assert.match(html, /Codex usage, token consumption and subscription cost are unmeasured/);
  assert.match(html, /Unknown effects prohibit continuation/);
  console.log('Viewer regressions passed: exact decoded authority; task start/continue/abandon identity; slow planning, stale/paused/unknown/error evidence; independent Pause and recovery; no implicit resume or retry.');
})().catch(error => { console.error(error); process.exitCode = 1; });
