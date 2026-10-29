/* Production viewer behavior under delayed HTTP, image decoding and browser clocks. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
const elements = new Map();
function node(id) {
  const result = {id, hidden: false, disabled: false, textContent: '', children: [], listeners: {},
    addEventListener(kind, callback) { this.listeners[kind] = callback; },
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
    replaceWith(other) { elements.set(id, other); }};
  Object.defineProperty(result, 'innerHTML', {set() { assert.fail('Render untrusted data as text'); }});
  return result;
}
for (const match of html.matchAll(/id="([^"]+)"/g)) elements.set(match[1], node(match[1]));
function element(id) {
  assert.ok(elements.has(id), `Production HTML is missing ${id}`);
  return elements.get(id);
}
const requests = [];
const decodes = [];
const timers = new Map();
const blobs = new Map();
const downloads = [];
let timerId = 0;
let epoch = 2000000000000;
class DeferredImage {
  listeners = {};
  naturalWidth = 800;
  naturalHeight = 600;
  decode() { return new Promise((resolve, reject) => decodes.push({image: this, resolve, reject})); }
  replaceWith(other) { elements.set('frame', other); }
}
const context = vm.createContext({Blob, AbortController, Image: DeferredImage,
  Date: class extends Date { static now() { return epoch; } },
  URL: {createObjectURL(blob) { const id = `blob:${blobs.size}`; blobs.set(id, blob); return id; }, revokeObjectURL() {}},
  document: {getElementById: element, createElement(tag) {
    const result = node(tag);
    if (tag === 'a') result.click = () => downloads.push({url: result.href, name: result.download});
    return result;
  }},
  fetch: (url, options) => new Promise((resolve, reject) => requests.push({url, options, resolve, reject})),
  setTimeout(callback, delay) { const id = ++timerId; timers.set(id, {callback, delay}); return id; },
  clearTimeout(id) { timers.delete(id); }});
const run = code => vm.runInContext(code, context);
const tick = () => new Promise(setImmediate);
function request(url) {
  const index = requests.findIndex(item => item.url === url);
  assert.notEqual(index, -1, `Missing request ${url}`);
  return requests.splice(index, 1)[0];
}
async function reply(item, value, status = 200) {
  item.resolve({ok: status >= 200 && status < 300, status, json: async () => value,
    blob: async () => new Blob(['original PNG fixture bytes'], {type: 'image/png'})});
  await tick();
}
function source(id, overrides = {}) {
  return {schema: 'computer-source/1', session: 'session-one', source_id: `session-one-${id}`,
    capture_id: id, sha256: 'a'.repeat(64), media_type: 'image/png', presented_ms: epoch - 500,
    received_wall: (epoch - 200) / 1000, width: 800, height: 600,
    window_width: 1000, window_height: 750, viewport: [10, 20, 780, 560], ...overrides};
}
function status(frame = null, overrides = {}) {
  return {schema: 'computer-status/1', session: 'session-one',
    target: {schema: 'computer-target/2', session: 'session-one', pid: 42, window_id: 7,
      paused: false, takeover_generation: 3, latest_frame: null, error: null},
    stop: {stop_requested: false, native_pause_confirmed: false, reason: null, grants_authority: false},
    remaining: {custodian_seconds: 123.25, inputs: 17, requests: 21, frames: 33, frame_bytes: 456789},
    actors: [{actor_id: 'player-a', stage: 'active'}], latest_source: frame,
    last_operation: {schema: 'computer-operation/1', operation_id: 'op-one', kind: 'input',
      status: 'unknown', reason: 'receipt unavailable', source: null},
    native_returncode: 0, player_claims: [{id: 'claim-one', kind: 'claim', text: '<b>Saved</b>', data: {saved: true}}],
    host: {index: 2, model: 'test-model', provider: 'test-provider', requests_total: 4,
      max_requests_total: 10, host_seconds_remaining: 88.5, latest_response_wall: epoch / 1000}, ...overrides};
}
async function poll(value, first = false) {
  if (!first) run('void refresh()');
  await reply(request('/api/status'), value);
}
async function fetchFrame(frame) {
  await reply(request(`/api/source/${encodeURIComponent(frame.source_id)}`), null);
}
async function decode(index = 0) {
  const pending = decodes.splice(index, 1)[0];
  assert.ok(pending, 'Expected pending image decode');
  pending.resolve(); await tick(); return pending.image;
}
const text = id => {
  function read(item) { return [item.textContent, ...(item.children || []).map(read)].join(' '); }
  return read(element(id));
};

(async () => {
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8'), context);
  run('void refresh(); void refresh()');
  assert.equal(requests.length, 1, 'Status polling never overlaps');
  const one = source(1);
  await poll(status(one), true);
  assert.equal(element('frame').hidden, true, 'Never display an undecoded source');
  assert.match(text('frame-note'), /loading/i);
  assert.match(text('custodian-remaining'), /123.25/);
  assert.match(text('host-remaining'), /88.5/);
  assert.match(text('host-requests'), /4.*10/);
  assert.match(text('resource-remaining'), /17.*21.*33.*456789/);
  assert.match(text('ownership'), /player-a.*active/);
  assert.match(text('operation'), /unknown.*receipt unavailable/);
  assert.match(text('native-exit'), /0.*not.*Save/i);
  assert.match(text('player-claims'), /<b>Saved<\/b>/, 'Player text remains literal and labelled separately');
  await fetchFrame(one);
  epoch += 30;
  const firstImage = await decode();
  assert.equal(element('frame'), firstImage);
  assert.equal(firstImage.hidden, false);
  assert.match(text('source-details'), /800.*600.*1000.*750/);
  assert.match(text('source-details'), /10, 20, 780, 560/);
  assert.match(text('source-details'), new RegExp(String(one.presented_ms)));
  assert.match(text('source-details'), new RegExp(String(one.received_wall)));
  const first = JSON.parse(run('JSON.stringify(observerMeasurementSnapshot().rows[0])'));
  assert.deepEqual(first, {session: one.session, source_id: one.source_id, capture_id: 1,
    presented_ms: one.presented_ms, observed_at_wall_ms: epoch - 30,
    decode_finished_wall_ms: epoch, dom_replaced_wall_ms: epoch, outcome: 'displayed', error: null});
  await poll(status(one));
  assert.equal(requests.length, 0, 'An unchanged immutable source is not fetched again');

  // Decode A cannot be displayed under B's metadata, including a same-ID/different-SHA fault.
  const two = source(2);
  await poll(status(two)); await fetchFrame(two);
  const three = source(3);
  await poll(status(three)); await fetchFrame(three);
  await decode();
  assert.equal(element('frame').hidden, true, 'Superseded decode cannot replace the current image');
  assert.doesNotMatch(text('source-details'), /session-one-2/);
  await decode();
  assert.match(text('source-details'), /session-one-3/);
  const changedSHA = {...three, sha256: 'b'.repeat(64)};
  await poll(status(changedSHA));
  assert.equal(element('frame').hidden, true, 'SHA changes cannot reuse a decoded image');
  await fetchFrame(changedSHA); await decode();
  assert.match(text('source-details'), /bbbbbbbb/);
  assert.equal(run('observerMeasurementSnapshot().rows[1].outcome'), 'superseded');

  // Source failures retain no plausible image or success; same source can recover next poll.
  const four = source(4, {source_id: 'source/with spaces'});
  await poll(status(four));
  await reply(request('/api/source/source%2Fwith%20spaces'), null, 503);
  assert.equal(element('frame').hidden, true);
  assert.match(text('frame-note'), /unavailable.*503/i);
  await poll(status(four)); await fetchFrame(four);
  decodes.shift().reject(new Error('bad PNG')); await tick();
  assert.match(text('frame-note'), /unavailable.*bad PNG/i);
  await poll(status(four)); await fetchFrame(four); await decode();

  // Outage keeps the displayed source explicitly historical, and never creates a capture.
  run('void refresh()');
  request('/api/status').reject(new Error('offline')); await tick();
  assert.match(text('connection'), /unavailable/i);
  assert.match(text('status-error'), /offline/);
  assert.match(text('frame-note'), /retained.*status unavailable/i);
  assert.equal(requests.length, 0);
  await poll(status(null));
  assert.equal(element('frame').hidden, true);
  assert.match(text('frame-note'), /no.*source/i);
  await poll(status(null), false);
  assert.doesNotMatch(text('status-error'), /offline/);
  run('void refresh()'); await reply(request('/api/status'), {}, 503);
  assert.match(text('status-error'), /503/);
  await poll({schema: 'mission11'});
  assert.match(text('status-error'), /unsupported/i);

  // Pause submits independently while status is stalled; late GETs cannot erase the request.
  run('void refresh()');
  const stalledStatus = request('/api/status');
  element('pause').listeners.click();
  const pause = request('/api/pause');
  assert.equal(pause.options.method, 'POST');
  assert.equal(pause.options.headers['Content-Type'], 'application/json');
  assert.equal(pause.options.body, '{}');
  assert.equal(element('pause').disabled, true);
  assert.match(text('stop-state'), /requested.*not.*confirmed/i);
  element('pause').listeners.click();
  assert.equal(requests.length, 0, 'Repeated clicks do not repeat Pause');
  await reply(stalledStatus, status(null));
  assert.match(text('stop-state'), /requested.*not.*confirmed/i);
  pause.reject(new Error('lost Pause response')); await tick();
  assert.match(text('pause-error'), /lost Pause response/);
  assert.match(text('stop-state'), /requested.*not.*confirmed/i);
  await poll(status(null, {stop: {stop_requested: true, native_pause_confirmed: true, reason: 'user Pause'}}));
  assert.match(text('stop-state'), /native.*confirmed/i);

  // The finite network watchdog releases the polling lock and preserves honest uncertainty.
  run('void refresh()');
  const timeout = [...timers.values()].find(timer => timer.delay === 8000);
  assert.ok(timeout); timeout.callback(); await tick();
  assert.match(text('status-error'), /timed out/i);
  request('/api/status'); // The fake transport intentionally never settles.
  await poll(status(null));

  for (let index = 0; index < 2001; index++) {
    run(`retainTiming({session:'bounded',source_id:'s',capture_id:${index},presented_ms:0,observed_at_wall_ms:0,decode_finished_wall_ms:null,dom_replaced_wall_ms:null,outcome:'superseded',error:null})`);
  }
  const timing = JSON.parse(run('JSON.stringify(observerMeasurementSnapshot())'));
  assert.equal(timing.schema, 'observer-timing/4');
  assert.equal(timing.rows.length, 2000);
  assert.ok(timing.omitted_rows > 0);
  assert.equal(timing.rows.at(-1).capture_id, 2000);
  element('download-observer-measurements').listeners.click();
  const download = downloads.at(-1);
  const exported = JSON.parse(await blobs.get(download.url).text());
  assert.deepEqual(exported, timing);
  assert.match(download.name, /^enactive-observer-timing-\d+\.json$/);
  assert.equal(requests.length, 0, 'Timing download is entirely local');
  assert.ok([...elements.values()].every(item => !item.listeners.keydown && !item.listeners.pointerdown));
  console.log('Viewer passed: original source/decode joins; superseded and failed images; original budgets and labelled assertions; passive outage handling; independent permanent Pause; bounded polling and local observer-timing/4 export.');
})().catch(error => { console.error(error); process.exitCode = 1; });
