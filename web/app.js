'use strict';
const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="controller-token"]').content;
let latest = null;
let displayed = null;
let requestedFrame = '';
let busy = false;
let lastFrame = '';
let localError = '';
let eventSignature = '';

function showError(message) {
  $('error').textContent = message;
  $('error').hidden = !message;
}
function authority() {
  const state = displayed;
  if (!state || !latest?.state?.frame_ok || latest.connection !== 'fresh' ||
      state.session !== latest.state.session || state.revision !== latest.state.revision) {
    throw new Error('Wait for the current game frame before choosing an input.');
  }
  return {expected_session: state.session, expected_revision: state.revision};
}
async function loadFrame(state) {
  if (!state.frame || state.frame === requestedFrame) return;
  requestedFrame = state.frame;
  const candidate = new Image();
  candidate.id = 'frame';
  candidate.alt = 'Actual frame captured by the native CDDA Tiles renderer';
  candidate.src = `/frame.png?name=${encodeURIComponent(state.frame)}`;
  try {
    await candidate.decode();
    if (requestedFrame !== state.frame) return;
    $('frame').replaceWith(candidate);
    $('frame-placeholder').hidden = true;
    if (!displayed || displayed.session !== state.session || displayed.revision !== state.revision) {
      $('key').value = '';
      $('action').value = '';
      $('direction').value = '';
    }
    displayed = state;
    lastFrame = state.frame;
    const current = latest?.connection === 'fresh' && latest?.state?.frame_ok &&
      latest.state.status !== 'dispatched' && latest.state.session === state.session &&
      latest.state.revision === state.revision;
    $('frame-shell').classList.toggle('stale', !current);
    $('frame-note').textContent = current ? 'FRESH · NATIVE CAPTURE' :
      latest?.state?.status === 'dispatched' ? 'INPUT DISPATCHED · WAITING FOR ENGINE' :
      'LAST FRAME · WAITING FOR CURRENT OBSERVATION';
  } catch (error) {
    if (requestedFrame === state.frame) {
      requestedFrame = '';
      displayed = null;
      $('frame-shell').classList.add('stale');
      $('frame-note').textContent = 'FRAME UNAVAILABLE · LAST FRAME';
      showError('The current game frame could not be loaded. Observe again.');
    }
  }
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll('.send, #resume, #observe').forEach((button) => { button.disabled = value; });
}
async function command(kind, payload = {}) {
  if (busy && kind !== 'pause' && kind !== 'goal') return;
  if (kind !== 'pause' && kind !== 'goal') setBusy(true);
  try {
    const response = await fetch('/api/command', {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CDDA-Token': token},
      body: JSON.stringify({kind, ...payload}), credentials: 'same-origin'
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || JSON.stringify(result));
    localError = result.error || '';
    $('last-result').textContent = JSON.stringify(result, null, 2);
    $('result-status').textContent = result.status || 'ERROR';
  } catch (error) {
    localError = error.message;
    showError(localError);
  } finally {
    if (kind !== 'pause' && kind !== 'goal') setBusy(false);
    await refresh();
  }
}
function timeline(events) {
  const signature = JSON.stringify(events);
  if (signature === eventSignature) return;
  eventSignature = signature;
  $('timeline').replaceChildren();
  [...events].reverse().slice(0, 30).forEach((event) => {
    const item = document.createElement('li');
    const outcome = event.outcome;
    if (outcome.error) item.className = 'event-error';
    const title = document.createElement('div');
    title.className = 'event-title';
    const text = document.createElement('span');
    const names = {startup: 'Session started paused', observe: 'Observed the game', reconcile: 'Observation reconciled',
      resume: 'Remote control resumed', pause: 'Pause requested', key: 'Sent key', action: 'Sent action',
      walk: 'Guarded walk', goal: 'Objective updated'};
    text.textContent = `${names[event.request.kind] || event.request.kind} ${event.request.key || event.request.action || ''}`;
    const time = document.createElement('span');
    time.className = 'event-time';
    time.textContent = new Date(event.timestamp_ms).toLocaleTimeString([], {hour12: false});
    title.append(text, time);
    const detail = document.createElement('div');
    detail.className = 'event-detail';
    detail.textContent = `${outcome.status}${outcome.error ? ' · ' + outcome.error : ''}${outcome.retirement ? ' · ' + outcome.retirement : ''}`;
    item.append(title, detail);
    $('timeline').append(item);
  });
  $('event-count').textContent = `${events.length} RECENT EVENTS`;
}
function render(data) {
  latest = data;
  const state = data.state;
  $('connection').textContent = {fresh: 'Connected', stale: 'Stale observation', disconnected: 'Disconnected / no recent observation'}[data.connection];
  $('connection-dot').className = `dot ${data.connection}`;
  $('age').textContent = data.age_ms === null ? 'No observation' : `${(data.age_ms / 1000).toFixed(1)}s old`;
  const paused = data.pause_requested || state?.paused;
  $('control-state').textContent = data.frozen ? 'PAUSED · UNRECONCILED' : paused ? 'PAUSED' : 'REMOTE CONTROL READY';
  $('control-state').classList.toggle('active', !paused && !data.frozen);
  $('category').textContent = state?.category || 'NO INPUT CONTEXT';
  $('revision').textContent = state ? `REV ${state.revision}` : 'REV —';
  $('authority').textContent = data.expect ? `Observation authority: ${data.expect}` : 'Observe before choosing an input.';
  $('latency').textContent = `Last response ${data.latency_ms === null ? '—' : data.latency_ms + ' ms'}`;
  const position = state?.scene?.position;
  $('position').textContent = position ? `Relative position ${position.join(', ')}` : 'Player position unavailable';
  $('frame-shell').classList.toggle('stale', data.connection !== 'fresh' || !state?.frame_ok || state.frame !== lastFrame);
  if (state?.frame_ok && state.status !== 'dispatched') {
    loadFrame(state);
  }
  $('frame-note').textContent = state?.status === 'dispatched' ? 'INPUT DISPATCHED · WAITING FOR ENGINE' :
    state?.frame_ok && state.frame !== lastFrame ? 'LOADING CURRENT FRAME' :
    !lastFrame ? 'NO NATIVE FRAME' : state?.frame_ok ? `${data.connection.toUpperCase()} · NATIVE CAPTURE` : 'LAST FRAME · CAPTURE UNAVAILABLE';
  const select = $('action');
  const actions = state?.actions || [];
  if (JSON.stringify(actions) !== select.dataset.actions) {
    const chosen = select.value;
    select.replaceChildren();
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Choose an action';
    select.append(placeholder);
    actions.forEach((action) => {
      const option = document.createElement('option');
      option.value = option.textContent = action;
      select.append(option);
    });
    if (actions.includes(chosen)) select.value = chosen;
    select.dataset.actions = JSON.stringify(actions);
  }
  if (document.activeElement !== $('goal')) $('goal').value = data.goal;
  if (data.last_result) {
    $('last-result').textContent = JSON.stringify(data.last_result, null, 2);
    $('result-status').textContent = data.last_result.status.toUpperCase();
  }
  $('journal').textContent = data.journal;
  showError(localError || data.error || data.last_result?.error || state?.error || '');
  timeline(data.events);
}
async function refresh() {
  try {
    const response = await fetch('/api/status', {cache: 'no-store', credentials: 'same-origin'});
    if (!response.ok) throw new Error(`Status request failed (${response.status})`);
    render(await response.json());
  } catch (error) {
    $('connection').textContent = 'Service disconnected';
    $('connection-dot').className = 'dot disconnected';
    $('frame-shell').classList.add('stale');
    $('frame-note').textContent = 'DISCONNECTED · LAST FRAME';
    showError(error.message);
  }
}
$('pause').addEventListener('click', () => command('pause'));
$('resume').addEventListener('click', () => command('resume'));
$('observe').addEventListener('click', () => command('observe'));
$('goal-form').addEventListener('submit', (event) => { event.preventDefault(); command('goal', {text: $('goal').value}); });
for (const kind of ['action', 'key']) {
  $(`${kind}-form`).addEventListener('submit', (event) => {
    event.preventDefault();
    try { command(kind, {[kind]: $(kind).value, ...authority()}); }
    catch (error) { showError(error.message); }
  });
}
$('walk-form').addEventListener('submit', (event) => {
  event.preventDefault();
  try { command('walk', {direction: $('direction').value, steps: Number($('steps').value), ...authority()}); }
  catch (error) { showError(error.message); }
});
(async function poll() { await refresh(); setTimeout(poll, 1000); })();
