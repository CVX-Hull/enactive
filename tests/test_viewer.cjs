/* Execute the production viewer against delayed image decoding, without a browser dependency. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {randomUUID} = require('node:crypto');
const missionFixture = {
  "mission": {
    "deadline": 1792484031.536052,
    "epoch": 0,
    "last_wall": 1792476831.565241,
    "pause_cause": "internal_bootstrap",
    "phase": "active",
    "player_id": "player-test",
    "reason": "Runtime recorded deliberate fresh readmission",
    "spent_inputs": 0,
    "started_at": 1792476831.536052,
    "mission_id": "mission-test",
    "remaining_inputs": 1500,
    "remaining_wall_seconds": 7199.963093996048,
    "clock_valid": true,
    "unreconciled": 0,
    "grants_authority": false,
    "lease_owner": {
      "mission_id": "mission-test",
      "epoch": 0,
      "actor_id": "player-test",
      "session": "game-test",
      "pause_generation": 2,
      "takeover_generation": 0,
      "operation": "interaction"
    },
    "objective": "Supplies and shelter",
    "actor_id": "player-test",
    "prompt_phase": null,
    "active_operation": "context",
    "skill": null,
    "progress": {
      "admitted": true,
      "lifecycle_needed": false,
      "source_ids": [
        "6bd4b315f0b053cf6f807f3a2588e0157b8f26154cb1a8fd946cbbce69f499e5"
      ],
      "grants_authority": false
    },
    "last_receipt": null,
    "current_source": {
      "schema": "gameplay/2",
      "record_type": "EvidenceRef",
      "observation_id": "6bd4b315f0b053cf6f807f3a2588e0157b8f26154cb1a8fd946cbbce69f499e5",
      "session": "game-test",
      "revision": 2,
      "timestamp_ms": 1792476831545,
      "received_monotonic": 3934865.927053708,
      "turn": 1,
      "frame_path": "/private/var/folders/2_/qz6x5vjx5kn_qrny49wntmq00000gn/T/tmpfdc5u3hx/.runtime/missions/mission-test/evidence/frames/6bd4b315f0b053cf6f807f3a2588e0157b8f26154cb1a8fd946cbbce69f499e5.png",
      "frame_sha256": "c2da6f0d745acbcd353ad0b65e1ba8840c5498b25cc9f495e7770e8f6ebe48ec",
      "boundary_kind": "normal_play",
      "visibility_version": "cdda-visible/1"
    },
    "remaining_limits": {
      "inputs": 1500,
      "wall_seconds": 7199.962509155273,
      "game_seconds": 43200,
      "frames": 4095,
      "frame_bytes": 1073740885,
      "primitive_mappings": 8192
    },
    "cleanup_reserve": {
      "inputs": 100,
      "wall_seconds": 900.0,
      "frames": 256,
      "frame_bytes": 134217728
    },
    "unresolved_effects": [],
    "memory_version": 3,
    "last_context_id": "packet-ac1dc299c52ffc7544309613bc667c06c4745ecc3f830ee3f9f79f01a5e23134",
    "next_needed_decision": "Player semantic decision",
    "configuration": {
      "source_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "native_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "skills": "skills-1",
      "lessons": "none",
      "model": "unreported",
      "effort": "unreported"
    },
    "metrics": {
      "harness_api_spend": 0,
      "external_tokens": null,
      "api_quota": null,
      "model_time_seconds": null,
      "game_seconds": 0,
      "archive": {
        "frames": 1,
        "bytes": 939,
        "metadata_bytes": 2069,
        "max_frames": 4096,
        "max_bytes": 1073741824,
        "max_metadata_bytes": 35651584
      }
    },
    "diagnostic": null,
    "freshness": {
      "age_seconds": 0.013952207751572132,
      "fresh": true
    },
    "memory_context": {
      "schema": "campaign-memory/2",
      "record_type": "Context",
      "packet_id": "packet-ac1dc299c52ffc7544309613bc667c06c4745ecc3f830ee3f9f79f01a5e23134",
      "scope": {
        "mission_id": "mission-test",
        "session": "game-test",
        "coordinate_epoch": 0
      },
      "query": "position supplies work",
      "memory_version": 3,
      "as_of": {
        "timestamp_ms": 1792476831571,
        "monotonic": 3934865.939170791
      },
      "claims": [
        {
          "coverage": "literal player-visible scene fields",
          "id": "native-6f0f81902ee46e8d551d3011ca1bbba20fc4b03628330e5f930fc22cc0cf4efb",
          "key": {
            "coverage_id": "native-scene",
            "property": "place",
            "subject": "player-position",
            "unit": "local-coordinate"
          },
          "kind": "native_fact",
          "observed_time": {
            "revision": 2,
            "turn": 1
          },
          "received_time": 1792476831563,
          "record_type": "Claim",
          "schema": "campaign-memory/2",
          "scope": {
            "coordinate_epoch": 0,
            "mission_id": "mission-test",
            "session": "game-test"
          },
          "sources": [
            "6bd4b315f0b053cf6f807f3a2588e0157b8f26154cb1a8fd946cbbce69f499e5"
          ],
          "status": "current",
          "supersedes": [],
          "supports": [
            {
              "claims": [],
              "sources": [
                "6bd4b315f0b053cf6f807f3a2588e0157b8f26154cb1a8fd946cbbce69f499e5"
              ]
            }
          ],
          "text": "player-position",
          "value": {
            "quantity": null,
            "state": "{\"position\":[0,0,0]}"
          }
        }
      ],
      "work": [],
      "sources": [
        {
          "id": "6bd4b315f0b053cf6f807f3a2588e0157b8f26154cb1a8fd946cbbce69f499e5",
          "status": "retained",
          "reference": {
            "schema": "gameplay/2",
            "record_type": "EvidenceRef",
            "observation_id": "6bd4b315f0b053cf6f807f3a2588e0157b8f26154cb1a8fd946cbbce69f499e5",
            "session": "game-test",
            "revision": 2,
            "timestamp_ms": 1792476831545,
            "received_monotonic": 3934865.927053708,
            "turn": 1,
            "frame_path": "/private/var/folders/2_/qz6x5vjx5kn_qrny49wntmq00000gn/T/tmpfdc5u3hx/.runtime/missions/mission-test/evidence/frames/6bd4b315f0b053cf6f807f3a2588e0157b8f26154cb1a8fd946cbbce69f499e5.png",
            "frame_sha256": "c2da6f0d745acbcd353ad0b65e1ba8840c5498b25cc9f495e7770e8f6ebe48ec",
            "boundary_kind": "normal_play",
            "visibility_version": "cdda-visible/1"
          }
        }
      ],
      "lesson_ids": [],
      "dispositions": {},
      "omitted": {
        "claims": 2,
        "work": 0,
        "bounds": 0,
        "reasons": {}
      },
      "reobservations": [],
      "grants_authority": false
    }
  }
}.mission;
const elements = new Map();
function element(id) {
  if (elements.has(id)) return elements.get(id);
  const classes = new Set();
  const node = {id, value: '', dataset: {}, hidden: false, textContent: '', children: [], listeners: {},
    classList: {add: x => classes.add(x), toggle: (x, yes) => yes ? classes.add(x) : classes.delete(x), contains: x => classes.has(x)},
    replaceWith: other => elements.set(id, other), replaceChildren() { this.children = []; },
    append(...children) { this.children.push(...children); }, addEventListener(kind, handler) { this.listeners[kind] = handler; }};
  Object.defineProperty(node, 'innerHTML', {set() { assert.fail('Untrusted viewer content must use textContent'); }});
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
const context = vm.createContext({crypto: {randomUUID}, Image: DeferredImage, document: {
  getElementById: element, querySelector: () => ({content: 'test-token'}),
  querySelectorAll: selector => selector === '.send' ? sendButtons : [], createElement: () => element(Symbol()), activeElement: null
}, fetch: (url, options) => new Promise((resolve, reject) => requests.push({url, options, resolve, reject})), setTimeout() {}});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8'), context);
const run = source => vm.runInContext(source, context);
function render(revision, frame, changes = {}) {
  context.input = {connection: 'fresh', age_ms: 0, pause_requested: false, frozen: false,
    mission: null, latency_ms: 10, goal: '', events: [], state: {protocol: 4, pause_origin: 'none', takeover_generation: 0, ui: null, boundary: {kind: 'normal_play', id: 'b-normal', control_generation: 0, recovery_operations: [], interrupt_request_id: null}, timestamp_ms: Date.now(), session: 'test', revision, frame,
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
  // The read-only objective follows saved status and treats markup as text.
  const objective = element('recorded-objective-text');
  assert.equal(objective.textContent, 'No objective recorded.');
  const requestsBeforeObjective = requests.length;
  const savedGoal = 'Survive the first day.\nFind shelter and preserve supplies.';
  context.input.goal = savedGoal;
  run('render(input)');
  assert.equal(objective.textContent, savedGoal);
  const untrustedGoal = '<img src=x onerror="fetch(\'/api/mission\')">\n<script>resume()</script> & "quoted"';
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
  // Mission observation uses the current mission/4 contract, with no admission controls.
  run('recoveryNeedsObserve = false');
  render(30, 'mission-current.png');
  context.input.mission = structuredClone(missionFixture);
  const mission = context.input.mission;
  mission.spent_inputs = 17;
  mission.active_operation = 'context-exact';
  mission.objective = '<img src=x onerror="resume()">Supplies and shelter';
  mission.memory_context.claims[0].text = '<script>sendKey()</script>';
  mission.memory_context.work = [{id: 'work-test', intent: 'Find water', status: 'interrupted',
    sources: ['source-work'], unresolved_effects: ['unknown-effect'], next_verification: 'Inspect source'}];
  mission.memory_context.dispositions = {'source-work': 'disputed'};
  const countBeforeMission = requests.length;
  run('render(input)');
  assert.equal(element('mission-state').textContent, 'ACTIVE');
  assert.equal(element('mission-summary').textContent, mission.objective);
  assert.equal(objective.textContent, mission.objective);
  assert.match(element('mission-player').textContent, /player-test/);
  assert.match(element('mission-operation').textContent, /context-exact/);
  assert.match(element('mission-progress').textContent, /17 primitive inputs/);
  assert.match(element('mission-progress').textContent, /model decisions unknown/);
  assert.match(element('mission-usage').textContent, /Harness API spend: 0/);
  for (const label of ['Model calls', 'External tokens', 'API quota', 'Model time', 'External cost', 'Interventions']) {
    assert.ok(element('mission-usage').textContent.includes(`${label}: unknown`), label);
  }
  assert.match(element('mission-memory-summary').textContent, /Historical.*query-specific/);
  assert.match(element('mission-memory-summary').textContent, /packet-ac1/);
  assert.match(element('mission-memory').textContent, /<script>sendKey/);
  assert.match(element('mission-memory').textContent, /interrupted/);
  assert.match(element('mission-memory').textContent, /source-work/);
  assert.match(element('mission-memory').textContent, /disputed/);
  assert.match(element('mission-memory').textContent, /"claims": 2/);
  assert.equal(requests.length, countBeforeMission, 'rendering mission/memory must not retrieve or send input');
  assert.ok(sendButtons.every(button => button.disabled));
  assert.equal(element('resume').disabled, true);
  assert.equal(element('pause').disabled, false);
  await decode();
  assert.ok(sendButtons.every(button => button.disabled), 'decoded frames cannot unlock mission-owned controls');
  assert.match(element('control-state').textContent, /MISSION ACTIVE/);
  for (const kind of ['action', 'key', 'walk', 'resume']) await run(`command('${kind}')`);
  assert.equal(requests.length, countBeforeMission, 'mission-owned viewer cannot submit manual input');
  assert.throws(() => run('recoveryAuthority("request_interrupt")'), /mission/i);

  // Lifecycle checkpoints remain visible between operations, without inventing a prompt.
  mission.active_operation = null;
  mission.lifecycle_phase = {origin_request_id: 'exit-root', operation: 'exit',
    checkpoint_id: 'exit-checkpoint', grants_authority: false};
  mission.native_process = {owner_mission_id: mission.mission_id, restored_from_disk: false,
    unresolved_custody_requests: ['uncertain-launch'], last_sample: {
      launch_id: 'launch-test', pid: 123, running: true, returncode: null, outcome: 'running', error: null}};
  mission.last_receipt = {transport_disposition: 'unknown', native_request_id: 'exit-native', logical_action_id: 'exit-logical'};
  mission.progress = {phase: {stage: 'awaiting_control', operation: 'exit'}};
  run('render(input)');
  assert.match(element('mission-operation').textContent, /No active operation/);
  assert.match(element('mission-lifecycle').textContent, /Awaiting lifecycle decision.*exit.*exit-root.*exit-checkpoint/);
  assert.doesNotMatch(element('mission-lifecycle').textContent, /Yes\/No|choose Yes|choose No|Really quit/i);
  assert.match(element('mission-process').textContent, /Historical last sample.*running: true/);
  assert.match(element('mission-process').textContent, /current liveness unknown/);
  assert.match(element('mission-process').textContent, /1 unresolved custody request/);
  assert.match(element('mission-exit').textContent, /No verified normal exit.*acknowledgment unknown/i);
  assert.deepEqual(JSON.parse(element('mission-evidence').textContent).lifecycle_phase, mission.lifecycle_phase);
  assert.deepEqual(JSON.parse(element('mission-evidence').textContent).native_process, mission.native_process);
  assert.ok(sendButtons.every(button => button.disabled));
  assert.equal(element('resume').disabled, true);
  assert.equal(element('pause').disabled, false);
  assert.equal(requests.length, countBeforeMission, 'lifecycle display sends no requests');

  // Process absence/code zero alone and a transport disconnect cannot prove normal exit.
  mission.native_process.last_sample = {...mission.native_process.last_sample,
    running: false, returncode: 0, outcome: 'exited'};
  context.input.connection = 'stale';
  run('render(input)');
  assert.match(element('mission-process').textContent, /Historical last sample.*running: false.*exit code: 0/);
  assert.match(element('mission-process').textContent, /status stale or unavailable/);
  assert.match(element('mission-exit').textContent, /No verified normal exit/);
  run('void refresh()');
  request('/api/status').reject(new Error('Service unavailable'));
  await tick();
  assert.match(element('mission-process').textContent, /service disconnected.*current liveness unknown/i);
  assert.match(element('mission-exit').textContent, /No verified normal exit/);
  assert.ok(sendButtons.every(button => button.disabled));
  context.input.connection = 'disconnected';

  const normalExit = {schema: 'mission/4', record_type: 'OwnedNormalExit',
    origin_request_id: 'exit-root', launch_request_id: 'launch-root', launch_id: 'launch-test',
    terminal_logical_id: 'exit-logical', native_request_id: 'exit-native', source_ids: ['exit-checkpoint'],
    no_save_required: true, returncode: 0, grants_authority: false,
    retirement: {launch_id: 'launch-test', exit_request_id: 'exit-root', native_request_id: 'exit-native',
      returncode: 0, retired_pending: true, grants_authority: false}};
  mission.lifecycle_phase = null;
  mission.progress = {phase: {stage: 'complete', operation: 'exit'}, normal_exit: normalExit};
  run('render(input)');
  assert.match(element('mission-exit').textContent, /Recorded verified normal exit effect.*launch-test/);
  assert.match(element('mission-exit').textContent, /acknowledgment unknown/i);
  assert.match(element('mission-exit').textContent, /Matches the recorded terminal exit input/);
  assert.match(element('mission-exit').textContent, /no save required.*untouched menu/i);
  assert.match(element('mission-process').textContent, /service disconnected.*current liveness unknown/i);
  assert.ok(sendButtons.every(button => button.disabled));

  mission.progress = {phase: {stage: 'complete', operation: 'exit'},
    normal_exit: {...normalExit, no_save_required: false, saved_checkpoint_request_id: 'saved-checkpoint'}};
  run('render(input)');
  assert.match(element('mission-exit').textContent, /saved checkpoint saved-checkpoint/);
  const finish = {schema: 'mission/4', record_type: 'NormalFinish', final_source_id: 'final-checkpoint',
    normal_exit_result_request_id: 'exit-result', completed_work_event_id: 'objective-event',
    disposition: 'completed', grants_authority: false};
  mission.progress = {normal_finish: finish};
  run('render(input)');
  assert.match(element('mission-exit').textContent, /player-reported objective completion.*independent campaign acceptance/);
  mission.progress = {normal_finish: {...finish, disposition: 'stopped', completed_work_event_id: null}};
  run('render(input)');
  assert.match(element('mission-exit').textContent, /normal cleanup; objective completion unclaimed/);
  mission.progress = {normal_finish: {...finish, completed_work_event_id: null}};
  run('render(input)');
  assert.doesNotMatch(element('mission-exit').textContent, /Recorded normal finish/);
  mission.progress = {phase: {stage: 'complete', operation: 'exit'}, normal_exit: normalExit};

  const exitReceipt = mission.last_receipt;
  mission.last_receipt = {transport_disposition: 'returned', native_request_id: 'unrelated-native',
    logical_action_id: 'unrelated-logical'};
  run('render(input)');
  assert.match(element('mission-exit').textContent, /Latest primitive receipt unrelated-native.*logical unrelated-logical.*acknowledgment returned/);
  assert.match(element('mission-exit').textContent, /Not correlated with a recorded terminal exit input/);
  mission.last_receipt = exitReceipt;

  const exitProgress = mission.progress;
  mission.progress = {source_ids: ['later-observation']};
  run('render(input)');
  assert.match(element('mission-exit').textContent, /No verified normal exit proof reported/,
    'a later Observe result cannot reconstruct a missing exit proof from the process sample');
  mission.progress = exitProgress;
  for (const malformed of [{...normalExit, returncode: false}, {...normalExit, grants_authority: true},
    {...normalExit, source_ids: []}, {...normalExit, retirement: []},
    {...normalExit, retirement: {...normalExit.retirement, native_request_id: null}},
    {...normalExit, retirement: {...normalExit.retirement, retired_pending: false}},
    {...normalExit, retirement: {...normalExit.retirement, launch_id: 'unrelated-launch'}}]) {
    mission.progress.normal_exit = malformed;
    run('render(input)');
    assert.match(element('mission-exit').textContent, /No verified normal exit/);
  }

  // Incomplete/malformed optional status stays inspectable and cannot manufacture proof or input.
  for (const malformed of [undefined, null, [], 'exit', {}, {grants_authority: true},
    {origin_request_id: 'exit-root', operation: 'exit', checkpoint_id: [], grants_authority: false},
    {last_sample: {running: 'true', outcome: 'running'}, unresolved_custody_requests: 'unknown'}]) {
    mission.lifecycle_phase = malformed;
    mission.native_process = malformed;
    mission.progress = {normal_exit: malformed};
    mission.last_receipt = malformed;
    run('render(input)');
    assert.doesNotMatch(element('mission-lifecycle').textContent, /Awaiting lifecycle decision/);
    assert.match(element('mission-process').textContent, /No usable process sample.*current liveness unknown/);
    assert.match(element('mission-exit').textContent, /No verified normal exit/);
    assert.ok(sendButtons.every(button => button.disabled));
    assert.equal(element('resume').disabled, true);
    assert.equal(element('pause').disabled, false);
    assert.equal(requests.length, countBeforeMission);
  }
  mission.lifecycle_phase = null;
  mission.native_process = null;
  mission.progress = null;
  mission.last_receipt = null;
  context.input.connection = 'fresh';
  run('render(input)');

  // Nonterminal phase alone owns execution even with no lease, including Pause and handoff.
  for (const phase of ['admitted', 'active', 'paused', 'reconciling', 'handoff', 'finishing']) {
    mission.phase = phase;
    mission.lease_owner = null;
    run('render(input)');
    assert.ok(sendButtons.every(button => button.disabled), phase);
    assert.equal(element('resume').disabled, true, phase);
    assert.equal(element('pause').disabled, false, phase);
    assert.match(element('mission-control-note').textContent, /native window/);
  }
  mission.phase = 'paused';
  mission.pause_cause = 'operator_pause';
  mission.reason = 'User paused during context';
  mission.freshness = {fresh: false, age_seconds: 9};
  context.input.state.timestamp_ms = Date.now() - 5000;
  run('render(input)');
  assert.equal(element('mission-state').textContent, 'PAUSED');
  assert.match(element('mission-reason').textContent, /operator_pause.*User paused/);
  assert.match(element('mission-freshness').textContent, /stale/);
  assert.match(element('mission-freshness').textContent, /displayed frame unavailable or stale/);
  assert.match(element('mission-source').textContent, /6bd4b315/);
  assert.equal(requests.length, countBeforeMission);

  // Mission Observe is async and source-bound to exact current identity/epoch. Pause never waits.
  mission.epoch = 7;
  run('void command("observe")');
  const observeMission = request('/api/mission', 'observe');
  const payload = JSON.parse(observeMission.options.body);
  assert.deepEqual(Object.keys(payload).sort(), ['schema', 'kind', 'request_id', 'mission_id', 'epoch'].sort());
  assert.equal(payload.schema, 'mission/4');
  assert.equal(payload.mission_id, 'mission-test');
  assert.equal(payload.epoch, 7);
  assert.match(payload.request_id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.equal(observeMission.options.headers['X-CDDA-Token'], 'test-token');
  assert.equal(element('observe').disabled, true);
  assert.equal(element('pause').disabled, false);
  await run('command("observe")');
  assert.equal(requests.length, 0, 'busy Observe cannot submit a duplicate');
  run('void command("pause")');
  const immediatePause = request('/api/command', 'pause');
  await reply(immediatePause, {status: 'pause_requested'});
  await statusReply();
  assert.equal(run('observeBusy'), true, 'Pause must complete independently of mission Observe');
  await reply(observeMission, {status: 'accepted', operation_id: payload.request_id});
  await statusReply();
  assert.equal(element('observe').disabled, false);
  assert.match(element('mission-result').textContent, /Admission recorded.*not ready.*effect proof/);
  assert.equal(element('resume').disabled, true, 'accepted is not Resume or authority');
  assert.equal(requests.length, 0, 'accepted work is polled through status, never automatically retried');

  // Explicit Observe while runtime work is busy is submitted once; rejection never retries.
  run('void command("observe")');
  await reply(request('/api/mission', 'observe'), {status: 'rejected', error: 'Mission operation busy'}, false);
  await statusReply();
  assert.match(element('mission-result').textContent, /Mission operation busy/);
  assert.match(element('error').textContent, /Mission operation busy/);
  assert.equal(requests.length, 0);
  assert.equal(element('pause').disabled, false);

  // A packet ID without a cached preview does not invent memory contents or freshness.
  const remembered = mission.memory_context;
  mission.memory_context = null;
  run('render(input)');
  assert.match(element('mission-memory-summary').textContent, /No journaled context.*packet-ac1/);
  assert.doesNotMatch(element('mission-memory').textContent, /native_fact/);
  assert.equal(requests.length, 0);
  mission.memory_context = remembered;

  // Changed epoch is used only on a new explicit Observe; lost response remains unknown.
  mission.epoch = 8;
  run('render(input); void command("observe")');
  const lostObserve = request('/api/mission', 'observe');
  const nextPayload = JSON.parse(lostObserve.options.body);
  assert.equal(nextPayload.epoch, 8);
  assert.notEqual(nextPayload.request_id, payload.request_id);
  lostObserve.reject(new Error('Connection lost'));
  await tick();
  await statusReply();
  assert.match(element('mission-result').textContent, /unknown.*do not retry/is);
  assert.equal(requests.length, 0, 'response loss must not trigger a retry or Resume');

  // Unknown/malformed phases and identities fail closed rather than falling back to ordinary Observe.
  for (const malformed of [{...mission, phase: 'unknown'}, {...mission, phase: null}, {...mission, phase: {}},
    {...mission, mission_id: ''}, {...mission, epoch: -1}, {}, [], 'active', undefined]) {
    context.input.mission = malformed;
    run('render(input)');
    assert.equal(element('mission-state').textContent, 'INCONSISTENT');
    assert.match(element('mission-control-note').textContent, /locked/);
    assert.ok(sendButtons.every(button => button.disabled));
    assert.equal(element('resume').disabled, true);
    assert.equal(element('observe').disabled, true);
    assert.equal(element('pause').disabled, false);
    await run('command("observe")');
    await run('command("resume")');
    assert.equal(requests.length, 0);
  }

  // Terminal history cannot refresh the old frame or undo Pause invalidation.
  context.input.mission = {...mission, phase: 'completed'};
  run('render(input)');
  assert.ok(sendButtons.every(button => button.disabled));
  assert.equal(element('resume').disabled, true);
  // A genuinely fresh decoded frame restores ordinary safeguards for terminal history.
  render(32, 'terminal-history.png');
  await decode();
  for (const phase of ['completed', 'failed', 'stopped']) {
    context.input.mission = {...mission, phase};
    run('render(input)');
    assert.equal(element('mission-state').textContent, phase.toUpperCase());
    assert.match(element('mission-control-note').textContent, /history.*owns no execution/i);
    assert.equal(element('resume').disabled, false, phase);
    assert.ok(sendButtons.every(button => !button.disabled), phase);
    run('void command("observe")');
    await reply(request('/api/command', 'observe'), {status: 'ready'});
    await statusReply();
    assert.equal(requests.length, 0);
    // A terminal label cannot release control without a complete valid identity.
    for (const malformed of [{phase}, ...[
      {mission_id: undefined}, {mission_id: null}, {mission_id: ''}, {mission_id: '  \t'},
      {mission_id: 17}, {mission_id: []}, {epoch: undefined}, {epoch: null},
      {epoch: -1}, {epoch: 1.5}, {epoch: Number.MAX_SAFE_INTEGER + 1}, {epoch: '8'}, {epoch: false}
    ].map(change => ({...mission, phase, ...change}))]) {
      context.input.mission = malformed;
      run('render(input)');
      assert.equal(element('mission-state').textContent, 'INCONSISTENT',
        `${phase} with malformed identity/epoch must fail closed: ${JSON.stringify(malformed)}`);
      assert.ok(sendButtons.every(button => button.disabled));
      assert.equal(element('resume').disabled, true);
      assert.equal(element('observe').disabled, true);
      assert.equal(element('pause').disabled, false);
      for (const kind of ['observe', 'resume', 'action', 'key', 'walk']) await run(`command('${kind}')`);
      assert.throws(() => run('recoveryAuthority("request_interrupt")'), /mission/i);
      assert.equal(requests.length, 0, 'malformed terminal status cannot dispatch manual input or Observe');
    }
  }
  render(31, 'mission-recovery.png', {boundary: activity});
  context.input.mission = {...mission, phase: 'active'};
  run('render(input)');
  await decode();
  assert.equal(element('recovery-interrupt').hidden, false, 'the frame still describes recovery eligibility');
  assert.equal(element('recovery-interrupt').disabled, true, 'mission recovery belongs to the player');
  await run('recover("request_interrupt")');
  assert.equal(requests.length, 0);
  context.input.mission = null;
  run('render(input)');
  assert.equal(element('recovery-interrupt').disabled, false);
  assert.equal(element('mission-state').textContent, 'NO MISSION');
  assert.match(element('mission-memory-summary').textContent, /No journaled context/);
  run('void command("observe")');
  await reply(request('/api/command', 'observe'), {status: 'ready'});
  await statusReply();
  assert.equal(requests.length, 0);

  const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
  const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
  assert.match(html, /<section class="recorded-objective" aria-labelledby="recorded-objective-heading">/);
  assert.match(html, /id="recorded-objective-text" tabindex="0">No objective recorded\.</);
  assert.ok(html.indexOf('id="recorded-objective-text"') < html.indexOf('id="frame-shell"'));
  assert.match(html, /Historical, query-specific/);
  assert.match(html, /cannot undo a committed input or cancel an activity/);
  assert.match(html, /<details><summary>Memory context/);
  for (const id of ['mission-lifecycle', 'mission-process', 'mission-exit']) {
    assert.ok(html.includes(`<dd id="${id}">`), `${id} must exist in the mission facts`);
  }
  assert.doesNotMatch(html + app, /api\/gameplay|task-form|task-start|task-continue|task-abandon|goal-form|mission_lease|renderGameplay/);
  console.log('Viewer regressions passed: decoded authority and freshness; mission observation, exact IDs/epoch, history and malformed status; lifecycle checkpoints, historical process samples and separate exit/ACK evidence; safe memory/usage rendering; independent Pause and ordinary recovery; no implicit input, Resume or retry.');
})().catch(error => { console.error(error); process.exitCode = 1; });
