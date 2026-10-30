/* Current snapshot transport stays separate from control and recorded inspection. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const tick = () => new Promise(setImmediate);
(async () => {
  let session = null, options, destroyed = false;
  const requests = [], candidates = [], timers = new Map(); let timerId = 0;
  const status = {textContent: ''}, button = {disabled: false, listeners: {}, addEventListener(k, f) { this.listeners[k] = f; }};
  const reader = {cancelPending() {}, destroy() { destroyed = true; },
    loadSnapshot(text, expected) { return new Promise(resolve => candidates.push({text, expected, resolve})); }};
  const context = vm.createContext({AbortController, TextEncoder, Date, Promise,
    EnactiveInvestigation: {mount(root, selected) { options = selected; return reader; }},
    fetch(url, config) { return new Promise(resolve => requests.push({url, config, resolve})); },
    setTimeout(callback, delay) { const id = ++timerId; timers.set(id, {callback, delay}); return id; },
    clearTimeout(id) { timers.delete(id); }});
  vm.runInContext(fs.readFileSync(require.resolve('../web/investigation-session.js'), 'utf8'), context);
  const api = context.EnactiveInvestigationSession.mount({}, {status, refreshButton: button, getSession: () => session});
  async function reply(code, text = '{}', length = Buffer.byteLength(text)) {
    const r = requests.shift(); assert.ok(r);
    assert.equal(r.url, '/api/investigation');
    let read = false;
    r.resolve({status: code, headers: {get: key => key === 'Content-Length' ? String(length) : null},
      async text() { read = true; return text; }});
    await tick(); return {request: r, wasRead: () => read};
  }
  api.activate(); assert.equal(requests.length, 0);
  session = 'current-one'; api.sessionChanged(session);
  assert.equal(requests.length, 1); assert.equal(requests[0].config.method, 'POST');
  assert.equal(button.disabled, true);
  await reply(202);
  const poll = [...timers.entries()].find(([, t]) => t.delay === 150); assert.ok(poll);
  timers.delete(poll[0]); poll[1].callback(); await tick();
  assert.equal(requests[0].config.method, 'GET');
  const raw = '{"opaque":"large JSON is parsed only by the reader worker"}';
  await reply(200, raw);
  assert.equal(candidates[0].text, raw); assert.equal(candidates[0].expected, session);
  options.onLoaded({kind: 'snapshot', snapshot: {session, wall_ms: 1000}}); candidates.shift().resolve(true); await tick();
  assert.equal(button.disabled, false); assert.match(status.textContent, /snapshot completed/);
  api.activate(); assert.equal(requests.length, 0, 'View activation never overwrites loaded inspection');
  session = 'current-two'; api.sessionChanged(session);
  assert.equal(requests.length, 0, 'Replacement admission retains historical inspection');
  assert.match(status.textContent, /recorded history/); assert.equal(button.textContent, 'Attach current session');
  button.listeners.click(); await reply(503); await tick();
  assert.match(status.textContent, /Previously loaded evidence remains recorded/);
  assert.equal(candidates.length, 0);
  button.listeners.click(); const late = requests[0];
  options.onImport(); assert.equal(late.config.signal.aborted, true);
  const importedStatus = status.textContent;
  await reply(200, raw); await tick();
  assert.equal(candidates.length, 0, 'A late server response cannot replace deliberate file import');
  assert.equal(status.textContent, importedStatus);
  options.onLoaded({kind: 'file'});
  options.onLoadFailed({kind: 'file'}); assert.match(status.textContent, /import failed/);
  options.onLoadFailed({kind: 'file', cancelled: true}); assert.match(status.textContent, /import cancelled/);
  session = 'current-three'; api.sessionChanged(session); assert.equal(requests.length, 0);
  button.listeners.click(); const oversized = await reply(200, '{}', 16 * 1024 * 1024 + 4097);
  assert.equal(oversized.wasRead(), false, 'Reject oversized HTTP framing before reading a large body');
  assert.match(status.textContent, /bounded HTTP contract/);
  button.listeners.click();
  const timeout = [...timers.entries()].find(([, t]) => t.delay === 12000); assert.ok(timeout);
  timers.delete(timeout[0]); timeout[1].callback(); await tick();
  assert.match(status.textContent, /12 seconds/); assert.equal(button.disabled, false);
  await reply(200, raw); assert.equal(candidates.length, 0);
  assert.equal(options.acceptSnapshot(session), true); assert.equal(options.acceptSnapshot('old'), false);
  api.destroy(); assert.equal(destroyed, true);
  button.listeners.click(); api.activate(); api.sessionChanged('other'); assert.equal(requests.length, 0);
  assert.equal(timers.size, 0);
  console.log('Live investigation passed: automatic attachment, frozen inspection, recorded import intent, stale responses, finite polling and bounded transport.');
})().catch(error => { console.error(error); process.exitCode = 1; });
