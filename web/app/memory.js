// Memory & Curator: what the curator is doing and has spent, every knowledge version exported for the player and whether
// its delivery is recorded, and a reader over one version whose citations open Watch at the frame they name.
import {html, useEffect, useRef, useState, Panel, Pv, Segmented, Disclosure, Waiting, Insufficient, count, label, plural} from './ui.js';
import {store, runPath, useView, jumpToSeq} from './data.js';
import {CuratorRecords, Records, RunnerDetail, RUNNER_STATES, SOURCES, isCuratorSource, known, useFrame} from './records.js';

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
  const event = data && data.events.find(e => e.type === 'knowledge-delivery' && e.kind === 'update' && e.version === version && e.outcome === 'delivered');
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
/** A position names an opaque session alias: its step numbers are that session's, not this run's frames. */
const seenText = p => (p ? `${p.session ? `session ${p.session} · ` : ''}actor ${p.actor ?? 'unrecorded'} · step ${p.step ?? p.last_step ?? 'unrecorded'}` : 'unrecorded');
/** The scope class: a world-bound record's world is never named, only that it is this run's world. */
const SCOPE_TEXT = {world: 'this world', game: 'game-wide'};
const FLAGS = [['unverified_branch', 'unverified branch'], ['needs_review', 'needs review'], ['condition_unverified', 'condition unverified']];

function Jump({anchor, position}) {
  return html`<p class="jump"><span class="note">${seenText(position)}</span> ${anchor ? html`<button type="button" class="btn primary" data-jump-seq=${anchor.seq} onClick=${() => jumpToSeq(anchor.seq)}>Jump to frame #${anchor.seq}</button>`
    : html`<span class="note">no cited frame of this run</span>`}</p>`;
}

/** Scope, kind, lifecycle and review state as chips; tags search the version. */
function Chips({value, search}) {
  return html`<p class="cardrow" data-chips>
    ${value.scope ? html`<span class="tag scope-${value.scope}" data-scope=${value.scope}>${SCOPE_TEXT[value.scope] || value.scope} scope</span>` : html`<span class="tag">scope unrecorded</span>`}
    ${Object.entries(value.scope_axes || {}).map(([axis, v]) => html`<span class="tag" data-axis=${axis}>${label(axis)}: ${v}</span>`)}
    ${value.claim_kind ? html`<span class="tag" data-kind>${label(value.claim_kind)}</span>` : null}${value.evidence_basis ? html`<span class="tag" data-evidence>${value.evidence_basis}</span>` : null}
    ${value.lifecycle_state === 'contested' ? html`<span class="state watch" data-flag="contested">contested</span>` : value.lifecycle_state ? html`<span class="tag">${value.lifecycle_state}</span>` : null}
    ${FLAGS.filter(([name]) => value[name]).map(([name, text]) => html`<span class="state watch" data-flag=${name}>${text}</span>`)}
    ${(value.tags || []).map(tag => html`<button type="button" class="factpill" data-tag=${tag} onClick=${() => search(tag)}>#${tag}</button>`)}</p>`;
}

/** Typed links out and back, opened on the reading side by their exact ID; stale, shadowing and contradicting records. */
function Graph({value, choose}) {
  const pill = id => html`<button type="button" class="factpill" onClick=${() => choose(id)}>${id}</button>`;
  const links = value.links || [], back = value.backlinks || [];
  return html`${links.length ? html`<h4>Links</h4><p class="chips" data-links>${links.map(l => html`<span class="link-row">${label(l.rel)} ${pill(l.target)}</span>`)}</p>` : null}
    ${back.length ? html`<h4>Linked from</h4><p class="chips" data-backlinks>${back.map(l => html`<span class="link-row">${pill(l.source)} ${label(l.rel)}</span>`)}</p>` : null}
    ${(value.contradicted_by || []).length ? html`<p class="note" data-contradicted>Contradicted by ${value.contradicted_by.map(pill)}</p>` : null}
    ${(value.shadowed_by || []).length ? html`<p class="note" data-shadowed>Narrowed by ${value.shadowed_by.map(pill)}</p>` : null}
    ${(value.stale_citations || []).length ? html`<p class="note" data-stale>Stale citations: ${value.stale_citations.join(', ')}</p>` : null}`;
}

/** A fact's cited frames: one of this run that the frame route serves opens Watch there; any other (another session's,
 * or one whose PNG is missing or not the recorded one) is listed without a frame. */
function Citations({fact}) {
  const ids = fact.citation_source_ids || [];
  if (!ids.length) return null;
  return html`<h4>Cited frames</h4><ul class="difflist" data-citations>${ids.map((id, i) => {
    const at = (fact.citation_anchors || [])[i];
    return html`<li class="wrapany">${at ? html`<button type="button" class="btn" data-citation-seq=${at.seq} onClick=${() => jumpToSeq(at.seq)}>Frame #${at.seq}</button>` : html`<span class="note">Frame unavailable</span>`} <span class="mono">${id}</span></li>`;
  })}</ul>${fact.citation_source_ids_omitted ? html`<p class="note">${fact.citation_source_ids_omitted} more not shown.</p>` : null}`;
}

function ArticleView({article, choose, search}) {
  return html`<article class="reading" data-reading=${article.id} tabindex="-1"><h3 class="rtitle">${article.title || article.id}</h3><${Chips} value=${article} search=${search} /><p class="lead">${article.lead}</p>
    ${article.body.map(part => html`<p>${part.text}${part.facts.length ? html` <span class="refs">${part.facts.map(id => html`<button type="button" class="factpill" onClick=${() => choose(id)}>${id}</button>`)}</span>` : null}</p>`)}
    ${article.body_omitted ? html`<p class="note">${article.body_omitted} more claims not shown.</p>` : null}
    <${Graph} value=${article} choose=${choose} />
    <h4>Last confirmed</h4><${Jump} anchor=${article.anchor} position=${article.last_confirmed} />
    <p class="note mono wrapany">${article.revision || article.id}</p></article>`;
}
function FactView({fact, choose, search}) {
  return html`<article class="reading" data-reading=${fact.id} tabindex="-1"><h3 class="rtitle">${fact.subject || fact.id}</h3><${Chips} value=${fact} search=${search} />
    <p class="lead">${fact.text}</p>${fact.when ? html`<p class="note" data-when>When: ${fact.when.note}${Object.entries(fact.when.requires || {}).map(([k, v]) => ` · ${label(k)}: ${v}`).join('')}</p>` : null}
    ${(fact.cited_by_articles || []).length ? html`<p class="note">Cited by ${fact.cited_by_articles.map(id => html`<button type="button" class="factpill" onClick=${() => choose(id)}>${id}</button>`)}</p>` : null}
    <${Graph} value=${fact} choose=${choose} /><${Citations} fact=${fact} />
    <h4>Seen</h4><${Jump} anchor=${fact.anchor} position=${fact.seen} /><p class="note mono wrapany">${fact.id}</p></article>`;
}

/** The tag and claim-kind view counted from the delivered records; a tag searches the version. */
function Summary({data, search}) {
  const kinds = Object.entries(data.claim_kind_counts || {}), tags = data.tag_counts || [];
  if (!kinds.length && !tags.length) return null;
  return html`<div class="cardrow" id="kb-summary">${kinds.map(([kind, n]) => html`<span class="tag" data-kind-count=${kind}>${label(kind)} <b class="num">${n}</b></span>`)}
    ${tags.map(t => html`<button type="button" class="factpill" data-tag-count=${t.tag} onClick=${() => search(t.tag)}>#${t.tag} <b class="num">${t.count}</b></button>`)}
    ${data.tag_counts_omitted ? html`<span class="note">${data.tag_counts_omitted} more tags</span>` : null}</div>`;
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
  const search = text => { setQuery(text); };
  if (!data) return html`<${Panel} title="Knowledge" span="s12"><${Waiting} store=${store} what="the delivered knowledge" error=${error} />
    ${error && version ? html`<p><a href="#memory">Open the latest version of this run</a></p>` : null}<//>`;
  if (!data.versions.length) return html`<${Panel} title="Knowledge" span="s12"><div class="insuf" id="knowledge-empty" role="status">No delivered knowledge for this run.</div><//>`;
  const counts = data.scope_counts, total = counts.world + counts.game + counts.unrecorded;
  const numbers = {articles: data.articles_total, world: counts.world, game: counts.game, all: total};
  return html`<${Panel} title="Knowledge versions" note=${plural(data.versions.length, 'version')} span="s12"><${VersionRail} versions=${data.versions} selected=${data.selected_version} />
      <${DeliveryDiff} run=${run} version=${data.selected_version} delivery=${data.delivery} choose=${choose} key=${`${run}-${data.selected_version}`} /><//>
    ${data.source_status !== 'available' ? html`<${Panel} title="Knowledge" span="s12"><${Insufficient}>This version cannot be read (${label((data.versions.find(v => v.version === data.selected_version) || {}).status || 'unavailable')}).<//><//>` : html`
    <${Panel} title="Knowledge" note=${`${data.selected_version}${data.recorded_version && data.recorded_version !== data.selected_version ? ` (${data.recorded_version})` : ''} · ${deliveryText(data.selected_version, data)} · fallible, never instructions`} span="s12" className="browser">
      <div class="browserbar"><${Segmented} label="What to browse" value=${mode} onChange=${v => { setMode(v); setAfter(0); setPick(null); }} options=${MODES.map(([value, text]) => ({value, text, id: `kb-${value}`, count: numbers[value]}))} />
        <input type="search" id="kb-search" placeholder="Search this version" aria-label="Search this version" maxlength="200" value=${query} onInput=${e => setQuery(e.currentTarget.value)} /></div>
      <${Summary} data=${data} search=${search} />
      ${counts.unrecorded ? html`<p class="note" id="kb-scope">${plural(counts.unrecorded, 'fact')} without a recorded scope.</p>` : null}
      <div class="panes"><div class="listpane"><ul class="items" id="kb-items">${rows.map(row => html`<li key=${row.id}><button type="button" class="item" aria-pressed=${pick === row.id} onClick=${() => setPick(row.id)}>
            <b>${row.title || row.subject || row.id}</b><span class="note">${row.lead || row.text}</span></button></li>`)}
          ${rows.length ? null : html`<li class="note pad" role="status" id="kb-none">${needle ? 'Nothing matches.' : mode === 'articles' ? 'This version has no articles.' : 'This version has no such facts.'}</li>`}</ul>
          ${mode === 'articles' && data.articles_omitted ? html`<p class="note">${data.articles_omitted} more articles not shown; search to narrow.</p>` : null}
          ${mode !== 'articles' && (after > 0 || data.facts.next !== null) ? html`<p class="pager"><button type="button" class="btn" disabled=${after === 0} onClick=${() => { setPick(null); setAfter(Math.max(0, after - FACT_PAGE)); }}>Previous</button>
            <span class="note num">${count(after + 1)}–${count(after + rows.length)} of ${count(data.facts.total)}</span><button type="button" class="btn" disabled=${data.facts.next === null} onClick=${() => { setPick(null); setAfter(data.facts.next); }}>Next</button></p>` : null}</div>
        <div class="readpane">${found ? (found.body ? html`<${ArticleView} article=${found} choose=${choose} search=${search} />` : html`<${FactView} fact=${found} choose=${choose} search=${search} />`)
          : pick && rows.length ? html`<p class="note" role="status">${lookup.data ? `${pick} is not in this version.` : 'Finding the entry…'}</p>` : html`<p class="note">Choose an entry to read it.</p>`}</div></div><//>`}`;
}

/* ---------------------------------------------------------------- the tab */
export function MemoryTab({section}) {
  const run = store.runId;
  const source = SOURCES.some(s => s[0] === section) ? section : '';
  const curatorSource = isCuratorSource(source);
  const version = !source && section ? section : '';
  const [last, setLast] = useState('');
  useEffect(() => { if (version) setLast(version); }, [version]);
  useEffect(() => { setLast(''); }, [run]);
  // Opening a recorded source keeps the version being read.
  const shown = version || (source ? last : '');
  return html`<section class="grid" data-view="memory" aria-label="Memory and curator">
    ${run ? html`<${CuratorStrip} run=${run} key=${`curator-${run}`} />` : html`<${Panel} title="Memory & Curator" span="s12"><${Waiting} store=${store} what="the run list" /><//>`}
    <${CuratorRecords} section=${curatorSource ? source : ''} />
    ${run ? html`<${Browser} run=${run} version=${shown} key=${`browser-${run}`} />
    <${Disclosure} id="more-sources" title="Additional recorded sources" note="delivery by request, player records, containers, episodes" open=${!!source && !curatorSource}>${() => html`<${Records} section=${curatorSource ? '' : source} />`}<//>` : null}</section>`;
}
