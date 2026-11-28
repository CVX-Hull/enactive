// Watch: the game screen, the continuity timeline, the player's working state and the story feed, on one shared step.
import {html, useEffect, useLayoutEffect, useMemo, useRef, useState, Panel, Pv, Segmented, Waiting, clockTime, gameClock, keyText, kilo,
  label, mmss, count, plural, readingNote, secs, actorNumber} from './ui.js';
import {store, set, framePath, selectedRun, setCursorIndex, setCursorSeq, cursorIndex, goLive, isLive, runStart, setFeedWide,
  recordedPage, runPath, useView} from './data.js';
import {findingText, vitalBadges} from './supervise.js';
import {Inspector} from './inspector.js';
import {isAlertEntry, isReadTool, isKnowledgeTool, toolLabel, cutTone, uncoveredCut, deliveryWord, deliveryTone, deltaChips,
  agendaAt, agendaDiffs, versionAt, cutsUpTo, actorNumbers, sourceReadText} from './continuity.js';

export {isAlertEntry};

/* ---------------------------------------------------------------- the player */
const SCALE_KEY = 'feed-scale';
const SCALES = [['fit', 'Fit', 'Scaled smoothly to the space'], ['1', '1:1', 'Pixel for pixel'], ['2', '2×', 'Twice the pixels, still crisp'],
  ['3', '3×', 'Three times the pixels, still crisp']];
function savedScale() {
  try { const v = localStorage.getItem(SCALE_KEY); return SCALES.some(([s]) => s === v) ? v : 'fit'; } catch { return 'fit'; }
}
const keysText = step => (step && step.keys && step.keys.length ? step.keys.map(keyText).join(' ') : '(observe)');
/** The words under the frame: which decision it shows and what the player sent (#437). */
function caption(step, prefix = '') {
  return step ? `${prefix}decision ${step.decision} · ${gameClock(step.game_time)} · ${label(step.mode || 'unknown')} · keys ${keysText(step)}` : '';
}
const SHORTCUTS = [['Space', 'hold or resume the view'], ['← / →', 'previous or next recorded frame'], ...(recordedPage ? [] : [['L', 'live']]),
  ['I', 'inspect the step'], ['T', 'wide player'], ['F', 'full screen'], ['0 1 2 3', 'Fit, 1:1, 2×, 3×']];
/** Shortcuts never take a key that the focused element itself uses. Fields, the timeline, the Pause button and the
 *  open Pause sheet keep every key; Space also stays with anything it activates (buttons, links, disclosure
 *  summaries, focusable elements), so letters and arrows still work after clicking a player button. */
function forPlayer(event) {
  if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return false;
  const sheet = document.getElementById('sheet');
  if (sheet && !sheet.hidden) return false;
  const target = event.target;
  if (!target || !target.closest) return true;
  if (target.closest('input, select, textarea, [contenteditable], #tl, #pause, form, [role="dialog"]')) return false;
  return !(event.key === ' ' && target.closest('button, a, summary, [tabindex]'));
}
/** The story entry of the step on screen. */
export const entryOfSeq = seq => store.feed.find(e => e.entry_kind === 'step' && e.seq === seq && e.exact_step) || store.feed.find(e => e.entry_kind === 'step' && e.seq === seq) || null;

/** The game feed (#435). Each frame is decoded before it replaces the last one, so the picture never blanks as frames
 *  arrive. Hold freezes this view only: it sends nothing to the run and is unrelated to the custody Pause. */
function FeedPlayer({run, step}) {
  const liveRunSelected = selectedRun()?.state === 'live';
  const following = store.cursor === null && liveRunSelected;
  // A step without a frame shows the newest earlier one, which the line under the stage names as that step's.
  const framed = following || !step ? null : step.source_id ? step : store.steps.slice(0, cursorIndex()).findLast(s => s.source_id) || null;
  const src = following ? store.control.frameUrl : framed ? framePath(run, framed.source_id) : null;
  const canvas = useRef(null), shell = useRef(null);
  const held = store.held, setHeld = value => { if (store.held !== value) set({held: value}); };
  const [scale, setScale] = useState(savedScale);
  const [shown, setShown] = useState(null);
  useEffect(() => {
    if (!src || held) return undefined;
    // What this frame is, fixed now: a newer frame arriving during the decode must not relabel it.
    const source = store.control.frameSource || null;
    const what = following
      ? {following: true, source, session: source && source.session, sourceId: source && source.source_id, latest: store.steps[store.steps.length - 1] || null}
      : {following: false, seq: framed.seq, wall: framed.wall};
    let cancelled = false;
    const image = new Image();
    image.src = src;
    image.decode().then(() => {
      const target = canvas.current;
      if (cancelled || !target) return;
      if (target.width !== image.naturalWidth || target.height !== image.naturalHeight) {
        target.width = image.naturalWidth; target.height = image.naturalHeight;
      }
      target.getContext('2d').drawImage(image, 0, 0);
      setShown({...what, width: image.naturalWidth, height: image.naturalHeight});
    }).catch(() => { /* a frame that fails to decode leaves the last good one in place */ });
    return () => { cancelled = true; };
  }, [src, held]);
  // While this stage has painted the very capture the control strip shows, the strip's copy is a duplicate and steps aside
  // (main.js). While a newer capture is being decoded here, or fails to, the strip's is the only one and stays in view.
  const ctrlSource = store.control.frameSource, ctrlStatus = store.control.status;
  const stageLive = following && !held && !!(shown && shown.following && ctrlSource && ctrlStatus
    && shown.session === ctrlStatus.session && shown.sourceId === ctrlSource.source_id);
  useLayoutEffect(() => {   // before the browser paints: the strip is never a frame late in returning
    if (store.stageLive !== stageLive) set({stageLive});
  }, [stageLive]);
  useEffect(() => () => { if (store.stageLive || store.held) set({stageLive: false, held: false}); }, []);
  // Integer scales size the canvas through the DOM style object (the page CSP forbids inline style attributes).
  useEffect(() => {
    const target = canvas.current;
    if (!target) return;
    const factor = Number(scale);
    target.style.width = shown && factor > 1 ? `${shown.width * factor}px` : '';
  }, [scale, shown && shown.width]);
  // Steps that arrived since the view was held while following the live run.
  const [heldAt, setHeldAt] = useState(null);
  const toggleHold = () => { setHeldAt(held ? null : store.steps.length); setHeld(!held); };
  // A once-a-second clock for the frame-age badge.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const choose = value => { setScale(value); try { localStorage.setItem(SCALE_KEY, value); } catch { /* no storage */ } };
  const expand = () => {
    const el = shell.current;
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else if (el && el.requestFullscreen) el.requestFullscreen().catch(() => {});
  };
  // Stepping always shows the step it moves to, so it releases a held view.
  const stepTo = target => { setHeld(false); setHeldAt(null); setCursorIndex(target); };
  const index = cursorIndex();
  const steps = store.steps;
  const actions = {
    hold: toggleHold,
    back: () => { if (index > 0) stepTo(index - 1); },
    forward: () => { if (index >= 0 && index < steps.length - 1) stepTo(index + 1); },
    live: () => { setHeld(false); setHeldAt(null); goLive(); },
    wide: () => setFeedWide(!store.feedWide),
    full: expand,
    inspect: () => { const entry = steps[index] && entryOfSeq(steps[index].seq); if (entry) set({inspect: entry.id}); },
  };
  const latest = useRef(actions);
  latest.current = actions;
  const scaleRef = useRef(choose);
  scaleRef.current = choose;
  useEffect(() => {
    const onKey = event => {
      if (!forPlayer(event)) return;
      const a = latest.current;
      const keyed = {' ': a.hold, ArrowLeft: a.back, ArrowRight: a.forward, l: a.live, L: a.live, t: a.wide, T: a.wide, f: a.full, F: a.full,
        i: a.inspect, I: a.inspect, 0: () => scaleRef.current('fit'), 1: () => scaleRef.current('1'), 2: () => scaleRef.current('2'), 3: () => scaleRef.current('3')}[event.key];
      if (!keyed) return;
      if (event.repeat && event.key === ' ') { event.preventDefault(); return; }   // holding Space toggles once
      event.preventDefault();
      keyed();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);
  const where = !shown ? 'waiting for the first frame'
    : shown.following ? `live · control path${shown.source ? ` · capture ${shown.source.capture_id} at ${clockTime(shown.source.presented_ms)}` : ''}`
    : `${recordedPage ? 'recorded step' : 'step'} ${shown.seq}${typeof shown.wall === 'number' ? ` at ${clockTime(shown.wall * 1000)}` : ''} · viewer · original frame · sha-256 checked`;
  const missing = !following && step && !step.source_id ? ` · no frame at step ${step.seq}` : '';
  // The caption names the decision on screen: the step for a recorded frame, the newest step while following live.
  const shownStep = shown && !shown.following ? steps.find(s => s.seq === shown.seq) : null;
  const words = shown ? (shown.following ? caption(held ? shown.latest : steps[steps.length - 1], 'latest ') : caption(shownStep)) : '';
  // Liveness: the frame's age (amber when the Pause condition "feed alive" is met) and how far the view is behind.
  const feedStale = !!(store.summary && store.summary.pause && store.summary.pause.conditions
    && store.summary.pause.conditions.some(c => c.id === 'feed_alive' && c.met));
  const age = shown && shown.following && shown.source && typeof shown.source.received_wall === 'number'
    ? Math.max(0, Math.round(now / 1000 - shown.source.received_wall)) : null;
  const behind = !liveRunSelected ? 0 : held && following && heldAt !== null ? Math.max(0, steps.length - heldAt)
    : !following && index >= 0 ? steps.length - 1 - index : 0;
  const atLatest = following || index === steps.length - 1;
  const canExpand = typeof document !== 'undefined' && document.fullscreenEnabled;
  const wide = store.feedWide;
  const s = store.summary;
  const badges = s && s.game_state && step && s.game_state.seq === step.seq ? vitalBadges(s.game_state) : [];
  const pill = following
    ? html`<span class="stagepill ${held ? 'held' : 'live'}"><i></i>${held ? 'HELD' : 'LIVE'}</span>`
    : html`<span class="stagepill history">STEP #${step ? step.seq : '—'} · ${recordedPage || !liveRunSelected ? 'RECORDED' : 'HISTORY'}</span>`;
  return html`<div class="frame-col"><div class="player" ref=${shell} data-scale=${scale} data-held=${held ? 'yes' : 'no'} data-wide=${wide ? 'yes' : 'no'}>
    <div class="player-view">${src || shown ? null : html`<span class="frame-empty">No frame</span>`}
      <canvas ref=${canvas} id="feed" role="img" hidden=${!shown}
        aria-label=${shown ? `Game screen, ${where}` : 'Game screen not yet shown'}></canvas></div>
    <div class="stagetop">${pill}${atLatest ? null : html`<button type="button" class="stageback" id="backlive" onClick=${actions.live}>${liveRunSelected ? 'Return to live' : 'Latest step'}</button>`}</div>
    <div class="stagemeta" id="playinfo" role="status">${step ? html`<b>Step ${step.seq}${following ? ' (live)' : ''}</b><span>Decision ${step.decision ?? '—'}</span><span>${gameClock(step.game_time)}</span><span>${label(step.mode || 'unknown')}</span>
      ${badges.map(b => html`<span class="vital ${b.critical ? 'critical' : ''}" title=${`read · ${readingNote(b.reading)}`}>${b.name}: ${b.text}</span>`)}
      <span class="mono src" title=${step.source_id || ''}>${step.source_id ? `source ${step.source_id.split('-').pop()}` : 'no frame at this step'}</span>` : 'No steps yet.'}</div>
    ${words ? html`<div class="player-caption" id="feed-caption" title=${words}>${words}</div>` : null}
    <div class="player-bar" role="toolbar" aria-label=${recordedPage ? 'Recorded frame player' : 'Feed player (view only; never pauses the run)'}>
      <button type="button" id="feed-back" aria-label="Previous recorded frame" title="Previous recorded frame (←)" disabled=${index <= 0} onClick=${actions.back}>◀</button>
      <button type="button" id="feed-hold" aria-pressed=${held} title=${recordedPage ? 'Freeze this view (Space)' : 'Freeze this view; the run keeps going (Space)'} onClick=${actions.hold}>Hold view</button>
      <button type="button" id="feed-forward" aria-label="Next recorded frame" title="Next recorded frame (→)" disabled=${index < 0 || index >= steps.length - 1} onClick=${actions.forward}>▶</button>
      ${age !== null ? html`<span class="badge ${feedStale ? 'stale' : ''}" id="feed-age" title="Time since this frame reached the page">frame ${age} s old</span>` : null}
      ${behind > 0 ? html`<button type="button" class="badge behind" id="feed-behind" title="Jump to the live frame" onClick=${actions.live}>${plural(behind, 'step')} behind live</button>` : null}
      <span class="player-gap"></span>
      <${Segmented} label="Scale" value=${scale} onChange=${choose} options=${SCALES.map(([value, text, hint]) => ({value, text, id: `feed-scale-${value}`, title: `${hint} (${value === 'fit' ? '0' : value})`}))} />
      <button type="button" id="feed-wide" aria-pressed=${wide} title="Wide player across the page (T)" onClick=${actions.wide}>Wide</button>
      ${canExpand ? html`<button type="button" id="feed-expand" title="Full screen (F)" onClick=${expand}>Expand</button>` : null}
      <details class="keys"><summary aria-label="Keyboard shortcuts">?</summary><dl>${SHORTCUTS.map(([k, d]) => html`<dt>${k}</dt><dd>${d}</dd>`)}</dl></details>
    </div>
    <div class="player-meta" id="feed-meta" aria-live="off">${held ? 'held · ' : ''}${where}${shown ? ` · ${shown.width} × ${shown.height} · ${scale === 'fit' ? 'fit' : scale === '1' ? '1:1' : `${scale}×`}` : ''}${missing}</div>
  </div></div>`;
}

/* ---------------------------------------------------------------- timeline */
const TIMELINE_NAME = 'Timeline playhead';
/** Four lanes, so a mark is told by its place as well as its colour: who was acting, what happened to the context, what
 *  reached memory or was read from it, and what went wrong. */
const LANES = [['actor', 'Actors'], ['context', 'Context'], ['memory', 'Memory'], ['alert', 'Alerts']];
const VIEW_W = 1000, LANE_H = 10;

/** Where each mark of the feed falls on the steps: indexes, spans and the actor band. */
function useMarks(steps, feed, summary) {
  return useMemo(() => {
    const at = new Map(steps.map((s, i) => [s.seq, i]));
    const walls = steps.map(s => s.wall);
    const byWall = wall => {   // the last step at or before a time
      if (typeof wall !== 'number') return steps.length - 1;
      let lo = 0, hi = walls.length - 1, found = -1;
      while (lo <= hi) { const mid = (lo + hi) >> 1; if ((walls[mid] ?? Infinity) <= wall) { found = mid; lo = mid + 1; } else hi = mid - 1; }
      return Math.max(0, found);
    };
    const index = e => at.get(e.seq);
    const out = {covered: [], uncovered: [], waits: [], brief: [], quiet: [], reads: [], alerts: [], actors: [], handoffs: []};
    const actorOf = new Map();
    for (const e of feed) {
      const i = index(e);
      if (e.entry_kind === 'step' && e.actor && e.exact_step && e.seq !== null) actorOf.set(e.seq, e.actor);
      if (i === undefined) continue;
      if (e.entry_kind === 'context_cut') out[cutTone(e)].push(i);
      else if (e.entry_kind === 'coverage_wait') out.waits.push([i, e.active ? steps.length - 1 : Math.max(i, byWall(e.end_wall)), !!e.active]);
      else if (e.entry_kind === 'knowledge_delivery') {
        if (e.outcome === 'delivered') out.brief.push(i);
        else if (e.delivery_kind === 'empty_suppressed') out.quiet.push(i);
      } else if (e.entry_kind === 'step' && (isReadTool(e.tool) || e.tool === 'player_agenda')) out.reads.push(i);
      if (isAlertEntry(e)) out.alerts.push(i);
    }
    const reserve = summary && summary.host_telemetry && summary.host_telemetry.spend_reserve_reached;
    if (reserve && reserve.count && reserve.latest && steps.length) out.alerts.push(byWall(reserve.latest.wall_time));
    // The actor band: each step's actor, carried forward over steps no trace entry names.
    const numbers = actorNumbers(feed);
    let current = null, start = 0;
    steps.forEach((s, i) => {
      const actor = actorOf.get(s.seq) ?? current;
      if (actor !== current) {
        if (current !== null) { out.actors.push({actor: current, from: start, to: i}); out.handoffs.push(i); }
        current = actor; start = i;
      }
    });
    if (current !== null) out.actors.push({actor: current, from: start, to: steps.length - 1});
    out.actors.forEach(a => { a.name = numbers.get(a.actor) || actorNumber(0); });
    return out;
  }, [steps, feed, summary && summary.host_telemetry]);
}

function Timeline() {
  const steps = store.steps;
  const index = cursorIndex();
  const step = steps[index];
  const last = Math.max(0, steps.length - 1);
  const followsLive = !recordedPage && selectedRun()?.state === 'live';
  const live = followsLive && isLive();
  const edge = followsLive ? 'the live edge' : 'the latest recorded step';
  const help = `Left and right arrows move one step. Hold Shift to move ten. Home goes to the first step. End goes to ${edge}.`;
  const place = i => (last ? i / last * VIEW_W : VIEW_W);
  const m = useMarks(steps, store.feed, store.summary);
  const onKeyDown = e => {
    const delta = e.shiftKey ? 10 : 1;
    if (e.key === 'ArrowLeft') { e.preventDefault(); setCursorIndex(index - delta); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); setCursorIndex(index + delta); }
    else if (e.key === 'End') { e.preventDefault(); goLive(); }
    else if (e.key === 'Home') { e.preventDefault(); setCursorIndex(0); }
  };
  const move = event => {
    const box = event.currentTarget.getBoundingClientRect();
    if (!box.width || !steps.length) return;
    setCursorIndex(Math.round(Math.min(1, Math.max(0, (event.clientX - box.left) / box.width)) * last));
  };
  const head = useRef(null), fill = useRef(null), names = useRef(null);
  useEffect(() => {   // placed through the DOM style object: the page CSP forbids inline style attributes
    const share = `${(last ? Math.max(0, index) / last : 1) * 100}%`;
    if (head.current) head.current.style.left = share;
    if (fill.current) fill.current.style.width = share;
    for (const node of names.current ? names.current.children : []) node.style.left = `${Number(node.dataset.at) * 100}%`;
  });
  const tick = (i, lane, extra = '') => html`<line class=${extra} x1=${place(i)} x2=${place(i)} y1=${lane * LANE_H + 1} y2=${(lane + 1) * LANE_H - 1} vector-effect="non-scaling-stroke" />`;
  const dot = (i, lane) => html`<line class="dot" x1=${place(i)} x2=${place(i)} y1=${lane * LANE_H + 4} y2=${lane * LANE_H + 6} vector-effect="non-scaling-stroke" />`;
  const span = (from, to, lane, klass) => html`<rect class=${klass} x=${place(from)} y=${lane * LANE_H + 1} width=${Math.max(3, place(to) - place(from))} height=${LANE_H - 2} />`;
  const t0 = runStart();
  const counts = {actor: m.actors.length, context: m.covered.length + m.uncovered.length, memory: m.brief.length + m.quiet.length, alert: m.alerts.length};
  return html`<section class="timeline panel interp" aria-label="Timeline">
    <span id="timeline-help" hidden>${help}</span>
    <div class="tl" id="tl" tabindex="0" role="slider" aria-label=${TIMELINE_NAME} aria-describedby="timeline-help" aria-valuemin="0" aria-valuemax=${last}
      aria-valuenow=${Math.max(0, index)} aria-valuetext=${step ? `Step ${step.seq}${live ? ', live' : ''}` : 'no steps'} onKeyDown=${onKeyDown}
      onPointerDown=${e => { if (e.button) return; e.currentTarget.setPointerCapture(e.pointerId); move(e); }}
      onPointerMove=${e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) move(e); }}>
      <svg class="tlmarks" viewBox=${`0 0 ${VIEW_W} ${LANE_H * LANES.length}`} preserveAspectRatio="none" aria-hidden="true">
        <g class="lane-bg">${LANES.map((_, lane) => html`<rect x="0" y=${lane * LANE_H + 1} width=${VIEW_W} height=${LANE_H - 2} />`)}</g>
        <g class="mark-actor">${m.actors.map((a, k) => span(a.from, a.to, 0, `actor-${k % 2 ? 'b' : 'a'}`))}${m.handoffs.map(i => tick(i, 0, 'handoff'))}</g>
        <g class="mark-context">${m.waits.map(([from, to, active]) => span(from, to, 1, `wait ${active ? 'active' : ''}`))}${m.covered.map(i => tick(i, 1, 'covered'))}${m.uncovered.map(i => tick(i, 1, 'uncovered'))}</g>
        <g class="mark-memory">${m.brief.map(i => tick(i, 2, 'brief'))}${m.quiet.map(i => tick(i, 2, 'quiet'))}${m.reads.map(i => dot(i, 2))}</g>
        <g class="mark-alert">${m.alerts.map(i => tick(i, 3))}</g></svg>
      <div class="tlactors" ref=${names} aria-hidden="true">${m.actors.map(a => html`<span data-at=${last ? a.from / last : 0}>${a.name}</span>`)}</div>
      <div class="tltrack"><div class="tlfill" ref=${fill}></div></div>
      <div class="tlhead" ref=${head}></div>
    </div>
    <div class="tlfoot"><span class="num">${step && typeof step.wall === 'number' ? mmss(step.wall - t0) : ''}</span>
      <span class="legend" id="tl-legend">
        <span class="lg-actor"><i></i>Actors <b class="num">${counts.actor}</b></span>
        <span class="lg-cut"><i></i>Cuts <b class="num">${counts.context}</b>${m.uncovered.length ? html` <span class="lg-uncovered">(${m.uncovered.length} uncovered)</span>` : null}</span>
        <span class="lg-wait"><i></i>Waits <b class="num">${m.waits.length}</b></span>
        <span class="lg-memory"><i></i>Memory <b class="num">${counts.memory}</b></span>
        <span class="lg-read"><i></i>Reads <b class="num">${m.reads.length}</b></span>
        <span class="lg-alert"><i></i>Alerts <b class="num">${counts.alert}</b></span></span>
      <span class="num">${steps.length ? `${count(Math.max(0, index) + 1)} / ${count(steps.length)}` : 'no steps'}</span></div></section>`;
}

/* ---------------------------------------------------------------- working state */
const STATUS_ORDER = {active: 0, paused: 1, done: 2, dropped: 3};
/** The player's committed `player_agenda` as of the playhead, the knowledge version it held then, and what a handoff carried. */
function AgendaDock({handoffs}) {
  const s = store.summary;
  const step = store.steps[cursorIndex()];
  const seq = step ? step.seq : null;
  const {state, change, carried} = agendaAt(seq, store.feed, s, handoffs);
  const version = versionAt(seq, store.feed);
  const numbers = actorNumbers(store.feed, handoffs);
  const threads = state ? [...state.threads].sort((a, b) => (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9)) : [];
  const unused = s && s.agenda && !s.agenda.tool_calls && !s.agenda.events_count;
  const cuts = state ? state.cut_count : cutsUpTo(seq, store.feed);
  const previous = carried ? numbers.get(carried.actor) : null;
  const from = previous ? `${previous} → ${actorNumber(Number(previous))}` : '';
  return html`<section class="dock panel interp" id="agenda-dock" aria-label="Working state">
    <header><h2>Working state</h2><span class="note num">player_agenda${seq === null ? '' : ` as of step ${seq}`}${change && change.seq !== null ? ` · last change #${change.seq}` : ''}</span>
      <span class="gap"></span>
      ${carried ? html`<span class="tag carry" id="dock-carried" title="The next actor started from what this handoff carried">carried at handoff #${carried.seq} · ${from}</span>` : null}
      ${version ? html`<a class="spill head" id="dock-version" href=${`#memory?version=${encodeURIComponent(version)}`}>${version} → Memory</a>` : null}</header>
    ${threads.length ? html`<ul class="threads" id="agenda-threads">${threads.map(t => html`<li data-status=${t.status}><span class="tstat">${t.status}</span><b>${t.title}</b>
        ${carried ? html`<span class="tag carry">carried</span>` : null}${t.notes || t.summary ? html`<span class="note">${t.notes || t.summary}</span>` : null}</li>`)}</ul>`
      : html`<p class="note" id="agenda-empty">Agenda empty (0 threads · ${plural(cuts, 'cut')})${unused ? ' — player_agenda unused' : ''}</p>`}</section>`;
}

/* ---------------------------------------------------------------- story feed */
const isContinuity = e => e.entry_kind === 'agenda_change' || (e.entry_kind === 'finding' && e.finding_kind === 'handoff')
  || (e.entry_kind === 'step' && (isReadTool(e.tool) || e.tool === 'player_agenda' || e.tool === 'player_handoff'));
const FILTERS = [['all', 'All', () => true], ['cuts', 'Cuts & Waits', e => e.entry_kind === 'context_cut' || e.entry_kind === 'coverage_wait'],
  ['memory', 'Memory', e => e.entry_kind === 'knowledge_delivery'], ['agenda', 'Agenda & Reads', isContinuity], ['alerts', 'Alerts', isAlertEntry]];
const WINDOW = 60, MORE = 120;

const searchText = e => [e.intent, e.tool, e.tool && toolLabel(e.tool), e.summary, e.knowledge_version, e.reason, e.cut_result, e.cut_result && label(e.cut_result),
  e.delivery_kind && deliveryWord(e.delivery_kind), e.op, e.agenda && e.agenda.threads.map(t => t.title).join(' '),
  e.entry_kind === 'coverage_wait' && 'coverage wait', e.entry_kind === 'context_cut' && 'context cut',
  e.finding_kind && findingText({kind: e.finding_kind, payload: e.payload}), (e.keys || []).map(keyText).join(' '),
  e.seq === null ? '' : `#${e.seq}`].filter(Boolean).join(' ').toLowerCase();
export const usd = (value, digits = 4) => (value === null || value === undefined ? null : `$${Number(value).toFixed(digits)}`);

function StepCard({entry}) {
  const keys = (entry.keys || []).map(keyText).join(' ');
  const read = entry.source_read;
  const meta = [entry.seq === null ? null : `#${entry.seq}${entry.exact_step ? '' : ' (on screen)'}`, entry.latency_ms === null ? null : `${Math.round(entry.latency_ms)} ms`,
    entry.reported_provider, entry.applied_service_tier && entry.applied_service_tier !== 'default' ? entry.applied_service_tier : null, usd(entry.reported_cost_usd)].filter(Boolean).join(' · ');
  const kind = isKnowledgeTool(entry.tool) ? 'knowledge' : entry.tool === 'player_source' ? 'source' : entry.tool === 'player_agenda' ? 'agenda' : entry.tool === 'player_handoff' ? 'handoff' : null;
  return html`${entry.intent ? html`<span class="intent">${entry.intent}</span>` : html`<span class="intent plain">${toolLabel(entry.tool)}${keys ? '' : ' · no input'}</span>`}
    <span class="cardrow">${entry.intent ? html`<${Pv} source="player_claim" />` : null}${kind ? html`<span class=${`toolchip ${kind}`}>${toolLabel(entry.tool)}</span>` : null}
      <span class="tool">${kind ? '' : toolLabel(entry.tool)}${keys ? html`${kind ? '' : ' · '}<b class="keys-sent">${keys}</b>` : null}</span>
      ${read ? html`<span class="tag alias" data-alias=${read.player_alias || ''}>${sourceReadText(read)}</span>${read.non_clickable === true ? html`<span class="tag quiet" title="The player read this frame without click access; the operator sees the real one">non-clickable</span>` : read.non_clickable === false ? html`<span class="tag quiet" title="The player read this clickable current-session frame">clickable</span>` : null}` : null}
      ${entry.status === 'error' || entry.status === 'refused' ? html`<span class="state alert">${entry.status}</span>` : entry.status === 'pending' ? html`<span class="state clear">pending</span>` : null}</span>
    <span class="meta num">${meta}</span>`;
}
function CutCard({entry}) {
  const saved = entry.tokens_before !== null && entry.tokens_after !== null ? entry.tokens_before - entry.tokens_after : null;
  const b = entry.briefing;
  return html`<span class="mtitle">Context cut${entry.cut_result ? ` · ${label(entry.cut_result)}` : ''}${b && b.knowledge_version ? ` · ${b.knowledge_version}` : entry.knowledge_version ? ` · ${entry.knowledge_version}` : ''}</span>
    <span class="cardrow"><span class="num">${kilo(entry.tokens_before)} → ${kilo(entry.tokens_after)} tokens${saved === null ? '' : ` (−${kilo(saved)})`}</span>
      ${uncoveredCut(entry) ? html`<span class="state watch uncovered" title="Turns removed that no briefing covered (#1037)">${plural(entry.uncovered_turns, 'uncovered turn')} · #1037</span>` : null}</span>
    <span class="meta num">${entry.removed_turns ?? '—'} turns cut · ${entry.images_before ?? '—'} → ${entry.images_after ?? '—'} imgs${(entry.triggers || []).length ? ` · ${entry.triggers.map(label).join(', ')}` : ''}</span>
    ${b ? html`<span class="joined"><span class="jtitle">Post-cut briefing</span><span class="num">${b.briefing_tokens === null ? 'tokens unrecorded' : `${kilo(b.briefing_tokens)} tok`} · ${plural(b.source_ids_count ?? 0, 'source')}${b.summary ? ` · ${b.summary}` : ''}</span></span>`
      : html`<span class="meta">No briefing joined to this cut.</span>`}`;
}
function WaitCard({entry}) {
  const ended = entry.active ? null : entry.ended_by === 'cut' ? 'closed by cut' : entry.ended_by === 'superseded' ? 'superseded' : label(entry.ended_by || 'ended');
  return html`<span class="mtitle">Coverage wait${entry.reason ? ` · ${label(entry.reason)}` : ''}</span>
    <span class="cardrow"><span class="num">${plural(entry.requests, 'request')} held · ${secs(entry.duration_seconds)} · peak ${kilo(entry.peak_tokens)} tok</span>
      ${entry.active ? html`<span class="waitbadge">WAITING</span>` : html`<span class="tag">${ended}</span>`}</span>
    ${entry.restore_possible ? html`<span class="meta">Open at the end of the trace: a restore may resume it.</span>` : null}`;
}
function DeliveryCard({entry}) {
  const chips = deltaChips(entry.delta_counts);
  const preview = entry.delta_preview || [];
  return html`<span class="mtitle"><span class=${`dkind ${deliveryTone(entry.delivery_kind)}`}>${deliveryWord(entry.delivery_kind)}</span>${entry.knowledge_version ? ` ${entry.knowledge_version}` : ''}${entry.previous_version ? html`<span class="note"> after ${entry.previous_version}</span>` : null}</span>
    <span class="num">${entry.delivery_kind === 'refused' || entry.delivery_kind === 'undelivered' ? label(entry.reason || entry.summary || 'reason unrecorded') : entry.summary || 'what changed is not recorded'}</span>
    ${chips.length ? html`<span class="chips">${chips.map(c => html`<span class="tag delta" data-bucket=${c.bucket}>${c.text}</span>`)}</span>` : null}
    ${preview.length ? html`<span class="meta">${preview.slice(0, 2).map(p => `${label(p.bucket)}: ${p.text || p.title || p.subject || p.id}`).join(' · ')}${preview.length > 2 ? ` · +${preview.length - 2}` : ''}</span>` : null}
    <span class="meta num">${entry.covered_step !== null && entry.covered_step !== undefined ? `covers through step ${entry.covered_step}` : 'coverage unrecorded'}</span>`;
}
const OPS = {upsert: 'Threads updated', set_status: 'Status changed', clear_completed: 'Completed threads cleared'};
function AgendaCard({entry, diff}) {
  const changed = diff || [];
  return html`<span class="mtitle">Agenda · ${OPS[entry.op] || label(entry.op || 'change')}</span>
    <span class="num">${plural(entry.thread_count, 'thread')} · ${entry.active_count} active</span>
    ${changed.length ? html`<span class="meta">${changed.slice(0, 3).map(t => `${t.title} (${t.change})`).join(' · ')}${changed.length > 3 ? ` · +${changed.length - 3}` : ''}</span>` : null}`;
}
function FindingCard({entry, numbers}) {
  const handoff = entry.finding_kind === 'handoff';
  return html`<span class="mtitle">${handoff && numbers ? `Handoff ${numbers.get(entry.payload && entry.payload.actor) || ''} → next actor` : findingText({kind: entry.finding_kind, payload: entry.payload})}</span>
    <span class="cardrow"><${Pv} source=${entry.source} /><span class="meta num">${entry.seq === null ? '' : `#${entry.seq}`}</span></span>`;
}
const CARDS = {step: StepCard, context_cut: CutCard, coverage_wait: WaitCard, knowledge_delivery: DeliveryCard, agenda_change: AgendaCard, finding: FindingCard};
const KLASS = e => (e.entry_kind === 'step' ? `step${isAlertEntry(e) ? ' bad' : ''}${isReadTool(e.tool) || e.tool === 'player_agenda' ? ' read' : ''}`
  : e.entry_kind === 'context_cut' ? `cut ${cutTone(e)}` : e.entry_kind === 'coverage_wait' ? `wait${e.active ? ' active' : ''}`
  : e.entry_kind === 'knowledge_delivery' ? `memory ${deliveryTone(e.delivery_kind)}` : e.entry_kind === 'agenda_change' ? 'agenda'
  : e.finding_kind === 'handoff' ? 'handoff' : `alert ${e.finding_kind === 'death' || e.finding_kind === 'custody_stop' ? 'severe' : ''}`);

function StoryFeed() {
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [extra, setExtra] = useState({newer: 0, older: 0});
  const [focus, setFocus] = useState(null);   // an entry another card pointed to
  const list = useRef(null);
  const index = cursorIndex();
  const step = store.steps[index];
  const seq = step ? step.seq : null;
  const needle = query.trim().toLowerCase();
  const counts = useMemo(() => Object.fromEntries(FILTERS.map(([key, , match]) => [key, store.feed.filter(match).length])), [store.feed]);
  const diffs = useMemo(() => agendaDiffs(store.feed, store.summary), [store.feed, store.summary && store.summary.agenda]);
  const numbers = useMemo(() => actorNumbers(store.feed), [store.feed]);
  const rows = useMemo(() => {   // newest first
    const match = FILTERS.find(([key]) => key === filter)[2];
    return store.feed.filter(e => match(e) && (!needle || searchText(e).includes(needle))).reverse();
  }, [store.feed, filter, needle]);
  const reset = patch => { setExtra({newer: 0, older: 0}); setFocus(null); patch(); };
  // The active entry, or the newest one at or before the playhead when the filter hides it.
  let active = rows.findIndex(e => e.seq === seq && e.entry_kind === 'step');
  if (active < 0) active = rows.findIndex(e => e.seq !== null && seq !== null && e.seq <= seq);
  const focused = focus === null ? -1 : rows.findIndex(e => e.id === focus);
  const center = Math.max(0, focused >= 0 ? focused : active);
  const from = Math.max(0, center - WINDOW - extra.newer), to = Math.min(rows.length, center + WINDOW + extra.older);
  useEffect(() => { setExtra({newer: 0, older: 0}); setFocus(null); }, [store.runId]);
  useEffect(() => {   // keep the active (or pointed-to) card in view inside the list, without moving the page
    const box = list.current, card = box && (box.querySelector('[data-focus="yes"]') || box.querySelector('[aria-current="true"]'));
    if (!card) { if (box && isLive()) box.scrollTop = 0; return; }
    const top = card.offsetTop, bottom = top + card.offsetHeight;
    if (top < box.scrollTop || bottom > box.scrollTop + box.clientHeight) box.scrollTop = Math.max(0, top - box.clientHeight / 3);
  }, [seq, filter, needle, store.runId, rows.length === 0, focus]);
  const show = id => { setFilter('all'); setQuery(''); setExtra({newer: 0, older: 0}); setFocus(id); };
  return html`<section class="story panel interp" aria-label="Story feed">
    <header class="storyhead"><h2>Continuity</h2><span class="note num" id="story-count">${needle ? `${count(rows.length)} found` : `${count(rows.length)} shown`}</span>
      <${Segmented} label="Story filter" className="chipset" value=${filter} onChange=${v => reset(() => setFilter(v))}
        options=${FILTERS.map(([value, text]) => ({value, text, id: `story-${value}`, count: counts[value]}))} />
      <input type="search" id="story-search" placeholder="Search the story" aria-label="Search the story" value=${query} onInput=${e => { const v = e.currentTarget.value; reset(() => setQuery(v)); }} /></header>
    ${!store.feedMeta ? html`<${Waiting} store=${store} what="the story" />` : html`
      ${store.feedMeta.source === 'host_trace' ? null : html`<p class="note" id="story-source">No host trace is available for this run, so the story has no intents, costs, context cuts or memory deliveries.</p>`}
      <ol class="storylist" ref=${list} id="story">
        ${from > 0 ? html`<li class="more"><button type="button" class="btn" onClick=${() => setExtra({...extra, newer: extra.newer + MORE})}>${count(from)} newer</button></li>` : null}
        ${rows.slice(from, to).map(entry => {
          const Card = CARDS[entry.entry_kind];
          const here = entry.seq === seq && entry.entry_kind === 'step';
          const version = entry.entry_kind === 'knowledge_delivery' ? entry.knowledge_version : entry.entry_kind === 'context_cut' && entry.briefing ? entry.briefing.knowledge_version : null;
          return html`<li key=${entry.id} class="card ${KLASS(entry)} ${here ? 'here' : ''}" aria-current=${here ? 'true' : null} data-entry=${entry.id} data-kind=${entry.entry_kind} data-focus=${focus === entry.id ? 'yes' : null}>
            <button type="button" class="cardmain" data-jump=${entry.seq} disabled=${entry.seq === null} onClick=${() => setCursorSeq(entry.seq)}><${Card} entry=${entry} diff=${diffs.get(entry.id)} numbers=${numbers} /></button>
            <div class="acts">${entry.entry_kind === 'step' ? html`<button type="button" class="inspect" aria-label=${`Inspect step ${entry.seq ?? ''}`} onClick=${() => { if (entry.seq !== null) setCursorSeq(entry.seq); set({inspect: entry.id}); }}>Inspect</button>` : null}
              ${entry.entry_kind === 'context_cut' && entry.briefing ? html`<button type="button" class="inspect" data-briefing=${entry.briefing.delivery_id} onClick=${() => show(entry.briefing.delivery_id)}>Briefing</button>` : null}
              ${version ? html`<a class="inspect" data-version=${version} href=${`#memory?version=${encodeURIComponent(version)}`}>${version} → Memory</a>` : null}</div></li>`;
        })}
        ${to < rows.length ? html`<li class="more"><button type="button" class="btn" onClick=${() => setExtra({...extra, older: extra.older + MORE})}>${count(rows.length - to)} older</button></li>` : null}
        ${rows.length ? null : html`<li class="more note" role="status">${needle ? 'No entry matches.' : 'Nothing of this kind in this run.'}</li>`}
      </ol>`}</section>`;
}

/* ---------------------------------------------------------------- the tab */
export function Watch() {
  const s = store.summary, run = store.runId;
  const handoffs = useView(run ? runPath(run, 'handoffs') : null, s && s.live ? 10000 : 0);
  if (!s) return html`<section class="watchgrid" data-view="watch" aria-label="Watch"><${Panel} title="Watch" span="s12"><${Waiting} store=${store} what="the run" /><//></section>`;
  const step = store.steps[cursorIndex()];
  const list = handoffs.data ? handoffs.data.handoffs : [];
  return html`<section class="watchgrid" data-view="watch" data-wide=${store.feedWide ? 'yes' : 'no'} aria-label="Watch">
    <div class="watchleft"><${FeedPlayer} run=${run} step=${step} /><${Timeline} /><${AgendaDock} handoffs=${list} /></div>
    <div class="watchright"><${StoryFeed} /><${Inspector} handoffs=${list} /></div></section>`;
}
