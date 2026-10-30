const assert = require('node:assert/strict');
const {validateText, validateSnapshotText, selectPage, intervalSummary, LIMITS} = require('../web/investigation-worker.js');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const clone = value => JSON.parse(JSON.stringify(value));
function event(id = 'e1', extra = {}) {
  return {id, kind: 'request', label: 'Request', text: '<script>hostile</script>',
    text_omitted_chars: 0, original_omitted_bytes: null, actor_id: 'actor/one', request_id: 'request1',
    tool_call_id: null, operation_id: null, program_id: null, run_id: null, native_id: null,
    source_id: null, start_wall_ms: 1000, end_wall_ms: 2000, clock: 'original wall approximation',
    elapsed_ms: 900, disposition: null, links: [], metrics: {}, ...extra};
}
function bundle() {
  return {schema: 'observer-investigation/1', cases: [{id: 'case-one', title: 'Recorded case', session: 's',
    source_commit: null, configuration: [], coverage: {event_candidates: 1, event_retained: 1,
      event_omitted: 0, source_candidates: 0, source_retained: 0, source_omitted: 0,
      observer_status: null, invalid_clocks: 0, notes: []}, events: [event()], sources: [], assessments: [],
    accounting: {attempts: null, host_seconds: null, configured_estimate_usd: null,
      missing_usage_attempts: null, conservative_reservation_usd: null}}]};
}
async function rejectEdit(edit, pattern) {
  const value = bundle(); edit(value); await assert.rejects(validateText(JSON.stringify(value), webcrypto), pattern);
}
(async () => {
  const model = await validateText(JSON.stringify(bundle()), webcrypto);
  assert.equal(model.cases[0].events[0].text, '<script>hostile</script>');
  const snapshot = {schema: 'observer-investigation-snapshot/1', session: 's', state: 'ready',
    snapshot_wall_ms: 2000, bundle: bundle(), error: null};
  assert.equal((await validateSnapshotText(JSON.stringify(snapshot), 's', webcrypto)).model.cases[0].session, 's');
  const tailed = await validateSnapshotText(JSON.stringify({...snapshot, snapshot_wall_ms: 3000}), 's', webcrypto);
  assert.deepEqual(tailed.model.indexes[0].bounds, [1000, 3000]);
  assert.equal(tailed.model.cases[0].events[0].end_wall_ms, 2000, 'Context axis extension never invents a request endpoint');
  assert.equal(intervalSummary(tailed.model.cases[0].events, tailed.model.indexes[0].bounds).uncovered_ms, 1000);
  const conflicting = await validateSnapshotText(JSON.stringify({...snapshot, snapshot_wall_ms: 900}), 's', webcrypto);
  assert.equal(conflicting.model.indexes[0].snapshotClockConflict, true);
  assert.deepEqual(conflicting.model.indexes[0].bounds, [1000, 2000]);
  const clocklessSnapshot = clone(snapshot); clocklessSnapshot.bundle.cases[0].events[0].clock = null;
  const noOrigin = await validateSnapshotText(JSON.stringify(clocklessSnapshot), 's', webcrypto);
  assert.equal(noOrigin.model.indexes[0].bounds, null);
  assert.match(noOrigin.model.indexes[0].snapshotAxisWarning, /No retained wall origin/);
  await assert.rejects(validateSnapshotText(JSON.stringify(snapshot), 'new-session', webcrypto), /changed session/);
  await assert.rejects(validateSnapshotText(JSON.stringify({...snapshot, arbitrary_path: 'private'}), 's', webcrypto), /unknown/);
  await assert.rejects(validateSnapshotText(JSON.stringify({...snapshot, bundle: {...bundle(), cases: []}}), 's', webcrypto), /1–4/);
  await assert.rejects(validateText('{', webcrypto), /JSON/);
  await assert.rejects(validateText(' '.repeat(LIMITS.encodedBytes + 1), webcrypto), /16 MiB/);
  await rejectEdit(b => b.schema = 'observer-investigation/2', /schema/);
  await rejectEdit(b => b.private_prompt = 'hidden', /unknown/);
  await rejectEdit(b => b.cases[0].events[0].metrics.raw_arguments = {}, /unknown/);
  await rejectEdit(b => b.cases[0].events[0].actor_id = {}, /string/);
  await rejectEdit(b => b.cases[0].events[0].text = '😀'.repeat(4001), /4000/);
  await rejectEdit(b => b.cases[0].events.push(event()), /duplicate/);
  await rejectEdit(b => b.cases[0].events[0].elapsed_ms = -1, /nonnegative/);
  await rejectEdit(b => b.cases[0].configuration = [{actor_id: 'a', key: 'secret'}], /unknown|missing/);
  await rejectEdit(b => b.cases[0].events = Array.from({length: 2001}, (_, i) => event(String(i))), /2000/);
  await rejectEdit(b => b.cases = Array.from({length: 5}, (_, i) => ({...clone(b.cases[0]), id: String(i)})), /1–4/);
  await rejectEdit(b => delete b.cases[0].events[0].run_id, /missing/);
  await rejectEdit(b => b.cases[0].events[0].metrics.first_content_ms = '1', /nonnegative/);
  await rejectEdit(b => b.cases[0].accounting.attempts = 0.5, /integer/);
  await rejectEdit(b => b.cases[0].coverage.event_omitted = 1, /coverage counts/);
  const unicode = bundle(); unicode.cases[0].events[0].text = '😀'.repeat(4000);
  await validateText(JSON.stringify(unicode), webcrypto);
  const config = {actor_id: 'a', model: null, provider: null, api: null, effort: null,
    requested_service_tier: null, provider_only: null, provider_order: null, allow_fallbacks: null};
  await rejectEdit(b => b.cases[0].configuration = [config, config, config], /at most 2/);
  await rejectEdit(b => b.cases[0].configuration = [{...config, provider_only: Array(33).fill('p')}], /at most 32/);
  await assert.rejects(validateText(JSON.stringify(bundle()).replace('"schema":', '"__proto__":{},"schema":'), webcrypto), /unknown/);
  const clocks = bundle();
  clocks.cases[0].events = [event('missing', {start_wall_ms: null}), event('inverted', {end_wall_ms: 1}),
    event('clockless', {clock: null}), event('omitted', {original_omitted_bytes: 27, text_omitted_chars: 3, links: ['absent']})];
  clocks.cases[0].coverage.event_candidates = clocks.cases[0].coverage.event_retained = 4;
  const checked = await validateText(JSON.stringify(clocks), webcrypto);
  assert.deepEqual(checked.indexes[0].unplottedIds, ['missing', 'inverted', 'clockless']);
  assert.equal(checked.cases[0].events[3].original_omitted_bytes, 27);
  assert.equal(checked.indexes[0].danglingLinks, 1);
  assert.deepEqual(checked.indexes[0].bounds, [1000, 2000]);
  const points = bundle();
  points.cases[0].events = [event('frame', {kind: 'source', end_wall_ms: null, elapsed_ms: null}),
    event('program-result', {kind: 'program', start_wall_ms: null}), event('censored-request', {end_wall_ms: null})];
  points.cases[0].coverage.event_candidates = points.cases[0].coverage.event_retained = 3;
  const pointModel = await validateText(JSON.stringify(points), webcrypto);
  assert.deepEqual(pointModel.indexes[0].pointIds, ['frame', 'program-result']);
  assert.deepEqual(pointModel.indexes[0].unplottedIds, ['censored-request']);
  assert.equal(pointModel.cases[0].events[0].elapsed_ms, null, 'A timestamp point never invents zero-duration work');
  assert.equal(selectPage(pointModel.cases[0].events, {start: 999, end: 1001}).rows[0].id, 'frame');
  const timing = intervalSummary([event('r', {start_wall_ms: 1000, end_wall_ms: 2000}),
    event('t', {kind: 'tool', start_wall_ms: 1500, end_wall_ms: 2500}), event('missing', {end_wall_ms: null})], [0, 3000]);
  assert.deepEqual(timing, {elapsed_ms: 3000, request_wall_union_ms: 1000, tool_wall_union_ms: 1000,
    overlap_ms: 500, uncovered_ms: 1500, no_full_wall_span: 1});
  const many = Array.from({length: 121}, (_, i) => event(`e${i}`, {kind: i % 2 ? 'request' : 'source'}));
  assert.equal(selectPage(many, {page: 1}).rows[0].id, 'e50');
  assert.equal(selectPage(many, {page: 2}).rows.length, 21);
  assert.equal(selectPage(many, {kind: 'source', page: 1}).rows.length, 11);
  assert.equal(selectPage(many, {query: '<script>'}).total, 121);
  assert.equal(selectPage(many, {start: 1500, end: 1600}).total, 121);
  assert.equal(selectPage(many, {start: 3000, end: 4000}).total, 0);
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1sAAAAASUVORK5CYII=', 'base64');
  const sha = Buffer.from(await webcrypto.subtle.digest('SHA-256', png)).toString('hex');
  const images = bundle();
  images.cases[0].sources = [{source_id: 'image1', capture_id: 1, presented_ms: null, received_wall_ms: 2000,
    sha256: sha, width: 1, height: 1, png_base64: png.toString('base64'), unavailable_reason: null}];
  images.cases[0].coverage.source_candidates = images.cases[0].coverage.source_retained = 1;
  const extraImages = clone(images); extraImages.cases[0].sources = Array.from({length: 17}, (_, i) => ({...clone(images.cases[0].sources[0]), source_id: String(i)}));
  await assert.rejects(validateText(JSON.stringify(extraImages), webcrypto), /16 PNG/);
  const stringCapture = clone(images); stringCapture.cases[0].sources[0].capture_id = '1';
  await assert.rejects(validateText(JSON.stringify(stringCapture), webcrypto), /nonnegative/);
  let parsed = await validateText(JSON.stringify(images), webcrypto);
  assert.equal(parsed.cases[0].sources[0].bytes.byteLength, png.length);
  // A valid large ancillary PNG chunk exercises the full permitted base64 path.
  // Use the platform CRC implementation, not a test PNG decoder.
  const {crc32} = require('node:zlib');
  const payload = Buffer.concat([Buffer.from('Comment\0'), Buffer.alloc(6 * 1024 * 1024, 65)]);
  const chunk = Buffer.alloc(payload.length + 12); chunk.writeUInt32BE(payload.length);
  chunk.write('tEXt', 4); payload.copy(chunk, 8);
  chunk.writeUInt32BE(crc32(chunk.subarray(4, -4)), chunk.length - 4);
  const largePng = Buffer.concat([png.subarray(0, 33), chunk, png.subarray(33)]);
  const largeImage = clone(images);
  largeImage.cases[0].sources[0].png_base64 = largePng.toString('base64');
  largeImage.cases[0].sources[0].sha256 = Buffer.from(await webcrypto.subtle.digest('SHA-256', largePng)).toString('hex');
  const largeModel = await validateText(JSON.stringify(largeImage), webcrypto);
  assert.equal(largeModel.cases[0].sources[0].bytes.byteLength, largePng.length, 'Valid multi-MiB base64 does not exhaust the regexp stack');
  images.cases[0].sources[0].sha256 = '0'.repeat(64);
  parsed = await validateText(JSON.stringify(images), webcrypto);
  assert.match(parsed.cases[0].sources[0].unavailable_reason, /digest/);
  assert.equal(parsed.cases[0].sources[0].bytes, null);
  images.cases[0].sources[0].width = 99999;
  images.cases[0].sources[0].height = 99999;
  parsed = await validateText(JSON.stringify(images), webcrypto);
  assert.match(parsed.cases[0].sources[0].unavailable_reason, /64 MiB/);
  images.cases[0].sources[0].width = 1; images.cases[0].sources[0].height = 1;
  images.cases[0].sources[0].png_base64 = 'bad';
  parsed = await validateText(JSON.stringify(images), webcrypto);
  assert.match(parsed.cases[0].sources[0].unavailable_reason, /base64/);
  const animation = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACGFjVEwAAAACAAAAAPONk3AAAAAaZmNUTAAAAAAAAAABAAAAAQAAAAAAAAAAAAEAZAAAGDbW+gAAAA1JREFUeJxj+M/A8B8ABQAB/4mZPR0AAAAaZmNUTAAAAAEAAAABAAAAAQAAAAAAAAAAAAEAZAAAg0U8LgAAABFmZEFUAAAAAnicY2Bg+P8fAAMCAf/1e6XXAAAAAElFTkSuQmCC', 'base64');
  images.cases[0].sources[0].png_base64 = animation.toString('base64');
  images.cases[0].sources[0].sha256 = Buffer.from(await webcrypto.subtle.digest('SHA-256', animation)).toString('hex');
  parsed = await validateText(JSON.stringify(images), webcrypto);
  assert.equal(parsed.cases[0].sources[0].bytes, null);
  assert.match(parsed.cases[0].sources[0].unavailable_reason, /animated PNG/);
  await workerChecks();
  await readerChecks(model);
  console.log('Investigation worker validation, original evidence, clock limits, image bounds, pagination and reader cancellation passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });

async function readerChecks(model) {
  model = clone(model);
  model.cases[0].events.push(event('native-child', {kind: 'native', label: 'Native receipt',
    disposition: 'completed', links: ['e1']}));
  model.cases[0].events[0].program_id = 'version-one';
  model.cases[0].events.push(event('saved-version', {kind: 'tool', label: 'player_program_save', program_id: 'version-one'}));
  model.cases[0].assessments.push({label: 'Reviewed note', text: 'Fallible assessment',
    attribution: 'reviewer', reference: 'retained report', evidence_ids: ['e1']});
  const workers = [], timers = new Map(), urls = new Set(), revoked = [], images = [];
  let timerId = 0;
  class Node {
    constructor(tag) { this.tag = tag; this.children = []; this.listeners = {}; this.dataset = {}; this.value = ''; this.className = ''; this.attributes = {};
      this.classList = {add: () => {}, remove: () => {}, toggle: () => {}}; }
    set textContent(value) { this.text = String(value); this.children = []; }
    get textContent() { return (this.text || '') + this.children.map(c => c.textContent || '').join(''); }
    set innerHTML(_) { assert.fail('Data must never become HTML'); }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; this.text = ''; }
    setAttribute(key, value) { this.attributes[key] = value; }
    removeAttribute(key) { delete this.attributes[key]; }
    addEventListener(type, callback) { this.listeners[type] = callback; }
    querySelectorAll(selector) { const all = descendants(this); return all.filter(n => selector === '[data-event-id]' && n.dataset.eventId); }
    contains(node) { return descendants(this).includes(node); }
    focus() { doc.activeElement = this; }
  }
  function descendants(node) { return node.children.flatMap(c => [c, ...descendants(c)]); }
  const doc = {createElement: tag => new Node(tag), createElementNS: (_, tag) => new Node(tag), activeElement: null};
  const root = new Node('root'); root.ownerDocument = doc;
  const context = vm.createContext({document: doc, Blob, console,
    Worker: class {
      constructor(url) { this.url = url; this.messages = []; this.terminated = false; workers.push(this); }
      postMessage(data) { this.messages.push(data); }
      terminate() { this.terminated = true; }
    },
    Image: class extends Node {
      constructor() { super('img'); images.push(this); this.naturalWidth = this.naturalHeight = 1; }
      decode() { return new Promise((resolve, reject) => { this.resolve = resolve; this.reject = reject; }); }
    },
    URL: {createObjectURL() { const url = `blob:owned-${urls.size + revoked.length}`; urls.add(url); return url; },
      revokeObjectURL(url) { revoked.push(url); urls.delete(url); }},
    setTimeout(callback, delay) { timers.set(++timerId, {callback, delay}); return timerId; },
    clearTimeout(id) { timers.delete(id); }});
  vm.runInContext(fs.readFileSync(require.resolve('../web/investigation.js'), 'utf8'), context);
  const api = context.EnactiveInvestigation.mount(root, {workerSource: '/* worker fixture */', initialText: '{}'});
  assert.equal(workers.length, 1); assert.equal(workers[0].messages[0].text, '{}');
  assert.equal([...timers.values()][0].delay, 30000);
  const stale = workers[0];
  api.loadFile({name: 'selected.json', size: 2});
  assert.equal(stale.terminated, true); assert.ok(revoked.includes(stale.url));
  stale.onmessage({data: {type: 'loaded', model}});
  assert.equal(workers[1].messages.length, 1, 'superseded load cannot render/request a page');
  const active = workers[1];
  active.onmessage({data: {type: 'loaded', model}});
  assert.equal(timers.size, 0);
  const pageRequest = active.messages.at(-1);
  assert.equal(pageRequest.type, 'page');
  active.onmessage({data: {type: 'page', token: pageRequest.token, ...selectPage(model.cases[0].events)}});
  const row = descendants(root).find(n => n.dataset.eventId === 'e1');
  assert.ok(row); row.listeners.click();
  assert.ok(root.textContent.includes('<script>hostile</script>'), 'hostile public text stays literal');
  assert.match(root.textContent, /Same program version: authoring \/ read records/);
  assert.ok(descendants(root).some(n => n.tag === 'button' && n.textContent === 'player_program_save · saved-version'));
  const reverseLink = descendants(root).find(n => n.tag === 'button' && n.textContent === 'Native receipt · native-child');
  assert.ok(reverseLink, 'A child can navigate to a native record that explicitly references it');
  reverseLink.listeners.click();
  assert.match(root.textContent, /Recorded disposition: completed/);
  assert.equal(doc.activeElement.textContent, 'Original evidence');
  const assessment = descendants(root).find(n => n.tag === 'article');
  const assessmentLink = descendants(assessment).find(n => n.tag === 'button');
  doc.activeElement = assessmentLink;
  assessmentLink.listeners.click();
  assert.equal(doc.activeElement.textContent, 'Original evidence', 'Assessment links bring the destination into view through focus');
  const sourceInput = descendants(root).find(n => n.tag === 'select' && n.id.endsWith('-source'));
  const sourceLabel = descendants(root).find(n => n.id === sourceInput.attributes['aria-labelledby']);
  assert.equal(sourceLabel.textContent, 'Exact source ID', 'The selected option does not become part of the field label');
  const search = descendants(root).find(n => n.type === 'search');
  search.value = 'request1'; search.listeners.input();
  assert.equal(active.messages.at(-1).filters.query, 'request1');
  const lastPageToken = active.messages.at(-1).token;
  active.onmessage({data: {type: 'page', token: pageRequest.token, rows: [], total: 0, page: 0, pages: 1}});
  assert.ok(descendants(root).some(n => n.dataset.eventId === 'e1'), 'stale page response ignored');
  assert.ok(lastPageToken > pageRequest.token);
  api.loadFile({size: 10});
  const timedOut = workers.at(-1);
  assert.equal(active.terminated, false, 'Validated evidence keeps its paging worker while a candidate loads');
  const selectedBeforeFailure = descendants(root).find(n => n.dataset.eventId === 'e1');
  [...timers.values()][0].callback();
  assert.equal(timedOut.terminated, true);
  assert.match(root.textContent, /30 seconds/);
  assert.equal(descendants(root).find(n => n.dataset.eventId === 'e1'), selectedBeforeFailure,
    'Failed replacement preserves the actual selected DOM/inspection rather than reconstructing it');
  assert.equal(descendants(root).find(n => n.className === 'ir-content').hidden, false);
  api.loadFile({size: 10});
  const cancelled = workers.at(-1);
  descendants(root).find(n => n.tag === 'button' && n.textContent === 'Cancel import').listeners.click();
  assert.equal(cancelled.terminated, true); assert.equal(timers.size, 0);
  assert.match(root.textContent, /cancelled/);
  // A single inspector keeps cancelled decode memory reserved until settlement.
  api.loadFile({size: 10});
  const imageModel = clone(model);
  imageModel.cases[0].sources = ['one', 'two'].map(source_id => ({source_id, width: 1, height: 1,
    bytes: new Uint8Array([137, 80]), unavailable_reason: null}));
  const imageWorker = workers.at(-1);
  imageWorker.onmessage({data: {type: 'loaded', model: imageModel}});
  const sourceSelect = descendants(root).find(n => n.tag === 'select' && n.children.some(c => c.value === 'one'));
  sourceSelect.value = 'one'; sourceSelect.listeners.change(); assert.equal(images.length, 1);
  sourceSelect.value = 'two'; sourceSelect.listeners.change();
  assert.equal(images.length, 1, 'do not start another decode before the cancelled decode settles');
  const decodeTimer = [...timers.values()].find(value => value.delay === 8000);
  assert.ok(decodeTimer); decodeTimer.callback();
  assert.match(root.textContent, /decode exceeded 8 seconds/);
  assert.equal(images.length, 1, 'Timeout never starts another image over a still-reserved decoder');
  images[0].reject(new Error('cancelled'));
  await new Promise(setImmediate); assert.equal(images.length, 2);
  images[1].resolve(); await new Promise(setImmediate);
  assert.match(root.textContent, /Original 1 × 1 PNG/);
  api.destroy(); assert.equal(imageWorker.terminated, true); assert.equal(urls.size, 0);
  assert.equal(root.children.length, 0);
  api.destroy(); api.loadFile({size: 2}); assert.equal(workers.at(-1), imageWorker);
}

async function workerChecks() {
  const messages = [];
  const self = {postMessage: message => messages.push(message)};
  const context = vm.createContext({self, crypto: webcrypto, TextEncoder, atob, Uint8Array, DataView});
  vm.runInContext(fs.readFileSync(require.resolve('../web/investigation-worker.js'), 'utf8'), context);
  await self.onmessage({data: {type: 'load', file: {size: 50, text: async () => JSON.stringify(bundle())}}});
  assert.equal(messages[0].type, 'loaded');
  await self.onmessage({data: {type: 'page', caseIndex: 0, token: 9, filters: {}}});
  assert.equal(messages[1].token, 9); assert.equal(messages[1].rows[0].id, 'e1');
  await self.onmessage({data: {type: 'load', file: {size: LIMITS.encodedBytes + 1, text() { assert.fail('oversized File must not be read'); }}}});
  assert.equal(messages[2].type, 'error'); assert.match(messages[2].message, /16 MiB/);
}
