'use strict';
const $ = id => document.getElementById(id);
const POLL_MS = 1000;
const IO_TIMEOUT_MS = 8000;
const TIMING_LIMIT = 2000;
let latest = null;
let statusError = '';
let statusBusy = false;
let pollTimer = null;
let pauseRequested = false;
let nativePauseConfirmed = false;
let pauseReason = '';
let displayed = null;
let candidate = null;
let sourceGeneration = 0;
const timingRows = [];
let omittedRows = 0;
const show = (id, value) => { $(id).textContent = value; };
const value = item => item === null || item === undefined ? 'unreported' : String(item);
const wallTime = seconds => Number.isFinite(seconds) ? `${seconds} s since epoch` : 'unreported';

// One finite watchdog covers HTTP, body consumption and image decode. An aborted
// or superseded request cannot later replace a source's metadata or pixels.
async function bounded(work, controller) {
  let timer;
  const timeout = new Promise((resolve, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new Error('Request timed out after 8 seconds'));
    }, IO_TIMEOUT_MS);
  });
  try { return await Promise.race([work(), timeout]); }
  finally { clearTimeout(timer); }
}
async function getJSON(url, controller, options = {}) {
  const response = await fetch(url, {cache: 'no-store', credentials: 'same-origin', ...options, signal: controller.signal});
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
function retainTiming(row) {
  timingRows.push(row);
  if (timingRows.length > TIMING_LIMIT) { timingRows.shift(); omittedRows += 1; }
  show('timing-summary', `${timingRows.length} source attempts retained; ${omittedRows} earlier rows omitted.`);
}
function observerMeasurementSnapshot() {
  return {schema: 'observer-timing/4', retention_limit: TIMING_LIMIT, omitted_rows: omittedRows,
    clock: 'Source presented_ms and browser timestamps are epoch milliseconds; source received_wall is epoch seconds. Shared wall clock is assumed, not verified.',
    scope: 'Status observation, image decode completion and DOM replacement only; not physical paint, model attention or useful success.',
    rows: timingRows.map(row => ({...row}))};
}
$('download-observer-measurements').addEventListener('click', () => {
  const blob = new Blob([JSON.stringify(observerMeasurementSnapshot(), null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `enactive-observer-timing-${Date.now()}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
});
function renderStop() {
  show('stop-state', nativePauseConfirmed ? 'Permanent Pause: native Pause confirmed.' :
    pauseRequested ? 'Permanent Pause requested; native Pause not yet confirmed.' : 'Pause has not been requested; native confirmation unreported.');
  if (pauseReason) $('stop-state').textContent += ` Reason: ${pauseReason}`;
  $('pause').disabled = pauseRequested || nativePauseConfirmed;
}
async function requestPause() {
  if (pauseRequested || nativePauseConfirmed) return;
  pauseRequested = true;
  renderStop();
  const controller = new AbortController();
  try {
    const result = await bounded(() => getJSON('/api/pause', controller, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'}), controller);
    // The pause route returns stop state; status reports the same facts later.
    if (result.native_pause_confirmed === true) nativePauseConfirmed = true;
    if (result.reason) pauseReason = result.reason;
  } catch (error) {
    show('pause-error', `Pause response unavailable: ${error.message}. The request is latched locally; native confirmation is unknown until reported.`);
    $('pause-error').hidden = false;
  }
  renderStop();
}
$('pause').addEventListener('click', () => { void requestPause(); });

function renderFacts(status) {
  show('session', value(status.session));
  show('ownership', status.actors?.length ? status.actors.map(actor => `${value(actor.actor_id)} (${value(actor.stage)})`).join('; ') : 'No actors reported.');
  const target = status.target;
  show('target', target ? `PID ${value(target.pid)} · window ${value(target.window_id)} · paused: ${value(target.paused)} · takeover generation ${value(target.takeover_generation)}${target.error ? ` · diagnostic: ${target.error}` : ''}` : 'No native target reported.');
  const operation = status.last_operation;
  show('operation', operation ? `${value(operation.kind)} ${value(operation.operation_id)} · ${value(operation.status)}${operation.reason ? ` · ${operation.reason}` : ''}` : 'No operation reported.');
  show('native-exit', status.native_returncode === null || status.native_returncode === undefined ? 'No exit code sampled.' : `Exit code ${status.native_returncode}; this is not proof of Save.`);
  show('custodian-remaining', `${value(status.remaining?.custodian_seconds)} seconds`);
  const remaining = status.remaining;
  show('resource-remaining', `Inputs: ${value(remaining?.inputs)} · requests: ${value(remaining?.requests)} · frames: ${value(remaining?.frames)} · PNG bytes: ${value(remaining?.frame_bytes)}`);
  const host = status.host;
  show('host-remaining', host ? `${value(host.host_seconds_remaining)} seconds` : 'No host report.');
  show('host-requests', host ? `${value(host.requests_total)} used / ${value(host.max_requests_total)} maximum HTTP attempts` : 'No host HTTP budget reported.');
  show('host-details', host ? `Host ${value(host.index)} · ${value(host.model)} · ${value(host.provider)} · last response ${wallTime(host.latest_response_wall)}` : 'No configuration reported.');
  const claims = (status.player_claims || []).map(claim => {
    const row = document.createElement('li');
    const label = document.createElement('strong');
    label.textContent = `Player assertion · ${value(claim.kind)} · ${value(claim.id)}`;
    const text = document.createElement('p');
    text.textContent = value(claim.text);
    row.append(label, text);
    if (claim.data && Object.keys(claim.data).length) {
      const detail = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = 'Player assertion data';
      const pre = document.createElement('pre');
      pre.textContent = JSON.stringify(claim.data, null, 2);
      detail.append(summary, pre);
      row.append(detail);
    }
    return row;
  });
  if (!claims.length) { const empty = document.createElement('li'); empty.textContent = 'No player assertions reported.'; claims.push(empty); }
  $('player-claims').replaceChildren(...claims);
  pauseRequested ||= status.stop?.stop_requested === true;
  nativePauseConfirmed ||= status.stop?.native_pause_confirmed === true;
  if (status.stop?.reason) pauseReason = status.stop.reason;
  renderStop();
}
function sourceKey(source) { return source ? JSON.stringify([source.session, source.source_id, source.sha256]) : null; }
function renderFrameNote(message) {
  show('frame-note', message);
  if (!displayed) {
    show('source-age', 'No displayed source.');
    show('source-details', 'No displayed source.');
    return;
  }
  const source = displayed.source;
  const age = (Date.now() - source.presented_ms) / 1000;
  const receiptAge = Date.now() / 1000 - source.received_wall;
  show('source-age', `Presented ${age.toFixed(1)} seconds ago · received ${receiptAge.toFixed(1)} seconds ago (wall-clock comparisons; negative values indicate clock differences).`);
  show('source-details', `Session: ${source.session}\nSource: ${source.source_id}\nCapture: ${source.capture_id}\nSHA-256: ${source.sha256}\nOriginal presented_ms: ${source.presented_ms}\nOriginal received_wall: ${source.received_wall}\nPNG: ${source.width} × ${source.height} · native window: ${source.window_width} × ${source.window_height}\nViewport: [${source.viewport.join(', ')}]`);
}
function clearDisplayed() {
  $('frame').hidden = true;
  if (displayed) URL.revokeObjectURL(displayed.url);
  displayed = null;
}
function validSource(source, session) {
  return source?.schema === 'computer-source/1' && source.session === session &&
    typeof source.source_id === 'string' && typeof source.sha256 === 'string' &&
    source.media_type === 'image/png' && Number.isFinite(source.presented_ms) &&
    Number.isFinite(source.received_wall) && Array.isArray(source.viewport) && source.viewport.length === 4;
}
async function selectSource(source, observedAt) {
  const generation = ++sourceGeneration;
  if (candidate) candidate.controller.abort();
  candidate = null;
  clearDisplayed();
  if (!source) { renderFrameNote('No captured source reported.'); return; }
  if (!validSource(source, latest.session)) { renderFrameNote('Source unavailable: unsupported source metadata.'); return; }
  // Copy original metadata before any asynchronous work. The selected identity
  // and its original observation timestamp stay together for the whole attempt.
  source = {...source, viewport: [...source.viewport]};
  const key = sourceKey(source);
  const controller = new AbortController();
  candidate = {key, controller};
  const row = {session: source.session, source_id: source.source_id, capture_id: source.capture_id,
    presented_ms: source.presented_ms, observed_at_wall_ms: observedAt,
    decode_finished_wall_ms: null, dom_replaced_wall_ms: null, outcome: 'pending', error: null};
  retainTiming(row);
  renderFrameNote(`Loading captured source ${source.source_id}; no decoded image displayed.`);
  let url = null;
  try {
    const image = await bounded(async () => {
      const response = await fetch(`/api/source/${encodeURIComponent(source.source_id)}`, {
        cache: 'force-cache', credentials: 'same-origin', signal: controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      if (generation !== sourceGeneration || controller.signal.aborted) return null;
      url = URL.createObjectURL(blob);
      const decoded = new Image();
      decoded.src = url;
      decoded.alt = 'Original PNG captured from the native window';
      await decoded.decode();
      row.decode_finished_wall_ms = Date.now();
      return decoded;
    }, controller);
    if (generation !== sourceGeneration) { row.outcome = 'superseded'; return; }
    if (image.naturalWidth !== source.width || image.naturalHeight !== source.height) throw new Error('PNG dimensions differ from original source metadata');
    image.id = 'frame';
    image.hidden = false;
    $('frame').replaceWith(image);
    row.dom_replaced_wall_ms = Date.now();
    row.outcome = 'displayed';
    displayed = {key, source, url};
    url = null; // Displayed image owns this URL until it is replaced.
    renderFrameNote(statusError ? 'Retained captured pixels; status unavailable.' : 'Captured pixels decoded and placed in the DOM; physical paint unmeasured.');
  } catch (error) {
    row.outcome = generation === sourceGeneration ? 'unavailable' : 'superseded';
    row.error = error.message;
    if (generation === sourceGeneration) renderFrameNote(`Source unavailable: ${error.message}. No decoded image displayed.`);
  } finally {
    if (url) URL.revokeObjectURL(url);
    if (generation === sourceGeneration) candidate = null;
  }
}
async function refresh() {
  if (statusBusy) return;
  clearTimeout(pollTimer);
  statusBusy = true;
  const controller = new AbortController();
  try {
    const status = await bounded(() => getJSON('/api/status', controller), controller);
    if (status.schema !== 'computer-status/1') throw new Error('Unsupported status schema');
    const observedAt = Date.now();
    latest = status;
    statusError = '';
    $('status-error').hidden = true;
    show('status-error', '');
    show('connection', 'Status received');
    renderFacts(status);
    const key = sourceKey(status.latest_source);
    if (key !== (candidate?.key || displayed?.key || null) || !status.latest_source) void selectSource(status.latest_source, observedAt);
    else if (displayed) renderFrameNote('Retained captured pixels; no new source reported.');
  } catch (error) {
    statusError = error.message;
    show('connection', 'Status unavailable');
    show('status-error', `Status unavailable: ${error.message}. Mechanical facts below are the last received snapshot; current ownership and state are unknown.`);
    $('status-error').hidden = false;
    if (displayed) renderFrameNote('Retained captured pixels; status unavailable.');
  } finally {
    statusBusy = false;
    pollTimer = setTimeout(() => { void refresh(); }, POLL_MS);
  }
}
void refresh();
