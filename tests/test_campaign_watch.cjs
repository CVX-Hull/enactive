// Browser protocol fixture: no claim of physical paint or human attention.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync(require('node:path').join(__dirname, '../tools/campaign_watch_ui.js'), 'utf8');

function fixture(change = () => {}, response = {accepted: 1, source: 'session-91'}) {
  const nodes = {};
  for (const id of ['watch-record', 'watch-feedback', 'current-session-full', 'control-freshness',
    'source-details', 'frame', 'watch', 'connection', 'status-error']) {
    nodes[id] = {hidden: false, textContent: '', dataset: {}, complete: true, naturalWidth: 10,
      getBoundingClientRect: () => ({left: 0, right: 10, top: 0, bottom: 10, width: 10, height: 10})};
  }
  nodes['watch-record'].dataset.next = '1';
  nodes['watch-record'].addEventListener = (_, handler) => { nodes.click = handler; };
  nodes['current-session-full'].textContent = 'session';
  nodes['control-freshness'].textContent = 'Last status received 2026-11-05T12:00:00Z; current';
  nodes['source-details'].textContent = `Session: session\nSource: session-91\nCapture: 91\nSHA-256: ${'a'.repeat(64)}\n`;
  nodes['connection'].dataset.state = 'ok'; nodes['status-error'].hidden = true;
  const document = {visibilityState: 'visible', querySelector: selector => nodes[selector.slice(1)],
    getElementById: id => nodes[id]};
  const calls = [];
  const context = {document, innerWidth: 100, innerHeight: 100, AbortSignal,
    getComputedStyle: () => ({visibility: 'visible', display: 'block'}),
    fetch: async (path, options) => { calls.push({path, ...JSON.parse(options.body)});
      return {ok: true, json: async () => response}; }};
  change(nodes, document, context);
  vm.runInNewContext(code, context);
  return {nodes, calls};
}

test('no background acknowledgement; only trusted explicit click records exact displayed source', async () => {
  const f = fixture();
  assert.equal(f.calls.length, 0);
  await f.nodes.click({isTrusted: false});
  assert.equal(f.calls.length, 0);
  await f.nodes.click({isTrusted: true});
  assert.deepEqual(f.calls, [{path: '/record', sequence: 1, session: 'session',
    observed: '2026-11-05T12:00:00Z', source: 'session-91', sha256: 'a'.repeat(64)}]);
});

for (const [name, change] of [
  ['hidden document', (_, document) => { document.visibilityState = 'hidden'; }],
  ['hidden Watch', nodes => { nodes.watch.hidden = true; }],
  ['undecoded frame', nodes => { nodes.frame.complete = false; }],
  ['empty frame', nodes => { nodes.frame.naturalWidth = 0; }],
  ['offscreen frame', nodes => { nodes.frame.getBoundingClientRect = () => ({right: -1}); }],
  ['hidden CSS frame', (_, __, context) => { context.getComputedStyle = () => ({visibility: 'hidden'}); }],
  ['wrong source session', nodes => { nodes['current-session-full'].textContent = 'other'; }],
  ['unavailable status', nodes => { nodes['status-error'].hidden = false; }],
  ['missing status timestamp', nodes => { nodes['control-freshness'].textContent = ''; }],
]) {
  test(name+' cannot acknowledge', async () => {
    const f = fixture(change); await f.nodes.click({isTrusted: true});
    assert.equal(f.calls.length, 0);
    assert.match(f.nodes['watch-feedback'].textContent, /unconfirmed/);
  });
}

test('partial confirmation does not advance the sequence', async () => {
  const f = fixture(() => {}, {accepted: 2, source: 'session-91'});
  await f.nodes.click({isTrusted: true}); await f.nodes.click({isTrusted: true});
  assert.deepEqual(f.calls.map(call => call.sequence), [1, 1]);
  assert.match(f.nodes['watch-feedback'].textContent, /Unmatched guard confirmation/);
});
