/* Execute the production viewer against delayed image decoding, without a browser dependency. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const elements = new Map();
function element(id) {
  if (elements.has(id)) return elements.get(id);
  const classes = new Set();
  const node = {id, value: '', dataset: {}, hidden: false, textContent: '',
    classList: {add: x => classes.add(x), toggle: (x, yes) => yes ? classes.add(x) : classes.delete(x), contains: x => classes.has(x)},
    replaceWith: other => elements.set(id, other), replaceChildren() {}, append() {}, addEventListener() {}};
  elements.set(id, node);
  return node;
}
const pending = [];
class DeferredImage {
  decode() { return new Promise((resolve, reject) => pending.push({resolve, reject})); }
  replaceWith(other) { elements.set('frame', other); }
}
const context = vm.createContext({Image: DeferredImage, document: {
  getElementById: element, querySelector: () => ({content: 'test-token'}),
  querySelectorAll: () => [], createElement: () => element(Symbol()), activeElement: null
}, fetch: () => new Promise(() => {}), setTimeout() {}});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8'), context);
const run = source => vm.runInContext(source, context);
function render(revision, frame, changes = {}) {
  context.input = {connection: 'fresh', age_ms: 0, pause_requested: false, frozen: false,
    latency_ms: 10, goal: '', events: [], state: {protocol: 3, boundary: {kind: 'normal_play'}, session: 'test', revision, frame,
      frame_ok: true, status: 'ready', actions: [], ...changes}};
  run('render(input)');
}
async function decode() { pending.shift().resolve(); await new Promise(setImmediate); }
(async () => {
  render(1, 'frame-1-1-1.png');
  assert.throws(() => run('authority()'), /Wait for/);
  await decode();
  assert.equal(run('authority().expected_revision'), 1);
  element('key').value = 'x';
  render(2, 'frame-1-1-2.png');
  assert.throws(() => run('authority()'), /Wait for/);
  await decode();
  assert.equal(element('key').value, '');
  assert.equal(run('authority().expected_revision'), 2);

  render(3, 'frame-1-1-3.png');
  render(4, 'frame-1-1-3.png', {status: 'dispatched', frame_ok: false});
  await decode();
  assert.throws(() => run('authority()'), /Wait for/);
  assert.equal(element('frame-shell').classList.contains('stale'), true);
  assert.match(element('frame-note').textContent, /DISPATCHED/);

  render(5, 'frame-1-1-5.png');
  render(6, 'frame-1-1-6.png');
  await decode(); // Obsolete image may not replace the last displayed frame.
  assert.equal(run('displayed.revision'), 3);
  await decode();
  assert.equal(run('authority().expected_revision'), 6);
  for (const kind of ['activity_poll', 'debug_prompt', 'unsupported', 'interrupt_confirmation']) {
    render(7, `frame-${kind}.png`, {boundary: {kind}});
    await decode();
    assert.throws(() => run('authority()'), /native control/);
    assert.match(element('category').textContent, new RegExp(kind.replaceAll('_', ' ').toUpperCase()));
  }
  render(8, 'frame-menu.png', {boundary: {kind: 'menu'}});
  await decode();
  assert.equal(run('authority().expected_revision'), 8);
  render(9, 'frame-old.png', {protocol: 2});
  await decode();
  assert.throws(() => run('authority()'), /native control/);
  console.log('Viewer regressions passed: image authority, cleared choices, stale/obsolete decode, boundary admission and mixed version.');
})().catch(error => { console.error(error); process.exitCode = 1; });
