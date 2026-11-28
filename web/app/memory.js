// Memory: the one owner of version provenance. Every knowledge version of the run in one chain (delivered, adopted,
// refused, exported, superseded, published), what the selected one's delivery recorded, and a reader over it: the world
// state by key and anchor, the articles, every fact, and how the player used memory and what it claimed.
import {html, useEffect, useRef, useState, Panel, Pv, Segmented, Waiting, Insufficient, count, label, plural, pct, runName} from './ui.js';
import {store, runPath, useView, jumpToSeq, framePath, sessionOf, selectRun} from './data.js';
import {Replacements, RecordedKnowledge, Handoffs, clockText, conditionText} from './records.js';
import {CHAIN_STATUS, DELTA_BUCKETS, LEGACY_BUCKETS, deliveryWord, deliveryTone, deltaChips} from './continuity.js';

/* ---------------------------------------------------------------- the version chain */
function chainWord(row) {
  if (row.delivery_status === 'delivered') {
    const first = (row.deliveries || []).find(d => d.outcome === 'delivered');
    return `Delivered${first && first.seq !== null && first.seq !== undefined ? ` #${first.seq}` : ''}${first ? ` · ${deliveryWord(first.delivery_kind).toLowerCase()}` : ''}`;
  }
  return CHAIN_STATUS[row.delivery_status] || label(row.delivery_status || 'unknown');
}
function VersionChain({chain, selected}) {
  const rail = useRef(null);
  useEffect(() => {
    const box = rail.current, pick = box && box.querySelector('[aria-current="true"]');
    if (pick) box.scrollLeft = Math.max(0, pick.offsetLeft - box.clientWidth / 2);
  }, [selected, chain.length]);
  return html`<nav class="rail" ref=${rail} aria-label="Knowledge versions" id="versions">${chain.map(v => html`<a class="vpill ${v.status === 'available' ? '' : 'bad'}" key=${v.version}
    data-status=${v.delivery_status} href=${`#memory?version=${encodeURIComponent(v.version)}`} aria-current=${v.version === selected ? 'true' : null}>
    <b>${v.version}</b><span class="vstat">${chainWord(v)}</span>
    <span class="num sub">${v.status === 'available' ? `${plural(v.facts_count, 'fact')} · ${plural(v.articles_count, 'article')}` : v.exported ? label(v.status) : 'no exported file'}</span></a>`)}</nav>`;
}

/** What the selected version's delivery recorded: kind, outcome and the changes it stated, never a diff made here. */
function DeliveryPanel({data}) {
  const d = data.delivery;
  const row = (data.version_chain || []).find(v => v.version === data.selected_version);
  if (!d) {
    const why = row ? {exported_not_delivered: 'exported for the player, and no delivery of it is recorded in this run',
      superseded: 'superseded before it was delivered: a later delivery replaced it', published_only: 'published by the curator; no file of it was exported to this run'}[row.delivery_status] : null;
    return html`<div class="delivery none" id="delivery-diff"><span class="mtitle">${data.selected_version || 'No version'}</span>
      <p class="note">${why ? `${data.selected_version} was ${why}.` : `No delivery of ${data.selected_version} to the player is recorded in this run.`}</p></div>`;
  }
  const chips = deltaChips(d.delta_counts);
  const buckets = [...DELTA_BUCKETS, ...LEGACY_BUCKETS];
  const preview = [...(d.delta_preview || [])].sort((a, b) => buckets.indexOf(a.bucket) - buckets.indexOf(b.bucket));
  const summaryText = d.summary || '';
  const extraParts = [];
  if (d.leads_count !== null && d.leads_count !== undefined && !/\bleads?\b/.test(summaryText)) extraParts.push(plural(d.leads_count, 'lead'));
  if (d.index_count !== null && d.index_count !== undefined && !/\bindex\b/.test(summaryText)) extraParts.push(d.index_count === 1 ? '1 index entry' : `${d.index_count} index entries`);
  const headline = [summaryText || (extraParts.length ? '' : 'what changed is not recorded'), ...extraParts].filter(Boolean).join(' · ');
  return html`<div class="delivery" id="delivery-diff" data-kind=${d.delivery_kind}>
    <div class="cardrow"><span class=${`dkind ${deliveryTone(d.delivery_kind)}`}>${deliveryWord(d.delivery_kind)}</span><span class="mtitle">${d.knowledge_version || data.selected_version}</span>
      <span class="tag">${label(d.outcome || 'outcome unrecorded')}</span>${d.previous_version ? html`<span class="note">after ${d.previous_version}</span>` : null}
      ${d.seq !== null && d.seq !== undefined ? html`<button type="button" class="btn" id="delivery-jump" onClick=${() => jumpToSeq(d.seq)}>Jump to step #${d.seq}</button>` : null}</div>
    <p class="num">${headline}</p>
    ${chips.length ? html`<p class="chips" id="delta-counts">${chips.map(c => html`<span class="tag delta" data-bucket=${c.bucket}>${c.text}</span>`)}</p>`
      : d.delta_counts ? html`<p class="note">The delivery stated no changes.</p>` : html`<p class="note">This delivery's text records no change buckets.</p>`}
    ${preview.length ? html`<details id="delta-preview"><summary>${plural(preview.length, 'recorded change')} in the delivery</summary><ul class="difflist">${preview.map(p => html`<li class=${p.bucket}><b>${label(p.bucket)}</b> <span>${p.text || p.title || p.subject || p.id}</span>${p.state_key ? html` <span class="note mono">${p.state_key}</span>` : null}${p.reason ? html` <span class="note">${label(p.reason)}</span>` : null}</li>`)}</ul></details>` : null}
    <p class="note">${deliveryWord(d.delivery_kind)} recorded in the player's trace${d.actor ? ` · actor ${d.actor.slice(0, 8)}` : ''}${d.request_id ? ` · request ${d.request_id}` : ''}.</p></div>`;
}

/* ---------------------------------------------------------------- frames a fact cites */
/** Select another admission, and once its steps have loaded put the playhead on the recorded step and open Watch. */
let opening = null;
function openRunStep(anchor, setBusy, setFailed) {
  const session = sessionOf(anchor.session || anchor.run);
  if (!session) { setFailed(true); return; }
  if (opening) clearInterval(opening);
  setBusy(true); setFailed(false);
  selectRun(session);
  const end = Date.now() + 30000;
  opening = setInterval(() => {
    if (store.runId === session && store.steps.length) {
      clearInterval(opening); opening = null; setBusy(null);
      jumpToSeq(anchor.seq);
    } else if (Date.now() > end || store.runId !== session) { clearInterval(opening); opening = null; setBusy(null); setFailed(true); }
  }, 200);
}
/** A cited frame: one of this run opens Watch there; one of another admission names that run and opens it; one the
 *  viewer cannot serve says why. */
function FrameAnchor({anchor, thumb = false}) {
  const [busy, setBusy] = useState(null);
  const [failed, setFailed] = useState(null);
  if (!anchor) return html`<span class="note">no cited frame</span>`;
  const other = anchor.run !== undefined && anchor.session !== store.runId;
  if (!other) return html`<span class="fanchor">${thumb ? html`<img class="thumb" src=${framePath(store.runId, anchor.source_id)} alt=${`Frame at step ${anchor.seq}`} loading="lazy" />` : null}
    <button type="button" class="btn primary" data-jump-seq=${anchor.seq} onClick=${() => jumpToSeq(anchor.seq)}>Frame #${anchor.seq}</button></span>`;
  if (!anchor.available) return html`<span class="fanchor"><span class="note">frame of ${anchor.run || 'another run'} unavailable (${label(anchor.reason || 'unknown')})</span></span>`;
  const name = (store.runs || []).find(r => r.session === anchor.session);
  return html`<span class="fanchor cross" data-cross-run=${anchor.run}>${thumb ? html`<img class="thumb" src=${framePath(anchor.session || anchor.run, anchor.source_id)} alt=${`Frame of ${anchor.run}`} loading="lazy" />` : null}
    <span class="tag xrun" title="A frame another admission of this lineage recorded">${name ? runName(name) : anchor.run} · step #${anchor.seq ?? '—'}</span>
    <button type="button" class="btn" data-open-run=${anchor.run} disabled=${busy !== null || !sessionOf(anchor.session || anchor.run) || anchor.seq === null || anchor.seq === undefined} onClick=${() => openRunStep(anchor, setBusy, setFailed)}>${busy ? 'Opening…' : `Open in ${anchor.run}`}</button>
    ${failed ? html`<span class="state watch">its steps did not load in time</span>` : null}</span>`;
}

/* ---------------------------------------------------------------- reader */
const FACT_PAGE = 100;
const SCOPES = [['all', 'All'], ['world', 'This world'], ['game', 'Game-wide']];
const KINDS = ['state', 'observation', 'outcome', 'synthesis', 'inference'];
/** A position names an opaque session alias: its step numbers are that session's, not this run's frames. */
const seenText = p => (p ? `${p.session ? `session ${p.session} · ` : ''}actor ${p.actor ?? 'unrecorded'} · step ${p.step ?? p.last_step ?? 'unrecorded'}${clockText(p)}` : 'unrecorded');
/** The scope class: a world-bound record's world is never named, only that it is this run's world. */
const SCOPE_TEXT = {world: 'this world', game: 'game-wide'};
const FLAGS = [['unverified_branch', 'unverified branch'], ['needs_review', 'needs review'], ['condition_unverified', 'condition unverified']];

function Jump({anchor, position}) {
  return html`<p class="jump"><span class="note wrapany">${seenText(position)}</span> ${anchor ? html`<${FrameAnchor} anchor=${anchor} />` : html`<span class="note">no cited frame of this run</span>`}</p>`;
}

/** Scope, kind, lifecycle and review state as chips; tags search the version. */
function Chips({value, search}) {
  const kind = value.statement_kind || value.claim_kind;
  return html`<p class="cardrow" data-chips>
    ${value.scope ? html`<span class="tag scope-${value.scope}" data-scope=${value.scope}>${SCOPE_TEXT[value.scope] || value.scope} scope</span>` : html`<span class="tag">scope unrecorded</span>`}
    ${Object.entries(value.scope_axes || {}).map(([axis, v]) => html`<span class="tag" data-axis=${axis}>${label(axis)}: ${v}</span>`)}
    ${kind ? html`<span class="tag" data-kind>${label(kind)}</span>` : null}${value.evidence_basis ? html`<span class="tag" data-evidence>${value.evidence_basis}</span>` : null}
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

function Citations({fact, clocks}) {
  const ids = fact.citation_source_ids || [];
  if (!ids.length) return null;
  return html`<h4>Cited frames</h4><ul class="difflist" data-citations>${ids.map((id, i) => {
    const at = (fact.citation_anchors || [])[i];
    return html`<li class="wrapany">${at ? html`<${FrameAnchor} anchor=${at} />` : html`<span class="note">Frame unavailable</span>`} <span class="mono">${id}</span>${id === fact.depiction_source_id ? ' · depiction' : ''}${clocks?.[id] ? ` · ${clocks[id]}` : ''}</li>`;
  })}</ul>${fact.citation_source_ids_omitted ? html`<p class="note">${fact.citation_source_ids_omitted} more not shown.</p>` : null}`;
}

function ArticleView({article, choose, search, history}) {
  return html`<article class="reading" data-reading=${article.id} tabindex="-1"><h3 class="rtitle">${article.title || article.id}</h3><${Chips} value=${article} search=${search} /><p class="lead">${article.lead}</p>
    ${article.body.map(part => html`<p>${part.text}${part.facts.length ? html` <span class="refs">${part.facts.map(id => html`<button type="button" class="factpill" onClick=${() => choose(id)}>${id}</button>`)}</span>` : null}</p>`)}
    ${article.body_omitted ? html`<p class="note">${article.body_omitted} more claims not shown.</p>` : null}
    <${Graph} value=${article} choose=${choose} /><${Replacements} history=${history} id=${article.id} />
    <h4>Last confirmed</h4><${Jump} anchor=${article.anchor} position=${article.last_confirmed} />
    <p class="note mono wrapany">${article.revision || article.id}</p></article>`;
}
function FactView({fact, choose, search, clocks, history}) {
  const when = conditionText(fact.when);
  const anchor = typeof fact.anchor === 'string' ? fact.anchor : null;
  const frame = fact.frame_anchor || (anchor ? null : fact.anchor);
  return html`<article class="reading" data-reading=${fact.id} tabindex="-1"><h3 class="rtitle">${fact.subject || fact.id}</h3><${Chips} value=${fact} search=${search} />
    <p class="lead">${fact.text}</p>${when ? html`<p class="note wrapany" data-when>When: ${when}</p>` : null}
    ${fact.state_key ? html`<p class="note wrapany">State key: ${fact.state_key}</p>` : null}
    ${anchor ? html`<p class="note wrapany">Anchor: <button type="button" class="factpill" onClick=${() => choose(anchor)}>${fact.anchor_display || anchor}</button></p>` : null}
    ${fact.depiction_source_id && !fact.citation_source_ids?.includes(fact.depiction_source_id) ? html`<p class="note wrapany">Depiction: ${fact.depiction_source_id}</p>` : null}
    ${(fact.cited_by_articles || []).length ? html`<p class="note">Cited by ${fact.cited_by_articles.map(id => html`<button type="button" class="factpill" onClick=${() => choose(id)}>${id}</button>`)}</p>` : null}
    <${Graph} value=${fact} choose=${choose} /><${Replacements} history=${history} id=${fact.id} /><${Citations} fact=${fact} clocks=${clocks} />
    <h4>Seen</h4><${Jump} anchor=${frame} position=${fact.seen} /><p class="note mono wrapany">${fact.id}</p></article>`;
}

/** The world state: readings grouped by what they are the state of, and the places facts are anchored to. */
function StateView({data, open}) {
  const groups = data.state_groups || [], places = data.anchor_groups || [];
  if (!groups.length && !places.length) return html`<${Insufficient}>No fact of this version states the world's state by key or anchor.<//>`;
  return html`<div class="stategrid" id="kb-state">
    <div class="stategroups">${groups.map(g => html`<article class="stategroup" data-state-key=${g.state_key}>
      <header><b class="mono">${g.state_key}</b><span class="note num">${plural(g.count, 'reading')}${g.facts_omitted ? ` · ${g.facts_omitted} not shown` : ''}</span></header>
      ${g.facts.map((f, i) => html`<div class="reading-row ${i ? 'older' : 'current'}"><span class="tag">${i ? 'also' : 'current'}</span><button type="button" class="link" data-open-fact=${f.id} onClick=${() => open(f.id)}>${f.text || f.subject || f.id}</button>
        ${f.statement_kind ? html`<span class="tag" data-kind>${label(f.statement_kind)}</span>` : null}${f.when ? html`<span class="note">When: ${conditionText(f.when)}</span>` : null}
        ${f.frame_anchor ? html`<${FrameAnchor} anchor=${f.frame_anchor} thumb=${i === 0} />` : null}</div>`)}
      ${Object.keys(g.replaced || {}).length ? html`<p class="chips replaced" data-replaced>Replaced: ${Object.entries(g.replaced).map(([from, r]) => html`<span class="link-row"><span class="mono">${from}</span> (${label(r.reason || 'replaced')}) → ${(r.by || []).map(id => html`<button type="button" class="factpill" onClick=${() => open(id)}>${id}</button>`)}</span>`)}</p>` : null}
    </article>`)}</div>
    ${places.length ? html`<aside class="anchorgroups" id="kb-anchors"><h3>Anchors</h3><ul>${places.map(p => html`<li data-anchor-key=${p.anchor}><b>${p.anchor_display || p.anchor}</b> <span class="note num">${plural(p.fact_count, 'fact')}</span>
      ${p.state_keys.length ? html`<span class="chips">${p.state_keys.map(k => html`<span class="tag mono">${k}</span>`)}</span>` : null}</li>`)}</ul></aside>` : null}</div>`;
}

/** When coverage, and flagged records, of the whole version. */
function Quality({q}) {
  if (!q) return null;
  const flags = [['stale', q.stale_count], ['contested', q.contested_count], ['unverified', q.unverified_count], ['needs review', q.needs_review_count]];
  return html`<span class="quality num" id="kb-quality" title="Across the whole version, before any filter">${plural(q.facts_count, 'fact')} · ${plural(q.state_count, 'state key')} · when ${q.when_coverage === null ? '—' : pct(q.when_coverage)}
    ${flags.map(([name, n]) => html` · <span class=${n ? 'flagged' : ''}>${n} ${name}</span>`)}</span>`;
}

/** The six most used tags on one line, the rest behind a count. A tag searches the version. */
function TagBar({data, search}) {
  const tags = data.tag_counts || [];
  if (!tags.length) return null;
  const top = tags.slice(0, 6), rest = tags.slice(6);
  const more = rest.length + (data.tag_counts_omitted || 0);
  const pill = t => html`<button type="button" class="factpill" data-tag-count=${t.tag} onClick=${() => search(t.tag)}>#${t.tag} <b class="num">${t.count}</b></button>`;
  return html`<div class="tagbar" id="kb-tags">${top.map(pill)}${more ? html`<details class="moretags"><summary>+${more} tags</summary><div class="tagpop">${rest.map(pill)}${data.tag_counts_omitted ? html`<span class="note">${data.tag_counts_omitted} more not listed</span>` : null}</div></details>` : null}</div>`;
}

const VIEWS = [['state', 'World State'], ['articles', 'Articles'], ['facts', 'All Facts'], ['usage', 'Usage & Claims']];

function Reader({run, version, section}) {
  const [view, setView] = useState(VIEWS.some(([id]) => id === section) ? section : null);
  const [query, setQuery] = useState('');
  const [needle, setNeedle] = useState('');
  const [scope, setScope] = useState('all');
  const [kind, setKind] = useState('');
  const [after, setAfter] = useState(0);
  const [pick, setPick] = useState(null);      // the entry ID on the reading side
  const [focus, setFocus] = useState(false);
  useEffect(() => { if (VIEWS.some(([id]) => id === section)) setView(section); }, [section]);
  useEffect(() => {   // a new search reads its first match
    if (query.trim() === needle) return undefined;
    const timer = setTimeout(() => { setNeedle(query.trim()); setAfter(0); setPick(null); }, 250);
    return () => clearTimeout(timer);
  }, [query, needle]);
  const params = new URLSearchParams();
  if (version) params.set('version', version);
  if (needle) params.set('q', needle);
  params.set('scope', scope);
  if (kind) params.set('kind', kind);
  params.set('after', String(after));
  params.set('limit', String(FACT_PAGE));
  const path = runPath(run, `delivered-knowledge?${params.toString()}`);
  const live = store.summary && store.summary.live;
  const result = useView(path, live ? 5000 : 0);
  // A new search or page keeps the last listing on screen until its own arrives, so the search box keeps its focus.
  const held = useRef(null);
  if (result.data) held.current = result.data;
  const error = result.error, data = result.data || (error ? null : held.current);
  // The view a version opens on: never an empty one. Articles stay one click away even when there are none.
  const q = data && data.quality;
  const fallback = !q ? 'facts' : q.default_view === 'state' && !(data.state_groups || []).length && !(data.anchor_groups || []).length ? 'facts' : q.default_view;
  const shown = view || fallback;
  // A picked entry may be on another page or under another filter: it is found by its exact ID.
  const onPage = data && (data.articles.find(a => a.id === pick) || data.facts.items.find(f => f.id === pick));
  const lookup = useView(pick && data && !onPage ? runPath(run, `delivered-knowledge?version=${encodeURIComponent(version || '')}&q=${encodeURIComponent(pick.slice(0, 200))}&limit=${FACT_PAGE}`) : null, 0);
  const pickedData = onPage ? data : lookup.data;
  const readings = !onPage && lookup.data ? lookup.data.facts.items.filter(f => f.state_key === pick) : [];
  const found = onPage || (lookup.data && (lookup.data.articles.find(a => a.id === pick) || lookup.data.facts.items.find(f => f.id === pick))) || readings[0] || null;
  const choose = id => { setPick(id); setFocus(true); };
  const open = id => { setView('facts'); choose(id); };
  useEffect(() => {
    if (!focus || !found) return;
    const target = document.querySelector('[data-reading]');
    if (target) target.focus();
    setFocus(false);
  }, [focus, found]);
  const rows = !data ? [] : shown === 'articles' ? data.articles : data.facts.items;
  // The first entry is read until the owner picks one; a pick made meanwhile stands. Never from a held listing.
  useEffect(() => { if (result.data && rows.length && !pick && (shown === 'articles' || shown === 'facts')) { const first = rows[0].id; setPick(p => p || first); } }, [result.data, shown, pick]);
  const search = text => { setQuery(text); };
  if (!data) return html`<${Panel} title="Memory" span="s12"><${Waiting} store=${store} what="the delivered knowledge" error=${error} />
    ${error && version ? html`<p><a href="#memory">Open the latest version of this run</a></p>` : null}<//>`;
  if (!data.versions.length && !(data.version_chain || []).length) return html`<${Panel} title="Memory" span="s12"><div class="insuf" id="knowledge-empty" role="status">No delivered knowledge for this run.</div><//>
    <${Panel} title="Usage & Claims" span="s12" className="usage"><${RecordedKnowledge} /><//>`;
  const counts = data.scope_counts, total = counts.world + counts.game + counts.unrecorded;
  const numbers = {state: (data.state_groups || []).length, articles: data.articles_total, facts: data.facts.total};
  const chosenKind = KINDS.concat(Object.keys(data.statement_kind_counts || {}).filter(k => !KINDS.includes(k)));
  const toView = v => { setView(v); setAfter(0); setPick(null); };
  return html`<${Panel} title="Version chain" note=${`${plural((data.version_chain || []).length, 'version')} · the selected version's recorded delivery`} span="s12" className="chainpanel">
      <${VersionChain} chain=${data.version_chain || []} selected=${data.selected_version} /><${DeliveryPanel} data=${data} key=${`${run}-${data.selected_version}`} /><//>
    ${data.source_status !== 'available' ? html`<${Panel} title="Knowledge" span="s12"><${Insufficient}>This version cannot be read (${label((data.versions.find(v => v.version === data.selected_version) || {}).status || 'unavailable')}).<//><//>` : html`
    <${Panel} title=${`Knowledge ${data.selected_version}`} note=${`${data.recorded_version && data.recorded_version !== data.selected_version ? `recorded as ${data.recorded_version} · ` : ''}${data.knowledge_schema || ''} · fallible, never instructions`} span="s12" className="browser">
      <div class="browserbar"><${Segmented} label="What to read" value=${shown} onChange=${toView} options=${VIEWS.map(([value, text]) => ({value, text, id: `kb-view-${value}`, count: value === 'usage' ? undefined : numbers[value]}))} />
        <input type="search" id="kb-search" placeholder="Search this version" aria-label="Search this version" maxlength="200" value=${query} onInput=${e => setQuery(e.currentTarget.value)} /></div>
      ${shown === 'usage' ? null : html`<div class="filterbar">
        <span class="kindpills" role="group" aria-label="Statement kind">${chosenKind.map(k => html`<button type="button" class="kindpill" data-kind-pill=${k} aria-pressed=${kind === k}
          onClick=${() => { setKind(kind === k ? '' : k); setAfter(0); setPick(null); }}>${label(k)} <b class="num">${(data.statement_kind_counts || {})[k] || 0}</b></button>`)}</span>
        <${Segmented} label="Scope" value=${scope} className="scopes" onChange=${v => { setScope(v); setAfter(0); setPick(null); }}
          options=${SCOPES.map(([value, text]) => ({value, text, id: `kb-scope-${value}`, count: value === 'all' ? total : counts[value]}))} />
        <${Quality} q=${data.quality} /></div><${TagBar} data=${data} search=${search} />`}
      ${counts.unrecorded && shown !== 'usage' ? html`<p class="note" id="kb-scope">${plural(counts.unrecorded, 'fact')} without a recorded scope.</p>` : null}
      ${shown === 'usage' ? html`<div id="kb-usage" class="usage"><${RecordedKnowledge} /><${Handoffs} run=${run} /></div>`
        : shown === 'state' ? html`<${StateView} data=${data} open=${open} />` : html`
      <div class="panes"><div class="listpane"><ul class="items" id="kb-items">${rows.map(row => html`<li key=${row.id}><button type="button" class="item" aria-pressed=${pick === row.id} onClick=${() => setPick(row.id)}>
            <b>${row.title || row.subject || row.id}</b><span class="note">${row.lead || row.text}</span></button></li>`)}
          ${rows.length ? null : html`<li class="note pad" role="status" id="kb-none">${needle || kind ? 'Nothing matches.' : shown === 'articles' ? 'This version has no articles: its knowledge is facts only.' : 'This version has no such facts.'}</li>`}</ul>
          ${shown === 'articles' && data.articles_omitted ? html`<p class="note">${data.articles_omitted} more articles not shown; search to narrow.</p>` : null}
          ${shown === 'facts' && (after > 0 || data.facts.next !== null) ? html`<p class="pager"><button type="button" class="btn" disabled=${after === 0} onClick=${() => { setPick(null); setAfter(Math.max(0, after - FACT_PAGE)); }}>Previous</button>
            <span class="note num">${count(after + 1)}–${count(after + rows.length)} of ${count(data.facts.total)}</span><button type="button" class="btn" disabled=${data.facts.next === null} onClick=${() => { setPick(null); setAfter(data.facts.next); }}>Next</button></p>` : null}</div>
        <div class="readpane">${readings.length > 1 ? html`<p class="chips">${readings.map(f => html`<button type="button" class="factpill" onClick=${() => choose(f.id)}>${f.id}</button>`)}</p>` : null}
          ${found ? (found.body ? html`<${ArticleView} article=${found} choose=${choose} search=${search} history=${pickedData.history} />` : html`<${FactView} fact=${found} choose=${choose} search=${search} clocks=${pickedData.frame_clocks} history=${pickedData.history} />`)
          : pick && rows.length ? html`<p class="note" role="status">${lookup.data ? `${pick} is not in this version.` : 'Finding the entry…'}</p>` : html`<p class="note">Choose an entry to read it.</p>`}</div></div>`}<//>`}`;
}

/* ---------------------------------------------------------------- the tab */
export function MemoryTab({section, version}) {
  const run = store.runId;
  return html`<section class="grid" data-view="memory" aria-label="Memory">
    ${run ? html`<${Reader} run=${run} version=${version} section=${section} key=${`reader-${run}`} />` : html`<${Panel} title="Memory" span="s12"><${Waiting} store=${store} what="the run list" /><//>`}</section>`;
}
