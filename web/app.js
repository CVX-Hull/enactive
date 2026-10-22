'use strict';
const $ = (id) => document.getElementById(id);
let token = document.querySelector('meta[name="controller-token"]').content;
let credentialRefresh = null;
let credentialEpoch = 0;
let credentialError = '';
let statusTransportFailed = false;
let transportError = '';
let latest = null;
let displayed = null;
let requestedFrame = '';
let gameplayBusy = false;
let missionError = '';
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
let memoryRendering;
const observerMeasurements = {status: [], frames: []};
function retainMeasurement(lane, sample) {
  observerMeasurements[lane].push(sample);
  if (observerMeasurements[lane].length > 32) observerMeasurements[lane].shift();
}
function observerMeasurementSnapshot() {
  return {schema: 'observer-timing/2',
    clock: 'browser performance.now() monotonic milliseconds; browser Date.now() and native state.timestamp_ms epoch milliseconds',
    scope: 'Local monotonic status/decode/DOM intervals and next animation callback opportunity, not paint; raw epoch anchors support offline correlation assuming a shared host wall clock. Native capture uses frame_ms/presented_ms via state.timestamp_ms when frame_ok; wall-clock discontinuities and negative cross-clock durations need interpretation. Failed, superseded and stale frames are not successful fresh presentation; native-to-browser and end-to-end player latency unmeasured',
    connection: latest?.connection || 'unavailable', displayed_frame_fresh: !!currentFrame(),
    displayed_frame_identity: frameIdentity(displayed),
    status: observerMeasurements.status.map(sample => ({...sample})),
    frames: observerMeasurements.frames.map(sample => ({...sample}))};
}
function renderMeasurements() {
  $('observer-measurements').textContent = JSON.stringify(observerMeasurementSnapshot(), null, 2);
}
function validFrameGeometry(state) {
  if (state?.protocol !== 6 || typeof state.frame_ok !== 'boolean') return false;
  const geometry = state.frame_geometry;
  if (!state.frame_ok) return geometry === null;
  if (!record(geometry) || Object.keys(geometry).sort().join(',') !==
      'output_height,output_width,viewport,window_height,window_width') return false;
  const dimension = value => Number.isInteger(value) && value >= 1 && value <= 16384;
  if (!['window_width', 'window_height', 'output_width', 'output_height'].every(key => dimension(geometry[key])) ||
      geometry.output_width * geometry.output_height > 16777216) return false;
  const viewport = geometry.viewport;
  return Array.isArray(viewport) && viewport.length === 4 &&
    viewport.every(value => Number.isInteger(value) && value >= 0 && value <= 16384) &&
    viewport[2] > 0 && viewport[3] > 0 && viewport[0] + viewport[2] <= geometry.output_width &&
    viewport[1] + viewport[3] <= geometry.output_height;
}

function showError(message) {
  $('error').textContent = message;
  $('error').hidden = !message;
}
function showErrors(extra = '') {
  const lastError = latest?.last_result?.error;
  showError([...new Set([localError, missionError, recoveryError, frameError, credentialError, transportError,
    latest?.error && `Controller snapshot diagnostic: ${latest.error}`,
    latest?.state?.error && `Native snapshot diagnostic: ${latest.state.error}`,
    lastError && (missionState().kind === 'terminal' ?
      `Recorded last-command history (not a current mission decision): ${lastError}` : lastError), extra].filter(Boolean))].join('\n'));
}
function refreshCredentials() {
  if (credentialRefresh) return credentialRefresh;
  credentialRefresh = (async () => {
    try {
      const response = await fetch('/', {cache: 'no-store', credentials: 'same-origin'});
      if (!response.ok) throw new Error('Controller page unavailable');
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const freshToken = page.querySelector('meta[name="controller-token"]')?.content;
      if (typeof freshToken !== 'string' || !freshToken.trim()) throw new Error('Controller credentials unavailable');
      token = freshToken;
      credentialError = '';
    } catch {
      credentialError = 'Local controller credentials could not be refreshed. Reload this page before another request.';
      throw new Error(credentialError);
    } finally {
      credentialRefresh = null;
      showErrors();
      updateControls();
    }
  })();
  credentialEpoch += 1;
  if (requestedFrame !== displayed?.frame) requestedFrame = '';
  invalidateAuthority();
  return credentialRefresh;
}
async function submit(url, payload, pause = false) {
  const sentToken = token;
  const send = credential => fetch(url, {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-CDDA-Token': credential},
    body: JSON.stringify(payload), credentials: 'same-origin'
  });
  const response = await send(sentToken);
  if (response.status === 403) {
    try { await refreshCredentials(); }
    catch { return response; }
    // Only an explicit Pause can repeat after the server rejected admission.
    if (pause && token !== sentToken) return send(token);
  }
  return response;
}
function frameIdentity(state) {
  if (!state) return '';
  const boundary = state.boundary;
  return JSON.stringify([state.protocol, state.session, state.revision, state.frame,
    boundary?.kind, boundary?.id, boundary?.control_generation, boundary?.interrupt_request_id,
    boundary?.recovery_operations, state.takeover_generation, state.pause_origin, state.frame_geometry]);
}
function currentFrame() {
  return !credentialRefresh && !statusTransportFailed && displayed && validFrameGeometry(displayed) && validFrameGeometry(latest?.state) && latest.state.frame_ok && latest.connection === 'fresh' &&
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
  if (displayed.protocol !== 6 || displayed.boundary?.input_receiver !== true || !['normal_play', 'menu'].includes(displayed.boundary?.kind)) {
    throw new Error('This input boundary needs native control. Observe again after returning to supported play or a menu.');
  }
  return {expected_session: displayed.session, expected_revision: displayed.revision};
}
function eligibleRecovery(kind) {
  if (!currentFrame() || displayed.protocol !== 6) return false;
  const boundary = displayed.boundary;
  const expected = {request_interrupt: 'activity_poll', answer_interrupt: 'interrupt_confirmation',
    continue_debug_once: 'debug_prompt'};
  return boundary?.kind === expected[kind] && typeof boundary.id === 'string' && boundary.id.length > 0 &&
    Number.isInteger(boundary.control_generation) && boundary.control_generation >= 0 &&
    boundary.recovery_operations?.length === 1 && boundary.recovery_operations[0] === kind &&
    (kind !== 'answer_interrupt' || typeof boundary.interrupt_request_id === 'string' && boundary.interrupt_request_id.length > 0);
}
function recoveryAuthority(kind, choice) {
  if (missionLocksControls()) throw new Error('Manual recovery is locked by mission execution or inconsistent mission status. Use Pause or the native window.');
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
// Phase and lease describe different things: a paused mission still owns its execution.
function missionState() {
  const mission = latest?.mission;
  if (mission === null) return {kind: 'none', mission: null};
  if (!mission || typeof mission !== 'object' || Array.isArray(mission) ||
      typeof mission.phase !== 'string' || typeof mission.mission_id !== 'string' || !mission.mission_id.trim() ||
      !Number.isSafeInteger(mission.epoch) || mission.epoch < 0) return {kind: 'invalid', mission};
  if (['completed', 'failed', 'stopped'].includes(mission.phase)) return {kind: 'terminal', mission};
  if (['admitted', 'active', 'paused', 'reconciling', 'handoff', 'finishing'].includes(mission.phase)) return {kind: 'nonterminal', mission};
  return {kind: 'invalid', mission};
}
function missionLocksControls() {
  return ['nonterminal', 'invalid'].includes(missionState().kind);
}
function renderControlState() {
  const mode = missionState();
  const paused = latest?.pause_requested || latest?.state?.paused;
  const disconnected = latest?.connection === 'disconnected';
  const statusSuffix = disconnected ? ' · DISCONNECTED' : latest?.connection !== 'fresh' ? ' · STATUS STALE' : '';
  $('control-state').textContent = credentialRefresh ? 'REFRESHING LOCAL CONTROLLER CREDENTIALS · PAUSE AVAILABLE' : mode.kind === 'invalid' ? `MISSION STATUS INCONSISTENT${statusSuffix}` :
    mode.kind === 'terminal' ? `MISSION ${mode.mission.phase.toUpperCase()} · HISTORY${statusSuffix}` :
    mode.kind === 'nonterminal' ? `MISSION ${mode.mission.phase.toUpperCase()} · ${known(mode.mission.actor_id)}${paused || latest?.frozen ? ' · CONTROL PAUSED' : ''}${statusSuffix}` :
    latest?.connection !== 'fresh' ? 'CONTROL UNAVAILABLE · STATUS DISCONNECTED OR STALE' :
    latest?.frozen ? 'PAUSED · UNRECONCILED' : paused ? 'PAUSED' : currentFrame() ? 'REMOTE CONTROL READY' : 'WAITING FOR CURRENT FRAME';
  $('control-state').classList.toggle('active', !!latest && !paused && !latest.frozen &&
    currentFrame() && mode.kind !== 'invalid' && mode.kind !== 'terminal');
}
function updateControls() {
  renderControlState();
  const missionLocked = missionLocksControls();
  const recoveryPending = recoveryBusy || recoveryNeedsObserve || !!latest?.control_pending;
  document.querySelectorAll('.send').forEach((button) => {
    button.disabled = missionLocked || gameplayBusy || recoveryPending || !currentFrame() || !!latest?.frozen || !!latest?.pause_requested;
  });
  $('resume').disabled = missionLocked || gameplayBusy || recoveryPending || !currentFrame() || !!latest?.frozen ||
    displayed?.boundary?.input_receiver !== true || !['normal_play', 'menu'].includes(displayed?.boundary?.kind);
  $('observe').disabled = !!credentialRefresh || observeBusy || missionState().kind === 'invalid';
  $('pause').disabled = false;
  for (const [id, kind] of [['recovery-interrupt', 'request_interrupt'], ['recovery-yes', 'answer_interrupt'],
    ['recovery-no', 'answer_interrupt'], ['recovery-debug', 'continue_debug_once']]) {
    const eligible = eligibleRecovery(kind);
    $(id).hidden = !eligible;
    $(id).disabled = missionLocked || recoveryPending || !eligible;
  }
  $('recovery-state').textContent = missionLocked ?
    'Manual recovery is locked while a mission owns execution or its status is inconsistent. Pause remains available.' :
    recoveryBusy ? 'Recovery request in flight; Pause is available.' :
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
async function loadFrame(state, statusSample) {
  if (!state.frame || state.frame === requestedFrame) return;
  requestedFrame = state.frame;
  const frameCredentialEpoch = credentialEpoch;
  const timing = {frame_identity: frameIdentity(state), session: state.session, revision: state.revision,
    frame: state.frame, native_capture_epoch_ms: state.timestamp_ms ?? null,
    status_sequence: statusSample?.sequence ?? null,
    status_ready_ms: statusSample?.response_ready_ms ?? null,
    status_ready_epoch_ms: statusSample?.response_ready_epoch_ms ?? null, decode_started_ms: performance.now(),
    decoded_ms: null, decode_ms: null, dom_replaced_ms: null, dom_replaced_epoch_ms: null, status_to_dom_ms: null,
    presentation_opportunity_ms: null, outcome: 'decoding'};
  retainMeasurement('frames', timing);
  renderMeasurements();
  const candidate = new Image();
  candidate.id = 'frame';
  candidate.alt = 'Actual frame captured by the native CDDA Tiles renderer';
  candidate.src = `/frame.png?name=${encodeURIComponent(state.frame)}`;
  try {
    await candidate.decode();
    timing.decoded_ms = performance.now();
    timing.decode_ms = timing.decoded_ms - timing.decode_started_ms;
    if (requestedFrame !== state.frame || frameCredentialEpoch !== credentialEpoch) {
      timing.outcome = 'superseded'; renderMeasurements(); return;
    }
    if (candidate.naturalWidth !== state.frame_geometry.output_width ||
        candidate.naturalHeight !== state.frame_geometry.output_height) {
      throw new Error('Decoded PNG dimensions disagree with frame geometry.');
    }
    $('frame').replaceWith(candidate);
    timing.dom_replaced_ms = performance.now();
    timing.dom_replaced_epoch_ms = Date.now();
    timing.status_to_dom_ms = timing.status_ready_ms === null ? null : timing.dom_replaced_ms - timing.status_ready_ms;
    timing.outcome = 'dom_replaced';
    // A callback offers a presentation opportunity; it is not proof of screen paint.
    requestAnimationFrame(() => {
      if (displayed === state && $('frame') === candidate) {
        timing.presentation_opportunity_ms = performance.now();
      }
      renderMeasurements();
    });
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
    $('frame-note').textContent = latest?.connection === 'disconnected' ? 'DISCONNECTED · LAST FRAME' :
      current ? 'FRESH · NATIVE CAPTURE' :
      latest?.state?.status === 'dispatched' ? 'INPUT DISPATCHED · WAITING FOR ENGINE' :
      'LAST FRAME · WAITING FOR CURRENT OBSERVATION';
    renderMission();
    showErrors();
    updateControls();
    renderMeasurements();
  } catch (error) {
    timing.outcome = 'decode_failed';
    renderMeasurements();
    if (requestedFrame === state.frame && frameCredentialEpoch === credentialEpoch) {
      requestedFrame = '';
      displayed = null;
      $('frame-shell').classList.add('stale');
      $('frame-note').textContent = 'FRAME UNAVAILABLE · LAST FRAME';
      frameError = `The current game frame could not be loaded: ${error.message}. Observe again.`;
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
  if (credentialRefresh && kind !== 'pause') return;
  if (kind === 'observe') {
    const mode = missionState().kind;
    if (mode === 'nonterminal') return missionObserve();
    if (mode === 'invalid') { showError('Mission status is inconsistent. Observe and manual controls are locked; Pause and the native window remain available.'); return; }
  }
  const ordinary = !['pause', 'observe'].includes(kind);
  if (ordinary && missionLocksControls()) {
    showError('Mission execution owns remote input or its status is inconsistent. Use Pause or take control in the native window.');
    return;
  }
  if (ordinary && (gameplayBusy || recoveryBusy || recoveryNeedsObserve || latest?.control_pending)) return;
  if (kind === 'observe' && observeBusy) return;
  if (ordinary) gameplayBusy = true;
  if (kind === 'observe') observeBusy = true;
  const observeEpoch = authorityEpoch;
  if (kind === 'pause' || ordinary) invalidateAuthority();
  updateControls();
  try {
    const response = await submit('/api/command', {kind, ...payload}, kind === 'pause');
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
async function missionObserve() {
  if (credentialRefresh || observeBusy) return;
  const {kind, mission} = missionState();
  if (kind !== 'nonterminal') return;
  observeBusy = true;
  missionError = '';
  updateControls();
  try {
    const request = {schema: 'mission/10', kind: 'observe', request_id: crypto.randomUUID(),
      mission_id: mission.mission_id, epoch: mission.epoch};
    const response = await submit('/api/mission', request);
    const result = await response.json();
    const admission = response.ok && result.status === 'accepted' ?
      'Admission recorded; not ready or effect proof. Watch status for the outcome.' :
      'Response recorded. Check mission status and retained evidence before another operation; no automatic retry.';
    $('mission-result').textContent = `${admission}\n${JSON.stringify(result, null, 2)}`;
    missionError = result.error || (response.ok ? '' : `Mission Observe failed (${response.status})`);
  } catch (error) {
    missionError = `Mission Observe response unavailable; outcome unknown: ${error.message}. Inspect status; do not retry an uncertain operation.`;
    $('mission-result').textContent = missionError;
  } finally {
    observeBusy = false;
    showErrors();
    updateControls();
    await refresh();
  }
}
function known(value) {
  return value === null || value === undefined ? 'unknown' :
    typeof value === 'object' ? JSON.stringify(value) : String(value);
}
function evidence(value, empty) {
  return value === null || value === undefined ? empty : JSON.stringify(value, null, 2);
}
function record(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function recordedId(value) {
  return typeof value === 'string' && value.trim().length > 0;
}
function renderLifecycle(mission) {
  const phase = mission?.lifecycle_phase;
  const checkpoint = record(phase) && phase.grants_authority === false &&
    [phase.origin_request_id, phase.operation, phase.checkpoint_id].every(recordedId);
  const terminal = missionState().kind === 'terminal';
  $('mission-lifecycle').textContent = checkpoint ?
    `${terminal ? 'Historical lifecycle checkpoint' : mission.active_operation === null ? 'Awaiting lifecycle decision' : 'Lifecycle checkpoint'} · ${phase.operation} · request ${phase.origin_request_id} · checkpoint ${phase.checkpoint_id} · grants no authority` :
    phase == null ? 'No lifecycle checkpoint reported' : 'Lifecycle checkpoint unavailable or inconsistent; inspect evidence';
  const process = mission?.native_process;
  const sample = record(process) && record(process.last_sample) ? process.last_sample : null;
  const sampled = sample && typeof sample.running === 'boolean' && typeof sample.outcome === 'string';
  const connection = latest?.connection === 'disconnected' ? 'service disconnected' :
    latest?.connection === 'fresh' ? 'status connected' : 'status stale or unavailable';
  const custody = record(process) && Array.isArray(process.unresolved_custody_requests) ?
    `${process.unresolved_custody_requests.length} unresolved custody request(s)` : 'unresolved custody unknown';
  $('mission-process').textContent = `${sampled ?
    `Historical last sample · owner ${known(process.owner_mission_id)} · launch ${known(sample.launch_id)} · running: ${sample.running} · outcome ${sample.outcome} · exit code: ${known(sample.returncode)}` :
    'No usable process sample'} · ${custody} · ${connection} · current liveness unknown`;
  const result = mission?.progress;
  const proof = record(result) ? result.normal_exit : null;
  const finish = record(result) ? result.normal_finish : null;
  const finishRecorded = record(finish) && finish.schema === 'mission/10' && finish.record_type === 'NormalFinish' &&
    finish.grants_authority === false && [finish.final_source_id, finish.normal_exit_result_request_id].every(recordedId) &&
    ((finish.disposition === 'stopped' && finish.completed_work_event_id === null) ||
     (finish.disposition === 'completed' && recordedId(finish.completed_work_event_id)));
  // Summarize the producer's recorded proof; process samples and ACKs cannot supply it.
  const verified = record(proof) && proof.schema === 'mission/10' && proof.record_type === 'OwnedNormalExit' &&
    proof.grants_authority === false && proof.returncode === 0 &&
    (proof.no_save_required === true || proof.no_save_required === false && recordedId(proof.saved_checkpoint_request_id)) &&
    [proof.origin_request_id, proof.launch_request_id, proof.launch_id,
      proof.terminal_logical_id, proof.native_request_id].every(recordedId) &&
    Array.isArray(proof.source_ids) && proof.source_ids.length > 0 && proof.source_ids.every(recordedId) &&
    record(proof.retirement) && proof.retirement.grants_authority === false && proof.retirement.returncode === 0 &&
    proof.retirement.launch_id === proof.launch_id && proof.retirement.exit_request_id === proof.origin_request_id &&
    typeof proof.retirement.retired_pending === 'boolean' &&
    proof.retirement.native_request_id === (proof.retirement.retired_pending ? proof.native_request_id : null) &&
    result.phase?.operation === 'exit' && result.phase?.stage === 'complete';
  const receipt = record(mission?.last_receipt) ? mission.last_receipt : null;
  const matchesExit = verified && receipt?.native_request_id === proof.native_request_id &&
    receipt?.logical_action_id === proof.terminal_logical_id;
  $('mission-exit').textContent = `${finishRecorded ?
    `Recorded normal finish report · ${finish.disposition === 'completed' ? 'player-reported objective completion' : 'normal cleanup; objective completion unclaimed'} · exit result ${finish.normal_exit_result_request_id} · final source ${finish.final_source_id} · mission state ${known(mission.phase)}. This report does not establish independent campaign acceptance` : verified ?
    `Recorded verified normal exit effect · launch ${proof.launch_id} · ${proof.no_save_required ? 'no save required (untouched menu)' : `saved checkpoint ${proof.saved_checkpoint_request_id}`}` :
    'No verified normal exit proof reported'}. Latest primitive receipt ${known(receipt?.native_request_id)} · logical ${known(receipt?.logical_action_id)} · acknowledgment ${known(receipt?.transport_disposition)}. ${matchesExit ?
    'Matches the recorded terminal exit input.' : 'Not correlated with a recorded terminal exit input.'} Acknowledgment and exit effect are separate evidence.`;
}
function countMap(value) {
  return record(value) && Object.values(value).every(count => Number.isSafeInteger(count) && count >= 0);
}
function measuredCounts(metrics) {
  const operations = metrics?.operations;
  const primitives = metrics?.primitives;
  const total = value => Object.values(value).reduce((sum, count) => sum + count, 0);
  return {
    operations: record(operations) && Number.isSafeInteger(operations.total) && operations.total >= 0 &&
      ['by_kind', 'by_skill', 'by_state'].every(key => countMap(operations[key])) &&
      total(operations.by_kind) === operations.total && total(operations.by_state) === operations.total &&
      total(operations.by_skill) === (operations.by_kind.skill || 0) ? operations : null,
    primitives: record(primitives) && Number.isSafeInteger(primitives.charged) && primitives.charged >= 0 &&
      countMap(primitives.by_state) && total(primitives.by_state) === primitives.charged ? primitives : null
  };
}
function labeledCounts(value) {
  return value ? Object.entries(value).map(([key, count]) => `${key}: ${count}`).join(' · ') || 'none recorded' : 'unavailable';
}
function renderActivity(mission) {
  const phase = mission?.activity_phase;
  const valid = record(phase) && phase.grants_authority === false && typeof phase.answered === 'boolean' &&
    [phase.origin_request_id, phase.checkpoint_id, phase.stage].every(recordedId) &&
    (phase.interrupt_request_id === null || recordedId(phase.interrupt_request_id));
  $('mission-activity').textContent = valid ?
    `${missionState().kind === 'terminal' ? 'Historical activity checkpoint' : 'Private paused activity'} · ${phase.stage} · request ${phase.origin_request_id} · checkpoint ${phase.checkpoint_id} · interrupt ${known(phase.interrupt_request_id)} · answered: ${phase.answered} · grants no authority` :
    phase == null ? 'No private activity checkpoint reported' : 'Activity checkpoint unavailable or inconsistent; inspect evidence';
  const reported = mission?.progress?.phase;
  $('mission-last-report').textContent = record(reported) ?
    `Last reported result · ${known(reported.operation)} · ${known(reported.stage)} · historical report, not a live phase or acceptance` :
    'No result phase reported; inspect retained evidence';
}
function memoryList(id, items, limit, describe) {
  const list = $(id);
  list.replaceChildren();
  const add = (title, lines = []) => {
    const item = document.createElement('li');
    const heading = document.createElement('strong');
    heading.textContent = title;
    item.append(heading);
    for (const line of lines) {
      const paragraph = document.createElement('p');
      paragraph.textContent = line;
      item.append(paragraph);
    }
    list.append(item);
  };
  if (!Array.isArray(items)) { add('Unavailable in this packet'); return; }
  if (!items.length) { add('None included in this query-specific packet'); return; }
  for (const item of items.slice(0, limit)) {
    const description = record(item) ? describe(item) : ['Malformed entry; inspect raw context'];
    add(description[0], description.slice(1));
  }
  if (items.length > limit) add(`${items.length - limit} additional entries not summarized; inspect raw context`);
}
function memoryValue(value) {
  const text = known(value);
  return text.length <= 2048 ? text : `${text.slice(0, 2048)}… [truncated; inspect raw context]`;
}
function memoryIds(value) {
  return Array.isArray(value) ? value.slice(0, 32).map(memoryValue).join(', ') || 'none reported' : 'unavailable';
}
function quantities(value) {
  return Array.isArray(value) ? value.slice(0, 16).map(item => record(item) ?
    `${memoryValue(item.subject)}: ${memoryValue(item.quantity)} ${memoryValue(item.unit)}` : 'malformed quantity').join('; ') || 'none reported' : 'unavailable';
}
function renderMemory(mission) {
  const memory = mission?.memory_context;
  const usable = record(memory) && memory.schema === 'campaign-memory/5' && memory.grants_authority === false;
  $('mission-memory-summary').textContent = usable ?
    `Historical, query-specific last journaled context · packet ${known(memory.packet_id)} · memory version ${known(memory.memory_version)} · query ${known(memory.query)} · as of ${known(memory.as_of)} · scope ${known(memory.scope)}. Status labels belong to that packet, not the current world. This preview is not current authority and is not recomputed by the viewer.` :
    `No journaled context preview available${memory == null ? '' : ' (unavailable or inconsistent packet)'}. Memory version ${known(mission?.memory_version)} · last packet ${known(mission?.last_context_id)}.`;
  const rendering = evidence(memory, 'No memory claims, work or source dispositions available.');
  // Polls repeat the same historical packet. Preserve scroll/selection while it
  // is being read; compare content as well as ID so corrections still render.
  if (rendering === memoryRendering) return;
  memoryRendering = rendering;
  $('mission-memory-readable').hidden = !usable;
  const packet = usable ? memory : {};
  memoryList('mission-claims', packet.claims, 32, claim => [
    `${memoryValue(claim.status)} · ${memoryValue(claim.kind)} · ${memoryValue(claim.id)}`,
    memoryValue(claim.text),
    `Value: ${memoryValue(claim.value)} · Coverage: ${memoryValue(claim.coverage)}`,
    `Sources: ${memoryIds(claim.sources)} · Observed: ${memoryValue(claim.observed_time)}`,
    `Supersedes: ${memoryIds(claim.supersedes)} · Support groups: ${memoryValue(claim.supports)}`
  ]);
  memoryList('mission-work', packet.work, 16, work => [
    `Historical Work status: ${memoryValue(work.status)} · ${memoryValue(work.intent)} · ${memoryValue(work.id)}`,
    `Recorded stage: ${memoryValue(work.stage)} · Progress: ${Number.isInteger(work.progress) && work.progress >= 0 && work.progress <= 100 ? `${work.progress}%` : 'unknown'} · Predecessor: ${memoryValue(work.predecessor_work_id)}`,
    `Available: ${quantities(work.available)} · Committed: ${quantities(work.committed)}`,
    `Predicted output: ${quantities(work.predicted_output)} · Observed output: ${quantities(work.observed_output)}`,
    `Next verification (at packet time): ${memoryValue(work.next_verification)} · Historical unresolved effects: ${memoryIds(work.unresolved_effects)}`,
    `Sources: ${memoryIds(work.sources)}`
  ]);
  memoryList('mission-sources', packet.sources, 16, source => [
    `${memoryValue(source.id)} · ${memoryValue(source.status)}`,
    `Session: ${memoryValue(source.reference?.session)} · Revision: ${memoryValue(source.reference?.revision)} · Turn: ${memoryValue(source.reference?.turn)}`
  ]);
  memoryList('mission-procedures', packet.procedures, 16, procedure => [
    `${memoryValue(procedure.status)} · ${memoryValue(procedure.goal)} · revision ${memoryValue(procedure.revision)}`,
    `Family: ${memoryValue(procedure.procedure_id)} · Owner: ${memoryValue(procedure.mission_id)} · Record: ${memoryValue(procedure.id)}`,
    `Applies: ${memoryValue(procedure.applicability)} · Invalidators: ${memoryValue(procedure.invalidators)}`,
    `Steps: ${memoryValue(procedure.steps)} · Stop: ${memoryValue(procedure.stop_conditions)}`,
    `Support episodes: ${Array.isArray(procedure.support) ? procedure.support.length : 'unknown'} · Counterexamples: ${Array.isArray(procedure.counterexamples) ? procedure.counterexamples.length : 'unknown'} · ${memoryValue(procedure.reason)}`
  ]);
  memoryList('mission-dispositions', record(packet.dispositions) ? Object.entries(packet.dispositions).map(([id, reasons]) => ({id, reasons})) : null,
    48, disposition => [memoryValue(disposition.id), memoryValue(disposition.reasons)]);
  memoryList('mission-reobservations', packet.reobservations, 48, observation => [
    `${memoryValue(observation.id)} · ${memoryValue(observation.reason)}`, memoryValue(observation.instruction),
    `Scope: ${memoryValue(observation.scope)}`
  ]);
  $('mission-omissions').textContent = `Omitted claims: ${known(packet.omitted?.claims)} · Work: ${known(packet.omitted?.work)} · Procedures: ${known(packet.omitted?.procedures)} · Bound exclusions: ${known(packet.omitted?.bounds)} · Reasons: ${known(packet.omitted?.reasons)}. This query-specific packet is not complete campaign memory. Work completion labels are reports, not independent acceptance.`;
  $('mission-memory').textContent = rendering;
}
function renderMission() {
  const {kind, mission} = missionState();
  const available = mission && typeof mission === 'object' && !Array.isArray(mission);
  $('mission-state').textContent = kind === 'none' ? 'NO MISSION' : kind === 'invalid' ? 'INCONSISTENT' : mission.phase.toUpperCase();
  $('mission-summary').textContent = available && typeof mission.objective === 'string' ? mission.objective : 'No mission objective recorded.';
  const configuration = available ? mission.configuration : null;
  $('mission-player').textContent = available ? `${known(mission.actor_id)} · model ${known(configuration?.model)} · effort ${known(configuration?.effort)}` : 'No player admitted';
  $('mission-identity').textContent = available ? `${known(mission.mission_id)} · epoch ${known(mission.epoch)}` : 'No mission identity';
  const snapshotLabel = latest?.connection === 'fresh' ? 'reported snapshot' : 'last reported snapshot; current status unavailable';
  $('mission-owner').textContent = !available ? 'Input lease unknown; no mission snapshot' :
    record(mission.lease_owner) ? `${kind === 'terminal' ? 'Inconsistent lease retained in terminal history' : 'Reported input lease'} · ${known(mission.lease_owner.actor_id)} · ${known(mission.lease_owner.operation)} · lease epoch ${known(mission.lease_owner.epoch)} · ${snapshotLabel}` :
    mission.lease_owner === null ? `No input lease in ${snapshotLabel}` : 'Input lease unknown; missing or inconsistent field';
  $('mission-operation').textContent = kind === 'terminal' ? 'No mission execution; terminal history' : available ? `${mission.active_operation ? known(mission.active_operation) : 'No active operation'} · skill ${mission.skill ? known(mission.skill) : 'none reported'}` : 'No active operation';
  renderLifecycle(available ? mission : null);
  renderActivity(available ? mission : null);
  const metrics = available ? mission.metrics : null;
  const counts = measuredCounts(metrics);
  $('mission-progress').textContent = `${counts.operations ? `${counts.operations.total} retained mission requests` : 'Mission requests: unavailable'} · ${counts.primitives ? `${counts.primitives.charged} charged primitive admissions` : 'Charged primitive admissions: unavailable'}. Requests are not model calls or independent tasks; admissions are not delivered keys.`;
  $('mission-counts').textContent = `Cumulative retained requests by kind: ${labeledCounts(counts.operations?.by_kind)}. By skill: ${labeledCounts(counts.operations?.by_skill)}. By state: ${labeledCounts(counts.operations?.by_state)}. Charged primitives by state: ${labeledCounts(counts.primitives?.by_state)}. Includes rejected, not_dispatched and unknown primitive admissions. Only ledger-admitted operations are counted; read-only calls and pre-admission rejections are excluded. The recent timeline is not the cumulative counter.`;
  $('mission-next').textContent = kind === 'terminal' ? 'No current mission decision; terminal history' :
    available ? known(mission.next_needed_decision) : 'Waiting for an explicitly admitted player mission';
  $('mission-reason').textContent = available ? `${known(mission.pause_cause)} · ${known(mission.reason)}` : 'No mission admitted';
  const freshness = available ? mission.freshness : null;
  $('mission-freshness').textContent = available ?
    `Mission evidence ${freshness?.fresh === true && latest?.connection === 'fresh' ? 'reported fresh' : 'stale or unavailable'} · age ${known(freshness?.age_seconds)}${Number.isFinite(freshness?.age_seconds) ? 's' : ''} · ${currentFrame() ? 'displayed frame fresh' : 'displayed frame unavailable or stale'}` : 'No mission evidence';
  const source = available ? mission.current_source : null;
  $('mission-source').textContent = source ? `${known(source.observation_id)} · session ${known(source.session)} · revision ${known(source.revision)}` : 'No current mission source';
  $('mission-unresolved').textContent = available && Array.isArray(mission.unresolved_effects) ?
    `${mission.unresolved_effects.length} unresolved effect(s) in ${snapshotLabel}. Historical ACKs and Work uncertainty remain separate.` :
    'Unknown unresolved effects; no usable effects list reported';
  $('mission-control-note').textContent = kind === 'invalid' ?
    'Mission status is inconsistent. Manual input, recovery, Resume and Observe are locked. Pause and control in the native window remain available.' :
    kind === 'nonterminal' ?
    'The player owns mission execution, including while paused or without an input lease. Manual input, recovery and Resume are locked. Pause or take control in the native window; native takeover invalidates mission authority.' :
    kind === 'terminal' ? 'Retained mission history owns no execution. Lease and effects describe the reported snapshot; historical process samples, ACKs and Work do not establish current liveness or unresolved effects. Ordinary controls require current decoded evidence and explicit Resume when paused.' :
    'Observer only: missions are admitted outside this viewer. Ordinary controls require current decoded evidence.';
  $('mission-evidence').textContent = kind === 'invalid' ? evidence(mission, 'Mission field missing from status.') : available ? evidence({progress: mission.progress, last_receipt: mission.last_receipt,
    current_source: mission.current_source, unresolved_effects: mission.unresolved_effects,
    prompt_phase: mission.prompt_phase, lifecycle_phase: mission.lifecycle_phase, activity_phase: mission.activity_phase,
    native_process: mission.native_process, diagnostic: mission.diagnostic}, '') : 'No retained mission evidence.';
  $('mission-budgets').textContent = available ? evidence({remaining_limits: mission.remaining_limits,
    cleanup_reserve: mission.cleanup_reserve, configuration: mission.configuration}, '') : 'No mission limits reported.';
  $('mission-usage').textContent = `Harness API spend: ${known(metrics?.harness_api_spend)}. Model requests: unknown. Tool calls: unknown. External tokens: ${known(metrics?.external_tokens)}. API quota: ${known(metrics?.api_quota)}. Model time: ${known(metrics?.model_time_seconds)}. External cost: unknown. Interventions: unknown. Game seconds: ${known(metrics?.game_seconds)}. Usage and remaining budgets do not establish mission outcomes.`;
  $('mission-archive').textContent = evidence(metrics?.archive, 'No archive usage reported.');
  renderMemory(available ? mission : null);
}
async function recover(kind, choice) {
  let payload;
  try { payload = recoveryAuthority(kind, choice); }
  catch (error) { showError(error.message); return; }
  recoveryBusy = true;
  invalidateAuthority();
  try {
    const response = await submit('/api/recovery', {kind, ...payload});
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
    const outcome = event.request.kind === 'run_receipt' ? envelope.result : envelope;
    if (outcome.error) item.className = 'event-error';
    const title = document.createElement('div');
    title.className = 'event-title';
    const text = document.createElement('span');
    const names = {startup: 'Session started paused', observe: 'Observed the game', reconcile: 'Observation reconciled',
      resume: 'Remote control resumed', pause: 'Pause requested', key: 'Sent key', action: 'Sent action',
      walk: 'Guarded walk', goal: 'Objective updated', request_interrupt: 'Interrupt requested',
      answer_interrupt: 'Interrupt answer', continue_debug_once: 'Debug continuation', control_unresolved: 'Recovery unresolved', run_admission: 'Run action admitted',
      run_receipt: 'Native action receipt'};
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
function render(data, statusSample = null) {
  latest = data;
  const state = data.state;
  $('connection').textContent = {fresh: 'Connected', stale: 'Stale observation', disconnected: 'Disconnected / no recent observation'}[data.connection];
  $('connection-dot').className = `dot ${data.connection}`;
  $('age').textContent = data.age_ms === null ? 'No observation' : `${(data.age_ms / 1000).toFixed(1)}s old`;
  const boundary = state?.boundary?.kind;
  $('category').textContent = boundary ? `${boundary.replaceAll('_', ' ').toUpperCase()} · ${state.category}` : 'NO VERIFIED INPUT BOUNDARY';
  $('revision').textContent = state ? `REV ${state.revision}` : 'REV —';
  $('authority').textContent = data.expect ? `Observation authority: ${data.expect}` : 'Observe before choosing an input.';
  $('latency').textContent = `Controller response ${data.latency_ms === null ? '—' : data.latency_ms + ' ms'}`;
  const position = state?.scene?.position;
  $('position').textContent = position ? `Relative position ${position.join(', ')}` : 'Player position unavailable';
  $('frame-shell').classList.toggle('stale', !currentFrame());
  const validGeometry = validFrameGeometry(state);
  if (state && !validGeometry) frameError = 'Unsupported native protocol 6 metadata or invalid required frame geometry; current frame unavailable.';
  else if (frameError.startsWith('Unsupported native protocol')) frameError = '';
  if (validGeometry && state.frame_ok && state.status !== 'dispatched') {
    loadFrame(state, statusSample);
  }
  $('frame-note').textContent = data.connection === 'disconnected' ? 'DISCONNECTED · LAST FRAME' :
    state && !validGeometry ? 'INVALID FRAME METADATA · LAST FRAME' :
    state?.status === 'dispatched' ? 'INPUT DISPATCHED · WAITING FOR ENGINE' :
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
  const recordedGoal = typeof data.mission?.objective === 'string' ? data.mission.objective : typeof data.goal === 'string' ? data.goal : '';
  $('recorded-objective-text').textContent = recordedGoal.trim() ? recordedGoal : 'No objective recorded.';
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
  renderMission();
  showErrors();
  updateControls();
  timeline(data.events);
  renderMeasurements();
}
async function refresh() {
  const sequence = ++refreshSequence;
  const sample = {sequence, started_ms: performance.now(), started_epoch_ms: Date.now(),
    response_ready_ms: null, response_ready_epoch_ms: null,
    status_round_trip_ms: null, frame_identity: '', outcome: 'pending'};
  retainMeasurement('status', sample);
  try {
    const response = await fetch('/api/status', {cache: 'no-store', credentials: 'same-origin'});
    if (!response.ok) throw new Error(`Status request failed (${response.status})`);
    const data = await response.json();
    sample.response_ready_ms = performance.now();
    sample.response_ready_epoch_ms = Date.now();
    sample.status_round_trip_ms = sample.response_ready_ms - sample.started_ms;
    sample.frame_identity = frameIdentity(data.state);
    if (sequence === refreshSequence) {
      if (statusTransportFailed || credentialRefresh) await refreshCredentials();
      if (sequence === refreshSequence) {
        statusTransportFailed = false;
        transportError = '';
        render(data, sample);
      }
    }
    sample.outcome = sequence === refreshSequence ? 'rendered' : 'superseded';
    renderMeasurements();
  } catch (error) {
    if (sample.response_ready_ms === null) {
      sample.response_ready_ms = performance.now();
      sample.response_ready_epoch_ms = Date.now();
    }
    sample.status_round_trip_ms = sample.response_ready_ms - sample.started_ms;
    sample.outcome = 'failed';
    renderMeasurements();
    if (sequence !== refreshSequence) return;
    statusTransportFailed = true;
    transportError = error.message;
    if (latest) latest = {...latest, connection: 'disconnected'};
    renderMission();
    updateControls();
    $('connection').textContent = 'Service disconnected';
    $('connection-dot').className = 'dot disconnected';
    $('frame-shell').classList.add('stale');
    $('frame-note').textContent = 'DISCONNECTED · LAST FRAME';
    showErrors();
    renderMeasurements();
  }
}
$('recovery-interrupt').addEventListener('click', () => recover('request_interrupt'));
$('recovery-yes').addEventListener('click', () => recover('answer_interrupt', 'YES'));
$('recovery-no').addEventListener('click', () => recover('answer_interrupt', 'NO'));
$('recovery-debug').addEventListener('click', () => recover('continue_debug_once'));
$('pause').addEventListener('click', () => command('pause'));
$('resume').addEventListener('click', () => command('resume'));
$('observe').addEventListener('click', () => command('observe'));
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
(async function poll() {
  await refresh();
  // Observe active play promptly without overlapping status requests or asking
  // the player/model to poll per key. Idle/disconnected views keep the old rate.
  const active = latest?.connection !== 'disconnected' &&
    (latest?.mission?.active_operation || latest?.pause_requested === false);
  setTimeout(poll, active ? 250 : 1000);
})();

(function checkFreshness() {
  updateControls();
  renderMission();
  renderMeasurements();
  if (latest?.state && Date.now() - latest.state.timestamp_ms > 3000) {
    $('frame-shell').classList.add('stale');
    $('frame-note').textContent = latest?.connection === 'disconnected' ? 'DISCONNECTED · LAST FRAME' : 'STALE · OBSERVE BEFORE CHOOSING INPUT';
  }
  setTimeout(checkFreshness, 1000);
})();
