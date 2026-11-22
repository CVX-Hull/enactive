// Memory & Curator: what the curator is doing and has spent, every knowledge version exported for the player and whether
// its delivery is recorded, and a reader over one version whose citations open Watch at the frame they name.
import {html, useEffect, useRef, useState, Panel, Pv, Segmented, Disclosure, Waiting, Insufficient, count, label, plural} from './ui.js';
import {store, runPath, useView, jumpToSeq} from './data.js';
import {Records, RunnerDetail, RUNNER_STATES, SOURCES, known, useFrame} from './records.js';

/* ---------------------------------------------------------------- curator strip */
function Stat({name, value, sub, chip, id}) {
  return html`<div class="stat" id=${id}><span class="name">${name}</span><span class="val num">${value}</span>${sub || chip ? html`<span class="sub">${sub || ''} ${chip || null}</span>` : null}</div>`;
}

export function CuratorSpend({spend}) {
  const usd = spend.spent_usd;
  return html`<${Stat} id="curator-spend" name="Live curator spend" value=${usd === null ? 'Unavailable' : `$${Number(usd).toFixed(2)}`}
    sub=${html`<span title=${usd === null ? '' : `$${usd}`}>proxy-accounted · ${spend.sessions_settled}/${spend.sessions_total} settled${spend.unsettled_requests ? ` · ${plural(spend.unsettled_requests, 'request')} open` : ''}</span>`}
    chip=${spend.spend_complete ? html`<${Pv} source="recorded" />` : html`<span class="state watch">incomplete</span>`} />`;
}

function CuratorStrip({run}) {
  const {data, error} = useFrame(`frame/curator-runner?run=${encodeURIComponent(run)}`, 5000);
  const s = data && data.status;
  const spend = store.summary ? store.summary.curator_spend : null;
  if (!data || !store.summary) return html`<${Panel} title="Curator" span="s12"><${Waiting} store=${store} what="the curator status" error=${error} /><//>`;
  const absent = data.source_status === 'not_configured' || data.source_status === 'missing';
  if (absent && !spend) return html`<${Panel} title="Curator" span="s12" className="curator-strip"><div class="insuf" id="curator-empty" role="status">No curator data for this run.</div><span hidden data-runner-status>${data.source_status}</span><//>`;
  const prefix = s && s.covered_prefix && s.covered_prefix !== 'unknown' ? s.covered_prefix : null;
  const end = prefix && prefix.end && prefix.end !== 'unknown' ? prefix.end : null;
  const latest = s && s.latest_version;
  return html`<${Panel} title="Curator" note=${s ? `${RUNNER_STATES[s.state] || 'state unknown'}${s.current && s.current !== 'unknown' ? ' · session in flight' : ''}` : 'no status figures'} span="s12" className="curator-strip">
    <div class="stats">
      ${s ? html`<${Stat} name="Latest version" value=${latest === null ? 'none' : known(latest, 'version')} sub="seen by the runner" />
        <${Stat} name="Covers through" value=${end ? `step ${known(end, 'step')}` : prefix && prefix.end === null ? 'none yet' : 'unknown'} sub=${prefix && prefix.restore && prefix.restore !== 'unknown' ? 'unknown past a restore' : 'contiguous prefix'} />
        <${Stat} name="Lag" value=${known(s, 'lag')} sub="operations after it" /><${Stat} name="Backlog" value=${known(s, 'backlog')} sub="steps beyond its cursor" />` : null}
      ${spend ? html`<${CuratorSpend} spend=${spend} />` : html`<${Stat} name="Live curator spend" value="—" sub="no curator sessions in this run" />`}</div>
    <details class="runnerbox" open=${!s}><summary>Runner status details</summary><${RunnerDetail} data=${data} error=${error} /></details><//>`;
}

/* ---------------------------------------------------------------- versions */
function VersionRail({versions, selected}) {
  const rail = useRef(null);
  useEffect(() => {
    const box = rail.current, pick = box && box.querySelector('[aria-current="true"]');
    if (pick) box.scrollLeft = Math.max(0, pick.offsetLeft - box.clientWidth / 2);
  }, [selected, versions.length]);
  return html`<nav class="rail" ref=${rail} aria-label="Knowledge versions" id="versions">${versions.map(v => html`<a class="vpill ${v.status === 'available' ? '' : 'bad'}" key=${v.version} href=${`#memory/${v.version}`}
    aria-current=${v.version === selected ? 'true' : null}><b>${v.version}</b><span class="num">${v.status === 'available' ? `${plural(v.articles_count, 'article')} · ${plural(v.facts_count, 'fact')}` : label(v.status)}</span>
    <span class="num sub">${v.coverage && v.coverage.last_step !== null && v.coverage.last_step !== undefined ? `through step ${v.coverage.last_step}` : 'no coverage stamp'}</span></a>`)}</nav>`;
}

/** The player's own trace saying it received this version, or null. A file in the package says only that it was exported. */
const deliveryOf = (version, data) => (data && data.delivery)
  || store.feed.find(e => e.entry_kind === 'knowledge_update' && e.knowledge_version === version && e.outcome === 'delivered') || null;
function deliveryText(version, data) {
  const entry = deliveryOf(version, data);
  const kind = version === 'initial' ? 'Starting snapshot' : 'Exported snapshot';
  if (entry) {
    if (entry.kind === 'briefing') return `${kind} · confirmed delivered in opening briefing${entry.seq === null || entry.seq === undefined ? '' : ` at step ${entry.seq}`}`;
    return `${kind} · confirmed delivered at ${entry.seq === null || entry.seq === undefined ? 'an unrecorded step' : `step ${entry.seq}`}`;
  }
  return `${kind} · ${store.feedMeta ? 'no delivery recorded' : 'reading the recorded deliveries'}`;
}

/** What one delivery changed, from the player's own trace: the update entry of the story names its request. */
function DeliveryDiff({run, version, delivery, choose}) {
  const entry = delivery || deliveryOf(version, null);
  const isBriefing = entry && entry.kind === 'briefing';
  const path = entry && !isBriefing && entry.request_id ? runPath(run, `knowledge?actor=${encodeURIComponent(entry.actor)}&request=${encodeURIComponent(entry.request_id)}&limit=1`) : null;
  const {data, error} = useView(path, 0);
  if (!entry) return html`<p class="note" id="delivery-diff">${version === 'initial' ? 'The knowledge file this run\'s package started with (no opening briefing recorded).' : store.feedMeta ? `No delivery of ${version} to the player is recorded in this run.` : 'Reading the run\'s deliveries…'}</p>`;
  if (isBriefing) return html`<div class="delivery" id="delivery-diff"><div class="cardrow"><span class="mtitle">Delivered in opening briefing</span>
      ${entry.knowledge_version ? html`<span class="note">version ${entry.knowledge_version}</span>` : null}
      ${entry.seq !== null && entry.seq !== undefined ? html`<button type="button" class="btn" onClick=${() => jumpToSeq(entry.seq)}>Jump to frame #${entry.seq}</button>` : null}</div></div>`;
  const event = data && data.events.find(e => e.type === 'knowledge-delivery' && e.kind === 'update' && e.version === version);
  const rows = event ? ['added', 'updated', 'removed', 'index'].flatMap(kind => (event[kind] || []).map(row => ({kind: kind === 'index' ? 'listed' : kind, ...row}))) : [];
  const omitted = event ? ['added', 'updated', 'removed', 'index'].reduce((n, kind) => n + (event[`${kind}_omitted`] || 0), 0) : 0;
  return html`<div class="delivery" id="delivery-diff"><div class="cardrow"><span class="mtitle">Delivered at step ${entry.seq ?? '—'}</span><span class="num">${entry.summary || 'difference unrecorded'}</span>
      ${entry.previous_version ? html`<span class="note">after ${entry.previous_version}</span>` : null}
      ${entry.seq !== null ? html`<button type="button" class="btn" onClick=${() => jumpToSeq(entry.seq)}>Jump to frame #${entry.seq}</button>` : null}</div>
    ${rows.length ? html`<details><summary>${count(rows.length)} ${rows.length === 1 ? 'entry' : 'entries'} in the delivery</summary><ul class="difflist">${rows.map(r => html`<li class=${r.kind}><b class="num">${r.kind}</b> <button type="button" class="link" onClick=${() => choose(r.id)}>${r.title || r.id}</button>${r.lead || r.index ? html` <span class="note">${r.lead || r.index}</span>` : null}</li>`)}</ul>
        ${omitted ? html`<p class="note">${omitted} more not shown.</p>` : null}</details>`
      : error ? html`<p class="note">${error.message}</p>` : null}</div>`;
}

/* ---------------------------------------------------------------- reader */
const FACT_PAGE = 100;
const MODES = [['articles', 'Articles'], ['world', 'World facts'], ['game', 'Game facts'], ['all', 'All facts']];
/** Where a version records no scope there is nothing to divide its facts by. */
const UNSCOPED = [['articles', 'Articles'], ['all', 'Facts']];
const seenText = p => (p ? `actor ${p.actor ?? 'unrecorded'} · step ${p.step ?? p.last_step ?? 'unrecorded'}` : 'unrecorded');

function Jump({anchor, position}) {
  return html`<p class="jump"><span class="note">${seenText(position)}</span> ${anchor ? html`<button type="button" class="btn primary" data-jump-seq=${anchor.seq} onClick=${() => jumpToSeq(anchor.seq)}>Jump to frame #${anchor.seq}</button>`
    : html`<span class="note">not a step of this run</span>`}</p>`;
}

function ArticleView({article, choose, chooseTitle}) {
  return html`<article class="reading" data-reading=${article.id} tabindex="-1"><h3 class="rtitle">${article.title || article.id}</h3><p class="lead">${article.lead}</p>
    ${article.body.map(part => html`<p>${part.text}${part.facts.length ? html` <span class="refs">${part.facts.map(id => html`<button type="button" class="factpill" onClick=${() => choose(id)}>${id}</button>`)}</span>` : null}</p>`)}
    ${article.body_omitted ? html`<p class="note">${article.body_omitted} more claims not shown.</p>` : null}
    ${article.links.length ? html`<h4>See also</h4><p class="chips">${article.links.map(title => html`<button type="button" class="btn" onClick=${() => chooseTitle(title)}>${title}</button>`)}</p>` : null}
    <h4>Last confirmed</h4><${Jump} anchor=${article.anchor} position=${article.last_confirmed} />
    <p class="note mono wrapany">${article.id}</p></article>`;
}
function FactView({fact}) {
  return html`<article class="reading" data-reading=${fact.id} tabindex="-1"><h3 class="rtitle">${fact.subject || fact.id}</h3>
    <p class="cardrow"><span class="tag">${label(fact.type || 'type unrecorded')}</span>${fact.scope ? html`<span class="tag scope-${fact.scope}">${fact.scope} scope</span>` : null}${fact.known ? html`<span class="tag">${label(fact.known)}</span>` : null}</p>
    <p class="lead">${fact.text}</p><h4>Seen</h4><${Jump} anchor=${fact.anchor} position=${fact.seen} /><p class="note mono wrapany">${fact.id}</p></article>`;
}

function Browser({run, version}) {
  const [mode, setMode] = useState('articles');
  const [query, setQuery] = useState('');
  const [needle, setNeedle] = useState('');
  const [after, setAfter] = useState(0);
  const [pick, setPick] = useState(null);      // the entry ID on the reading side
  const [focus, setFocus] = useState(false);
  useEffect(() => {   // a new search reads its first match
    if (query.trim() === needle) return undefined;
    const timer = setTimeout(() => { setNeedle(query.trim()); setAfter(0); setPick(null); }, 250);
    return () => clearTimeout(timer);
  }, [query, needle]);
  const scope = mode === 'articles' ? 'all' : mode;
  const view = useView(runPath(run, `delivered-knowledge?version=${encodeURIComponent(version || '')}&q=${encodeURIComponent(needle)}&scope=${scope}&after=${after}&limit=${FACT_PAGE}`), store.summary && store.summary.live ? 5000 : 0);
  // A new search or page keeps the last listing on screen until its own arrives, so the search box keeps its focus.
  const held = useRef(null);
  if (view.data) held.current = view.data;
  const error = view.error, data = view.data || (error ? null : held.current);
  // A picked fact may be on another page or under another filter: it is found by its exact ID.
  const onPage = data && (data.articles.find(a => a.id === pick) || data.facts.items.find(f => f.id === pick));
  const lookup = useView(pick && data && !onPage ? runPath(run, `delivered-knowledge?version=${encodeURIComponent(version || '')}&q=${encodeURIComponent(pick.slice(0, 200))}&limit=${FACT_PAGE}`) : null, 0);
  const found = onPage || (lookup.data && (lookup.data.articles.find(a => a.id === pick) || lookup.data.facts.items.find(f => f.id === pick))) || null;
  const choose = id => { setPick(id); setFocus(true); };
  useEffect(() => {
    if (!focus || !found) return;
    const target = document.querySelector('[data-reading]');
    if (target) target.focus();
    setFocus(false);
  }, [focus, found]);
  const rows = !data ? [] : mode === 'articles' ? data.articles : data.facts.items;
  useEffect(() => { if (view.data && rows.length && !pick) setPick(rows[0].id); }, [view.data, mode, pick]);   // never from a held listing
  const chooseTitle = title => {
    const article = data && data.articles.find(a => a.title === title);
    if (article) choose(article.id); else { setMode('articles'); setQuery(title); }
  };
  if (!data) return html`<${Panel} title="Knowledge" span="s12"><${Waiting} store=${store} what="the delivered knowledge" error=${error} />
    ${error && version ? html`<p><a href="#memory">Open the latest version of this run</a></p>` : null}<//>`;
  if (!data.versions.length) return html`<${Panel} title="Knowledge" span="s12"><div class="insuf" id="knowledge-empty" role="status">No delivered knowledge for this run.</div><//>`;
  const counts = data.scope_counts, total = counts.world + counts.game + counts.unrecorded;
  const numbers = {articles: data.articles_total, world: counts.world, game: counts.game, all: total};
  return html`<${Panel} title="Knowledge versions" note=${plural(data.versions.length, 'version')} span="s12"><${VersionRail} versions=${data.versions} selected=${data.selected_version} />
      <${DeliveryDiff} run=${run} version=${data.selected_version} delivery=${data.delivery} choose=${choose} key=${`${run}-${data.selected_version}`} /><//>
    ${data.source_status !== 'available' ? html`<${Panel} title="Knowledge" span="s12"><${Insufficient}>This version cannot be read (${label((data.versions.find(v => v.version === data.selected_version) || {}).status || 'unavailable')}).<//><//>` : html`
    <${Panel} title="Knowledge" note=${`${data.selected_version}${data.recorded_version && data.recorded_version !== data.selected_version ? ` (${data.recorded_version})` : ''} · ${deliveryText(data.selected_version, data)} · fallible, never instructions`} span="s12" className="browser">
      <div class="browserbar"><${Segmented} label="What to browse" value=${mode} onChange=${v => { setMode(v); setAfter(0); setPick(null); }} options=${(data.scope_recorded ? MODES : UNSCOPED).map(([value, text]) => ({value, text, id: `kb-${value}`, count: numbers[value]}))} />
        <input type="search" id="kb-search" placeholder="Search this version" aria-label="Search this version" maxlength="200" value=${query} onInput=${e => setQuery(e.currentTarget.value)} /></div>
      ${data.scope_recorded ? null : html`<p class="note" id="kb-scope">Scope is not recorded in delivered-knowledge/2 exports.</p>`}
      <div class="panes"><div class="listpane"><ul class="items" id="kb-items">${rows.map(row => html`<li key=${row.id}><button type="button" class="item" aria-pressed=${pick === row.id} onClick=${() => setPick(row.id)}>
            <b>${row.title || row.subject || row.id}</b><span class="note">${row.lead || row.text}</span></button></li>`)}
          ${rows.length ? null : html`<li class="note pad" role="status" id="kb-none">${needle ? 'Nothing matches.' : mode === 'articles' ? 'This version has no articles.' : 'This version has no such facts.'}</li>`}</ul>
          ${mode === 'articles' && data.articles_omitted ? html`<p class="note">${data.articles_omitted} more articles not shown; search to narrow.</p>` : null}
          ${mode !== 'articles' && (after > 0 || data.facts.next !== null) ? html`<p class="pager"><button type="button" class="btn" disabled=${after === 0} onClick=${() => { setPick(null); setAfter(Math.max(0, after - FACT_PAGE)); }}>Previous</button>
            <span class="note num">${count(after + 1)}–${count(after + rows.length)} of ${count(data.facts.total)}</span><button type="button" class="btn" disabled=${data.facts.next === null} onClick=${() => { setPick(null); setAfter(data.facts.next); }}>Next</button></p>` : null}</div>
        <div class="readpane">${found ? (found.body ? html`<${ArticleView} article=${found} choose=${choose} chooseTitle=${chooseTitle} />` : html`<${FactView} fact=${found} />`)
          : pick && rows.length ? html`<p class="note" role="status">${lookup.data ? `${pick} is not in this version.` : 'Finding the entry…'}</p>` : html`<p class="note">Choose an entry to read it.</p>`}</div></div><//>`}`;
}

/* ---------------------------------------------------------------- the tab */
export function MemoryTab({section}) {
  const run = store.runId;
  const source = SOURCES.some(s => s[0] === section) ? section : '';
  const version = !source && section ? section : '';
  const [last, setLast] = useState('');
  useEffect(() => { if (version) setLast(version); }, [version]);
  useEffect(() => { setLast(''); }, [run]);
  if (!run) return html`<section class="grid" data-view="memory" aria-label="Memory and curator"><${Panel} title="Memory & Curator" span="s12"><${Waiting} store=${store} what="the run list" /><//></section>`;
  // Opening a recorded source keeps the version being read.
  const shown = version || (source ? last : '');
  return html`<section class="grid" data-view="memory" aria-label="Memory and curator">
    <${CuratorStrip} run=${run} key=${`curator-${run}`} />
    <${Browser} run=${run} version=${shown} key=${`browser-${run}`} />
    <${Disclosure} id="more-sources" title="Additional recorded sources" note="delivery by request, player records, configured curator journals and receipts, containers, episodes" open=${!!source}>${() => html`<${Records} section=${source} />`}<//></section>`;
}
