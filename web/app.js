'use strict';
const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="controller-token"]').content;
let latest = null;
let displayed = null;
let requestedFrame = '';
let gameplayBusy = false;
let taskBusy = false;
let taskError = '';
let recoveryBusy = false;
let observeBusy = false;
let recoveryError = '';
let recoveryResult = null;
let recoveryNeedsObserve = false;
let refreshSequence = 0;
let invalidatedAuthority = '';
let authorityEpoch = 0;
let lastFrame = '';
let localError = '';
let frameError = '';
let eventSignature = '';

function showError(message) {
  $('error').textContent = message;
  $('error').hidden = !message;
}
function showErrors(extra = '') {
  showError([...new Set([localError, taskError, recoveryError, frameError, latest?.error,
    latest?.last_result?.error, latest?.state?.error, extra].filter(Boolean))].join('\n'));
}
function frameIdentity(state) {
  if (!state) return '';
  const boundary = state.boundary;
  return JSON.stringify([state.protocol, state.session, state.revision, state.frame,
    boundary?.kind, boundary?.id, boundary?.control_generation, boundary?.interrupt_request_id,
    boundary?.recovery_operations]);
}
function currentFrame() {
  return displayed && latest?.state?.frame_ok && latest.connection === 'fresh' &&
    latest.state.status !== 'dispatched' && displayed.frame &&
    Number.isInteger(latest.state.timestamp_ms) && Date.now() - latest.state.timestamp_ms <= 3000 &&
    Date.now() - latest.state.timestamp_ms >= -1000 &&
    frameIdentity(displayed) === frameIdentity(latest.state) &&
    frameIdentity(displayed) !== invalidatedAuthority;
}
function authority() {
  if (!currentFrame()) {
    throw new Error('Wait for the current game frame before choosing an input.');
  }
  if (displayed.protocol !== 3 || !['normal_play', 'menu'].includes(displayed.boundary?.kind)) {
    throw new Error('This input boundary needs native control. Observe again after returning to supported play or a menu.');
  }
  return {expected_session: displayed.session, expected_revision: displayed.revision};
}
function eligibleRecovery(kind) {
  if (!currentFrame() || displayed.protocol !== 3) return false;
  const boundary = displayed.boundary;
  const expected = {request_interrupt: 'activity_poll', answer_interrupt: 'interrupt_confirmation',
    continue_debug_once: 'debug_prompt'};
  return boundary?.kind === expected[kind] && typeof boundary.id === 'string' && boundary.id.length > 0 &&
    Number.isInteger(boundary.control_generation) && boundary.control_generation >= 0 &&
    boundary.recovery_operations?.length === 1 && boundary.recovery_operations[0] === kind &&
    (kind !== 'answer_interrupt' || typeof boundary.interrupt_request_id === 'string' && boundary.interrupt_request_id.length > 0);
}
function recoveryAuthority(kind, choice) {
  if (!eligibleRecovery(kind)) throw new Error('Observe and wait for the exact current recovery frame.');
  if (recoveryBusy || recoveryNeedsObserve || latest.control_pending) {
    throw new Error('Recovery is unresolved. Explicitly Observe after expiry before another operation.');
  }
  const state = displayed;
  const payload = {expected_session: state.session, expected_control_generation: state.boundary.control_generation};
  if (kind !== 'request_interrupt') Object.assign(payload, {expected_boundary_id: state.boundary.id,
    expected_revision: state.revision, expected_frame: state.frame});
  if (kind === 'answer_interrupt') {
    if (!['YES', 'NO'].includes(choice)) throw new Error('Choose Yes or No explicitly.');
    Object.assign(payload, {interrupt_request_id: state.boundary.interrupt_request_id, choice});
  }
  return payload;
}
function updateControls() {
  const recoveryPending = recoveryBusy || recoveryNeedsObserve || !!latest?.control_pending;
  document.querySelectorAll('.send').forEach((button) => {
    button.disabled = !!latest?.run_lease || gameplayBusy || taskBusy || recoveryPending || !currentFrame() || !!latest?.frozen || !!latest?.pause_requested;
  });
  $('resume').disabled = !!latest?.run_lease || gameplayBusy || taskBusy || recoveryPending || !currentFrame() || !!latest?.frozen ||
    !['normal_play', 'menu'].includes(displayed?.boundary?.kind);
  const task = latest?.gameplay;
  const run = task?.run;
  const ready = !taskBusy && !gameplayBusy && !recoveryPending && !latest?.pending &&
    !latest?.run_lease && currentFrame() && displayed?.protocol === 3 && displayed?.boundary?.kind === 'normal_play' &&
    !latest?.frozen && !latest?.pause_requested && !displayed?.paused;
  $('task-start').disabled = !ready || !!task && run?.state !== 'abandoned';
  $('task-continue').disabled = !ready || !task ||
    !['blocked', 'interrupted', 'paused', 'failed', 'budget_exhausted'].includes(run?.state) ||
    task.last_receipt?.disposition === 'unknown';
  $('task-abandon').disabled = taskBusy || !task || run?.state === 'abandoned';
  $('observe').disabled = observeBusy;
  $('pause').disabled = false;
  for (const [id, kind] of [['recovery-interrupt', 'request_interrupt'], ['recovery-yes', 'answer_interrupt'],
    ['recovery-no', 'answer_interrupt'], ['recovery-debug', 'continue_debug_once']]) {
    const eligible = eligibleRecovery(kind);
    $(id).hidden = !eligible;
    $(id).disabled = recoveryPending || !eligible;
  }
  $('recovery-state').textContent = recoveryBusy ? 'Recovery request in flight; Pause is available.' :
    latest?.control_pending || recoveryNeedsObserve ? 'Recovery unresolved. Explicitly Observe after native expiry to reconcile; do not retry.' :
    ['request_interrupt', 'answer_interrupt', 'continue_debug_once'].some(eligibleRecovery) ?
      'Recovery available for the displayed boundary. Gameplay stays paused.' :
      'No recovery operation authorized by the current decoded frame. Observe to inspect.';
}
function invalidateAuthority() {
  // A response or passive repaint of the frame used for submission cannot rearm it.
  authorityEpoch += 1;
  invalidatedAuthority = frameIdentity(latest?.state);
  updateControls();
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
    const current = currentFrame();
    if (current) frameError = '';
    $('frame-shell').classList.toggle('stale', !current);
    $('frame-note').textContent = current ? 'FRESH · NATIVE CAPTURE' :
      latest?.state?.status === 'dispatched' ? 'INPUT DISPATCHED · WAITING FOR ENGINE' :
      'LAST FRAME · WAITING FOR CURRENT OBSERVATION';
    renderGameplay(latest?.gameplay);
    updateControls();
  } catch (error) {
    if (requestedFrame === state.frame) {
      requestedFrame = '';
      displayed = null;
      $('frame-shell').classList.add('stale');
      $('frame-note').textContent = 'FRAME UNAVAILABLE · LAST FRAME';
      frameError = 'The current game frame could not be loaded. Observe again.';
      showErrors();
      updateControls();
    }
  }
}
function showResult(result, recovery = false) {
  $(recovery ? 'recovery-result' : 'last-result').textContent = JSON.stringify(result, null, 2);
  if (!recovery) $('result-status').textContent = result.status || 'ERROR';
}
async function command(kind, payload = {}) {
  const ordinary = !['pause', 'goal', 'observe'].includes(kind);
  if (ordinary && latest?.run_lease) {
    showError('A gameplay run owns input. Pause to take over, then observe and resume.');
    return;
  }
  if (ordinary && (gameplayBusy || taskBusy || recoveryBusy || recoveryNeedsObserve || latest?.control_pending)) return;
  if (kind === 'observe' && observeBusy) return;
  if (ordinary) gameplayBusy = true;
  if (kind === 'observe') observeBusy = true;
  const observeEpoch = authorityEpoch;
  if (kind === 'pause' || ordinary) invalidateAuthority();
  updateControls();
  try {
    const response = await fetch('/api/command', {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CDDA-Token': token},
      body: JSON.stringify({kind, ...payload}), credentials: 'same-origin'
    });
    const result = await response.json();
    showResult(result);
    localError = result.error || (response.ok ? '' : `Command failed (${response.status})`);
    if (kind === 'observe' && response.ok && result.status === 'ready' &&
        observeEpoch === authorityEpoch && !recoveryBusy) {
      recoveryNeedsObserve = false;
      invalidatedAuthority = '';
    }
  } catch (error) {
    localError = error.message;
    showError(localError);
  } finally {
    if (ordinary) gameplayBusy = false;
    if (kind === 'observe') observeBusy = false;
    showErrors();
    updateControls();
    await refresh();
  }
}
function taskAuthority() {
  const expected = authority();
  if (displayed.boundary?.kind !== 'normal_play' || latest.frozen || latest.pause_requested || displayed.paused) {
    throw new Error('Observe normal play and explicitly Resume remote control before starting or continuing a task.');
  }
  return expected;
}
async function gameplayCommand(kind) {
  if (taskBusy) return;
  let payload;
  try {
    updateControls();
    if (!['start', 'continue', 'abandon'].includes(kind) || $(`task-${kind}`).disabled) {
      throw new Error('This task operation is unavailable. Check the task state, resume control and observe a fresh frame.');
    }
    if (kind === 'start') {
      const direction = $('task-direction').value;
      const distance = Number($('task-distance').value);
      if (!['north', 'east', 'south', 'west'].includes(direction) || !Number.isInteger(distance) || distance < 1 || distance > 4) {
        throw new Error('Choose a cardinal direction and an outbound distance from 1 to 4 tiles.');
      }
      payload = {direction, distance, ...taskAuthority()};
    } else {
      const task = latest.gameplay;
      if (typeof task.run_id !== 'string' || !Number.isInteger(task.run.execution_epoch)) {
        throw new Error('The service has not supplied an exact run identity and execution epoch.');
      }
      payload = {run_id: task.run_id, execution_epoch: task.run.execution_epoch};
      if (kind === 'continue') Object.assign(payload, taskAuthority());
    }
  } catch (error) { taskError = error.message; showErrors(); return; }
  taskBusy = true;
  taskError = '';
  invalidateAuthority();
  try {
    const response = await fetch('/api/gameplay', {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CDDA-Token': token},
      body: JSON.stringify({kind, ...payload}), credentials: 'same-origin'
    });
    const result = await response.json();
    $('task-result').textContent = JSON.stringify(result, null, 2);
    taskError = result.error || (response.ok ? '' : `Task request failed (${response.status})`);
  } catch (error) {
    taskError = `Task response unavailable: ${error.message}. Inspect status before choosing another operation.`;
    $('task-result').textContent = taskError;
  } finally {
    taskBusy = false;
    showErrors();
    updateControls();
    await refresh();
  }
}
function renderGameplay(gameplay) {
  const task = gameplay?.task;
  const run = gameplay?.run;
  const planner = gameplay?.planner;
  $('task-state').textContent = run?.state?.replaceAll('_', ' ').toUpperCase() || 'NOT STARTED';
  $('task-summary').textContent = task ? `${task.distance} tile(s) ${task.direction}, then return to ${task.origin.join(', ')}. Target ${task.target.join(', ')}.` :
    'Choose a short route from the current observed position.';
  const steps = run?.progress?.verified_steps;
  const leg = Number.isInteger(steps) && task ? steps >= task.distance ? 'Return' : 'Outbound' : '';
  $('task-stage').textContent = run ? `${leg} · ${run.stage_id || 'No stage admitted'} · epoch ${run.execution_epoch}` : 'No task admitted';
  $('task-player').textContent = run ? `${run.model_id || 'Identity unreported'} · ${run.configuration_id || 'Configuration unreported'}${planner?.pending_request_id ? ' · waiting for candidate' : ''}` :
    'External chat · waiting for explicit start';
  $('task-executor').textContent = run?.lease_owner ? `${run.lease_owner}${run.paused ? ' · paused' : ' · run owns input'}` :
    run?.paused ? 'Paused · no run owns input' : 'No run owns input';
  $('task-progress').textContent = run ? `${steps} / ${2 * task.distance} verified step(s) · displacement ${run.progress.displacement.join(', ')}` : 'No verified movement';
  $('task-next').textContent = run?.next_check || 'Observe, then resume remote control to start.';
  $('task-reason').textContent = run?.last_public_reason || 'No task admitted';
  $('task-control-note').textContent = run?.state === 'completed' ?
    'Completed task and progress retained. Abandon this task before starting another.' :
    'Start and Continue use the current decoded frame. Continue keeps the original task and budgets; resume remote control explicitly first. Unknown effects prohibit continuation.';
  $('task-freshness').textContent = run ? `${run.fresh ? 'Task evidence fresh' : 'Task evidence stale or unavailable'} · ${currentFrame() ? 'displayed frame fresh' : 'displayed frame unavailable or stale'}` : 'No task evidence';
  $('task-evidence').textContent = gameplay ? JSON.stringify({run_id: gameplay.run_id, task_id: task.task_id,
    evidence: run.evidence, last_receipt: gameplay.last_receipt,
    pending_request_id: planner?.pending_request_id, planner_deadline_ms: planner?.deadline_ms}, null, 2) : 'No retained task evidence.';
  $('task-budgets').textContent = task ? JSON.stringify({original: task.budgets, remaining: run.remaining_budgets}, null, 2) : 'Original budgets appear after admission.';
}
async function recover(kind, choice) {
  let payload;
  try { payload = recoveryAuthority(kind, choice); }
  catch (error) { showError(error.message); return; }
  recoveryBusy = true;
  invalidateAuthority();
  try {
    const response = await fetch('/api/recovery', {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CDDA-Token': token},
      body: JSON.stringify({kind, ...payload}), credentials: 'same-origin'
    });
    recoveryResult = await response.json();
    showResult(recoveryResult, true);
    recoveryError = recoveryResult.error || (response.ok ? '' : `Recovery failed (${response.status})`);
    recoveryNeedsObserve = !response.ok || recoveryResult.status === 'unknown';
    if (recoveryNeedsObserve) authorityEpoch += 1;
  } catch (error) {
    recoveryError = error.message;
    recoveryNeedsObserve = true;
    authorityEpoch += 1;
    recoveryResult = {status: 'unknown', error: recoveryError, detail: 'Response unavailable; delivery is unknown. Explicitly Observe after expiry.'};
    showResult(recoveryResult, true);
  } finally {
    recoveryBusy = false;
    showErrors();
    updateControls();
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
    const envelope = event.outcome;
    const outcome = ['run_receipt', 'gameplay_receipt'].includes(event.request.kind) ? envelope.result : envelope;
    if (outcome.error) item.className = 'event-error';
    const title = document.createElement('div');
    title.className = 'event-title';
    const text = document.createElement('span');
    const names = {startup: 'Session started paused', observe: 'Observed the game', reconcile: 'Observation reconciled',
      resume: 'Remote control resumed', pause: 'Pause requested', key: 'Sent key', action: 'Sent action',
      walk: 'Guarded walk', goal: 'Objective updated', request_interrupt: 'Interrupt requested',
      answer_interrupt: 'Interrupt answer', continue_debug_once: 'Debug continuation', control_unresolved: 'Recovery unresolved', run_admission: 'Run action admitted',
      run_receipt: 'Native action receipt', gameplay_receipt: 'Task action receipt',
      malformed_gameplay_receipt: 'Invalid task receipt'};
    text.textContent = `${names[event.request.kind] || event.request.kind} ${event.request.key || event.request.action || ''}`;
    const time = document.createElement('span');
    time.className = 'event-time';
    time.textContent = new Date(event.timestamp_ms).toLocaleTimeString([], {hour12: false});
    title.append(text, time);
    const detail = document.createElement('div');
    detail.className = 'event-detail';
    detail.textContent = `${outcome.status || (event.request.kind === 'run_admission' ? 'Admission recorded; delivery not yet established' : 'Evidence recorded')}${outcome.error ? ' · ' + outcome.error : ''}${outcome.retirement ? ' · ' + outcome.retirement : ''}`;
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
  $('control-state').textContent = data.frozen ? 'PAUSED · UNRECONCILED' : paused ? 'PAUSED' : data.run_lease ? `RUN OWNED · ${data.run_lease.owner}` : 'REMOTE CONTROL READY';
  $('control-state').classList.toggle('active', !paused && !data.frozen);
  const boundary = state?.boundary?.kind;
  $('category').textContent = boundary ? `${boundary.replaceAll('_', ' ').toUpperCase()} · ${state.category}` : 'NO VERIFIED INPUT BOUNDARY';
  $('revision').textContent = state ? `REV ${state.revision}` : 'REV —';
  $('authority').textContent = data.expect ? `Observation authority: ${data.expect}` : 'Observe before choosing an input.';
  $('latency').textContent = `Last response ${data.latency_ms === null ? '—' : data.latency_ms + ' ms'}`;
  const position = state?.scene?.position;
  $('position').textContent = position ? `Relative position ${position.join(', ')}` : 'Player position unavailable';
  $('frame-shell').classList.toggle('stale', !currentFrame());
  if (state?.frame_ok && state.status !== 'dispatched') {
    loadFrame(state);
  }
  $('frame-note').textContent = state?.status === 'dispatched' ? 'INPUT DISPATCHED · WAITING FOR ENGINE' :
    state?.frame_ok && state.frame !== lastFrame ? 'LOADING CURRENT FRAME' :
    !lastFrame ? 'NO NATIVE FRAME' : currentFrame() ? 'FRESH · NATIVE CAPTURE' :
    state?.frame_ok ? 'LAST FRAME · WAITING FOR CURRENT OBSERVATION' : 'LAST FRAME · CAPTURE UNAVAILABLE';
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
  const recordedGoal = typeof data.goal === 'string' ? data.goal : '';
  $('recorded-objective-text').textContent = recordedGoal.trim() ? recordedGoal : 'No objective recorded.';
  if (document.activeElement !== $('goal')) $('goal').value = data.goal;
  if (data.last_result) {
    $('last-result').textContent = JSON.stringify(data.last_result, null, 2);
    $('result-status').textContent = data.last_result.status.toUpperCase();
  }
  const recoveryEvents = data.events.filter(event => ['request_interrupt', 'answer_interrupt', 'continue_debug_once'].includes(event.request.kind));
  if (!recoveryResult && recoveryEvents.length) showResult(recoveryEvents[recoveryEvents.length - 1].outcome, true);
  const gameplayUnknowns = data.unknown_outcomes || [];
  const recoveryUnknowns = data.control_unknown_outcomes || [];
  $('gameplay-pending').textContent = `Gameplay: ${gameplayBusy ? 'request in flight' : data.pending ? 'pending / unresolved' : 'no live request'} · ${gameplayUnknowns.length} retained unknown outcome(s)`;
  $('recovery-pending').textContent = `Recovery: ${recoveryBusy ? 'request in flight' : data.control_pending || recoveryNeedsObserve ? 'pending / unresolved' : 'no live request'} · ${recoveryUnknowns.length} retained unknown outcome(s)`;
  $('gameplay-evidence').textContent = JSON.stringify({pending: data.pending || null, unknown_outcomes: gameplayUnknowns,
    historical_incidents: (data.historical_unknowns || []).filter(item => item.channel === 'gameplay')}, null, 2);
  $('recovery-evidence').textContent = JSON.stringify({pending: data.control_pending || null, unknown_outcomes: recoveryUnknowns,
    historical_incidents: (data.historical_unknowns || []).filter(item => item.channel === 'control')}, null, 2);
  $('journal').textContent = data.journal;
  renderGameplay(data.gameplay);
  showErrors();
  updateControls();
  timeline(data.events);
}
async function refresh() {
  const sequence = ++refreshSequence;
  try {
    const response = await fetch('/api/status', {cache: 'no-store', credentials: 'same-origin'});
    if (!response.ok) throw new Error(`Status request failed (${response.status})`);
    const data = await response.json();
    if (sequence === refreshSequence) render(data);
  } catch (error) {
    if (sequence !== refreshSequence) return;
    if (latest) latest = {...latest, connection: 'disconnected'};
    renderGameplay(latest?.gameplay);
    updateControls();
    $('connection').textContent = 'Service disconnected';
    $('connection-dot').className = 'dot disconnected';
    $('frame-shell').classList.add('stale');
    $('frame-note').textContent = 'DISCONNECTED · LAST FRAME';
    showErrors(error.message);
  }
}
$('recovery-interrupt').addEventListener('click', () => recover('request_interrupt'));
$('recovery-yes').addEventListener('click', () => recover('answer_interrupt', 'YES'));
$('recovery-no').addEventListener('click', () => recover('answer_interrupt', 'NO'));
$('recovery-debug').addEventListener('click', () => recover('continue_debug_once'));
$('task-form').addEventListener('submit', (event) => { event.preventDefault(); gameplayCommand('start'); });
$('task-continue').addEventListener('click', () => gameplayCommand('continue'));
$('task-abandon').addEventListener('click', () => gameplayCommand('abandon'));
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

(function checkFreshness() {
  updateControls();
  renderGameplay(latest?.gameplay);
  if (latest?.state && Date.now() - latest.state.timestamp_ms > 3000) {
    $('frame-shell').classList.add('stale');
    $('frame-note').textContent = 'STALE · OBSERVE BEFORE CHOOSING INPUT';
  }
  setTimeout(checkFreshness, 1000);
})();
