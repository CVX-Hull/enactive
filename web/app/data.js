// Viewer data: a tiny store, the only place that fetches /api/view/*, and the pollers.
// Any 503, timeout or network error from a viewer route means "viewer unavailable":
// interpretive panels grey out and the strip says so. Nothing here touches the control
// strip or Pause (those live in control.js).
import {useState, useEffect} from './ui.js';

export const API = 'spectator-view/4';
export const recordedPage = location.pathname === '/recorded/';
const VIEW_TIMEOUT_MS = 4000;
export const SUMMARY_MS = 2000;
export const RUNS_MS = 10000;
export const LIMIT = 500;
/** A live feed re-reads this many of its newest entries: pending calls settle and findings may be added late. */
const FEED_OVERLAP = 60;
/** Every this many polls a live feed is read whole, for a finding placed further back than the overlap. */
const FEED_WHOLE = 30;

/* ---------------------------------------------------------------- store */
const subscribers = new Set();
/** `feedFinalized` is the recorded state ('final', or 'live' for a run never finalized) in which a run that is no longer
 *  live had its whole feed read; null while it is live, so the last passes' findings are read once more when it ends. */
const EMPTY_RUN = {summary: null, steps: [], feed: [], feedMeta: null, feedFinalized: null, feedFinalCursor: null, cursor: null, inspect: null, held: false};
export const store = {
  viewerOk: true, viewerSeen: false, lastOk: null,
  runs: null, runId: null, // runId: the selected run's session, the only name two runs never share
  runsTotal: 0, skippedNonCurrent: 0,   // older-core stores the viewer did not list
  ...EMPTY_RUN,            // cursor: null = following live; otherwise a step seq. inspect: a feed entry ID. held: the view is frozen
  control: {ok: null, status: null, frameUrl: null},
  stageLive: false,        // the Watch stage is showing the live control-path frame
  themeEpoch: 0,
  feedWide: savedFlag('feed-wide'),   // the player spans the page (#437); a per-browser view choice
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
/** A route that answered, but with nothing for this question (a 404 or 409): it greys nothing else. */
export class RouteError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

export async function viewerGet(path, schema = API) {
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
    if (response.status === 413) throw new RouteError('Response too large (HTTP 413); select a request or fewer entries.', 413);
    throw new RouteError(body && body.error ? String(body.error) : `The viewer has nothing here (HTTP ${response.status})`, response.status);
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

/** Fetch one viewer route into component state, again on an interval if it has one. A one-shot read (`every` 0) that
 *  failed is repeated when the viewer returns; one that succeeded is of something that does not change, and is kept.
 *  The error stays with this route: a 404 or 409 here is a calm notice in its own panel and greys nothing else. */
export function useView(path, every = 5000, schema = API, refresh = 0) {
  const [state, setState] = useState({path: null, data: null, error: null});
  useEffect(() => {
    if (!path) return undefined;
    let dead = false, timer, failed = false, ok = store.viewerOk;
    const run = async () => {
      failed = false;
      try {
        const data = await viewerGet(path, schema);
        if (!dead) setState({path, data, error: null});
      } catch (error) {
        failed = true;
        if (!dead) setState(s => ({path, data: s.path === path && !(error instanceof RouteError) ? s.data : null, error}));
      }
      if (!dead && every) timer = setTimeout(run, every);
    };
    const onChange = () => {
      const returned = store.viewerOk && !ok;
      ok = store.viewerOk;
      if (returned && failed && !every && !dead) void run();
    };
    subscribers.add(onChange);
    void run();
    return () => { dead = true; clearTimeout(timer); subscribers.delete(onChange); };
  }, [path, every, schema, refresh]);
  return state.path === path ? state : {path, data: null, error: null};
}

/* ---------------------------------------------------------------- run polling */
let generation = 0;
/** Pages of a list route (`items`, `next`), continuing from the known cursor until it ends. */
async function pages(path, after, token) {
  let items = [], last = null, next = after, done = false;
  for (let page = 0; page < 40; page++) {
    const body = await viewerGet(`${path}${path.includes('?') ? '&' : '?'}after=${next}&limit=${LIMIT}`);
    if (token !== generation) return null;
    items = items.concat(body.items || []);
    last = body;
    if (body.next === null || body.next === undefined) { done = true; next = null; break; }
    next = body.next;
  }
  return {items, last, next, done};
}

async function pollRunOnce(run, token) {
  const summary = await viewerGet(runPath(run, 'summary'));
  const seen = store.steps.length ? store.steps[store.steps.length - 1].seq : 0;
  const steps = await pages(runPath(run, 'steps'), seen, token);
  if (!steps || token !== generation) return;
  set({summary, steps: steps.items.length ? store.steps.concat(steps.items) : store.steps});
  announce();
  await pollFeed(run, token, summary);
}

let feedPolls = 0;
/** The feed's recent part replaces what was held from the same point on, so an entry that moved or settled is not kept
 *  twice. A run that is no longer live has its feed read whole (continuing past 40 pages until `next` is null), after
 *  which it does not change. */
async function pollFeed(run, token, {live, state}) {
  if (!live && store.feedFinalized === state) return;
  const continuingFinal = !live && store.feedFinalCursor !== null;
  const whole = !continuingFinal && (!live || !store.feedMeta || feedPolls++ % FEED_WHOLE === FEED_WHOLE - 1);
  const keep = continuingFinal ? store.feed.length : whole ? 0 : Math.max(0, store.feed.length - FEED_OVERLAP);
  const cursor = continuingFinal ? store.feedFinalCursor : keep ? store.feed[keep - 1].order : 0;
  const found = await pages(runPath(run, 'feed'), cursor, token);
  if (!found || token !== generation) return;
  const {source, total, counts} = found.last;
  const read = new Set(found.items.map(e => e.id));
  set({
    feed: store.feed.slice(0, keep).filter(e => !read.has(e.id)).concat(found.items),
    feedMeta: {source, total, counts},
    feedFinalized: !live && found.done ? state : null,
    feedFinalCursor: !live && !found.done ? found.next : null,
  });
}

// Until the owner picks a run, the page follows the live run, including one listed after the first load.
let ownerPicked = false;
export function selectRun(session) {
  ownerPicked = true;
  if (session === store.runId) return;
  generation++;
  set({runId: session, ...EMPTY_RUN});
  announce();
  // The new run's data is wanted now, not at the next tick of the old run's poll.
  if (!loopInFlight) { clearTimeout(runTimer); void loop(); }
}
/** The session of a run named by its session or by its run name, as the viewer's own routes resolve one. */
export function sessionOf(name) {
  const runs = store.runs || [];
  const found = runs.find(r => r.session === name) || runs.find(r => r.run === name);
  return found ? found.session : null;
}

let runsTimer = null, runTimer = null;
/** True while one poll of the selected run is running: there is never a second chain of polls beside it. */
let loopInFlight = false;
async function loadRuns() {
  try {
    const listing = await pages('runs', 0, generation);
    const runs = listing ? listing.items : store.runs || [];
    const patch = {runs};
    if (listing) Object.assign(patch, {runsTotal: listing.last.total ?? runs.length, skippedNonCurrent: listing.last.skipped_non_current || 0});
    const live = runs.find(r => r.state === 'live');
    const shown = runs.some(r => r.session === store.runId);
    if (!store.runId || !shown || (!ownerPicked && live && live.session !== store.runId)) {
      const pick = live || runs[0];
      if (pick) { generation++; Object.assign(patch, {runId: pick.session, ...EMPTY_RUN}); }
    }
    set(patch);
    announce();
  } catch { /* viewerGet marked the outage */ }
  runsTimer = setTimeout(loadRuns, store.viewerOk ? RUNS_MS : 3000);
}
async function loop() {
  if (loopInFlight) return;
  loopInFlight = true;
  clearTimeout(runTimer);
  try {
    if (store.runId) {
      const token = generation;
      try { await pollRunOnce(store.runId, token); } catch { /* outage or missing run: keep what we have, greyed */ }
    }
  } finally {
    loopInFlight = false;
    clearTimeout(runTimer);
    runTimer = setTimeout(loop, SUMMARY_MS);
  }
}
/** A page that becomes visible polls at once, unless a poll is already running; either way one chain continues. */
function onVisible() {
  if (document.visibilityState !== 'visible' || loopInFlight) return;
  clearTimeout(runTimer);
  void loop();
}
export function startPolling() {
  clearTimeout(runsTimer); clearTimeout(runTimer);
  void loadRuns().then(() => { void loop(); });
  document.addEventListener('visibilitychange', onVisible);
}
/** For the browser tests: whether a poll of the selected run is running now. */
export const pollState = () => ({inFlight: loopInFlight});

/* ---------------------------------------------------------------- playhead */
/** Epoch seconds of the run's first step. */
export const runStart = () => (store.steps[0] && typeof store.steps[0].wall === 'number' ? store.steps[0].wall : 0);
export const liveRun = () => (store.runs || []).find(r => r.state === 'live') || null;
export const selectedRun = () => (store.runs || []).find(r => r.session === store.runId) || null;
/** False only while the owner has moved the playhead into history; an unavailable viewer counts as live. */
export function isLive() {
  if (!store.viewerOk) return true;
  return store.cursor === null;
}
/** The playhead follows the live run now: neither moved into history nor held, and the selected run is the live one. */
export const followingLive = () => selectedRun()?.state === 'live' && isLive() && !store.held;
/** The index of the step at or after `seq`, else the last one; -1 without steps. */
export function indexOfSeq(seq) {
  const i = store.steps.findIndex(s => s.seq >= seq);
  return i < 0 ? store.steps.length - 1 : i;
}
export function cursorIndex() {
  if (!store.steps.length) return -1;
  return store.cursor === null ? store.steps.length - 1 : indexOfSeq(store.cursor);
}
/** The step the playhead is on, or null. */
export const cursorStep = () => store.steps[cursorIndex()] || null;
export function setCursorIndex(index) {
  const steps = store.steps;
  if (!steps.length) return;
  const i = Math.max(0, Math.min(steps.length - 1, index));
  const run = selectedRun();
  const atEdge = i === steps.length - 1;
  set({cursor: atEdge && run && run.state === 'live' ? null : steps[i].seq});
  announce();
}
/** Put the playhead on a recorded step; unlike a move, this never falls back to following live. */
export function setCursorSeq(seq) { set({cursor: seq}); announce(); }
/** Open Watch at one step of the selected run. */
export function jumpToSeq(seq) {
  setCursorSeq(seq);
  if (location.hash !== '#watch') location.hash = '#watch';
}
export function goLive() { set({cursor: null}); announce(); }

/** The facts the Pause sheet repeats: those of the run that Pause would end, or none. Another run's are never given. */
export function announce() {
  const status = store.control.status;
  const s = store.summary && status && store.summary.session === status.session ? store.summary : null;
  const reported = s && s.host_telemetry ? s.host_telemetry.reported_cost_usd : null;
  const money = reported !== null && reported !== undefined ? `$${Number(reported).toFixed(2)} spent (provider-reported)` : s ? `$${Number(s.dollars ?? 0).toFixed(2)} spent (estimated)` : '';
  const facts = s ? `Decision ${s.decisions ?? '?'}, ${money}.` : '';
  document.dispatchEvent(new CustomEvent('enactive:facts', {detail: {text: store.viewerOk ? facts : ''}}));
}

/* ---------------------------------------------------------------- control events (from control.js) */
document.addEventListener('enactive:control', event => {
  const before = store.control;
  store.control = {...before, ok: event.detail.ok, status: event.detail.status};
  if (before.ok !== event.detail.ok || before.status?.session !== event.detail.status?.session) { set({}); announce(); }
});
document.addEventListener('enactive:frame', event => set({control: {...store.control, frameUrl: event.detail.url, frameSource: event.detail.source}}));
document.addEventListener('enactive:theme', () => set({themeEpoch: store.themeEpoch + 1}));
document.dispatchEvent(new CustomEvent('enactive:hello'));
