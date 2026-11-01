'use strict';
const $ = id => document.getElementById(id);
const POLL_MS = 1000;
const IO_TIMEOUT_MS = 8000;
const TIMING_LIMIT = 2000;
let latest = null;
let statusError = '';
let statusBusy = false;
let pollTimer = null;
let currentSession = null;
let investigationSession = null;
let previousSession = null;
let statusReceivedAt = null;
let sessionGeneration = 0;
const retiredSessions = new Set();
const stopStates = new Map();
const pauseIntents = new Set();
let pauseFeedback = null;
let lastPauseReceiver = null;
let displayed = null;
let candidate = null;
let sourceGeneration = 0;
const timingRows = [];
let omittedRows = 0;
const show = (id, value) => { if ($(id).textContent !== value) $(id).textContent = value; };
const value = item => item === null || item === undefined ? 'unreported' : String(item);
// An unknown quantity never gains a unit: "unreported", never "unreported seconds".
const measured = (item, unit) => item === null || item === undefined ? 'unreported' : `${item} ${unit}`;
const shortIdentity = item => {
  const text = value(item);
  return text.length > 22 ? `${text.slice(0, 12)}…${text.slice(-6)}` : text;
};
const wallTime = seconds => {
  if (!Number.isFinite(seconds)) return 'unreported';
  const date = new Date(seconds * 1000);
  return Number.isFinite(date.valueOf()) ? date.toISOString().replace('T', ' ').replace('Z', ' UTC') : 'invalid clock';
};
const clockTime = seconds => {
  const full = wallTime(seconds);
  if (/UTC$/.test(full)) return `${full.slice(11, 19)} UTC`;
  return full === 'unreported' ? 'time unreported' : full;
};

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
    scope: 'Status observation, image decode completion and DOM replacement (including a hidden Watch panel) only; not visibility, physical paint, model attention or useful success.',
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
for (const name of ['watch', 'inspection']) {
  const button = $(`${name}-size`);
  let originalSize = false;
  button.addEventListener('click', () => {
    originalSize = !originalSize;
    $(`${name}-frame-shell`).className = `frame-shell${originalSize ? ' actual-pixels' : ''}`;
    button.setAttribute('aria-pressed', String(originalSize));
    button.textContent = originalSize ? 'Fit image to panel' : 'Show original pixel size';
  });
}
function stopState(session = currentSession) {
  if (!stopStates.has(session)) stopStates.set(session, {requested: false, confirmed: false, reason: ''});
  return stopStates.get(session);
}
function mergeStop(session, stop) {
  const state = stopState(session);
  state.requested ||= stop?.stop_requested === true;
  state.confirmed ||= stop?.native_pause_confirmed === true;
  if (stop?.reason) state.reason = stop.reason;
  if (lastPauseReceiver?.session === session) {
    lastPauseReceiver.stop.stop_requested ||= state.requested;
    lastPauseReceiver.stop.native_pause_confirmed ||= state.confirmed;
  }
}
function renderStop() {
  const state = stopState();
  const pending = [...pauseIntents].some(intent => intent.scope === currentSession);
  show('stop-state', state.confirmed ? 'Permanent Pause: native Pause confirmed for this session.' :
    state.requested || pending ? 'Permanent Pause requested; native Pause not yet confirmed for this session.' :
    'Pause state unknown; no native confirmation for this session.');
  if (!currentSession) $('stop-state').textContent += ' Actual receiving session unknown until a response.';
  if (state.reason) $('stop-state').textContent += ` Reason: ${state.reason}`;
  // A lost response is not proof of nondelivery. Another deliberate click is a
  // new emergency intent; it is never an automatic retry of input.
  $('pause').disabled = pending || state.confirmed;
  const feedback = pauseFeedback?.scope === currentSession ? pauseFeedback : null;
  $('pause-error').hidden = !feedback;
  const confirmation = state.confirmed ? 'Native Pause is already confirmed for this session by received evidence.' :
    'Delivery and native confirmation remain unknown until reported. A deliberate new click sends a new emergency intent.';
  show('pause-error', feedback ? feedback.unidentified ?
    `Unidentified earlier Pause response unavailable: ${feedback.reason}. Its receiving target is unknown; ${state.confirmed ? confirmation : 'current-session facts above are unchanged.'}` :
    `Pause response unavailable: ${feedback.reason}. ${confirmation}` : '');
  const outsideHistory = lastPauseReceiver && lastPauseReceiver.session !== currentSession && lastPauseReceiver.session !== previousSession;
  $('pause-receiver').hidden = !outsideHistory;
  show('pause-receiver', outsideHistory ? `Last identified Pause receiver · session ${lastPauseReceiver.session}: ${lastPauseReceiver.stop.native_pause_confirmed ? 'native Pause confirmed by received evidence' : 'retained evidence has no native Pause confirmation'}. This receiver is outside the current/previous session view; it is not the current control target.` : '');
  const old = stopStates.get(previousSession);
  show('stop-history', previousSession && (old?.requested || old?.confirmed) ? `Historical Pause · session ${previousSession}: ${old.confirmed ? 'native Pause confirmed' : 'Pause requested; native confirmation unknown'}. This is not the current control target.` : 'No previous-session Pause evidence retained.');
}
function adoptSession(session) {
  if (session === currentSession) return true;
  if (typeof session !== 'string' || !session || retiredSessions.has(session)) return false;
  if (currentSession) retiredSessions.add(currentSession);
  previousSession = currentSession;
  currentSession = session;
  sessionGeneration += 1;
  for (const key of stopStates.keys()) if (key !== currentSession && key !== previousSession && key !== null) stopStates.delete(key);
  if (lastPauseReceiver?.session === session) mergeStop(session, lastPauseReceiver.stop);
  for (const key of activitySnapshots.keys()) if (key !== currentSession && key !== previousSession) activitySnapshots.delete(key);
  latest = null;
  statusReceivedAt = null;
  statusError = '';
  activityError = '';
  pauseFeedback = null;
  show('pause-error', ''); $('pause-error').hidden = true;
  renderFacts({session});
  if (!following && timelineSession !== currentSession && timelineSession !== previousSession) {
    selectedEntry = null; listedEntries = []; renderEntryList();
    ++inspectionGeneration; inspectionController?.abort();
    if (inspectionURL) URL.revokeObjectURL(inspectionURL);
    inspectionURL = null; $('inspection-frame').hidden = true;
    show('inspection-heading', 'Linked evidence unavailable');
    show('entry-summary', 'The inspected session is outside the current and one previous session retained on this page.');
    show('inspection-scope', `Recorded evidence unavailable; current control target is ${session}.`);
    show('entry-text', ''); show('entry-details', 'Entry not retained in client history.'); $('entry-links').replaceChildren();
    show('inspection-coverage', 'Selected evidence unavailable outside retained history.');
    show('inspection-frame-note', 'Pixels unavailable: inspected session not retained.');
    show('inspection-source', '');
  }
  ++sourceGeneration;
  candidate?.controller.abort();
  candidate = null;
  clearDisplayed();
  renderFrameNote('No source received for the current session.');
  show('current-session', shortIdentity(session));
  show('current-session-full', session);
  investigationSession?.sessionChanged(session);
  show('control-freshness', 'Current-session status not yet received; liveness unknown.');
  show('latest-statement', 'No public statement available for this session.');
  show('statement-meta', 'Missing narration does not establish inactivity.');
  show('activity-summary', 'Current-session activity not yet received.');
  renderRecentActivity([], 'No current-session activity available.');
  if (selectedEntry) { renderInspectionScope(selectedEntry); void loadInspectionSource(selectedEntry); }
  renderStop();
  renderTimeline();
  return true;
}
async function requestPause() {
  if ($('pause').disabled) return;
  const intent = {scope: currentSession};
  pauseIntents.add(intent);
  pauseFeedback = null;
  renderStop();
  const controller = new AbortController();
  try {
    const result = await bounded(() => getJSON('/api/pause', controller, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'}), controller);
    if (result.schema !== 'computer-pause/1' || typeof result.session !== 'string' || !result.session || !result.stop) {
      throw new Error('Unsupported or unidentified Pause response');
    }
    // A receipt can identify a third, previously unseen receiver. Its opaque ID
    // cannot establish that it is newer than current status. Keep one receiver,
    // disclose the receiver, and merge its facts if status later identifies it.
    const retained = lastPauseReceiver?.session === result.session ? lastPauseReceiver.stop : null;
    const known = stopStates.get(result.session);
    lastPauseReceiver = {session: result.session, stop: {
      stop_requested: result.stop.stop_requested === true || retained?.stop_requested === true || known?.requested === true,
      native_pause_confirmed: result.stop.native_pause_confirmed === true || retained?.native_pause_confirmed === true || known?.confirmed === true,
      reason: typeof result.stop.reason === 'string' ? result.stop.reason.slice(0, 600) : null}};
    // The receiver identifies the target. A late old receipt is history, while a
    // replacement receiver can identify itself before the next status arrives.
    if (!currentSession || (currentSession === intent.scope && !retiredSessions.has(result.session))) adoptSession(result.session);
    if (result.session === currentSession || result.session === previousSession) mergeStop(result.session, result.stop);
    // Old receipts update labelled history only; they cannot replace a current
    // diagnostic or describe known current confirmation as unknown.
  } catch (error) {
    if (intent.scope === currentSession) stopState().requested = true;
    if (intent.scope === currentSession) {
      pauseFeedback = {scope: currentSession, reason: error.message, unidentified: false};
    } else if (intent.scope === null && !stopState().confirmed) {
      pauseFeedback = {scope: currentSession, reason: error.message, unidentified: true};
    } // A historical request failure cannot overwrite current-session feedback.
  } finally {
    pauseIntents.delete(intent);
    renderStop();
  }
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
  show('custodian-remaining', measured(status.remaining?.custodian_seconds, 'seconds'));
  const remaining = status.remaining;
  show('resource-remaining', `Inputs: ${value(remaining?.inputs)} · requests: ${value(remaining?.requests)} · frames: ${value(remaining?.frames)} · PNG bytes: ${value(remaining?.frame_bytes)}`);
  const host = status.host;
  show('host-remaining', host ? measured(host.host_seconds_remaining, 'seconds') : 'No host report.');
  show('host-requests', host ? `${measured(host.requests_total, 'used')} / ${measured(host.max_requests_total, 'maximum HTTP attempts')}` : 'No host HTTP budget reported.');
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
  mergeStop(status.session, status.stop);
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
  // The full clock caveat lives in "What this view shows"; a negative age states it inline.
  show('source-age', `Presented ${age.toFixed(1)} s ago · received ${receiptAge.toFixed(1)} s ago${age < 0 || receiptAge < 0 ? ' · negative: the clocks differ' : ''}`);
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
  if (!validSource(source, currentSession)) { renderFrameNote('Source unavailable: unsupported source metadata.'); return; }
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
    if (generation !== sourceGeneration || !image || source.session !== currentSession) { row.outcome = 'superseded'; return; }
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
  const generation = sessionGeneration;
  const controller = new AbortController();
  try {
    const status = await bounded(() => getJSON('/api/status', controller), controller);
    if (status.schema !== 'computer-status/1' || typeof status.session !== 'string' || !status.session) throw new Error('Unsupported status schema');
    if (generation !== sessionGeneration && status.session !== currentSession) return;
    if (!adoptSession(status.session)) return;
    const observedAt = Date.now();
    statusReceivedAt = observedAt;
    latest = status;
    statusError = '';
    $('status-error').hidden = true;
    show('status-error', '');
    show('connection', 'Status received · liveness not certified');
    $('connection').setAttribute('data-state', 'ok');
    show('control-freshness', `Last status received ${new Date(observedAt).toISOString()}; recorded ACTIVE/PID is not proof of liveness.`);
    renderFacts(status);
    const key = sourceKey(status.latest_source);
    if (key !== (candidate?.key || displayed?.key || null) || !status.latest_source) void selectSource(status.latest_source, observedAt);
    else if (displayed) renderFrameNote('Retained captured pixels; no new source reported.');
  } catch (error) {
    if (generation !== sessionGeneration) return;
    statusError = error.message;
    show('connection', 'Status unavailable · last snapshot retained');
    $('connection').setAttribute('data-state', 'error');
    show('control-freshness', statusReceivedAt === null ? 'No current-session status received; liveness unknown.' : `Last status received ${new Date(statusReceivedAt).toISOString()}; current state unknown.`);
    show('status-error', `Status unavailable: ${error.message}. Mechanical facts below are the last received snapshot; current ownership and state are unknown.`);
    $('status-error').hidden = false;
    if (displayed) renderFrameNote('Retained captured pixels; status unavailable.');
  } finally {
    statusBusy = false;
    pollTimer = setTimeout(() => { void refresh(); }, POLL_MS);
  }
}

// Activity uses its own finite passive poll. A stalled projection never holds
// status, source loading or the independent emergency Pause path.
const ACTIVITY_LIMIT = 200;
const activitySnapshots = new Map();
let activityBusy = false;
let activityTimer = null;
let activityError = '';
let following = true;
let timelineSession = null;
let listedEntries = [];
let selectedEntry = null;
let inspectionGeneration = 0;
let inspectionController = null;
let inspectionURL = null;
let activeView = 'watch';
let deepLink = null;
let visibleEntries = [];
const VIEWS = ['watch', 'timeline', 'analysis'];
const entryKey = entry => JSON.stringify([entry.session, entry.producer, entry.actor_id ?? null, entry.id]);
const eventLabels = {'assistant-text': 'Player statement', 'request-start': 'Model request started',
  'response-complete': 'Model response received', 'tool-start': 'Tool requested', 'tool-result': 'Tool result',
  input: 'Computer input', observe: 'Observation', handoff: 'Actor handoff',
  'host-start': 'Player host started', settled: 'Player host ended', abort: 'Host interrupted',
  'provider-retry': 'Provider retry'};
const entryTitle = entry => `${eventLabels[entry.kind] || value(entry.kind)}${entry.tool ? ` · ${entry.tool}` : ''}${entry.status ? ` · ${entry.status}` : ''}`;
const omittedSummary = snapshot => Number.isFinite(snapshot.omitted_entries) ? `${snapshot.omitted_entries} omitted by server` : 'earlier omissions unknown (incomplete coverage)';
function activateView(view, updateLink = true) {
  activeView = view;
  for (const name of VIEWS) {
    const active = name === view;
    $(`tab-${name}`).setAttribute('aria-selected', String(active));
    $(`tab-${name}`).tabIndex = active ? 0 : -1;
    $(name).hidden = !active;
  }
  if (updateLink) updateLocation();
  if (view === 'analysis') investigationSession?.activate();
}
for (const name of VIEWS) {
  const tab = $(`tab-${name}`);
  tab.addEventListener('click', () => activateView(name));
  tab.addEventListener('keydown', event => {
    const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End', 'Enter', ' '];
    if (!keys.includes(event.key)) return;
    event.preventDefault();
    if (event.key === 'Enter' || event.key === ' ') activateView(name);
    else {
      const target = event.key === 'Home' ? VIEWS[0] : event.key === 'End' ? VIEWS[VIEWS.length - 1] :
        VIEWS[(VIEWS.indexOf(name) + (event.key === 'ArrowRight' ? 1 : VIEWS.length - 1)) % VIEWS.length];
      $(`tab-${name}`).tabIndex = -1;
      $(`tab-${target}`).tabIndex = 0;
      $(`tab-${target}`).focus();
    }
  });
}
$('open-timeline').addEventListener('click', () => { activateView('timeline'); $('tab-timeline').focus(); });
function updateLocation() {
  if (typeof history === 'undefined' || typeof URLSearchParams === 'undefined') return;
  const params = new URLSearchParams({view: activeView});
  if (selectedEntry) { params.set('session', selectedEntry.session); params.set('event', selectedEntry.id); params.set('producer', selectedEntry.producer); if (selectedEntry.actor_id) params.set('actor', selectedEntry.actor_id); }
  history.replaceState(null, '', `#${params}`);
}
function renderActivity(snapshot) {
  const statement = snapshot.latest_statement;
  show('latest-statement', statement?.text ? statement.text : 'No public statement available for this session.');
  show('statement-meta', statement ? `Fallible public statement · actor ${value(statement.actor_id)} · request ${value(statement.request_id)} · original wall ${wallTime(statement.created_wall)} · original bytes omitted: ${value(statement.omitted_bytes)}; further display bytes omitted: ${value(statement.display_omitted_bytes)}. No captured frame is linked to a statement, so its claims are unverified until checked against the pixels. Historical/terminal labels are recorded claims, not liveness.` : 'Missing or empty narration does not establish inactivity.');
  show('activity-summary', `${snapshot.entries.length} retained entries · ${omittedSummary(snapshot)}${snapshot.clientOmitted ? ` · ${snapshot.clientOmitted} further omitted on this page` : ''}.`);
  renderRecentActivity(snapshot.entries.slice(-3).reverse(), 'No use observed in available coverage; missing coverage is unknown.');
  show('frame-change', frameChange(snapshot.entries));
}
// The Watch feed: newest first, each with its wall-clock age, or one explicit empty row.
function renderRecentActivity(entries, emptyText) {
  const rows = entries.map(entry => {
    const row = document.createElement('li');
    const title = document.createElement('span');
    title.textContent = entryTitle(entry);
    const when = document.createElement('span');
    when.className = 'when';
    // The recorded clock time, not a relative age: it cannot go stale during an
    // outage and needs no browser-clock comparison.
    when.textContent = clockTime(entry.created_wall);
    row.append(title, when);
    return row;
  });
  if (!rows.length) { const empty = document.createElement('li'); empty.className = 'empty'; empty.textContent = emptyText; rows.push(empty); }
  $('recent-activity').replaceChildren(...rows);
}
// A neutral recorded fact against over-trust: the latest input's capture against
// the previous retained capture. It reads hashes only and infers no failure,
// success or game meaning; a differing hash shows only that the PNG differs.
function frameChange(entries) {
  const computer = entries.filter(entry => entry.producer === 'computer');
  const index = computer.findLastIndex(entry => entry.kind === 'input');
  if (index < 0) return 'No recorded input capture to compare yet.';
  const latest = computer[index];
  if (typeof latest.source?.sha256 !== 'string') return `The latest input (${shortIdentity(latest.operation_id)}) has no recorded capture.`;
  const before = computer.slice(0, index).findLast(entry => typeof entry.source?.sha256 === 'string');
  if (!before) return 'The latest input has no earlier retained capture to compare.';
  return before.source.sha256 === latest.source.sha256
    ? `Frame unchanged: ${shortIdentity(latest.operation_id)} returned an image identical (SHA-256) to the previous retained capture. A repeated image is a valid capture, not a failure.`
    : `The latest input's PNG differs (SHA-256) from the previous retained capture. A changed image does not establish useful progress.`;
}

// "Since you last looked": entries that arrive during hidden intervals are added up
// until the reader marks them seen. Time and polling never clear or change the count.
let latestActivity = null;
let hiddenFrom = null;
let away = null;
function renderSinceLastLook() {
  const visible = typeof document.visibilityState !== 'string' || document.visibilityState === 'visible';
  if (!away || !visible) { $('since-last-look').hidden = true; $('mark-seen').hidden = true; return; }
  const omitted = away.omissions ? '; older ones may have been omitted' : '';
  show('since-last-look', away.changed ? `The control target changed while this page was hidden${away.arrived ? `; ${away.arrived} retained entries arrived in the earlier session before that` : ''}. Earlier activity is in Timeline.` :
    `${away.arrived} retained ${away.arrived === 1 ? 'entry' : 'entries'} arrived while this page was hidden${omitted}.`);
  $('since-last-look').hidden = false; $('mark-seen').hidden = false;
}
// Hidden tabs throttle timers, so the count is fixed from a fresh poll accepted after the
// reader returns, never from the last poll made while hidden.
let returning = null;
function settleReturn() {
  if (!returning) return;
  away ??= {arrived: 0, changed: false, omissions: false};
  if (!away.changed) {
    if (currentSession !== returning.session || latestActivity?.session !== returning.session) away.changed = true;
    else {
      away.arrived += latestActivity.entries.filter(entry => !returning.keys.has(entryKey(entry))).length;
      // Unknown omission counts are not zero.
      away.omissions ||= Boolean(latestActivity.clientOmitted) || latestActivity.omitted_entries !== 0;
    }
  }
  returning = null;
  // Hidden again before the return poll landed: the rest of this hidden interval counts too.
  if (document.visibilityState === 'hidden' && latestActivity) hiddenFrom = {session: latestActivity.session, keys: new Set(latestActivity.entries.map(entryKey))};
  renderSinceLastLook();
}
if (typeof document.addEventListener === 'function') document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') {
    if (latestActivity && !hiddenFrom && !returning) hiddenFrom = {session: latestActivity.session, keys: new Set(latestActivity.entries.map(entryKey))};
  } else if (hiddenFrom) {
    returning = hiddenFrom; hiddenFrom = null;
    void refreshActivity();
  }
  renderSinceLastLook();
});
$('mark-seen').addEventListener('click', () => { away = null; renderSinceLastLook(); $('open-timeline').focus(); });
function renderCoverage(snapshot) {
  show('activity-coverage', snapshot ? `Host: ${value(snapshot.coverage?.host)} · computer records: ${value(snapshot.coverage?.computer)} · ${omittedSummary(snapshot)}. Cross-process ordering is approximate.` : 'Coverage unknown; no current-session activity received.');
  show('coverage-details', snapshot ? JSON.stringify({coverage: snapshot.coverage, omitted_entries: snapshot.omitted_entries,
    omitted_fields: snapshot.omitted_fields, omitted_text_bytes: snapshot.omitted_text_bytes,
    further_client_entries_omitted: snapshot.clientOmitted || 0}, null, 2) : 'No coverage received.');
}
function renderTimeline() {
  const requestedSession = following ? currentSession : timelineSession;
  const snapshot = activitySnapshots.get(requestedSession);
  const outsideHistory = requestedSession !== currentSession && requestedSession !== previousSession;
  const unavailableOption = $('timeline-session').children[2];
  if (unavailableOption) unavailableOption.hidden = !outsideHistory;
  $('timeline-session').value = outsideHistory ? 'unavailable' : requestedSession === previousSession && requestedSession ? 'previous' : 'current';
  const previousOption = $('timeline-session').children[1];
  if (previousOption) { previousOption.disabled = !previousSession; previousOption.textContent = previousSession ? `Previous · ${previousSession}` : 'Previous session (unavailable)'; }
  show('timeline-scope', `${requestedSession || 'Unknown session'}${outsideHistory ? ' · inspection unavailable (outside retained history)' : requestedSession && requestedSession !== currentSession ? ' · historical client snapshot' : ' · current session'}${following ? ' · following latest' : ' · inspection frozen'}`);
  show('activity-error', activityError ? `Activity unavailable: ${activityError}. Last received activity retained; current activity unknown.` : '');
  $('activity-error').hidden = !activityError;
  renderCoverage(snapshot);
  if (!following) {
    const listed = new Set(listedEntries.map(entryKey));
    const added = snapshot?.newItems ?? (snapshot?.entries.filter(entry => !listed.has(entryKey(entry))).length || 0);
    show('new-items', `${added} new retained entries in inspected session${requestedSession !== currentSession ? `; current session has changed (${activitySnapshots.get(currentSession)?.entries.length || 0} current entries retained)` : ''}. Follow latest to leave frozen inspection.`);
    return;
  }
  listedEntries = snapshot?.entries || [];
  renderEntryList();
  show('new-items', 'Following latest. Select an entry to freeze inspection.');
}
function renderEntryList() {
  const list = $('activity-list');
  const scroll = list.scrollTop;
  // During inspection this function is never called by polling, preserving the
  // same focused DOM row, selection and scroll instead of rebuilding it.
  const query = ($('timeline-filter').value || '').slice(0, 200).toLocaleLowerCase();
  const kind = $('timeline-kind').value || 'all';
  visibleEntries = listedEntries.filter(entry => {
    const matchesKind = kind === 'all' || kind === 'statements' && entry.kind === 'assistant-text' ||
      kind === 'model' && ['request-start', 'response-complete'].includes(entry.kind) ||
      kind === 'tools' && ['tool-start', 'tool-result'].includes(entry.kind) ||
      kind === 'computer' && entry.producer === 'computer';
    return matchesKind && (!query || ['id', 'kind', 'actor_id', 'request_id', 'tool_call_id', 'operation_id', 'program_id', 'status', 'reason', 'text']
      .some(field => typeof entry[field] === 'string' && entry[field].toLocaleLowerCase().includes(query)));
  });
  renderTimelineResults();
  const buttons = new Map();
  const entryGroups = new Map();
  const makeButton = entry => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = entryTitle(entry);
    button.setAttribute('aria-pressed', String(selectedEntry && entryKey(entry) === entryKey(selectedEntry) || false));
    const meta = document.createElement('span');
    meta.className = 'entry-meta';
    meta.textContent = `${value(entry.actor_id || entry.producer).slice(0, 12)} · ${wallTime(entry.created_wall)}`;
    button.append(meta);
    button.addEventListener('focus', () => { if (following) { following = false; timelineSession = entry.session; renderTimeline(); } });
    button.addEventListener('click', () => selectEntry(entry, button));
    buttons.set(entryKey(entry), button);
    return button;
  };
  const groups = new Map();
  for (const entry of visibleEntries) {
    const key = $('timeline-group').checked && entry.request_id ? JSON.stringify(['request', entry.session, entry.actor_id, entry.request_id]) :
      $('timeline-group').checked && entry.operation_id ? JSON.stringify(['operation', entry.session, entry.actor_id, entry.operation_id]) : entryKey(entry);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(entry);
  }
  list.replaceChildren(...[...groups.values()].map(entries => {
    const row = document.createElement('li');
    if (entries.length === 1) row.append(makeButton(entries[0]));
    else {
      const group = document.createElement('details');
      const label = document.createElement('summary');
      const times = entries.map(entry => entry.created_wall).filter(Number.isFinite);
      const elapsed = times.length > 1 ? ` · ${(Math.max(...times) - Math.min(...times)).toFixed(3)}s recorded wall span` : ' · duration unknown';
      label.textContent = `${shortIdentity(entries[0].actor_id)} · ${entries[0].request_id || shortIdentity(entries[0].operation_id)} · ${entries.length} matching rows${elapsed}`;
      group.append(label, ...entries.map(makeButton));
      group.open = entries.some(entry => selectedEntry && entryKey(entry) === entryKey(selectedEntry));
      for (const entry of entries) entryGroups.set(entryKey(entry), group);
      group.addEventListener('toggle', () => { if (following) { following = false; timelineSession = currentSession; renderTimeline(); } });
      row.append(group);
    }
    return row;
  }));
  timelineButtons = buttons;
  timelineGroups = entryGroups;
  list.scrollTop = scroll;
  $('timeline-empty').hidden = visibleEntries.length > 0;
}
let timelineButtons = new Map();
let timelineGroups = new Map();
function renderTimelineResults() {
  const filteredSelection = selectedEntry && !visibleEntries.some(entry => entryKey(entry) === entryKey(selectedEntry));
  show('timeline-results', `${visibleEntries.length} of ${listedEntries.length} retained rows match. Search covers retained rows only; omitted history is not searched.${filteredSelection ? ' Selected evidence is outside these filters.' : ''}`);
}
for (const [id, event] of [['timeline-filter', 'input'], ['timeline-kind', 'change'], ['timeline-group', 'change']]) {
  $(id).addEventListener(event, () => renderEntryList());
}
function renderInspectionScope(entry) {
  show('inspection-scope', `Recorded session ${entry.session}${entry.session !== currentSession ? ' · historical' : ''} · original wall ${wallTime(entry.created_wall)}. Current control target is ${currentSession || 'unknown'}.`);
  const snapshot = activitySnapshots.get(entry.session);
  show('inspection-coverage', snapshot ? `Selected session coverage: host ${value(snapshot.coverage?.host)}; computer ${value(snapshot.coverage?.computer)}; ${omittedSummary(snapshot)}. Related evidence may be missing.` : 'Selected session evidence unavailable outside retained history.');
}
function selectEntry(entry, button = null) {
  following = false;
  timelineSession = entry.session;
  selectedEntry = entry;
  const selectedGroup = timelineGroups.get(entryKey(entry));
  if (selectedGroup) selectedGroup.open = true;
  renderTimelineResults();
  for (const [key, row] of timelineButtons) row.setAttribute('aria-pressed', String(key === entryKey(entry)));
  show('inspection-heading', entryTitle(entry));
  renderInspectionScope(entry);
  show('entry-summary', `${value(entry.producer)} · actor ${value(entry.actor_id)}${entry.reason ? ` · ${entry.reason}` : ''}`);
  show('entry-text', entry.text || 'No public text recorded for this entry.');
  // The endpoint is an allowlisted projection; keep provenance progressive and
  // text-only. It carries no raw requests, arguments or private reasoning.
  show('entry-details', JSON.stringify(entry, null, 2));
  const links = [];
  const snapshot = activitySnapshots.get(entry.session);
  for (const [label, field] of [['request', 'request_id'], ['tool call', 'tool_call_id'], ['operation', 'operation_id'], ['program', 'program_id']]) {
    if (!entry[field]) continue;
    const matches = snapshot?.entries.filter(other => entryKey(other) !== entryKey(entry) && other[field] === entry[field] && (field !== 'request_id' && field !== 'tool_call_id' || other.actor_id === entry.actor_id && (field !== 'tool_call_id' || other.request_id === entry.request_id))) || [];
    const group = document.createElement('p');
    group.textContent = `${label}: ${entry[field]} · `;
    if (!matches.length) group.append(document.createTextNode('No other retained entry with this explicit identity; related evidence unavailable.'));
    for (const other of matches) {
      const link = document.createElement('button');
      link.type = 'button'; link.className = 'evidence-link'; link.textContent = entryTitle(other);
      link.addEventListener('click', () => selectEntry(other)); group.append(link);
    }
    links.push(group);
  }
  $('entry-links').replaceChildren(...links);
  renderTimeline();
  updateLocation();
  void loadInspectionSource(entry);
}
async function loadInspectionSource(entry) {
  const generation = ++inspectionGeneration;
  inspectionController?.abort();
  if (inspectionURL) URL.revokeObjectURL(inspectionURL);
  inspectionURL = null;
  $('inspection-frame').hidden = true;
  show('inspection-source', '');
  const source = entry.source;
  if (!source) { show('inspection-frame-note', 'Pixels unavailable: this entry has no explicit source relationship. Latest pixels are not substituted.'); return; }
  show('inspection-source', `Original source ${value(source.source_id)} · session ${value(source.session)} · original presented_ms ${value(source.presented_ms)} · original received_wall ${value(source.received_wall)}. These clocks are not the later collection time.`);
  if (entry.session !== currentSession || !validSource(source, entry.session)) {
    show('inspection-frame-note', 'Pixels unavailable: historical session or unsupported original source metadata.'); return;
  }
  const controller = new AbortController();
  inspectionController = controller;
  show('inspection-frame-note', 'Loading the explicitly linked retained source…');
  let url = null;
  try {
    const image = await bounded(async () => {
      const response = await fetch(`/api/source/${encodeURIComponent(source.source_id)}`, {cache: 'force-cache', credentials: 'same-origin', signal: controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      if (generation !== inspectionGeneration || controller.signal.aborted) return null;
      url = URL.createObjectURL(blob);
      const decoded = new Image(); decoded.src = url; await decoded.decode(); return decoded;
    }, controller);
    if (generation !== inspectionGeneration || entry.session !== currentSession || !image) return;
    if (image.naturalWidth !== source.width || image.naturalHeight !== source.height) throw new Error('PNG dimensions differ from original source metadata');
    image.id = 'inspection-frame'; image.alt = 'Retained source explicitly linked to the selected entry'; image.hidden = false;
    $('inspection-frame').replaceWith(image);
    inspectionURL = url; url = null;
    show('inspection-frame-note', 'Explicitly linked pixels decoded; physical paint unmeasured.');
  } catch (error) {
    if (generation === inspectionGeneration) show('inspection-frame-note', `Pixels unavailable: ${error.message}. Latest pixels are not substituted.`);
  } finally { if (url) URL.revokeObjectURL(url); }
}
$('follow-latest').addEventListener('click', () => {
  following = true; timelineSession = currentSession; selectedEntry = null; deepLink = null;
  ++inspectionGeneration; inspectionController?.abort();
  if (inspectionURL) URL.revokeObjectURL(inspectionURL);
  inspectionURL = null; $('inspection-frame').hidden = true;
  show('inspection-heading', 'Select an entry'); show('inspection-scope', 'Inspection does not stop automation or replay input.');
  show('entry-summary', 'Choose recorded activity to inspect its original evidence.'); show('entry-text', '');
  show('entry-details', 'No entry selected.'); $('entry-links').replaceChildren();
  show('inspection-coverage', 'Select evidence to see its retained coverage.');
  show('inspection-frame-note', 'No source selected.'); show('inspection-source', '');
  renderTimeline(); updateLocation(); void refreshActivity();
});
$('timeline-session').addEventListener('change', () => {
  following = false;
  timelineSession = $('timeline-session').value === 'previous' ? previousSession : currentSession;
  listedEntries = activitySnapshots.get(timelineSession)?.entries || [];
  renderEntryList(); renderTimeline();
});
function resolveDeepLink() {
  if (!deepLink) return;
  const snapshot = activitySnapshots.get(deepLink.session);
  const entry = snapshot?.entries.find(item => item.id === deepLink.event && (!deepLink.producer || item.producer === deepLink.producer) && (!deepLink.actor || item.actor_id === deepLink.actor));
  if (entry) { deepLink = null; selectEntry(entry); return; }
  show('inspection-heading', 'Linked evidence unavailable');
  show('inspection-coverage', 'Linked evidence is not retained; coverage is unavailable.');
  show('entry-summary', `Session ${deepLink.session} · entry ${deepLink.event} is not retained on this page. Reload, eviction or server replacement may have removed it.`);
  show('inspection-frame-note', 'Pixels unavailable; no unrelated latest source substituted.');
}
async function refreshActivity() {
  if (activityBusy) return;
  clearTimeout(activityTimer); activityBusy = true;
  const generation = sessionGeneration;
  const controller = new AbortController();
  try {
    const snapshot = await bounded(() => getJSON('/api/activity', controller), controller);
    if (snapshot.schema !== 'observer-activity/1' || typeof snapshot.session !== 'string' || !Array.isArray(snapshot.entries)) throw new Error('Unsupported activity schema');
    if (snapshot.session !== currentSession || generation !== sessionGeneration) return;
    const entries = snapshot.entries.filter(entry => entry.session === snapshot.session && typeof entry.id === 'string' && typeof entry.producer === 'string');
    const seen = new Set();
    snapshot.entries = entries.filter(entry => { const key = entryKey(entry); if (seen.has(key)) return false; seen.add(key); return true; }).slice(-ACTIVITY_LIMIT);
    snapshot.clientOmitted = entries.length - snapshot.entries.length;
    if (snapshot.latest_statement?.session !== snapshot.session) snapshot.latest_statement = null;
    const retained = activitySnapshots.get(snapshot.session);
    if (!following && timelineSession === snapshot.session && retained) {
      const oldKeys = new Set(retained.entries.map(entryKey));
      retained.newItems = snapshot.entries.filter(entry => !oldKeys.has(entryKey(entry))).length;
    } else activitySnapshots.set(snapshot.session, snapshot);
    activityError = '';
    latestActivity = snapshot; // The newest poll, even while Timeline inspection is frozen.
    renderActivity(snapshot); renderTimeline(); resolveDeepLink(); settleReturn();
  } catch (error) {
    if (generation === sessionGeneration) { activityError = error.message; renderTimeline(); show('activity-summary', `Activity unavailable: ${error.message}. Last snapshot retained; current activity unknown.`); }
  } finally {
    activityBusy = false; activityTimer = setTimeout(() => { void refreshActivity(); }, POLL_MS);
  }
}
if (typeof location !== 'undefined' && typeof URLSearchParams !== 'undefined') {
  const params = new URLSearchParams(location.hash.slice(1));
  if (VIEWS.includes(params.get('view'))) activateView(params.get('view'), false);
  if (params.has('session') && params.has('event')) {
    deepLink = {session: params.get('session'), event: params.get('event'), producer: params.get('producer'), actor: params.get('actor')};
    following = false; timelineSession = deepLink.session; resolveDeepLink();
  }
}
// Session attachment reads only the current identity; the shared reader has no
// actor capability. Missing assets cannot prevent the independent Pause handler.
try {
  if (typeof EnactiveInvestigationSession === 'undefined') throw new Error('Investigation reader asset unavailable');
  investigationSession = EnactiveInvestigationSession.mount($('investigation-root'), {
    status: $('investigation-session-status'), refreshButton: $('investigation-refresh'), getSession: () => currentSession});
  if (activeView === 'analysis') investigationSession.activate();
} catch (error) {
  $('investigation-root').textContent = `Recorded investigation unavailable: ${error.message}. Current-target Pause remains independent.`;
}
void refresh();
void refreshActivity();
