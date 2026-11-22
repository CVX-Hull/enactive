// Watch: the game screen, the timeline playhead and the story feed, on one shared step.
import {html, useEffect, useLayoutEffect, useMemo, useRef, useState, Panel, Pv, Segmented, Waiting, clockTime, gameClock, keyText, kilo, label, mmss, count, plural, readingNote} from './ui.js';
import {store, set, framePath, selectedRun, setCursorIndex, setCursorSeq, cursorIndex, goLive, isLive, runStart, setFeedWide, recordedPage} from './data.js';
import {findingText, pauseMet, vitalBadges} from './supervise.js';
import {Inspector} from './inspector.js';

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
/** What counts as an alert, on the timeline and in the story alike: a finding, or a call that failed or was refused. */
export const isAlertEntry = e => e.entry_kind === 'finding' || (e.entry_kind === 'step' && (e.status === 'error' || e.status === 'refused'));
/** The story entries the timeline marks: three lanes, so a mark is told by its place as well as its colour. */
const LANES = [['cut', 'Context cut', e => e.entry_kind === 'context_cut' && e.outcome === 'applied'],
  ['memory', 'Memory update', e => e.entry_kind === 'knowledge_update' && e.outcome !== 'refused'],
  ['alert', 'Alert', isAlertEntry]];
const VIEW_W = 1000, LANE_H = 10;

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
  const marks = useMemo(() => {
    const at = new Map(steps.map((s, i) => [s.seq, i]));
    return LANES.map(([, , match]) => store.feed.filter(match).map(e => at.get(e.seq)).filter(i => i !== undefined));
  }, [store.feed, steps]);
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
  const head = useRef(null), fill = useRef(null);
  useEffect(() => {   // sized through the DOM style object: the page CSP forbids inline style attributes
    const share = `${(last ? Math.max(0, index) / last : 1) * 100}%`;
    if (head.current) head.current.style.left = share;
    if (fill.current) fill.current.style.width = share;
  });
  const t0 = runStart();
  return html`<section class="timeline panel interp" aria-label="Timeline">
    <span id="timeline-help" hidden>${help}</span>
    <div class="tl" id="tl" tabindex="0" role="slider" aria-label=${TIMELINE_NAME} aria-describedby="timeline-help" aria-valuemin="0" aria-valuemax=${last}
      aria-valuenow=${Math.max(0, index)} aria-valuetext=${step ? `Step ${step.seq}${live ? ', live' : ''}` : 'no steps'} onKeyDown=${onKeyDown}
      onPointerDown=${e => { if (e.button) return; e.currentTarget.setPointerCapture(e.pointerId); move(e); }}
      onPointerMove=${e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) move(e); }}>
      <div class="tltrack"><div class="tlfill" ref=${fill}></div></div>
      <svg class="tlmarks" viewBox=${`0 0 ${VIEW_W} ${LANE_H * 3}`} preserveAspectRatio="none" aria-hidden="true">
        ${marks.map((list, lane) => html`<g class=${`mark-${LANES[lane][0]}`}>${list.map(i => html`<line x1=${place(i)} x2=${place(i)} y1=${lane * LANE_H + 1} y2=${(lane + 1) * LANE_H - 1} vector-effect="non-scaling-stroke" />`)}</g>`)}</svg>
      <div class="tlhead" ref=${head}></div>
    </div>
    <div class="tlfoot"><span class="num">${step && typeof step.wall === 'number' ? mmss(step.wall - t0) : ''}</span>
      <span class="legend" id="tl-legend">${LANES.map(([key, name], lane) => html`<span class=${`lg-${key}`}><i></i>${name} <b class="num">${marks[lane].length}</b></span>`)}</span>
      <span class="num">${steps.length ? `${count(Math.max(0, index) + 1)} / ${count(steps.length)}` : 'no steps'}</span></div></section>`;
}

/* ---------------------------------------------------------------- story feed */
const FILTERS = [['all', 'All', e => !(e.entry_kind === 'context_cut' && e.outcome !== 'applied')], ['cuts', 'Cuts', e => e.entry_kind === 'context_cut'],
  ['memory', 'Memory', e => e.entry_kind === 'knowledge_update'], ['alerts', 'Alerts', isAlertEntry]];
const WINDOW = 60, MORE = 120;

const searchText = e => [e.intent, e.tool, e.summary, e.knowledge_version, e.reason, e.finding_kind && findingText({kind: e.finding_kind, payload: e.payload}),
  (e.keys || []).map(keyText).join(' '), e.seq === null ? '' : `#${e.seq}`].filter(Boolean).join(' ').toLowerCase();
export const toolText = tool => label(tool || 'recorded step');
export const usd = (value, digits = 4) => (value === null || value === undefined ? null : `$${Number(value).toFixed(digits)}`);

function StepCard({entry}) {
  const keys = (entry.keys || []).map(keyText).join(' ');
  const meta = [entry.seq === null ? null : `#${entry.seq}${entry.exact_step ? '' : ' (on screen)'}`, entry.latency_ms === null ? null : `${Math.round(entry.latency_ms)} ms`,
    entry.reported_provider, usd(entry.reported_cost_usd)].filter(Boolean).join(' · ');
  return html`${entry.intent ? html`<span class="intent">${entry.intent}</span>` : html`<span class="intent plain">${toolText(entry.tool)}${keys ? '' : ' · no input'}</span>`}
    <span class="cardrow">${entry.intent ? html`<${Pv} source="player_claim" />` : null}<span class="tool">${toolText(entry.tool)}${keys ? html` · <b class="keys-sent">${keys}</b>` : null}</span>${
      entry.status === 'error' || entry.status === 'refused' ? html`<span class="state alert">${entry.status}</span>` : entry.status === 'pending' ? html`<span class="state clear">pending</span>` : null}</span>
    <span class="meta num">${meta}</span>`;
}
function CutCard({entry}) {
  const applied = entry.outcome === 'applied';
  const saved = applied && entry.tokens_before !== null && entry.tokens_after !== null ? entry.tokens_before - entry.tokens_after : null;
  return html`<span class="mtitle">${applied ? 'Context cut' : 'Cut held back'}${entry.knowledge_version ? ` · ${entry.knowledge_version}` : ''}</span>
    ${applied ? html`<span class="num">${kilo(entry.tokens_before)} → ${kilo(entry.tokens_after)} tokens${saved === null ? '' : ` (−${kilo(saved)})`}</span>
      <span class="meta num">${entry.images_before ?? '—'} → ${entry.images_after ?? '—'} imgs · ${entry.removed_turns ?? '—'} turns cut${entry.triggers.length ? ` · ${entry.triggers.map(label).join(', ')}` : ''}</span>`
    : html`<span class="meta num">${kilo(entry.tokens_before)} tokens · ${label(entry.reason || 'reason unknown')}</span>`}`;
}
function UpdateCard({entry}) {
  const refused = entry.outcome === 'refused';
  return html`<span class="mtitle">${refused ? 'Memory update refused' : 'Memory updated'}${entry.knowledge_version ? ` · ${entry.knowledge_version}` : ''}</span>
    <span class="num">${refused ? label(entry.reason || 'reason unknown') : entry.summary || 'what changed is not recorded'}</span>
    <span class="meta num">${entry.covered_step !== null ? `covers through step ${entry.covered_step}` : 'coverage unrecorded'}</span>`;
}
function FindingCard({entry}) {
  return html`<span class="mtitle">${findingText({kind: entry.finding_kind, payload: entry.payload})}</span>
    <span class="cardrow"><${Pv} source=${entry.source} /><span class="meta num">${entry.seq === null ? '' : `#${entry.seq}`}</span></span>`;
}
const CARDS = {step: StepCard, context_cut: CutCard, knowledge_update: UpdateCard, finding: FindingCard};
const KLASS = entry => (entry.entry_kind === 'step' ? (isAlertEntry(entry) ? 'step bad' : 'step') : entry.entry_kind === 'context_cut' ? `cut ${entry.outcome === 'applied' ? '' : 'held'}`
  : entry.entry_kind === 'knowledge_update' ? 'memory' : `alert ${entry.finding_kind === 'death' || entry.finding_kind === 'custody_stop' ? 'severe' : ''}`);

function StoryFeed() {
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [extra, setExtra] = useState({newer: 0, older: 0});
  const list = useRef(null);
  const index = cursorIndex();
  const step = store.steps[index];
  const seq = step ? step.seq : null;
  const needle = query.trim().toLowerCase();
  const counts = useMemo(() => Object.fromEntries(FILTERS.map(([key, , match]) => [key, store.feed.filter(match).length])), [store.feed]);
  const rows = useMemo(() => {   // newest first
    const match = FILTERS.find(([key]) => key === filter)[2];
    return store.feed.filter(e => match(e) && (!needle || searchText(e).includes(needle))).reverse();
  }, [store.feed, filter, needle]);
  const reset = patch => { setExtra({newer: 0, older: 0}); patch(); };
  // The active entry, or the newest one at or before the playhead when the filter hides it.
  let active = rows.findIndex(e => e.seq === seq && e.entry_kind === 'step');
  if (active < 0) active = rows.findIndex(e => e.seq !== null && seq !== null && e.seq <= seq);
  const center = Math.max(0, active);
  const from = Math.max(0, center - WINDOW - extra.newer), to = Math.min(rows.length, center + WINDOW + extra.older);
  useEffect(() => { setExtra({newer: 0, older: 0}); }, [store.runId]);
  useEffect(() => {   // keep the active card in view inside the list, without moving the page
    const box = list.current, card = box && box.querySelector('[aria-current="true"]');
    if (!card) { if (box && isLive()) box.scrollTop = 0; return; }
    const top = card.offsetTop, bottom = top + card.offsetHeight;
    if (top < box.scrollTop || bottom > box.scrollTop + box.clientHeight) box.scrollTop = Math.max(0, top - box.clientHeight / 3);
  }, [seq, filter, needle, store.runId, rows.length === 0]);
  const held = store.feedMeta ? store.feed.filter(e => e.entry_kind === 'context_cut' && e.outcome === 'held_back').length : 0;
  return html`<section class="story panel interp" aria-label="Story feed">
    <header class="storyhead"><h2>Story</h2><${Segmented} label="Story filter" className="chipset" value=${filter} onChange=${v => reset(() => setFilter(v))}
        options=${FILTERS.map(([value, text]) => ({value, text, id: `story-${value}`, count: counts[value]}))} />
      <input type="search" id="story-search" placeholder="Search" aria-label="Search the story" value=${query} onInput=${e => { const v = e.currentTarget.value; reset(() => setQuery(v)); }} />
      <span class="note num" id="story-count">${needle ? `${count(rows.length)} found` : filter === 'cuts' && held ? `${count(held)} held back` : ''}</span></header>
    ${!store.feedMeta ? html`<${Waiting} store=${store} what="the story" />` : html`
      ${store.feedMeta.source === 'host_trace' ? null : html`<p class="note" id="story-source">No host trace is available for this run, so the story has no intents, costs, context cuts or memory updates.</p>`}
      <ol class="storylist" ref=${list} id="story">
        ${from > 0 ? html`<li class="more"><button type="button" class="btn" onClick=${() => setExtra({...extra, newer: extra.newer + MORE})}>${count(from)} newer</button></li>` : null}
        ${rows.slice(from, to).map(entry => {
          const Card = CARDS[entry.entry_kind];
          const here = entry.seq === seq && entry.entry_kind === 'step';
          return html`<li key=${entry.id} class="card ${KLASS(entry)} ${here ? 'here' : ''}" aria-current=${here ? 'true' : null} data-entry=${entry.id} data-kind=${entry.entry_kind}>
            <button type="button" class="cardmain" data-jump=${entry.seq} disabled=${entry.seq === null} onClick=${() => setCursorSeq(entry.seq)}><${Card} entry=${entry} /></button>
            ${entry.entry_kind === 'step' ? html`<button type="button" class="inspect" aria-label=${`Inspect step ${entry.seq ?? ''}`} onClick=${() => { if (entry.seq !== null) setCursorSeq(entry.seq); set({inspect: entry.id}); }}>Inspect</button>`
              : entry.entry_kind === 'knowledge_update' && entry.knowledge_version && entry.outcome !== 'refused' ? html`<a class="inspect" href=${`#memory/${encodeURIComponent(entry.knowledge_version)}`}>Open in Memory →</a>` : null}</li>`;
        })}
        ${to < rows.length ? html`<li class="more"><button type="button" class="btn" onClick=${() => setExtra({...extra, older: extra.older + MORE})}>${count(rows.length - to)} older</button></li>` : null}
        ${rows.length ? null : html`<li class="more note" role="status">${needle ? 'No entry matches.' : 'Nothing of this kind in this run.'}</li>`}
      </ol>`}</section>`;
}

/* ---------------------------------------------------------------- the tab */
export function Watch() {
  const s = store.summary, run = store.runId;
  if (!s) return html`<section class="watchgrid" data-view="watch" aria-label="Watch"><${Panel} title="Watch" span="s12"><${Waiting} store=${store} what="the run" /><//></section>`;
  const step = store.steps[cursorIndex()];
  return html`<section class="watchgrid" data-view="watch" data-wide=${store.feedWide ? 'yes' : 'no'} aria-label="Watch">
    <div class="watchleft">
      ${pauseMet(s) ? html`<a class="pausealert" id="pausealert" href="#diagnostics/pause"><span class="state alert">Pause?</span> ${s.pause.met.join('; ')}. See why →</a>` : null}
      <${FeedPlayer} run=${run} step=${step} /><${Timeline} /></div>
    <div class="watchright"><${StoryFeed} /><${Inspector} /></div></section>`;
}
