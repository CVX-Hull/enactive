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
    setAttribute(key, value) { this[key] = value; },
    focus() { context.document.activeElement = this; this.listeners.focus?.(); },
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
  replaceWith(other) { elements.set(this.id || 'frame', other); }
}
const context = vm.createContext({Blob, AbortController, Image: DeferredImage,
  Date: class extends Date { static now() { return epoch; } },
  URL: {createObjectURL(blob) { const id = `blob:${blobs.size}`; blobs.set(id, blob); return id; }, revokeObjectURL() {}},
  document: {getElementById: element, createTextNode(text) { return {textContent: text}; }, createElement(tag) {
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
  assert.equal(typeof element('tab-watch').listeners.keydown, 'function', 'Observer tabs support keyboard navigation');
  run('void refresh(); void refresh()');
  assert.equal(requests.filter(item => item.url === '/api/status').length, 1, 'Status polling never overlaps');
  await reply(request('/api/activity'), {schema:'observer-activity/1', session:'session-one', revision:0, entries:[]});
  element('pause').listeners.click();
  const beforeStatusPause = request('/api/pause');
  assert.equal(beforeStatusPause.options.body, '{}', 'Pause dispatches before any status');
  assert.match(text('stop-state'), /session unknown/i);
  const one = source(1);
  await poll(status(one), true);
  assert.equal(element('pause').disabled, false, 'An unidentified old pending intent cannot disable a newly identified session');
  await reply(beforeStatusPause, {native_pause_confirmed:true});
  assert.match(text('pause-error'), /unsupported|unidentified/i);
  assert.doesNotMatch(text('stop-state'), /native Pause confirmed/);
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
  assert.match(text('pause-error'), /already confirmed for this session/);
  assert.doesNotMatch(text('pause-error'), /remain unknown|new emergency intent/,
    'Confirmation arriving after response loss refreshes feedback from current facts');

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
  assert.ok([...elements.values()].every(item => !item.listeners.pointerdown));
  assert.equal(typeof element('tab-timeline').listeners.keydown, 'function');
  // Tabs move focus independently of manual activation, with no game controls.
  const key = key => ({key, preventDefault() { this.prevented = true; }});
  element('tab-watch').listeners.keydown(key('ArrowRight'));
  assert.equal(context.document.activeElement, element('tab-timeline'));
  assert.equal(run('activeView'), 'watch', 'Arrow navigation does not trigger a perceptibly loaded view');
  element('tab-timeline').listeners.keydown(key('Enter'));
  assert.equal(run('activeView'), 'timeline');

  // A historical Pause response cannot confirm a new admission. An actual new
  // receiver can identify itself before its status, and stop evidence is monotone.
  const twoSession = status(null, {session:'session-two', target:null, stop:{stop_requested:false,native_pause_confirmed:false}});
  await poll(twoSession);
  assert.equal(element('pause').disabled, false, 'Old permanent Pause is not inherited by a fresh session');
  element('pause').listeners.click();
  const oldPause = request('/api/pause');
  await poll(status(null, {session:'session-three', target:null, stop:{}}));
  assert.equal(element('pause').disabled, false, 'Old pending Pause cannot disable the fresh session');
  await reply(oldPause, {schema:'computer-pause/1',session:'session-two',stop:{stop_requested:true,native_pause_confirmed:true}});
  assert.equal(element('pause').disabled, false);
  assert.match(text('stop-history'), /Historical Pause.*session-two.*native Pause confirmed/);
  assert.equal(element('pause-error').hidden, true, 'Old success is history, not a current-session error');
  element('pause').listeners.click();
  const replacementPause = request('/api/pause');
  run('void refresh()');
  const oldStatus = request('/api/status');
  await reply(replacementPause, {schema:'computer-pause/1',session:'session-four',stop:{stop_requested:true,native_pause_confirmed:true,reason:'operator'}});
  assert.equal(run('currentSession'), 'session-four');
  await reply(oldStatus, status(null, {session:'session-three', stop:{}}));
  assert.equal(run('currentSession'), 'session-four', 'Late old status cannot restore an earlier session');
  await poll(status(null, {session:'session-four',stop:{stop_requested:false,native_pause_confirmed:false}}));
  assert.match(text('stop-state'), /native Pause confirmed/, 'Earlier same-session facts cannot erase a confirmation');

  await poll(status(null, {session:'same-session-lost-response',stop:{}}));
  element('pause').listeners.click();
  const sameSessionLost = request('/api/pause');
  await poll(status(null, {session:'same-session-lost-response',stop:{stop_requested:true,native_pause_confirmed:true}}));
  sameSessionLost.reject(new Error('POST response lost'));
  await tick();
  assert.match(text('pause-error'), /already confirmed for this session/);
  assert.doesNotMatch(text('pause-error'), /remain unknown|new emergency intent/);
  assert.match(text('stop-state'), /native Pause confirmed/);

  await poll(status(null, {session:'lost-old-session',stop:{}}));
  element('pause').listeners.click();
  const lostOldPause = request('/api/pause');
  await poll(status(null, {session:'confirmed-current-session',stop:{stop_requested:true,native_pause_confirmed:true}}));
  lostOldPause.reject(new Error('Old response lost'));
  await tick();
  assert.equal(element('pause-error').hidden, true, 'An old lost response cannot replace current-session feedback');
  assert.match(text('stop-state'), /native Pause confirmed/);
  assert.equal(element('pause').disabled, true);

  await poll(status(null, {session:'old-success-pending',stop:{}}));
  element('pause').listeners.click();
  const delayedOldSuccess = request('/api/pause');
  await poll(status(null, {session:'confirmed-after-old-success',stop:{}}));
  element('pause').listeners.click();
  const lostCurrentResponse = request('/api/pause');
  await poll(status(null, {session:'confirmed-after-old-success',stop:{stop_requested:true,native_pause_confirmed:true}}));
  lostCurrentResponse.reject(new Error('Current response unavailable'));
  await tick();
  const currentFeedback = text('pause-error');
  await reply(delayedOldSuccess,{schema:'computer-pause/1',session:'old-success-pending',stop:{stop_requested:true,native_pause_confirmed:true}});
  assert.equal(text('pause-error'),currentFeedback,'Old success cannot replace a current diagnostic');
  assert.match(text('stop-history'),/old-success-pending.*native Pause confirmed/);
  assert.match(text('stop-state'),/native Pause confirmed/);

  await poll(status(null, {session:'session-five',stop:{}}));
  assert.match(text('stop-history'),/Historical Pause.*confirmed-after-old-success.*native Pause confirmed/);
  const activity = (entries, overrides={}) => ({schema:'observer-activity/1',session:'session-five',revision:1,entries,latest_statement:null,omitted_entries:0,coverage:{host:'available',computer:'available'},...overrides});
  const event = (id, overrides={}) => ({id,session:'session-five',producer:'host',actor_id:'actor-a',kind:'assistant-text',request_id:'same-local-request',text:'<img src=x onerror=boom> literal statement',created_wall:epoch/1000,omitted_bytes:7,display_omitted_bytes:3,...overrides});
  async function activityPoll(snapshot) { run('void refreshActivity()'); await reply(request('/api/activity'), snapshot); }
  const a = event('host:actor-a:1');
  const b = event('host:actor-b:1',{actor_id:'actor-b',kind:'request-start',text:null});
  await activityPoll(activity([a,b],{latest_statement:a,omitted_entries:6}));
  assert.match(text('latest-statement'), /<img src=x onerror=boom>/, 'Narration remains literal untrusted text');
  assert.match(text('statement-meta'), /7 original bytes omitted; 3 further/);
  assert.match(text('activity-summary'), /6 omitted/);
  const row = element('activity-list').children[0].children[0];
  element('activity-list').scrollTop = 80;
  row.focus(); row.listeners.click();
  assert.equal(run('following'), false);
  assert.match(text('entry-links'), /No other retained entry/, 'Duplicate actor-local request IDs never link different actors');
  assert.match(text('inspection-frame-note'), /no explicit source relationship/);
  const c = event('host:actor-a:2',{kind:'tool-result',status:'unknown',text:null,operation_id:'op-original',original_dispositions:[{status:'unknown'}],additional_collection_dispositions:[{status:'completed'}]});
  await activityPoll(activity([a,b,c],{latest_statement:a,revision:2}));
  assert.equal(element('activity-list').children[0].children[0], row, 'Polling preserves the actual focused row DOM');
  assert.equal(context.document.activeElement, row);
  assert.equal(element('activity-list').scrollTop, 80);
  assert.equal(run('selectedEntry.id'), a.id);
  assert.match(text('new-items'), /1 new retained/);
  assert.equal(run('activitySnapshots.get(currentSession).entries.length'), 2, 'Frozen inspection retains one bounded snapshot, not another advancing copy');
  element('follow-latest').listeners.click();
  await reply(request('/api/activity'), activity([a,b,c]));
  assert.equal(element('activity-list').children.length, 3);
  element('activity-list').children[2].children[0].listeners.click();
  assert.match(text('entry-details'), /original_dispositions.*|original_dispositions/s);
  assert.match(text('entry-details'), /additional_collection_dispositions/);

  // Inspection image completion never substitutes an old selection, updates
  // Watch measurements or supplies previous-session pixels from a new server.
  const linked = source(99,{session:'session-five',source_id:'five-source'});
  element('follow-latest').listeners.click();
  await reply(request('/api/activity'),activity([event('linked',{source:linked}),a]));
  const timingBefore = run('observerMeasurementSnapshot().rows.length');
  element('activity-list').children[0].children[0].listeners.click();
  await fetchFrame(linked);
  element('activity-list').children[1].children[0].listeners.click();
  await decode();
  assert.equal(element('inspection-frame').hidden,true,'Late selected-source decode cannot replace an entry without source');
  assert.match(text('inspection-frame-note'), /no explicit source relationship/);
  assert.equal(run('observerMeasurementSnapshot().rows.length'),timingBefore,'Timeline source loading does not contaminate Watch timing');
  element('activity-list').children[0].children[0].listeners.click();
  await reply(request('/api/source/five-source'),null,404);
  assert.match(text('inspection-frame-note'), /unavailable.*404/i);
  await poll(status(null,{session:'session-six',stop:{}}));
  assert.match(text('inspection-frame-note'), /historical session/);
  assert.equal(requests.filter(item=>item.url.includes('/api/source/')).length,0,'Previous-session pixels are not fetched from replacement server');
  assert.match(text('inspection-scope'), /session-five/);
  assert.match(text('current-session'), /session-six/);
  element('pause').listeners.click();
  const timelinePause=request('/api/pause');
  assert.equal(timelinePause.options.body,'{}','Pause is available from Timeline while inspecting history');
  await reply(timelinePause,{schema:'computer-pause/1',session:'session-six',stop:{stop_requested:true,native_pause_confirmed:true}});
  assert.match(text('stop-state'),/native Pause confirmed/);

  // Session-scoped activity is discarded after replacement, including an old
  // response that was already in flight. Missing coverage remains explicit.
  run('void refreshActivity()'); const staleActivity=request('/api/activity');
  await poll(status(null,{session:'session-seven',stop:{}}));
  await reply(staleActivity,activity([a]));
  assert.match(text('activity-summary'),/not yet received/);
  element('follow-latest').listeners.click();
  const sevenEntries=Array.from({length:205},(_,index)=>event(`seven-${index}`,{session:'session-seven'}));
  await reply(request('/api/activity'),activity(sevenEntries,{session:'session-seven',latest_statement:a,coverage:{host:'unavailable:OSError',computer:'available'}}));
  assert.equal(run('activitySnapshots.get(currentSession).entries.length'),200);
  assert.ok(run('activitySnapshots.size')<=2);
  assert.match(text('latest-statement'),/No public statement/,'A wrong-session statement cannot be presented as current');
  assert.match(text('activity-coverage'),/unavailable:OSError/);
  assert.match(text('activity-summary'),/5 further omitted/);
  run('void refreshActivity()');
  await reply(request('/api/activity'),activity(sevenEntries,{session:'session-seven',omitted_entries:null,coverage:{host:'available',computer:'unavailable:OSError',computer_operations:null}}));
  assert.match(text('activity-summary'),/omissions unknown/);

  const requestsBeforeZoom=requests.length;
  element('watch-size').listeners.click();
  assert.equal(element('watch-size')['aria-pressed'],'true');
  assert.match(element('watch-frame-shell').className,/actual-pixels/);
  element('inspection-size').listeners.click();
  assert.match(element('inspection-frame-shell').className,/actual-pixels/);
  assert.equal(requests.length,requestsBeforeZoom,'Pixel-size presentation creates no source or control request');
  assert.match(run('observerMeasurementSnapshot().scope'),/hidden Watch/);
  run('void refreshActivity()'); request('/api/activity').reject(new Error('projection offline')); await tick();
  assert.match(text('activity-error'),/projection offline.*current activity unknown/);
  assert.equal(element('activity-list').children.length,200,'Outage retains labelled evidence');
  run("deepLink={session:'evicted-session',event:'missing'};resolveDeepLink()");
  assert.match(text('inspection-heading'),/unavailable/);
  assert.equal(element('inspection-frame').hidden,true);

  // Isolated page: Pause identifies the actual receiver before any status.
  // The already-pending initial GET from an unknown older receiver is fenced.
  const freshContext = vm.createContext({...context});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8'), freshContext);
  const unknownOldStatus = request('/api/status');
  const unknownActivity = request('/api/activity');
  element('pause').listeners.click();
  await reply(request('/api/pause'), {schema:'computer-pause/1',session:'actual-receiver',stop:{stop_requested:true,native_pause_confirmed:true}});
  await reply(unknownOldStatus,status(null,{session:'unseen-old-session',stop:{}}));
  assert.equal(vm.runInContext('currentSession',freshContext),'actual-receiver');
  assert.match(text('stop-state'),/native Pause confirmed/);
  await reply(unknownActivity,activity([]));

  console.log('Viewer passed: original source/decode joins; superseded and failed images; original budgets and labelled assertions; passive outage handling; independent permanent Pause; bounded polling and local observer-timing/4 export; session/Pause races; inert narration; frozen selection/focus; explicit gaps and bounded activity.');
})().catch(error => { console.error(error); process.exitCode = 1; });
