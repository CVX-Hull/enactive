// Control strip. Vanilla DOM, no framework, no viewer: it reads only the custodian's
// /api/status and /api/source/<id> (through the supervised gateway) and posts Pause.
// A viewer or framework failure therefore cannot change what this file shows or does.
// The page and tools/campaign_watch_ui.js (the operator check) agree on these element
// ids and text formats; see docs/contracts/evaluation.md "Control path and viewer".
const $ = id => document.getElementById(id);
const POLL_MS = 1000;
const TIMEOUT_MS = 2500;
const HOLD_MS = 800;
const REASONS = {loop: 'Runaway loop or stall', fault: 'Harness or custody fault', spend: 'Spend', other: 'Other'};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function chip(kind, word, detail) {
  const node = el('span', `pv ${kind}`, word);
  if (detail) { node.append(' ', el('small', '', detail)); }
  return node;
}
function emit(name, detail) { document.dispatchEvent(new CustomEvent(name, {detail})); }

/* ------------------------------------------------------------------ theme */
const root = document.documentElement;
try { const saved = localStorage.getItem('theme'); if (saved === 'light' || saved === 'dark') root.dataset.theme = saved; } catch { /* no storage */ }
$('theme').addEventListener('click', () => {
  const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  root.dataset.theme = dark ? 'light' : 'dark';
  try { localStorage.setItem('theme', root.dataset.theme); } catch { /* no storage */ }
  emit('enactive:theme', {theme: root.dataset.theme});
});

/* ------------------------------------------------------------------ status */
let session = null;
let latest = null;          // last good status
let receivedAt = null;      // browser time of the last good status
let shown = null;           // {key, source} of the decoded frame in #frame
let frameGeneration = 0;
let loadingKey = null;     // a source being fetched; a slow fetch must not be restarted by every poll
let live = true;            // from the page's playhead; the operator check needs live
let playheadNote = false;

const short = id => (id.length > 12 ? `${id.slice(0, 8)}…` : id);
const val = x => (x === null || x === undefined ? 'unreported' : String(x));
const minutes = s => (Number.isFinite(s) ? (s >= 120 ? `${Math.round(s / 60)} min` : `${Math.round(s)} s`) : 'unreported');

function stateLine(status) {
  const stop = status.stop || {};
  if (stop.stop_requested) {
    return stop.native_pause_confirmed ? 'Paused · native pause confirmed' : 'Pause requested · native confirmation pending';
  }
  if (status.native_returncode !== null && status.native_returncode !== undefined) {
    return `Native process exited (code ${status.native_returncode})`;
  }
  return 'Running';
}

function renderSub() {
  const sub = $('statussub');
  const parts = [];
  if (latest) {
    const source = latest.latest_source;
    if (source) {
      const age = (Date.now() - source.presented_ms) / 1000;
      const text = age < 0 ? 'last frame · clocks differ' : `last frame ${Math.round(age)} s ago`;
      parts.push(el('span', '', text), chip('rec', 'recorded', 'control path'));
    } else parts.push(el('span', '', 'no frame yet'));
    const actors = (latest.actors || []).filter(a => a.stage === 'active');
    if (actors.length) parts.push(el('span', '', `${actors.map(a => a.actor_id).join(', ')} active`));
    const op = latest.last_operation;
    if (op) parts.push(el('span', '', `last ${val(op.kind)} ${val(op.status)}`));
    const rem = latest.remaining;
    if (rem) parts.push(el('span', '', `${minutes(rem.custodian_seconds)} left · ${val(rem.inputs)} inputs`));
    const host = latest.host;
    if (host) parts.push(el('span', '', `${val(host.model)} · ${val(host.requests_total)}/${val(host.max_requests_total)} requests`));
  }
  if (!live) parts.push(el('span', 'state watch', 'check off · inspecting history'));
  sub.replaceChildren(...parts);
}

function renderStatus(status) {
  latest = status;
  const nowIso = new Date(receivedAt).toISOString();
  $('connection').textContent = 'Status received';
  $('connection').dataset.state = 'ok';
  $('control-freshness').textContent = `Last status received ${nowIso}; recorded state is not proof of liveness.`;
  $('status-error').hidden = true;
  $('status-error').textContent = '';
  $('statusline').textContent = `${stateLine(status)} · session ${short(status.session)}`;
  $('current-session-full').textContent = status.session;
  const stopped = !!status.stop?.stop_requested;
  const button = $('pause');
  button.disabled = stopped;
  button.firstChild.textContent = stopped ? 'Pause requested' : 'Pause run…';
  $('pause-hint').hidden = stopped;
  renderSub();
  emit('enactive:control', {ok: true, status, receivedAt});
}

function renderStatusError(error) {
  $('connection').textContent = 'Status unavailable';
  $('connection').dataset.state = 'error';
  $('control-freshness').textContent = receivedAt === null
    ? 'No current-session status received; liveness unknown.'
    : `Last status received ${new Date(receivedAt).toISOString()}; current state unknown.`;
  $('status-error').textContent = `Status unavailable: ${error.message}. What is shown is the last snapshot; Pause still works.`;
  $('status-error').hidden = false;
  emit('enactive:control', {ok: false, status: latest, receivedAt});
}

async function getJSON(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(path, {...options, signal: controller.signal, cache: 'no-store', credentials: 'same-origin'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } finally { clearTimeout(timer); }
}

/* ------------------------------------------------------------------ frame */
function hex(buffer) { return [...new Uint8Array(buffer)].map(b => b.toString(16).padStart(2, '0')).join(''); }

async function showSource(source) {
  const generation = ++frameGeneration;
  if (!source || source.schema !== 'computer-source/1' || source.session !== session
      || typeof source.source_id !== 'string' || !/^[a-f0-9]{64}$/.test(source.sha256 || '')) {
    $('frame-note').textContent = source ? 'Frame metadata unsupported' : 'No frame yet';
    return;
  }
  let url = null;
  loadingKey = source.source_id;
  try {
    const response = await fetch(`/api/source/${encodeURIComponent(source.source_id)}`, {cache: 'force-cache', credentials: 'same-origin'});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    if (generation !== frameGeneration) return;
    if (globalThis.crypto?.subtle) {
      const digest = hex(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer()));
      if (digest !== source.sha256) throw new Error('PNG digest differs from the recorded source');
    }
    url = URL.createObjectURL(blob);
    const decoded = new Image();
    decoded.src = url;
    await decoded.decode();
    if (generation !== frameGeneration) return;
    decoded.id = 'frame';
    decoded.alt = 'Live game screen from the control path';
    decoded.hidden = false;
    $('frame').replaceWith(decoded);
    if (shown) URL.revokeObjectURL(shown.url);
    shown = {key: source.source_id, url, source};
    url = null;
    $('frame-note').textContent = source.source_id.slice(-12);
    $('source-details').textContent = `Session: ${source.session}\nSource: ${source.source_id}\nCapture: ${source.capture_id}\n`
      + `SHA-256: ${source.sha256}\nOriginal presented_ms: ${source.presented_ms}\nOriginal received_wall: ${source.received_wall}\n`
      + `PNG: ${source.width} × ${source.height} · native window: ${source.window_width} × ${source.window_height}\n`
      + `Viewport: [${source.viewport.join(', ')}]`;
    emit('enactive:frame', {url: shown.url, source});
  } catch (error) {
    if (generation === frameGeneration) $('frame-note').textContent = `Frame unavailable: ${error.message}`;
  } finally {
    if (url) URL.revokeObjectURL(url);
    if (generation === frameGeneration) loadingKey = null;
  }
}

let busy = false;
async function poll() {
  if (busy) return;
  busy = true;
  try {
    const status = await getJSON('/api/status');
    if (status.schema !== 'computer-status/1' || typeof status.session !== 'string' || !status.session) {
      throw new Error('Unsupported status schema');
    }
    if (session !== status.session) {
      session = status.session; shown = null; loadingKey = null; frameGeneration++;
      $('source-details').textContent = 'No displayed source.';
      $('frame').hidden = true;
    }
    receivedAt = Date.now();
    renderStatus(status);
    const key = status.latest_source ? status.latest_source.source_id : null;
    if (key !== (shown && shown.key) && key !== loadingKey) void showSource(status.latest_source);
  } catch (error) {
    renderStatusError(error);
  } finally {
    busy = false;
    setTimeout(poll, POLL_MS);
  }
}
void poll();
setInterval(() => { if (latest) renderSub(); }, 1000);

// The viewer page loads after this file; it asks for the current state once it is listening.
document.addEventListener('enactive:hello', () => {
  if (latest) emit('enactive:control', {ok: $('connection').dataset.state === 'ok', status: latest, receivedAt});
  if (shown) emit('enactive:frame', {url: shown.url, source: shown.source});
});

/* ------------------------------------------------------------------ operator check: live only */
function checkButton() { return document.getElementById('watch-record'); }
function applyCheck() {
  const button = checkButton();
  if (!button) return;
  if (!live) {
    button.dataset.playheadLock = '1';
    if (!button.disabled) button.disabled = true;
    button.title = 'Disabled while the playhead is not live: return to live to record a check';
  } else if (button.dataset.playheadLock) {
    delete button.dataset.playheadLock;
    button.disabled = false;
    button.removeAttribute('title');
  }
}
document.addEventListener('enactive:playhead', event => {
  live = event.detail.live !== false;
  applyCheck(); renderSub();
});
if (checkButton()) {
  // The check script re-enables its button after each attempt; keep it off while not live.
  new MutationObserver(() => { if (!live && !checkButton().disabled) applyCheck(); })
    .observe(checkButton(), {attributes: true, attributeFilter: ['disabled']});
}

/* ------------------------------------------------------------------ Pause: hold to confirm, then a sheet */
const pause = $('pause');
const sheet = $('sheet');
const form = $('sheetform');
let holdTimer = null;
let returnFocus = null;
let factsExtra = '';
document.addEventListener('enactive:facts', event => { factsExtra = event.detail.text || ''; });

function endHold() {
  clearTimeout(holdTimer); holdTimer = null;
  $('fillbar').style.transition = 'none';
  $('fillbar').style.width = '0';
}
function startHold(event) {
  if (pause.disabled || (event.button !== undefined && event.button !== 0)) return;
  $('fillbar').style.transition = `width ${HOLD_MS}ms linear`;
  $('fillbar').style.width = '100%';
  holdTimer = setTimeout(openSheet, HOLD_MS);
}
pause.addEventListener('pointerdown', startHold);
for (const name of ['pointerup', 'pointerleave', 'pointercancel']) pause.addEventListener(name, endHold);
pause.addEventListener('contextmenu', event => event.preventDefault());
pause.addEventListener('keydown', event => {
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); if (!event.repeat) openSheet(); }
});
pause.addEventListener('click', () => {
  if (!pause.disabled && sheet.hidden) $('pause-hint').textContent = 'Keep holding for about a second, or press Enter, to open the confirmation.';
});

function openSheet() {
  endHold();
  if (!sheet.hidden || pause.disabled) return;
  returnFocus = document.activeElement;
  const who = latest ? `Session ${short(latest.session)}. ` : '';
  $('sheet-title').textContent = 'Pause this run?';
  $('sheetfacts').textContent = `${who}${factsExtra} Pause permanently ends this run; it cannot be resumed. `
    + 'The run is recorded as censored with your reason.';
  for (const radio of form.elements.why) radio.checked = false;
  $('sheet-error').hidden = true;
  $('sheetsubmit').disabled = false;
  sheet.hidden = false;
  form.elements.why[0].focus();
}
function closeSheet() {
  sheet.hidden = true;
  (returnFocus && returnFocus.focus ? returnFocus : pause).focus();
}
$('sheetcancel').addEventListener('click', closeSheet);
sheet.addEventListener('pointerdown', event => { if (event.target === sheet) closeSheet(); });
document.addEventListener('keydown', event => {
  if (sheet.hidden) return;
  if (event.key === 'Escape') { event.preventDefault(); closeSheet(); return; }
  if (event.key === 'Tab') {
    const items = [...form.querySelectorAll('input, button')].filter(node => !node.disabled);
    const first = items[0], last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
});
form.addEventListener('submit', async event => {
  event.preventDefault();
  const choice = form.elements.why.value;
  const error = $('sheet-error');
  if (!REASONS[choice]) {
    error.textContent = 'Choose a reason before pausing.';
    error.hidden = false;
    form.elements.why[0].focus();
    return;
  }
  $('sheetsubmit').disabled = true;
  error.hidden = true;
  try {
    const result = await getJSON('/api/pause', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({reason: choice})});
    if (result.schema !== 'computer-pause/1' || typeof result.session !== 'string' || !result.stop?.stop_requested) {
      throw new Error('Unsupported or unconfirmed Pause reply');
    }
    const note = $('pause-result');
    note.textContent = `Pause requested (${REASONS[choice]}). Native confirmation appears in the status line.`;
    note.hidden = false;
    $('statusline').textContent = `Pause requested · native confirmation pending · session ${short(result.session)}`;
    sheet.hidden = true;
    pause.focus();
    void poll();
  } catch (failure) {
    error.textContent = `Pause was not accepted: ${failure.message}. Use the native window if it is urgent.`;
    error.hidden = false;
    $('sheetsubmit').disabled = false;
  }
});
