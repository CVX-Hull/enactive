/* Closed recorded-evidence ingress. This worker has no transport or runtime authority. */
'use strict';
const LIMITS = Object.freeze({encodedBytes: 16 * 1024 * 1024, cases: 4, events: 2000,
  sources: 16, pixels: 64 * 1024 * 1024, page: 50});
const KINDS = ['request', 'tool', 'program', 'operation', 'native', 'source', 'statement', 'observer'];
const METRICS = ['input_tokens', 'output_tokens', 'reasoning_tokens', 'cache_read_tokens',
  'cache_write_tokens', 'payload_bytes', 'text_bytes', 'image_bytes', 'image_parts',
  'projection_ms', 'first_body_ms', 'first_content_ms', 'first_tool_argument_ms', 'headers_ms'];
function fail(path, message) { throw new Error(`${path}: ${message}`); }
function object(value, fields, path, optional = false) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) fail(path, 'expected object');
  for (const key of Object.keys(value)) if (!fields.includes(key)) fail(path, `unknown field ${key.slice(0, 80)}`);
  if (!optional) for (const key of fields) if (!Object.hasOwn(value, key)) fail(path, `missing ${key}`);
}
function string(value, max, path, nullable = false) {
  if (nullable && value === null) return null;
  if (typeof value !== 'string') fail(path, 'expected string');
  let count = 0;
  for (const unused of value) { if (++count > max) fail(path, `exceeds ${max} characters`); }
  return value;
}
function number(value, path, nullable = true, integer = false) {
  if (nullable && value === null) return null;
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || (integer && !Number.isSafeInteger(value))) {
    fail(path, 'expected finite nonnegative number' + (integer ? ' integer' : ''));
  }
  return value;
}
function array(value, max, path, item) {
  if (!Array.isArray(value) || value.length > max) fail(path, `expected array of at most ${max}`);
  return value.map((entry, i) => item(entry, `${path}[${i}]`));
}
const identity = (v, p, nullable = true) => string(v, 256, p, nullable);
const note = (v, p, nullable = true) => string(v, 1000, p, nullable);
function unique(values, field, path) {
  const seen = new Set();
  for (const value of values) { if (seen.has(value[field])) fail(path, `duplicate ${field}`); seen.add(value[field]); }
}
function configuration(v, p) {
  const fields = ['actor_id', 'model', 'provider', 'api', 'effort', 'requested_service_tier',
    'provider_only', 'provider_order', 'allow_fallbacks'];
  object(v, fields, p);
  const out = {};
  for (const field of fields.slice(0, 6)) out[field] = identity(v[field], `${p}.${field}`);
  for (const field of ['provider_only', 'provider_order']) out[field] = v[field] === null ? null :
    array(v[field], 32, `${p}.${field}`, (x, q) => identity(x, q, false));
  if (v.allow_fallbacks !== null && typeof v.allow_fallbacks !== 'boolean') fail(p, 'allow_fallbacks must be boolean or null');
  out.allow_fallbacks = v.allow_fallbacks;
  return out;
}
function event(v, p) {
  const fields = ['id', 'kind', 'label', 'text', 'text_omitted_chars', 'original_omitted_bytes',
    'actor_id', 'request_id', 'tool_call_id', 'operation_id', 'program_id', 'run_id', 'native_id',
    'source_id', 'start_wall_ms', 'end_wall_ms', 'clock', 'elapsed_ms', 'disposition', 'links', 'metrics'];
  object(v, fields, p);
  const out = {id: identity(v.id, `${p}.id`, false), kind: v.kind};
  if (!KINDS.includes(v.kind)) fail(p, 'unknown event kind');
  out.label = string(v.label, 240, `${p}.label`);
  out.text = string(v.text, 4000, `${p}.text`);
  out.text_omitted_chars = number(v.text_omitted_chars, `${p}.text_omitted_chars`, false, true);
  out.original_omitted_bytes = number(v.original_omitted_bytes, `${p}.original_omitted_bytes`, true, true);
  for (const field of fields.slice(6, 14)) out[field] = identity(v[field], `${p}.${field}`);
  for (const field of ['start_wall_ms', 'end_wall_ms', 'elapsed_ms']) out[field] = number(v[field], `${p}.${field}`);
  out.clock = note(v.clock, `${p}.clock`);
  out.disposition = note(v.disposition, `${p}.disposition`);
  out.links = array(v.links, 64, `${p}.links`, (x, q) => identity(x, q, false));
  object(v.metrics, METRICS, `${p}.metrics`, true);
  out.metrics = {};
  for (const key of Object.keys(v.metrics)) out.metrics[key] = number(v.metrics[key], `${p}.metrics.${key}`);
  return out;
}
async function source(v, p, cryptoAPI) {
  const fields = ['source_id', 'capture_id', 'presented_ms', 'received_wall_ms', 'sha256', 'width', 'height', 'png_base64', 'unavailable_reason'];
  object(v, fields, p);
  const out = {source_id: identity(v.source_id, `${p}.source_id`, false)};
  out.capture_id = number(v.capture_id, `${p}.capture_id`, true, true);
  for (const field of ['presented_ms', 'received_wall_ms']) out[field] = number(v[field], `${p}.${field}`);
  out.sha256 = identity(v.sha256, `${p}.sha256`);
  for (const field of ['width', 'height']) out[field] = number(v[field], `${p}.${field}`, true, true);
  out.unavailable_reason = note(v.unavailable_reason, `${p}.unavailable_reason`);
  out.bytes = null;
  if (v.png_base64 === null) {
    if (!out.unavailable_reason) fail(p, 'missing bytes require unavailable_reason');
    return out;
  }
  if (typeof v.png_base64 !== 'string') fail(p, 'png_base64 must be string or null');
  function unavailable(reason) { out.unavailable_reason = reason; return out; }
  if (!out.width || !out.height || out.width * out.height * 4 > LIMITS.pixels) return unavailable('Image unavailable: exceeds 64 MiB RGBA pixel budget or missing geometry.');
  const encoded = v.png_base64, padding = encoded.endsWith('==') ? 2 : encoded.endsWith('=') ? 1 : 0;
  // A repeated-group regexp can exhaust V8's stack on valid multi-MiB PNGs.
  const alphabet = encoded.slice(0, encoded.length - padding);
  if (encoded.length % 4 || /[^A-Za-z0-9+/]/.test(alphabet)) return unavailable('Image unavailable: malformed base64.');
  const binary = atob(v.png_base64);
  const bytes = Uint8Array.from(binary, character => character.charCodeAt(0));
  if (bytes.length < 33 || ![137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82].every((x, i) => bytes[i] === x)) return unavailable('Image unavailable: malformed PNG header.');
  const header = new DataView(bytes.buffer);
  if (header.getUint32(16) !== out.width || header.getUint32(20) !== out.height) return unavailable('Image unavailable: PNG geometry differs from recorded geometry.');
  // Multi-frame PNGs require more than the declared single-image pixel budget.
  // Inspect only bounded chunk framing; the browser still owns PNG decoding.
  for (let cursor = 8; cursor + 12 <= bytes.length;) {
    const length = header.getUint32(cursor);
    if (length > bytes.length - cursor - 12) return unavailable('Image unavailable: truncated PNG chunk.');
    if (bytes[cursor + 4] === 97 && bytes[cursor + 5] === 99 && bytes[cursor + 6] === 84 && bytes[cursor + 7] === 76) {
      if (length !== 8 || header.getUint32(cursor + 8) !== 1) return unavailable('Image unavailable: animated PNG is not a static original capture.');
    }
    cursor += length + 12;
  }
  const digest = Array.from(new Uint8Array(await cryptoAPI.subtle.digest('SHA-256', bytes)), x => x.toString(16).padStart(2, '0')).join('');
  if (digest !== out.sha256) return unavailable('Image unavailable: SHA-256 digest mismatch.');
  if (out.unavailable_reason) return out;
  out.bytes = bytes;
  return out;
}
function eventRange(e) {
  if (!e.clock) return null;
  if (e.start_wall_ms !== null && e.end_wall_ms !== null) {
    return e.end_wall_ms >= e.start_wall_ms ? {start: e.start_wall_ms, end: e.end_wall_ms, point: false} : null;
  }
  // Known timestamps are instants, never invented zero-duration executions or
  // completed censored requests. Their original elapsed measurement stays null.
  if (['source', 'statement', 'operation', 'observer', 'program'].includes(e.kind)) {
    const at = e.start_wall_ms ?? e.end_wall_ms;
    if (at !== null) return {start: at, end: at, point: true};
  }
  return null;
}
function plottable(e) { return eventRange(e) !== null; }
function indexCase(c) {
  const plotted = c.events.filter(plottable);
  const ids = new Set(c.events.map(e => e.id));
  return {bounds: plotted.length ? [Math.min(...plotted.map(e => eventRange(e).start)), Math.max(...plotted.map(e => eventRange(e).end))] : null,
    ranges: Object.fromEntries(plotted.map(e => [e.id, eventRange(e)])),
    pointIds: plotted.filter(e => eventRange(e).point).map(e => e.id),
    plottableIds: plotted.map(e => e.id), unplottedIds: c.events.filter(e => !plottable(e)).map(e => e.id),
    danglingLinks: c.events.reduce((sum, e) => sum + e.links.filter(id => !ids.has(id)).length, 0)};
}
async function validateText(text, cryptoAPI = globalThis.crypto) {
  if (typeof text !== 'string') fail('bundle', 'expected JSON text');
  if (text.length > LIMITS.encodedBytes || new TextEncoder().encode(text).byteLength > LIMITS.encodedBytes) fail('bundle', 'exceeds 16 MiB encoded JSON');
  let root;
  try { root = JSON.parse(text); } catch (_) { fail('bundle', 'invalid JSON'); }
  object(root, ['schema', 'cases'], 'bundle');
  if (root.schema !== 'observer-investigation/1') fail('bundle', 'unsupported schema');
  if (!Array.isArray(root.cases) || !root.cases.length || root.cases.length > LIMITS.cases) fail('cases', 'requires 1–4 cases');
  let sources = 0;
  const cases = [];
  for (const [i, v] of root.cases.entries()) {
    const p = `cases[${i}]`;
    object(v, ['id', 'title', 'session', 'source_commit', 'configuration', 'coverage', 'events', 'sources', 'assessments', 'accounting'], p);
    const c = {id: identity(v.id, `${p}.id`, false), title: string(v.title, 240, `${p}.title`),
      session: identity(v.session, `${p}.session`), source_commit: identity(v.source_commit, `${p}.source_commit`)};
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(c.id)) fail(p, 'invalid case id');
    c.configuration = array(v.configuration, 2, `${p}.configuration`, configuration);
    const counts = ['event_candidates', 'event_retained', 'event_omitted', 'source_candidates', 'source_retained', 'source_omitted', 'invalid_clocks'];
    object(v.coverage, [...counts, 'observer_status', 'notes'], `${p}.coverage`);
    c.coverage = {};
    for (const field of counts) c.coverage[field] = number(v.coverage[field], `${p}.coverage.${field}`, false, true);
    c.coverage.observer_status = note(v.coverage.observer_status, `${p}.coverage.observer_status`);
    c.coverage.notes = array(v.coverage.notes, 32, `${p}.coverage.notes`, (x, q) => note(x, q, false));
    c.events = array(v.events, LIMITS.events, `${p}.events`, event);
    unique(c.events, 'id', p);
    if (!Array.isArray(v.sources) || (sources += v.sources.length) > LIMITS.sources) fail(p, 'at most 16 PNG entries');
    c.sources = [];
    for (const [j, s] of v.sources.entries()) c.sources.push(await source(s, `${p}.sources[${j}]`, cryptoAPI));
    unique(c.sources, 'source_id', p);
    c.assessments = array(v.assessments, 16, `${p}.assessments`, (a, q) => {
      object(a, ['label', 'text', 'attribution', 'reference', 'evidence_ids'], q);
      return {label: string(a.label, 240, `${q}.label`), text: string(a.text, 4000, `${q}.text`),
        attribution: identity(a.attribution, `${q}.attribution`), reference: note(a.reference, `${q}.reference`),
        evidence_ids: array(a.evidence_ids, 64, `${q}.evidence_ids`, (x, r) => identity(x, r, false))};
    });
    const accountingFields = ['attempts', 'host_seconds', 'configured_estimate_usd', 'missing_usage_attempts', 'conservative_reservation_usd'];
    object(v.accounting, accountingFields, `${p}.accounting`);
    c.accounting = {};
    for (const field of accountingFields) c.accounting[field] = number(v.accounting[field], `${p}.accounting.${field}`, true,
      ['attempts', 'missing_usage_attempts'].includes(field));
    if (c.coverage.event_retained !== c.events.length || c.coverage.event_candidates !== c.events.length + c.coverage.event_omitted ||
        c.coverage.source_retained !== c.sources.length || c.coverage.source_candidates !== c.sources.length + c.coverage.source_omitted) {
      fail(p, 'inconsistent coverage counts');
    }
    cases.push(c);
  }
  unique(cases, 'id', 'cases');
  return {schema: root.schema, cases, indexes: cases.map(indexCase)};
}
async function validateSnapshotText(text, expectedSession, cryptoAPI = globalThis.crypto) {
  if (typeof text !== 'string' || text.length > LIMITS.encodedBytes + 4096 ||
      new TextEncoder().encode(text).byteLength > LIMITS.encodedBytes + 4096) fail('snapshot', 'exceeds bounded envelope');
  let envelope;
  try { envelope = JSON.parse(text); } catch (_) { fail('snapshot', 'invalid JSON'); }
  object(envelope, ['schema', 'session', 'state', 'snapshot_wall_ms', 'bundle', 'error'], 'snapshot');
  if (envelope.schema !== 'observer-investigation-snapshot/1' || envelope.state !== 'ready' || envelope.error !== null ||
      typeof expectedSession !== 'string' || envelope.session !== expectedSession) fail('snapshot', 'unsupported or changed session');
  number(envelope.snapshot_wall_ms, 'snapshot.snapshot_wall_ms', false);
  const model = await validateText(JSON.stringify(envelope.bundle), cryptoAPI);
  if (model.cases.length !== 1 || model.cases[0].session !== envelope.session) fail('snapshot', 'bundle session differs');
  const index = model.indexes[0];
  index.snapshotWallMs = envelope.snapshot_wall_ms;
  if (index.bounds) {
    index.recordedBounds = [...index.bounds];
    index.snapshotClockConflict = model.cases[0].events.some(e =>
      [e.start_wall_ms, e.end_wall_ms].some(t => t !== null && t > envelope.snapshot_wall_ms));
    if (index.snapshotClockConflict) index.snapshotAxisWarning = 'Snapshot completion conflicts with retained wall bounds; the axis was not extended.';
    if (!index.snapshotClockConflict) index.bounds[1] = envelope.snapshot_wall_ms;
  } else index.snapshotAxisWarning = 'No retained wall origin is available. Snapshot completion alone cannot define an elapsed interval.';
  return {model, snapshot: {session: envelope.session, wall_ms: envelope.snapshot_wall_ms}};
}
function selectPage(events, {page = 0, kind = '', query = '', start = null, end = null} = {}) {
  const needle = query.toLowerCase();
  const filtered = events.filter(e => (!kind || e.kind === kind) && (!needle ||
    [e.id, e.label, e.text, e.actor_id, e.request_id, e.run_id, e.program_id, e.operation_id, e.native_id, e.source_id].some(v => v && v.toLowerCase().includes(needle))) &&
    (start === null || end === null || (eventRange(e) && eventRange(e).start <= end && eventRange(e).end >= start)));
  const pages = Math.max(1, Math.ceil(filtered.length / LIMITS.page));
  const selected = Math.max(0, Math.min(Number.isSafeInteger(page) ? page : 0, pages - 1));
  return {rows: filtered.slice(selected * LIMITS.page, (selected + 1) * LIMITS.page), total: filtered.length, page: selected, pages};
}
function intervalSummary(events, bounds, start = null, end = null) {
  if (!bounds) return null;
  const a = start ?? bounds[0], b = end ?? bounds[1];
  if (!Number.isFinite(a) || !Number.isFinite(b) || b < a) return null;
  const selected = events.filter(e => ['request', 'tool'].includes(e.kind));
  function spans(kind) {
    return selected.filter(e => e.kind === kind && eventRange(e) && !eventRange(e).point)
      .map(e => [Math.max(a, e.start_wall_ms), Math.min(b, e.end_wall_ms)])
      .filter(([s, t]) => t >= s);
  }
  function union(rows) {
    let total = 0, last = null;
    for (const [s, t] of rows.sort((x, y) => x[0] - y[0])) {
      if (last === null || s > last[1]) { if (last) total += last[1] - last[0]; last = [s, t]; }
      else last[1] = Math.max(last[1], t);
    }
    return total + (last ? last[1] - last[0] : 0);
  }
  const request = spans('request'), tool = spans('tool');
  const requests = union(request), tools = union(tool), covered = union([...request, ...tool]);
  return {elapsed_ms: b - a, request_wall_union_ms: requests, tool_wall_union_ms: tools,
    overlap_ms: Math.max(0, requests + tools - covered), uncovered_ms: Math.max(0, b - a - covered),
    no_full_wall_span: selected.filter(e => !eventRange(e) || eventRange(e).point).length};
}
if (typeof module !== 'undefined' && module.exports) module.exports = {validateText, validateSnapshotText, selectPage, intervalSummary, LIMITS};
if (typeof self !== 'undefined' && typeof self.postMessage === 'function') {
  let model = null;
  self.onmessage = async ({data}) => {
    try {
      if (data.type === 'load') {
        if (data.file && data.file.size > LIMITS.encodedBytes) fail('bundle', 'exceeds 16 MiB encoded JSON');
        const text = data.file ? await data.file.text() : data.text;
        const validated = data.snapshot ? await validateSnapshotText(text, data.expectedSession) : {model: await validateText(text)};
        model = validated.model;
        self.postMessage({type: 'loaded', ...validated});
      } else if (data.type === 'page' && model) {
        const c = model.cases[data.caseIndex];
        if (!c) fail('page', 'unknown case');
        self.postMessage({type: 'page', token: data.token, ...selectPage(c.events, data.filters),
          timing: intervalSummary(c.events, model.indexes[data.caseIndex].bounds, data.filters?.start, data.filters?.end)});
      }
    } catch (error) { self.postMessage({type: 'error', message: error.message}); }
  };
}
