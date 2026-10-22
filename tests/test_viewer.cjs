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
    "activity_phase": null,
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
      "operations": {"total": 23, "by_kind": {"observe": 4, "skill": 19}, "by_skill": {"activity": 19}, "by_state": {"completed": 20, "blocked": 3}},
      "primitives": {"charged": 17, "by_state": {"returned": 12, "unknown": 2, "not_dispatched": 2, "rejected": 1}},
      "model_requests": null,
      "tool_calls": null,
      "interventions": null,
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
      "schema": "campaign-memory/5",
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
          "schema": "campaign-memory/5",
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
      "procedures": [], "procedure_refs": [], "procedure_sources": [],
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
function renderedText(id) {
  function content(node) { return [node.textContent, ...node.children.map(content)].join(' '); }
  return content(element(id));
}
let monotonic = 0;
let epoch = null;
let bootstrapToken = 'test-token';
class PageParser {
  parseFromString(source, type) {
    assert.equal(source, 'normal controller page');
    assert.equal(type, 'text/html');
    return {querySelector(selector) {
      assert.equal(selector, 'meta[name="controller-token"]');
      return bootstrapToken === null ? null : {content: bootstrapToken};
    }};
  }
}
const presentationCallbacks = [];
const pending = [];
const requests = [];
const sendButtons = [element('action-send'), element('key-send'), element('walk-send')];
class DeferredImage {
  naturalWidth = 800;
  naturalHeight = 600;
  decode() { return new Promise((resolve, reject) => pending.push({resolve, reject})); }
  replaceWith(other) { elements.set('frame', other); }
}
const context = vm.createContext({DOMParser: PageParser, Date: class extends Date { static now() { return epoch ?? Date.now(); } }, performance: {now: () => monotonic}, requestAnimationFrame: callback => presentationCallbacks.push(callback), crypto: {randomUUID}, Image: DeferredImage, document: {
  getElementById: element, querySelector: () => ({content: 'test-token'}),
  querySelectorAll: selector => selector === '.send' ? sendButtons : [], createElement: () => element(Symbol()), activeElement: null
}, fetch: (url, options) => new Promise((resolve, reject) => requests.push({url, options, resolve, reject})), setTimeout() {}});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8'), context);
const run = source => vm.runInContext(source, context);
function render(revision, frame, changes = {}, apply = true) {
  context.input = {connection: 'fresh', age_ms: 0, pause_requested: false, frozen: false,
    mission: null, latency_ms: 10, goal: '', events: [], state: {protocol: 6, pause_origin: 'none', takeover_generation: 0, ui: null, boundary: {kind: 'normal_play', input_receiver: true, id: 'b-normal', control_generation: 0, recovery_operations: [], interrupt_request_id: null}, timestamp_ms: epoch ?? Date.now(), session: 'test', revision, frame,
      frame_ok: true, frame_geometry: {window_width: 800, window_height: 600, output_width: 800, output_height: 600, viewport: [0, 0, 800, 600]}, status: 'ready', actions: [], ...changes}};
  if (changes.frame_ok === false && !Object.hasOwn(changes, 'frame_geometry')) context.input.state.frame_geometry = null;
  if (apply) run('render(input)');
}
const tick = () => new Promise(setImmediate);
function boundary(kind, generation = 1, owner = null) {
  return {kind, input_receiver: ['normal_play', 'menu'].includes(kind), id: `boundary-${kind}-${generation}`, control_generation: generation,
    recovery_operations: {activity_poll: ['request_interrupt'], interrupt_confirmation: ['answer_interrupt'],
      debug_prompt: ['continue_debug_once']}[kind] || [], interrupt_request_id: owner};
}
function request(url, kind) {
  const index = requests.findIndex(item => item.url === url && (!kind || JSON.parse(item.options.body).kind === kind));
  assert.notEqual(index, -1, `Missing request ${url} ${kind || ''}`);
  return requests.splice(index, 1)[0];
}
async function reply(item, result, status = true) {
  const code = typeof status === 'boolean' ? (status ? 200 : 409) : status;
  item.resolve({ok: code >= 200 && code < 300, status: code, json: async () => result}); await tick();
}
async function pageReply(value = 'test-token') {
  const item = request('/');
  assert.equal(item.options.cache, 'no-store');
  assert.equal(item.options.credentials, 'same-origin');
  bootstrapToken = value;
  item.resolve({ok: true, text: async () => 'normal controller page'});
  await tick();
}
async function forbidden(item) { await reply(item, {error: 'Valid local controller token required'}, 403); }
async function statusReply(reconnectedToken) {
  await reply(request('/api/status'), context.input);
  if (reconnectedToken !== undefined) await pageReply(reconnectedToken);
}
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
  assert.equal(run('observerMeasurementSnapshot().frames.at(-2).outcome'), 'superseded');
  await decode();
  assert.equal(run('authority().expected_revision'), 6);
  for (const kind of ['activity_poll', 'debug_prompt', 'unsupported', 'interrupt_confirmation']) {
    render(7, `frame-${kind}.png`, {boundary: {kind}});
    await decode();
    assert.throws(() => run('authority()'), /native control/);
    assert.match(element('category').textContent, new RegExp(kind.replaceAll('_', ' ').toUpperCase()));
  }
  render(8, 'frame-menu.png', {boundary: boundary('menu')});
  await decode();
  assert.equal(run('authority().expected_revision'), 8);
  // Required geometry and protocol guards reject metadata before requesting a PNG.
  const geometry = structuredClone(context.input.state.frame_geometry);
  const malformedGeometry = [undefined, null, [], {}, {...geometry, window_width: 0},
    {...geometry, extra: 1},
    {...geometry, output_height: 16385}, {...geometry, output_width: true},
    {...geometry, window_height: 1.5}, {...geometry, output_width: 16384, output_height: 16384},
    {...geometry, viewport: [-1, 0, 10, 10]}, {...geometry, viewport: [0, 0, 0, 10]},
    {...geometry, viewport: [799, 0, 2, 10]}, {...geometry, viewport: [0, 599, 10, 2]},
    {...geometry, viewport: [0, 0, 800, 600, 0]}, {...geometry, viewport: [0, 0, 1.5, 10]}];
  for (const [index, value] of malformedGeometry.entries()) {
    const pendingCount = pending.length;
    render(9, `bad-geometry-${index}.png`, {frame_geometry: value});
    assert.equal(pending.length, pendingCount, 'malformed geometry must not start decode');
    assert.throws(() => run('authority()'), /Wait for/);
    assert.equal(element('resume').disabled, true);
    assert.match(element('error').textContent, /protocol 6|geometry/i);
    assert.equal(element('pause').disabled, false);
  }
  for (const protocol of [4, 5, 7, '6']) {
    render(9, `unsupported-wire-${protocol}.png`, {protocol});
    assert.equal(pending.length, 0, `native ${protocol} has no supported decode path`);
    assert.throws(() => run('authority()'), /Wait for/);
  }
  for (const input_receiver of [false, undefined, null, 1, 'true']) {
    render(9, `not-a-receiver-${input_receiver}.png`, {boundary: {...boundary('menu'), input_receiver}});
    await decode();
    assert.throws(() => run('authority()'), /native control/);
    assert.equal(element('resume').disabled, true);
    assert.equal(element('pause').disabled, false);
  }
  render(9, 'no-frame-with-geometry.png', {frame_ok: false, frame_geometry: geometry});
  assert.throws(() => run('authority()'), /Wait for/);
  render(9, 'valid-after-bad.png');
  await decode();
  assert.equal(run('authority().expected_revision'), 9);
  assert.doesNotMatch(element('error').textContent, /protocol 6|geometry/i);
  render(9, 'mismatched-dimensions.png', {frame_geometry: {...geometry, output_width: 801}});
  await decode();
  assert.throws(() => run('authority()'), /Wait for/);
  assert.match(element('error').textContent, /PNG dimensions disagree/);
  render(9, 'disconnected-during-decode.png');
  context.input.connection = 'disconnected';
  run('render(input)');
  await decode();
  assert.equal(element('resume').disabled, true);
  assert.match(element('frame-note').textContent, /DISCONNECTED/);
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
  assert.equal(run('observerMeasurementSnapshot().frames.at(-1).outcome'), 'decode_failed');
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
  // Mission observation uses the current mission/10 contract, with no admission controls.
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
  mission.memory_context.claims[0].status = 'unknown';
  mission.memory_context.claims[0].supersedes = ['retired-water-claim'];
  mission.memory_context.work[0] = {...mission.memory_context.work[0], stage: 'awaiting storage',
    predecessor_work_id: 'work-predecessor', progress: 40, available: [], committed: [],
    predicted_output: [{subject: 'clean-water', quantity: 2, unit: 'litre'}], observed_output: []};
  mission.memory_context.dispositions = {'source-work': ['disputed source; reobserve']};
  mission.memory_context.reobservations = [{id: 'work-test', reason: 'unknown delivery', instruction: 'Inspect water storage'}];
  mission.memory_context.sources.push({id: 'source-work', status: 'disputed', reference: null});
  const countBeforeMission = requests.length;
  run('render(input)');
  assert.equal(element('mission-state').textContent, 'ACTIVE');
  assert.equal(element('mission-summary').textContent, mission.objective);
  assert.equal(objective.textContent, mission.objective);
  assert.match(element('mission-player').textContent, /player-test/);
  assert.match(element('mission-operation').textContent, /context-exact/);
  assert.match(element('mission-progress').textContent, /23 retained mission requests.*17 charged primitive admissions/);
  assert.match(element('mission-progress').textContent, /not model calls.*not delivered keys/);
  assert.match(element('mission-counts').textContent, /by kind.*observe: 4.*skill: 19/);
  assert.match(element('mission-counts').textContent, /unknown: 2.*not_dispatched: 2.*rejected: 1/);
  assert.match(element('mission-usage').textContent, /Harness API spend: 0/);
  for (const label of ['Model requests', 'Tool calls', 'External tokens', 'API quota', 'Model time', 'External cost', 'Interventions']) {
    assert.ok(element('mission-usage').textContent.includes(`${label}: unknown`), label);
  }
  assert.match(element('mission-memory-summary').textContent, /Historical.*query-specific/);
  assert.match(element('mission-memory-summary').textContent, /packet-ac1/);
  assert.match(element('mission-memory').textContent, /<script>sendKey/);
  assert.match(element('mission-memory').textContent, /interrupted/);
  assert.match(element('mission-memory').textContent, /source-work/);
  assert.match(element('mission-memory').textContent, /disputed/);
  assert.match(element('mission-memory').textContent, /"claims": 2/);
  assert.match(renderedText('mission-claims'), /unknown.*<script>sendKey.*retired-water-claim/s);
  assert.match(renderedText('mission-work'), /interrupted.*awaiting storage.*40.*work-predecessor/s);
  assert.match(renderedText('mission-work'), /Next verification.*Inspect source.*unknown-effect/s);
  assert.match(renderedText('mission-work'), /Predicted output.*clean-water.*2 litre.*Observed output: none reported/s);
  assert.match(renderedText('mission-sources'), /source-work.*disputed/s);
  assert.match(renderedText('mission-dispositions'), /source-work.*disputed source/s);
  assert.match(renderedText('mission-reobservations'), /work-test.*unknown delivery.*Inspect water storage/s);
  assert.match(element('mission-omissions').textContent, /Omitted claims: 2.*not complete/s);
  const stableClaim = element('mission-claims').children[0];
  run('render(input)');
  assert.equal(element('mission-claims').children[0], stableClaim,
    'polling the same historical packet must not rebuild a list being read');
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

  // Measurements are cumulative producer values; recent events and spent_inputs cannot fill gaps.
  const measured = mission.metrics;
  for (const broken of [null, {}, {operations: {total: 0}, primitives: {charged: 0}},
    {operations: {...measured.operations, total: -1}, primitives: {...measured.primitives, charged: false}}]) {
    mission.metrics = broken;
    run('render(input)');
    assert.match(element('mission-progress').textContent, /Mission requests: unavailable.*Charged primitive admissions: unavailable/);
    assert.match(element('mission-usage').textContent, /Model requests: unknown.*Tool calls: unknown.*Interventions: unknown/);
    assert.ok(sendButtons.every(button => button.disabled));
    assert.equal(element('pause').disabled, false);
  }
  mission.metrics = {...measured, operations: {total: 0, by_kind: {}, by_skill: {}, by_state: {}},
    primitives: {charged: 0, by_state: {}}};
  run('render(input)');
  assert.match(element('mission-progress').textContent, /0 retained mission requests.*0 charged primitive admissions/);
  mission.metrics = measured;
  for (const broken of [
    {...measured, operations: {...measured.operations, total: 24}},
    {...measured, operations: {...measured.operations, by_skill: {activity: 20}}},
    {...measured, primitives: {...measured.primitives, charged: 18}}
  ]) {
    mission.metrics = broken;
    run('render(input)');
    assert.match(element('mission-progress').textContent, /unavailable/);
    assert.equal(requests.length, countBeforeMission);
  }
  mission.metrics = measured;
  mission.activity_phase = {origin_request_id: 'activity-root', checkpoint_id: 'activity-checkpoint',
    stage: 'awaiting_interrupt_answer', interrupt_request_id: 'interrupt-root', answered: false, grants_authority: false};
  mission.active_operation = null;
  mission.progress = {phase: {operation: 'activity', stage: 'poll_returned'}};
  run('render(input)');
  assert.match(element('mission-activity').textContent, /Private paused activity.*awaiting_interrupt_answer.*activity-root.*activity-checkpoint.*interrupt-root.*false.*no authority/);
  assert.match(element('mission-last-report').textContent, /Last reported.*activity.*poll_returned.*not a live phase/);
  assert.match(element('mission-operation').textContent, /No active operation/);
  for (const malformed of [[], {}, {...mission.activity_phase, answered: 'false'}, {...mission.activity_phase, grants_authority: true}]) {
    mission.activity_phase = malformed;
    run('render(input)');
    assert.match(element('mission-activity').textContent, /unavailable or inconsistent/);
    assert.equal(element('resume').disabled, true);
  }
  mission.activity_phase = null;

  const savedMemory = structuredClone(mission.memory_context);
  mission.memory_context.claims = [null, ...Array.from({length: 35}, (_, id) =>
    ({id: `bounded-${id}`, text: 'x'.repeat(5000), status: 'unknown'}))];
  mission.memory_context.work[0].progress = null;
  run('render(input)');
  assert.match(renderedText('mission-claims'), /Malformed entry/);
  assert.match(renderedText('mission-claims'), /4 additional entries not summarized/);
  assert.ok(!renderedText('mission-claims').includes('x'.repeat(2049)));
  assert.match(renderedText('mission-claims'), /truncated; inspect raw context/);
  assert.match(renderedText('mission-work'), /Progress: unknown ·/);
  assert.doesNotMatch(renderedText('mission-work'), /unknown%/);
  assert.equal(element('mission-claims').children.length, 33);
  for (const unsupported of [{...savedMemory, grants_authority: true}, {...savedMemory, schema: 'campaign-memory/3'}]) {
    mission.memory_context = unsupported;
    run('render(input)');
    assert.equal(element('mission-memory-readable').hidden, true);
    assert.match(element('mission-memory-summary').textContent, /inconsistent packet/);
  }
  assert.ok(sendButtons.every(button => button.disabled));
  assert.equal(requests.length, countBeforeMission);
  mission.memory_context = savedMemory;

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

  const normalExit = {schema: 'mission/10', record_type: 'OwnedNormalExit',
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
  const finish = {schema: 'mission/10', record_type: 'NormalFinish', final_source_id: 'final-checkpoint',
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
    {...normalExit, schema: 'mission/8'},
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
  assert.match(element('mission-freshness').textContent, /age 9s/);
  mission.freshness.age_seconds = null;
  run('render(input)');
  assert.match(element('mission-freshness').textContent, /age unknown ·/);
  assert.match(element('mission-freshness').textContent, /displayed frame unavailable or stale/);
  assert.match(element('mission-source').textContent, /6bd4b315/);
  assert.equal(requests.length, countBeforeMission);

  // Mission Observe is async and source-bound to exact current identity/epoch. Pause never waits.
  mission.epoch = 7;
  run('void command("observe")');
  const observeMission = request('/api/mission', 'observe');
  const payload = JSON.parse(observeMission.options.body);
  assert.deepEqual(Object.keys(payload).sort(), ['schema', 'kind', 'request_id', 'mission_id', 'epoch'].sort());
  assert.equal(payload.schema, 'mission/10');
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
  await statusReply('test-token');
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
  // Reconnect refreshes status only, preserving the uncertain Observe result.
  run('void refresh()');
  request('/api/status').reject(new Error('Still disconnected'));
  await tick();
  assert.equal(element('resume').disabled, true);
  assert.ok(sendButtons.every(button => button.disabled));
  run('void refresh()');
  await statusReply('test-token');
  assert.match(element('mission-result').textContent, /unknown.*do not retry/is);
  assert.equal(requests.length, 0, 'reconnect cannot replay a lost POST');

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
  const terminal = context.input.mission;
  terminal.lease_owner = null;
  terminal.unresolved_effects = [];
  terminal.native_process = {last_sample: {running: true, outcome: 'running'}, unresolved_custody_requests: []};
  context.input.frozen = true;
  context.input.connection = 'disconnected';
  run('render(input)');
  assert.match(element('control-state').textContent, /MISSION COMPLETED.*HISTORY.*DISCONNECTED/);
  assert.doesNotMatch(element('control-state').textContent, /UNRECONCILED|READY/);
  assert.match(element('mission-owner').textContent, /No input lease.*reported snapshot/i);
  assert.match(element('mission-unresolved').textContent, /0 unresolved effect.*reported snapshot/i);
  assert.match(element('mission-process').textContent, /Historical last sample.*running: true.*current liveness unknown/);
  assert.match(element('mission-control-note').textContent, /history.*owns no execution/i);
  assert.match(renderedText('mission-work'), /Historical Work status.*interrupted/s);
  delete terminal.lease_owner;
  delete terminal.unresolved_effects;
  run('render(input)');
  assert.match(element('mission-owner').textContent, /unknown/i);
  assert.match(element('mission-unresolved').textContent, /unknown/i);
  assert.doesNotMatch(element('mission-unresolved').textContent, /0 unresolved/);
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

  // Raw wall anchors correlate retained native frames; durations keep the monotonic clock.
  requests.length = 0;
  run('recoveryNeedsObserve = false');
  epoch = 2000000000100;
  monotonic = 100;
  run('void refresh()');
  assert.equal(run('observerMeasurementSnapshot().status.at(-1).response_ready_epoch_ms'), null);
  epoch = 2000000000080; // A wall-clock adjustment must not change monotonic durations.
  monotonic = 130;
  render(40, 'measured.png', {timestamp_ms: 2000000000000}, false);
  await statusReply();
  assert.equal(element('resume').disabled, true, 'status receipt cannot stand in for decode');
  epoch = 2000000000060;
  monotonic = 150;
  await decode();
  monotonic = 160;
  presentationCallbacks.splice(0).forEach(callback => callback(monotonic));
  const snapshot = JSON.parse(run('JSON.stringify(observerMeasurementSnapshot())'));
  const frameTiming = snapshot.frames.at(-1);
  assert.equal(snapshot.schema, 'observer-timing/2');
  assert.match(snapshot.clock, /performance.now.*monotonic.*Date.now.*epoch/);
  assert.equal(snapshot.status.at(-1).started_epoch_ms, 2000000000100);
  assert.equal(snapshot.status.at(-1).response_ready_epoch_ms, 2000000000080);
  assert.equal(frameTiming.native_capture_epoch_ms, 2000000000000);
  assert.equal(frameTiming.status_ready_ms, 130);
  assert.equal(frameTiming.status_ready_epoch_ms, 2000000000080);
  assert.equal(frameTiming.dom_replaced_epoch_ms, 2000000000060);
  assert.equal(frameTiming.dom_replaced_epoch_ms - frameTiming.status_ready_epoch_ms, -20,
    'raw wall-clock discontinuities remain visible for offline interpretation');
  assert.equal(element('resume').disabled, false);
  assert.ok(sendButtons.every(button => !button.disabled));
  assert.equal(element('pause').disabled, false);
  assert.equal(snapshot.status.at(-1).status_round_trip_ms, 30);
  assert.equal(frameTiming.decode_ms, 20);
  assert.equal(frameTiming.status_to_dom_ms, 20);
  assert.equal(frameTiming.presentation_opportunity_ms, 160);
  assert.equal(frameTiming.frame, 'measured.png');
  assert.match(frameTiming.frame_identity, /measured.png/);
  assert.equal(frameTiming.status_sequence, snapshot.status.at(-1).sequence);
  assert.match(element('observer-measurements').textContent, /measured.png/);
  context.input.state.timestamp_ms = epoch - 5000;
  run('render(input)');
  assert.equal(run('observerMeasurementSnapshot().displayed_frame_fresh'), false,
    'successful decode metrics do not imply continuing freshness');
  assert.equal(element('resume').disabled, true);
  for (let index = 0; index < 40; index++) {
    monotonic += 1;
    run('void refresh()');
    await statusReply();
  }
  const rolled = JSON.parse(run('JSON.stringify(observerMeasurementSnapshot())'));
  assert.equal(rolled.status.length, 32);
  assert.ok(!rolled.status.some(sample => sample.sequence === frameTiming.status_sequence));
  assert.deepEqual(rolled.frames.find(sample => sample.frame === 'measured.png'), frameTiming,
    'a frame keeps its original native and status clock anchors after status rollover');
  assert.equal(rolled.displayed_frame_fresh, false, 'retained anchors do not refresh stale authority');
  assert.equal(requests.length, 0);

  // Failed/superseded status records retain raw anchors and cannot acquire frame authority.
  epoch = 2000000000200;
  monotonic = 300;
  run('void refresh()');
  epoch = 2000000000190;
  monotonic = 315;
  request('/api/status').reject(new Error('timing transport failure'));
  await tick();
  const failedStatus = JSON.parse(run('JSON.stringify(observerMeasurementSnapshot().status.at(-1))'));
  assert.equal(failedStatus.outcome, 'failed');
  assert.equal(failedStatus.started_epoch_ms, 2000000000200);
  assert.equal(failedStatus.response_ready_epoch_ms, 2000000000190);
  assert.equal(failedStatus.status_round_trip_ms, 15);
  assert.equal(element('resume').disabled, true);
  assert.equal(element('pause').disabled, false);

  monotonic = 320;
  run('void refresh()');
  const supersededRequest = request('/api/status');
  epoch = 2000000000210;
  monotonic = 325;
  run('void refresh()');
  epoch = 2000000000220;
  monotonic = 330;
  render(41, 'superseded-decode.png', {}, false);
  await statusReply('test-token');
  const supersededFrame = context.input;
  epoch = 2000000000230;
  monotonic = 340;
  render(42, 'failed-decode.png', {}, false);
  await reply(supersededRequest, context.input);
  const supersededStatus = JSON.parse(run('JSON.stringify(observerMeasurementSnapshot().status.at(-2))'));
  assert.equal(supersededStatus.outcome, 'superseded');
  assert.equal(supersededStatus.started_epoch_ms, 2000000000190);
  assert.equal(supersededStatus.response_ready_epoch_ms, 2000000000230);
  assert.equal(supersededStatus.status_round_trip_ms, 20);
  assert.equal(run('latest.state.frame'), supersededFrame.state.frame);
  monotonic = 345;
  run('void refresh()');
  epoch = 2000000000240;
  monotonic = 350;
  await statusReply();
  epoch = 2000000000250;
  monotonic = 360;
  await decode(); // The newer frame requested above supersedes this completed decode.
  pending.shift().reject(new Error('timing decode failure'));
  await tick();
  const outcomes = JSON.parse(run('JSON.stringify(observerMeasurementSnapshot().frames.slice(-2))'));
  assert.deepEqual(outcomes.map(sample => sample.outcome), ['superseded', 'decode_failed']);
  assert.deepEqual(outcomes.map(sample => sample.native_capture_epoch_ms), [2000000000220, 2000000000230]);
  assert.deepEqual(outcomes.map(sample => sample.status_ready_epoch_ms), [2000000000220, 2000000000240]);
  assert.deepEqual(outcomes.map(sample => sample.status_ready_ms), [330, 350]);
  assert.ok(outcomes.every(sample => sample.dom_replaced_ms === null && sample.dom_replaced_epoch_ms === null &&
    sample.status_to_dom_ms === null && sample.presentation_opportunity_ms === null));
  assert.equal(element('resume').disabled, true);
  assert.equal(element('pause').disabled, false);

  render(43, 'unavailable-anchors.png', {timestamp_ms: undefined});
  await decode();
  const unavailable = JSON.parse(run('JSON.stringify(observerMeasurementSnapshot().frames.at(-1))'));
  assert.equal(unavailable.native_capture_epoch_ms, null);
  assert.equal(unavailable.status_sequence, null);
  assert.equal(unavailable.status_ready_ms, null);
  assert.equal(unavailable.status_ready_epoch_ms, null);
  assert.equal(unavailable.status_to_dom_ms, null);
  assert.equal(unavailable.dom_replaced_epoch_ms, epoch);
  assert.equal(element('resume').disabled, true, 'missing anchors do not create authority');
  assert.equal(requests.length, 0);
  for (let index = 0; index < 40; index++) {
    render(50 + index, `bounded-timing-${index}.png`);
    monotonic += 1;
    await decode();
    presentationCallbacks.splice(0).forEach(callback => callback(monotonic));
  }
  assert.equal(run('observerMeasurementSnapshot().frames.length'), 32);
  assert.equal(requests.length, 0, 'local timing cannot submit remote requests');

  // A native disconnect with a successful status transport does not rotate credentials.
  context.input.connection = 'disconnected';
  run('void refresh()');
  await statusReply();
  assert.equal(requests.length, 0);
  render(100, 'credentials-before-reconnect.png');
  await decode();
  assert.equal(element('resume').disabled, false);
  run('void refresh()');
  request('/api/status').reject(new Error('controller restarted'));
  await tick();
  run('void refresh()');
  await statusReply();
  assert.equal(requests.filter(item => item.url === '/').length, 1);
  assert.equal(element('observe').disabled, true);
  assert.equal(element('resume').disabled, true);
  assert.ok(sendButtons.every(button => button.disabled));
  assert.equal(element('pause').disabled, false);
  for (const kind of ['key', 'resume', 'observe']) await run(`command('${kind}')`);
  assert.equal(requests.length, 1, 'only the shared credential request is in flight');
  await pageReply('reconnect-token');
  assert.equal(requests.length, 0, 'reconnect refreshes credentials without sending commands');
  assert.throws(() => run('authority()'), /Wait for/);
  assert.equal(element('resume').disabled, true, 'token rotation cannot rearm the old decoded frame');
  assert.equal(element('observe').disabled, false);

  // A fast restart can reject Pause before any status poll sees a transport failure.
  render(101, 'credentials-before-pause.png');
  await decode();
  run('void command("pause")');
  const stalePause = request('/api/command', 'pause');
  assert.equal(stalePause.options.headers['X-CDDA-Token'], 'reconnect-token');
  await forbidden(stalePause);
  await pageReply('pause-token');
  const retriedPause = request('/api/command', 'pause');
  assert.equal(retriedPause.options.headers['X-CDDA-Token'], 'pause-token');
  assert.deepEqual(JSON.parse(retriedPause.options.body), {kind: 'pause'});
  await reply(retriedPause, {status: 'pause_requested'});
  await statusReply();
  assert.equal(requests.length, 0, 'the explicit Pause has exactly one retry');
  assert.equal(element('resume').disabled, true);

  // Other requests are never replayed after a known credential rejection.
  for (const kind of ['key', 'resume', 'observe']) {
    render(102, `credential-rejection-${kind}.png`);
    await decode();
    run(`void command('${kind}', ${kind === 'key' ? '{key: "x", ...authority()}' : '{}'})`);
    await forbidden(request('/api/command', kind));
    await pageReply(`after-${kind}`);
    await statusReply();
    assert.equal(requests.length, 0, `${kind} must not be replayed after 403`);
    assert.match(element('error').textContent, /Valid local controller token required/);
    assert.equal(element('resume').disabled, true);
  }
  render(103, 'credential-recovery.png', {boundary: activity});
  await decode();
  run('void recover("request_interrupt")');
  await forbidden(request('/api/recovery', 'request_interrupt'));
  await pageReply('after-recovery');
  await statusReply();
  assert.equal(requests.length, 0, 'recovery is not replayed');
  assert.equal(run('recoveryNeedsObserve'), true);

  context.input.mission = {...mission, phase: 'active'};
  run('render(input); void command("observe")');
  await forbidden(request('/api/mission', 'observe'));
  assert.equal(element('observe').disabled, true);
  assert.equal(element('pause').disabled, false);
  // Explicit Pause sends immediately even if the credential page request is stalled.
  run('void command("pause")');
  const independentPause = request('/api/command', 'pause');
  assert.equal(independentPause.options.headers['X-CDDA-Token'], 'after-recovery');
  assert.equal(requests.length, 1, 'the credential request is still pending during the first Pause POST');
  assert.equal(requests[0].url, '/');
  assert.equal(requests.filter(item => item.url === '/api/mission').length, 0);
  await reply(independentPause, {status: 'pause_requested'});
  await statusReply();
  assert.equal(requests.length, 1, 'a successful Pause does not await or repeat through the stalled page');
  await pageReply('after-mission-observe');
  await statusReply();
  assert.equal(requests.length, 0);
  assert.equal(run('missionLocksControls()'), true);
  assert.equal(element('resume').disabled, true);

  // Unknown transport results never cause a credential refresh or a retry, including Pause.
  context.input.mission = null;
  run('render(input); recoveryNeedsObserve = false');
  for (const kind of ['pause', 'observe', 'key']) {
    run(`void command('${kind}')`);
    request('/api/command', kind).reject(new Error(`lost ${kind} response`));
    await tick();
    await statusReply();
    assert.equal(requests.length, 0, `${kind} unknown outcome cannot retry or bootstrap`);
    assert.match(element('error').textContent, new RegExp(`lost ${kind} response`));
  }

  // Refresh failures, missing tokens, unchanged tokens and repeated 403s are bounded.
  for (const mode of ['network', 'missing', 'unchanged', 'second-403']) {
    run('void command("pause")');
    await forbidden(request('/api/command', 'pause'));
    if (mode === 'network') {
      request('/').reject(new Error('page unavailable'));
      await tick();
    } else {
      await pageReply(mode === 'missing' ? null : mode === 'unchanged' ? 'after-mission-observe' : 'last-token');
    }
    if (mode === 'second-403') await forbidden(request('/api/command', 'pause'));
    await statusReply();
    assert.equal(requests.length, 0, `${mode} cannot loop or retry again`);
    assert.equal(element('pause').disabled, false);
    assert.match(element('error').textContent, /Valid local controller token required/);
    if (mode === 'network' || mode === 'missing') assert.match(element('error').textContent, /credentials.*refreshed/i);
  }
  // A reconnect can rotate the token before an older Pause's 403 arrives.
  run('void command("pause")');
  const lateRejectedPause = request('/api/command', 'pause');
  assert.equal(lateRejectedPause.options.headers['X-CDDA-Token'], 'last-token');
  run('void refresh()');
  request('/api/status').reject(new Error('second restart'));
  await tick();
  run('void refresh()');
  await statusReply();
  await pageReply('concurrent-token');
  await forbidden(lateRejectedPause);
  await pageReply('concurrent-token'); // Already current globally, but changed from this POST's token.
  const lateRetry = request('/api/command', 'pause');
  assert.equal(lateRetry.options.headers['X-CDDA-Token'], 'concurrent-token');
  await reply(lateRetry, {status: 'pause_requested'});
  await statusReply();
  assert.equal(requests.length, 0);

  // Both reconnect and a rejected POST share one credential request in flight.
  run('void command("pause")');
  const sharedPause = request('/api/command', 'pause');
  run('void refresh()');
  request('/api/status').reject(new Error('third restart'));
  await tick();
  run('void refresh()');
  await statusReply();
  await forbidden(sharedPause);
  assert.equal(requests.filter(item => item.url === '/').length, 1);
  await pageReply('shared-token');
  await reply(request('/api/command', 'pause'), {status: 'pause_requested'});
  await statusReply();
  assert.equal(requests.length, 0);

  // A decode started before token refresh cannot become the post-refresh authority.
  render(110, 'decode-before-bootstrap.png');
  run('void command("pause")');
  await forbidden(request('/api/command', 'pause'));
  await pageReply('decode-token');
  await reply(request('/api/command', 'pause'), {status: 'pause_requested'});
  await statusReply();
  run('void command("observe")');
  await reply(request('/api/command', 'observe'), {status: 'ready'});
  await statusReply();
  await decode(); // Old candidate, even though explicit Observe has since cleared invalidation.
  assert.equal(run('observerMeasurementSnapshot().frames.at(-2).outcome'), 'superseded');
  assert.throws(() => run('authority()'), /Wait for/);
  assert.equal(element('resume').disabled, true);
  await decode(); // Candidate requested from the post-refresh status.
  assert.equal(run('authority().expected_revision'), 110);
  assert.equal(element('resume').disabled, false);
  assert.equal(requests.length, 0);

  // Failure of a pre-refresh decode also cannot erase a newer same-name candidate.
  render(111, 'failed-decode-before-bootstrap.png');
  run('void command("pause")');
  await forbidden(request('/api/command', 'pause'));
  await pageReply('failure-fence-token');
  await reply(request('/api/command', 'pause'), {status: 'pause_requested'});
  await statusReply();
  pending.pop().resolve(); // Decode the candidate requested after credential refresh first.
  await tick();
  run('void command("observe")');
  await reply(request('/api/command', 'observe'), {status: 'ready'});
  await statusReply();
  assert.equal(run('authority().expected_revision'), 111);
  pending.shift().reject(new Error('old credential generation image failed'));
  await tick();
  assert.equal(run('authority().expected_revision'), 111);
  assert.doesNotMatch(element('error').textContent, /old credential generation image failed/);
  assert.equal(requests.length, 0);

  // Terminal command history is labeled; live native/controller/manual/transport failures stay visible.
  context.input.mission = {...mission, phase: 'completed'};
  context.input.last_result = {status: 'unknown', error: 'Old timeout. Observe to reconcile, then resume.'};
  context.input.error = 'New controller fault';
  context.input.state.error = 'New native fault';
  context.input.unknown_outcomes = [{id: 'retained-unknown', status: 'unknown'}];
  run('render(input); void command("pause")');
  request('/api/command', 'pause').reject(new Error('New manual Pause transport failure'));
  await tick();
  await statusReply();
  assert.match(element('error').textContent,
    /Recorded last-command history \(not a current mission decision\): Old timeout\. Observe to reconcile, then resume\./);
  assert.match(element('error').textContent, /Controller snapshot diagnostic: New controller fault/);
  assert.match(element('error').textContent, /Native snapshot diagnostic: New native fault/);
  assert.match(element('error').textContent, /New manual Pause transport failure/);
  assert.equal(JSON.parse(element('last-result').textContent).error, context.input.last_result.error);
  assert.match(element('gameplay-evidence').textContent, /retained-unknown/);
  assert.doesNotMatch(element('error').textContent, /unresolved historical mission effect/i);
  run('void refresh()');
  request('/api/status').reject(new Error('New status transport failure'));
  await tick();
  run('render(input)');
  assert.match(element('error').textContent, /New status transport failure/,
    'a later render cannot erase the current transport error');
  assert.match(element('error').textContent, /Recorded last-command history/);
  run('void refresh()');
  await statusReply('final-token');
  assert.doesNotMatch(element('error').textContent, /New status transport failure/);
  assert.match(element('error').textContent, /New manual Pause transport failure/);
  assert.equal(requests.length, 0);

  assert.doesNotMatch(element('observer-measurements').textContent + element('error').textContent,
    /reconnect-token|pause-token|after-key|after-resume|after-observe|after-recovery|after-mission-observe|last-token|concurrent-token|shared-token|decode-token|failure-fence-token|final-token/);

  const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
  const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
  assert.match(html, /id="observer-timing-note">.*same computer.*wall-clock.*not.*end-to-end player latency/);
  assert.match(html, /<section class="recorded-objective" aria-labelledby="recorded-objective-heading">/);
  assert.match(html, /id="recorded-objective-text" tabindex="0">No objective recorded\.</);
  assert.ok(html.indexOf('id="recorded-objective-text"') < html.indexOf('id="frame-shell"'));
  assert.match(html, /Historical, query-specific/);
  assert.match(html, /cannot undo a committed input or cancel an activity/);
  assert.match(html, /<summary>Memory context/);
  for (const id of ['mission-lifecycle', 'mission-process', 'mission-exit']) {
    assert.ok(html.includes(`<dd id="${id}">`), `${id} must exist in the mission facts`);
  }
  assert.doesNotMatch(html + app, /api\/gameplay|task-form|task-start|task-continue|task-abandon|goal-form|mission_lease|renderGameplay/);
  console.log('Viewer regressions passed: native6 geometry and decoded authority/freshness; mission10 observation and memory5 history; terminal snapshot versus historical uncertainty; reconnect without replay; bounded native/status/DOM clock correlation with monotonic durations; independent Pause and ordinary recovery; rotated credentials without action replay; one bounded rejected-Pause retry; recorded terminal diagnostics.');
})().catch(error => { console.error(error); process.exitCode = 1; });
