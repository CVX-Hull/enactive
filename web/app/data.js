// Viewer data: a tiny store, the only place that fetches /api/view/*, and the pollers.
// Any 503, timeout or network error from a viewer route means "viewer unavailable":
// interpretive panels grey out and the strip says so. Nothing here touches the control
// strip, Pause or the operator check (those live in control.js).
import {useState, useEffect} from './ui.js';

const VIEW_TIMEOUT_MS = 4000;
export const SUMMARY_MS = 2000;
export const RUNS_MS = 10000;
export const LIMIT = 500;

/* ---------------------------------------------------------------- store */
const subscribers = new Set();
export const store = {
  viewerOk: true, viewerSeen: false, lastOk: null,
  runs: null, runId: null,
  summary: null, steps: [], requests: [], markers: [],
  cursor: null,            // null = following live; otherwise a step seq
  control: {ok: null, status: null, frameUrl: null},
  themeEpoch: 0,
  feedWide: savedFlag('feed-wide'),   // the feed player spans the page (#437); a per-browser view choice
};
function savedFlag(key) {
  try { return localStorage.getItem(key) === 'yes'; } catch { return false; }
}
export function setFeedWide(wide) {
  try { localStorage.setItem('feed-wide', wide ? 'yes' : 'no'); } catch { /* no storage */ }
  set({feedWide: wide});
}
export function set(patch) {
  Object.assign(store, patch);
  for (const f of subscribers) f();
}
export function useStore() {
  const [, force] = useState(0);
  useEffect(() => {
    const f = () => force(n => n + 1);
    subscribers.add(f);
    f();   // a change between the first render and this effect would otherwise be missed
    return () => subscribers.delete(f);
  }, []);
  return store;
}

/* ---------------------------------------------------------------- fetching */
export class ViewerDown extends Error {}

export async function viewerGet(path, schema = 'spectator-view/1') {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), VIEW_TIMEOUT_MS);
  let response;
  try {
    response = await fetch(`/api/view/${path}`, {signal: controller.signal, cache: 'no-store', credentials: 'same-origin'});
  } catch {
    markViewer(false);
    throw new ViewerDown('Viewer unavailable');
  } finally { clearTimeout(timer); }
  if (response.status === 503) { markViewer(false); throw new ViewerDown('Viewer unavailable'); }
  let body = null;
  try { body = await response.json(); } catch { /* not JSON */ }
  if (!response.ok) {
    if (response.status >= 500) { markViewer(false); throw new ViewerDown('Viewer unavailable'); }
    markViewer(true);
    throw new Error(body && body.error ? String(body.error) : `The viewer has nothing here (HTTP ${response.status})`);
  }
  if (!body || body.schema !== schema) {
    markViewer(false);
    throw new ViewerDown('Unsupported viewer response');
  }
  markViewer(true);
  return body;
}
function markViewer(ok) {
  if (ok) {
    if (!store.viewerOk || !store.viewerSeen) { set({viewerOk: true, viewerSeen: true, lastOk: Date.now()}); announce(); } else store.lastOk = Date.now();
  } else if (store.viewerOk || !store.viewerSeen) { set({viewerOk: false, viewerSeen: true}); announce(); }
}

export const runPath = (run, tail) => `run/${encodeURIComponent(run)}/${tail}`;
export const framePath = (run, sourceId) => `/api/view/${runPath(run, `frame/${encodeURIComponent(sourceId)}`)}`;

/** Fetch one viewer route into component state; refetch on an interval and when the viewer returns. */
export function useView(path, every = 5000, schema = 'spectator-view/1') {
  const [state, setState] = useState({path: null, data: null, error: null});
  useEffect(() => {
    if (!path) return undefined;
    let dead = false, timer;
    const run = async () => {
      try {
        const data = await viewerGet(path, schema);
        if (!dead) setState({path, data, error: null});
      } catch (error) {
        if (!dead) setState(s => ({path, data: s.path === path ? s.data : null, error}));
      }
      if (!dead && every) timer = setTimeout(run, every);
    };
    void run();
    return () => { dead = true; clearTimeout(timer); };
  }, [path, every, schema]);
  return state.path === path ? state : {path, data: null, error: null};
}

/* ---------------------------------------------------------------- run polling */
let generation = 0;
/** Pages of a list route (`items`, `next`), continuing from the known cursor until it ends. */
async function pages(path, after, token) {
  let items = [], last = null;
  for (let page = 0; page < 40; page++) {
    const body = await viewerGet(`${path}${path.includes('?') ? '&' : '?'}after=${after}&limit=${LIMIT}`);
    if (token !== generation) return null;
    items = items.concat(body.items || []);
    last = body;
    if (body.next === null || body.next === undefined) break;
    after = body.next;
  }
  return {items, last};
}

async function pollRunOnce(run, token) {
  const summary = await viewerGet(runPath(run, 'summary'));
  const seen = store.steps.length ? store.steps[store.steps.length - 1].seq : 0;
  const steps = await pages(runPath(run, 'steps'), seen, token);
  if (!steps) return;
  const known = store.requests.length ? store.requests[store.requests.length - 1].id : 0;
  const requests = await pages(runPath(run, 'requests'), known, token);
  if (!requests || token !== generation) return;
  set({summary, steps: store.steps.concat(steps.items), requests: store.requests.concat(requests.items),
    markers: requests.last && requests.last.markers ? requests.last.markers : store.markers});
  announce();
}

// Until the owner picks a run, the page follows the live run, including one listed after the first load.
let ownerPicked = false;
export function selectRun(run) {
  ownerPicked = true;
  if (run === store.runId) return;
  generation++;
  set({runId: run, summary: null, steps: [], requests: [], markers: [], cursor: null});
  announce();
}

let runsTimer = null, runTimer = null;
async function loadRuns() {
  try {
    const listing = await pages('runs', 0, generation);
    const runs = listing ? listing.items : store.runs || [];
    const patch = {runs};
    const live = runs.find(r => r.state === 'live');
    const shown = runs.some(r => r.run === store.runId);
    if (!store.runId || !shown || (!ownerPicked && live && live.run !== store.runId)) {
      const pick = live || runs[0];
      if (pick) { generation++; Object.assign(patch, {runId: pick.run, summary: null, steps: [], requests: [], markers: [], cursor: null}); }
    }
    set(patch);
    announce();
  } catch { /* viewerGet marked the outage */ }
  runsTimer = setTimeout(loadRuns, store.viewerOk ? RUNS_MS : 3000);
}
async function loop() {
  if (store.runId) {
    const token = generation;
    try { await pollRunOnce(store.runId, token); } catch { /* outage or missing run: keep what we have, greyed */ }
  }
  runTimer = setTimeout(loop, SUMMARY_MS);
}
export function startPolling() {
  clearTimeout(runsTimer); clearTimeout(runTimer);
  void loadRuns().then(() => { void loop(); });
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') { clearTimeout(runTimer); void loop(); } });
}

/* ---------------------------------------------------------------- playhead */
/** Epoch seconds of the run's first step or request: the viewer reports no separate start time. */
export function runStart() {
  const walls = [store.steps[0] && store.steps[0].wall, store.requests[0] && store.requests[0].wall].filter(w => typeof w === 'number');
  return walls.length ? Math.min(...walls) : 0;
}
export const liveRun =() => (store.runs || []).find(r => r.state === 'live') || null;
export const selectedRun = () => (store.runs || []).find(r => r.run === store.runId) || null;
/** False only while the owner has moved the playhead into history. The operator check depends on the
 *  control path, never on viewer data: a viewer that is down, slow, or has not yet listed the live run
 *  must not disable it (ADR008 item 5). */
export function isLive() {
  if (!store.viewerOk) return true;
  return store.cursor === null;
}
export function cursorIndex() {
  if (!store.steps.length) return -1;
  if (store.cursor === null) return store.steps.length - 1;
  const i = store.steps.findIndex(s => s.seq >= store.cursor);
  return i < 0 ? store.steps.length - 1 : i;
}
export function setCursorIndex(index) {
  const steps = store.steps;
  if (!steps.length) return;
  const i = Math.max(0, Math.min(steps.length - 1, index));
  const run = selectedRun();
  const atEdge = i === steps.length - 1;
  set({cursor: atEdge && run && run.state === 'live' ? null : steps[i].seq});
  announce();
}
export function goLive() { set({cursor: null}); announce(); }

let lastLive = null;
export function announce() {
  const live = isLive();
  if (live !== lastLive) {
    lastLive = live;
    document.dispatchEvent(new CustomEvent('enactive:playhead', {detail: {live}}));
  }
  const s = store.summary;
  const facts = s ? `Decision ${s.decisions ?? '?'}, $${Number(s.dollars ?? 0).toFixed(2)} spent.` : '';
  document.dispatchEvent(new CustomEvent('enactive:facts', {detail: {text: store.viewerOk ? facts : ''}}));
}

/* ---------------------------------------------------------------- control events (from control.js) */
document.addEventListener('enactive:control', event => {
  const flipped = store.control.ok !== event.detail.ok;
  store.control = {...store.control, ok: event.detail.ok, status: event.detail.status};
  if (flipped) set({});
});
document.addEventListener('enactive:frame', event => set({control: {...store.control, frameUrl: event.detail.url, frameSource: event.detail.source}}));
document.addEventListener('enactive:theme', () => set({themeEpoch: store.themeEpoch + 1}));
document.dispatchEvent(new CustomEvent('enactive:hello'));
