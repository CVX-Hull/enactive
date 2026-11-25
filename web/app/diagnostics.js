// Diagnostics: one run's money, context, routing and custody, then the sections that drill into them.
import {html, useState, useEffect, useMemo, useRef, Panel, Pv, Unvalidated, Waiting, Table, Insufficient, Disclosure, SubNav, fmtH, fmtMoney, pct, trim, bytes, kilo, count, plural, mmss, shortId, scalar, label, compact} from './ui.js';
import {store, useView, runPath, framePath, runStart, jumpToSeq} from './data.js';
import {Chart, contextOption, spendOption, transitionsOption} from './charts.js';
import {PauseConditions, GameState, findingText} from './supervise.js';
import {RequestContext} from './inspector.js';
import {Explore, Compare} from './crossrun.js';
import {Changes, Failures, Components} from './improve.js';

const TOOL_LABELS = {computer_input: 'input', computer_observe: 'observe', computer_result: 'collect result', player_source: 're-read frame',
  player_memory_append: 'memory write', player_memory_query: 'memory query', player_memory_read: 'memory read', player_memory_context: 'memory bundle',
  player_knowledge_read: 'knowledge read', player_knowledge_query: 'knowledge query', player_hint: 'hint',
  player_program_save: 'program save', player_program_run: 'program run', player_handoff: 'handoff', player_finish: 'finish'};
export const toolLabel = t => TOOL_LABELS[t] || t;

/* ---------------------------------------------------------------- cards */
function Card({id, title, big, sub, chips, children}) {
  return html`<section class="kpi panel interp" id=${id} aria-label=${title}><h3>${title}</h3><div class="big num">${big}</div>${sub ? html`<div class="sub num">${sub}</div>` : null}
    ${chips ? html`<div class="chips">${chips}</div>` : null}${children}</section>`;
}
const money2 = text => (text === null || text === undefined ? '—' : `$${Number(text).toFixed(2)}`);

/* Boundary grooming runs after an admission ends and writes outside its package, so only a receipt the operator attached states its spend. */
const GROOMING = {not_configured: 'recorded outside admission', other_run: 'recorded outside admission', missing: 'receipt missing', unreadable: 'receipt unreadable',
  too_large: 'receipt unreadable', empty: 'receipt unreadable', malformed: 'receipt unreadable', unsupported: 'receipt unsupported'};

/** The parts of the loop's spend, each on the basis it was counted: what the provider reported for player and recall, and
 *  what the curator's proxy charged, which holds a reservation where the actual cost is unknown. A part that states no
 *  amount is never zero, and their sum is a partial one unless every part is there and closed. */
export function spendParts(s) {
  const host = s.host_telemetry, curator = s.curator_spend, grooming = s.boundary_grooming, receipt = s.custodian_receipt && s.custodian_receipt.accounting;
  const traced = !!host && host.reported_cost_usd !== null;
  const counted = host && host.unpriced_requests !== null ? host : receipt;
  const unpriced = {player: counted ? counted.unpriced_requests || 0 : 0, recall: counted ? counted.unpriced_recall_requests || 0 : 0};
  const open = unpriced.player + unpriced.recall;
  const settled = host && host.spend_complete !== null ? host.spend_complete : receipt ? true : null;
  const player = {usd: traced ? host.reported_cost_usd : receipt ? receipt.reported_usd : null, closed: settled === true && !open};
  const live = {usd: curator ? curator.spent_usd : null, closed: !!curator && curator.spend_complete};
  const boundary = {usd: grooming ? grooming.spent_usd : null, closed: !!grooming && grooming.spend_complete === true};
  const parts = [player, live, boundary];
  const present = parts.filter(p => p.usd !== null);
  return {player, live, boundary, unpriced, open, settled, source: traced ? 'host trace' : 'custodian receipt',
    // Without player and recall the rest is not a spend of the loop; each part then stands alone.
    sum: player.usd === null ? null : present.reduce((a, p) => a + Number(p.usd), 0),
    partial: parts.some(p => p.usd === null || !p.closed), any: present.length > 0};
}

function SpendCard({s}) {
  const p = spendParts(s), curator = s.curator_spend, grooming = s.boundary_grooming;
  const reserve = s.host_telemetry?.spend_reserve_reached;
  const limit = s.facts && typeof s.facts.spend_allowance_usd === 'number' ? s.facts.spend_allowance_usd : null;
  const reported = p.player.usd, curated = p.live.usd;
  const included = [reported !== null && 'player + recall', curated !== null && 'live curator', p.boundary.usd !== null && 'boundary grooming'].filter(Boolean).join(' + ');
  const groomed = p.boundary.usd !== null ? `${money2(p.boundary.usd)} · ${grooming.status}${p.boundary.closed ? '' : ' · unsettled'}`
    : grooming && grooming.source_status === 'available' ? `unavailable · ${grooming.status}` : GROOMING[grooming ? grooming.source_status : 'not_configured'] || 'unavailable';
  return html`<${Card} id="kpi-spend" title="Loop spend" big=${p.sum === null ? '—' : `$${p.sum.toFixed(2)}`} sub=${p.sum === null ? 'no provider-reported cost, so no combined figure' : included}
    chips=${html`${p.any && p.partial ? html`<span class="state watch" id="spend-partial" title="Not the whole loop: a part below is unavailable, not attached or not closed">partial</span>` : null}
      ${reported === null ? null : html`<${Pv} source="recorded" detail=${p.source} />`}
      ${p.settled === false ? html`<span class="state watch" title="An actor has not settled or has no trace, its settlement differs from the events read, or a request has no provider price">player open</span>` : null}
      ${curator && !curator.spend_complete ? html`<span class="state watch">curator incomplete</span>` : null}
      ${p.open ? html`<span class="state watch">unpriced</span>` : null}`}>
    <dl class="kv"><dt>${p.open ? 'Player + recall subtotal' : 'Player + recall'} <small>provider-reported</small></dt><dd title=${reported === null ? '' : `$${reported}`} data-exact=${reported}>${reported === null ? 'Unavailable' : money2(reported)}${reported !== null && limit !== null ? ` of ${fmtMoney(limit)}` : ''}</dd></dl>
    ${reported !== null && limit ? html`<progress class="meterbar" max=${limit} value=${Number(reported)} aria-label="Player spend against its limit"></progress>` : null}
    <dl class="kv">${p.open ? html`<dt>${s.live ? 'Unpriced or in flight' : 'Unpriced attempts'}</dt><dd>${p.unpriced.player} player · ${p.unpriced.recall} recall</dd>` : null}
      ${reserve?.count > 0 ? html`<dt>Spend reserve</dt><dd>Reached ${plural(reserve.count, 'time')}${reserve.latest ? ` · latest ${money2(reserve.latest.spent_usd)} spent of ${money2(reserve.latest.spend_limit_usd)} · ${money2(reserve.latest.finish_reserve_usd)} finish reserve` : ''}</dd>` : null}
      <dt>Live curator <small>proxy-accounted</small></dt><dd title=${curated === null ? '' : `$${curated}; a charge is the reservation where the actual cost is unknown`} data-exact=${curated}>${!curator ? 'no session recorded' : `${curated === null ? 'Unavailable' : money2(curated)} · ${curator.sessions_settled}/${curator.sessions_total} settled`}</dd>
      <dt>Boundary grooming <small>proxy-accounted</small></dt><dd id="spend-grooming" title=${p.boundary.usd === null ? '' : `$${p.boundary.usd}`} data-exact=${p.boundary.usd}>${groomed}</dd>
      <dt>Configured-rate estimate</dt><dd>${fmtMoney(s.dollars)}</dd></dl><//>`;
}

function ContextCard({s}) {
  const host = s.host_telemetry;
  if (!host) return html`<${Card} id="kpi-context" title="Context and cache" big="—" sub="no host trace for this run" />`;
  const t = host.token_summary, cuts = host.context_cuts;
  const results = Object.entries(cuts.by_result || {}).filter(([, n]) => n > 0).map(([result, n]) => `${count(n)} ${label(result)}`);
  return html`<${Card} id="kpi-context" title="Context and cache" big=${`${kilo(t.p50_prompt_tokens)} tok`} sub=${`p50 prompt · max ${kilo(t.max_prompt_tokens)}`} chips=${html`<${Pv} source="recorded" detail="host trace" />`}>
    <dl class="kv"><dt>Latest prompt</dt><dd>${kilo(t.latest_prompt_tokens)} tok</dd><dt>Cache hit share</dt><dd>${pct(t.cache_hit_share, 1)}</dd>
      <dt>Context cuts</dt><dd>${cuts.applied} applied · ${cuts.held_back} held back</dd>
      ${results.length ? html`<dt>Cut results</dt><dd>${results.join(' · ')}</dd>` : null}
      ${host.tail_notices?.count > 0 ? html`<dt>Tail notices</dt><dd>${count(host.tail_notices.count)}</dd>` : null}
      <dt>Memory updates</dt><dd>${host.knowledge_updates.count}${host.knowledge_updates.latest_version ? ` · ${host.knowledge_updates.latest_version}` : ''}</dd></dl><//>`;
}

function RoutingCard({s, tools}) {
  const host = s.host_telemetry, facts = s.facts || {};
  const ends = host ? Object.entries(host.response_by_endpoint) : [];
  const total = ends.reduce((a, e) => a + e[1], 0);
  const input = tools && (tools.tools.find(t => t.tool === 'computer_input') || tools.tools[0]);
  return html`<${Card} id="kpi-routing" title="Routing and latency" big=${ends.length ? ends[0][0] : facts.provider || '—'}
    sub=${ends.length ? `most responses · ${plural(total, 'response')} · ${plural(ends.length, 'endpoint')}` : 'answering endpoint not recorded'}
    chips=${ends.map(([name, n]) => html`<span class="tag endpoint">${name}: <b class="num">${count(n)}</b></span>`)}>
    <dl class="kv"><dt>Model · effort</dt><dd class="wrapany">${facts.model || '—'} · ${facts.effort || '—'}</dd>
      <dt>Requests</dt><dd>${host ? `${count(host.player_requests)} player · ${count(host.recall_requests)} recall` : '—'}</dd>
      <dt>${input ? `${toolLabel(input.tool)} latency` : 'Tool latency'}</dt><dd>${input ? `p50 ${input.p50_ms === null ? '—' : Math.round(input.p50_ms)} · p95 ${input.p95_ms === null ? '—' : Math.round(input.p95_ms)} ms` : '—'}</dd></dl><//>`;
}

const RECEIPT_DISPOSITIONS = {
  incomplete: 'Incomplete', interrupted: 'Interrupted', player_task_complete_unassessed: 'Player reported task complete (unassessed)',
  player_cannot_continue_unassessed: 'Player reported unable to continue (unassessed)',
  player_external_stop_complete_unassessed: 'Player reported external stop complete (unassessed)'
};
const RECEIPT_FIELDS = [['normal_native_exit_zero', 'Normal native exit (code 0)'], ['native_absence_verified', 'Native absence verified'],
  ['deciding_hosts_quiescent', 'Deciding hosts quiescent'], ['input_authority_revoked', 'Input authority revoked']];
const yesNo = v => (v === true ? 'Yes' : v === false ? 'No' : 'Unavailable');
const evaluationNote = s => (s.state === 'final' ? 'final record' : s.live ? 'live' : 'evaluation unfinished');

function CustodyCard({s}) {
  const out = s.outcome || {}, receipt = s.custodian_receipt;
  const verdict = out.lost ? 'lost' : out.died ? 'died' : out.censor_reason ? `censored (${label(out.censor_reason)})` : s.live ? 'running' : 'ended';
  return html`<${Card} id="kpi-custody" title="Custody and outcome" big=${`${fmtH(out.hours)} game h`} sub=${verdict} chips=${html`<${Pv} source="derived" /><span class="tag" id="evaluation-note">${evaluationNote(s)}</span>`}>
    <div class="custodian-receipt">${receipt ? html`<dl class="kv"><dt>Custodian receipt</dt><dd>${RECEIPT_DISPOSITIONS[receipt.outcome] ?? 'Unavailable'}</dd>
      ${RECEIPT_FIELDS.map(([key, text]) => html`<dt>${text}</dt><dd>${yesNo(receipt[key])}</dd>`)}</dl>`
      : html`<p class="note">${s.live ? 'The custodian writes its receipt when the run ends.' : 'Receipt unavailable for this run.'}</p>`}</div><//>`;
}

/* ---------------------------------------------------------------- charts */
function ContextChart({data}) {
  const player = useMemo(() => data.requests.filter(r => !r.is_recall && r.prompt_tokens !== null), [data]);
  const cuts = data.cuts.filter(c => c.outcome === 'applied');
  const option = useMemo(() => (player.length ? contextOption(player, cuts) : null), [data, store.themeEpoch]);
  const latest = useRef(player);
  latest.current = player;   // the chart outlives a live poll; its click reads the newest requests
  const pick = chart => chart.getZr().on('click', e => {
    const point = chart.convertFromPixel({gridIndex: 0}, [e.offsetX, e.offsetY]);
    if (!point || !latest.current.length) return;
    const row = latest.current[Math.max(0, Math.min(latest.current.length - 1, Math.round(point[0])))];
    if (row.seq !== null) jumpToSeq(row.seq);
  });
  return html`<${Panel} title="Context tokens and cuts" note="per player request · dashed: a context cut · click to open Watch" span="s7">
    ${option ? html`<${Chart} option=${option} epoch=${`${store.themeEpoch}-${store.runId}`} onReady=${pick} label="Prompt tokens per player request, cached and uncached, with context cuts" className="ctxchart" />` : html`<${Insufficient}>No request in this run carries usage.<//>`}
    ${cuts.length ? html`<details><summary class="note">Context cuts as a table</summary><div class="tall"><${Table} columns=${[{title: 'Step', render: c => (c.seq === null ? '—' : html`#${c.seq}`)}, {title: 'Tokens', num: true, render: c => `${kilo(c.tokens_before)} → ${kilo(c.tokens_after)}`},
      {title: 'Images', num: true, render: c => `${c.images_before ?? '—'} → ${c.images_after ?? '—'}`}, {title: 'Turns cut', num: true, render: c => c.removed_turns ?? '—'}, {title: 'Result', render: c => c.cut_result ? label(c.cut_result) : '—'}, {title: 'Version', render: c => c.knowledge_version || '—'}, {title: 'Why', render: c => c.triggers.map(label).join(', ')}]}
      rows=${cuts} onPick=${(i, c) => { if (c.seq !== null) jumpToSeq(c.seq); }} /></div></details>` : null}
    ${data.requests_omitted ? html`<p class="note">${count(data.requests_omitted)} of ${count(data.requests_total)} requests are not drawn.</p>` : null}<//>`;
}

function SpendChart({data}) {
  const option = useMemo(() => (data.requests.length ? spendOption(data.requests, data.spend.spend_limit_usd) : null), [data, store.themeEpoch]);
  const reported = data.requests.some(r => r.reported_cost_usd !== null);
  const unpriced = data.requests.filter(r => (reported ? r.reported_cost_usd : r.estimated_dollars) === null).length;
  return html`<${Panel} title="Cumulative spend" note=${reported ? 'provider-reported, player and recall requests' : 'configured-rate estimate: no provider cost is recorded'} span="s5">
    ${option && !data.requests_omitted ? html`<${Chart} option=${option} epoch=${`${store.themeEpoch}-${store.runId}`} label="Cumulative spend by request" className="spendchart" />`
      : html`<${Insufficient}>${data.requests_omitted ? 'Not drawn: this run has more requests than the view carries, so a sum would be partial.' : 'No requests recorded.'}<//>`}
    ${unpriced ? html`<p class="note" id="spend-unpriced">${plural(unpriced, 'request')} with no ${reported ? 'provider price' : 'estimate'} ${unpriced === 1 ? 'is' : 'are'} not in this line, so it is a subtotal.</p>` : null}
    <p class="note">Curator spend is recorded per session, not per request, and is in the card above.</p><//>`;
}

function ToolTable({tools}) {
  return html`<${Panel} title="Tool usage" note="volume, speed and failures" span="s12"><${Table} columns=${[{title: 'Tool', render: t => toolLabel(t.tool)}, {title: 'Calls', num: true, render: t => count(t.calls)},
    {title: 'p50 ms', num: true, render: t => (t.p50_ms === null ? '—' : Math.round(t.p50_ms))}, {title: 'p95 ms', num: true, render: t => (t.p95_ms === null ? '—' : Math.round(t.p95_ms))},
    {title: 'Errors', num: true, key: 'errors'}, {title: 'Refused', num: true, key: 'refused'}, {title: 'Result text', num: true, render: t => bytes(t.result_bytes)}]} rows=${tools.tools} empty="No tool call recorded." /><//>`;
}

/* ---------------------------------------------------------------- findings, readers, metrics */
function Findings({s}) {
  const t0 = runStart();
  // Image evictions are many and routine; they are not findings a person follows.
  const findings = (s.findings || []).filter(f => f.kind !== 'context_eviction' && f.wall !== null);
  return html`<${Panel} title="Findings" note="newest first, up to 100 · open one in Watch" span="s7">
    ${findings.length ? html`<ul class="feed tall" id="findings">${findings.map(f => html`<li><button type="button" data-jump=${f.seq_start} onClick=${() => jumpToSeq(f.seq_start)}>
      <span class="t">${mmss(Math.max(0, f.wall - t0))}</span><span>${findingText(f)}</span><${Pv} source=${f.source} detail=${f.confidence ? pct(f.confidence) : ''} /></button></li>`)}</ul>` : html`<div class="insuf" id="findings">No findings recorded for this run.</div>`}<//>`;
}

function ReaderCoverage({s}) {
  return html`<${Panel} title="Reader coverage" note="how often each reader produced a value, and its held-out validation" span="s12">
    <${Table} columns=${[{title: 'Reader', key: 'reader'}, {title: 'Coverage', num: true, render: r => pct(r.coverage, 1)}, {title: 'Frames', num: true, render: r => `${trim(r.count)}/${trim(r.denominator)}`},
      {title: 'Held-out', num: true, render: r => (r.validation ? `${pct(r.validation.accuracy, 1)} of ${r.validation.n} · floor ${pct(r.validation.floor, 1)}` : '—')},
      {title: 'Status', render: r => (r.validation ? html`<span class="state ${r.validation.pass === true ? 'clear' : 'watch'}">${r.validation.pass === true ? 'passes' : r.validation.pass === false ? 'below floor' : 'unmeasured'}</span>` : html`<span class="note">not validated</span>`)}]} rows=${s.reader_coverage || []} empty="No reader coverage recorded." /><//>`;
}

const GROUPS = {survival: 'Survival', custody: 'Custody', pace: 'Pace and game time', stall: 'Stalls', mode: 'Mode', host: 'Host and spend', input: 'Input', memory: 'Memory',
  handoff: 'Handoffs', programs: 'Programs', tools: 'Tool calls', needs: 'Needs', lineage: 'Lineage', run: 'Run losses'};
const metricText = m => {
  if (m.value && typeof m.value === 'object' && typeof m.value.calls === 'number') return `${m.value.calls} calls, ${m.value.refused} refused, ${m.value.errors} errors`;
  const v = scalar(m.value);
  if (v === null) return m.value === null || (Array.isArray(m.value) && !m.value.length) ? 'none' : compact(m.value);
  return Math.abs(v) >= 100 ? String(Math.round(v)) : trim(+v.toFixed(3));
};
const metricNote = m => [m.count !== null && m.count !== undefined ? `n ${trim(m.count)}${m.denominator ? `/${trim(m.denominator)}` : ''}` : '', m.missing ? (typeof m.missing === 'number' ? `${trim(m.missing)} missing` : (/missing/i.test(label(m.missing)) ? label(m.missing) : `missing: ${label(m.missing)}`)) : ''].filter(Boolean).join(' · ');

function Metrics({s}) {
  const labels = s.labels || {}, facts = s.facts || {};
  const groups = new Map();
  for (const m of s.metrics || []) {
    if (m.name === 'reader.coverage' || m.name === 'ladder.reached') continue;
    const title = GROUPS[m.name.split('.')[0]] || label(m.name.split('.')[0]);
    if (!groups.has(title)) groups.set(title, []);
    groups.get(title).push(m);
  }
  return html`<${Panel} title="Run facts" note=${evaluationNote(s)} span="s4"><dl class="kv"><dt>Run</dt><dd>${shortId(s.run)}</dd><dt>Decisions</dt><dd>${s.decisions ?? '—'} <${Pv} source="recorded" /></dd><dt>Episodes</dt><dd>${(s.outcome || {}).episodes ?? '—'}</dd>
      <dt>Arm · start</dt><dd>${labels.arm || '—'} · ${labels.start || '—'}</dd><dt>Scenario</dt><dd>${labels.scenario || '—'}</dd><dt>Source commit</dt><dd>${String(facts.source_commit || '').slice(0, 7) || '—'}</dd>
      <dt>Evaluator</dt><dd>core ${s.versions?.core_version} · ${s.versions?.binding_id} ${s.versions?.binding_version}</dd></dl><//>
    ${[...groups.entries()].map(([name, list]) => html`<${Panel} title=${name} span="s4"><dl class="kv">${list.map(m => html`<dt>${label(m.name.split('.').slice(1).join('.'))}${m.key ? ` · ${m.key}` : ''} <${Pv} source=${m.source} /><${Unvalidated} metric=${m} /></dt>
      <dd title=${metricNote(m)}>${metricText(m)} <span class="note sub">${metricNote(m)}</span></dd>`)}</dl><//>`)}
    <${Panel} title="Milestone ladder" note=${s.ladder ? `highest reached: ${label(s.ladder.highest || 'none')}` : ''} span="s12">
      <${Table} columns=${[{title: 'Milestone', render: r => label(r.id)}, {title: 'Status', render: r => label(r.status)}, {title: 'Evidence', render: r => html`<${Pv} source=${r.evidence} />`},
        {title: 'At decision', num: true, render: r => (r.clocks ? r.clocks.decision : '—')}, {title: '$', num: true, render: r => (r.clocks ? fmtMoney(r.clocks.dollars) : '—')}]}
        rows=${s.ladder ? s.ladder.rungs || [] : []} empty="No ladder recorded." /><//>`;
}

/* ---------------------------------------------------------------- calls and requests */
function Calls({run, tools}) {
  const [tool, setTool] = useState('');
  const [status, setStatus] = useState('');
  const [pick, setPick] = useState(null);
  const calls = useView(`${runPath(run, 'calls')}?tool=${encodeURIComponent(tool)}&status=${encodeURIComponent(status)}&limit=100`);
  const option = useMemo(() => transitionsOption(tools.tools || [], tools.transitions || [], toolLabel), [tools, store.themeEpoch]);
  const list = calls.data ? calls.data.items || [] : [];
  const chosen = pick === null ? null : list[pick];
  return html`<${Panel} title="Calls" note="the first 100 that match · open a call to see the frame it produced" span="s7">
      <div class="filters"><label>Tool <select aria-label="Tool filter" value=${tool} onChange=${e => { setTool(e.target.value); setPick(null); }}><option value="">all</option>${tools.tools.map(t => html`<option value=${t.tool}>${toolLabel(t.tool)}</option>`)}</select></label>
        <label>Status <select aria-label="Status filter" value=${status} onChange=${e => { setStatus(e.target.value); setPick(null); }}><option value="">all</option><option value="ok">ok</option><option value="error">error</option><option value="refused">refused</option></select></label></div>
      ${calls.data ? html`<div class="tall calls"><${Table} columns=${[{title: 'Decision', num: true, key: 'decision'}, {title: 'Tool', render: c => toolLabel(c.tool)}, {title: 'Status', key: 'status'}, {title: 'ms', num: true, render: c => (c.latency_ms === null ? '—' : Math.round(c.latency_ms))}, {title: 'Result', num: true, render: c => bytes(c.result_bytes)}]}
        rows=${list} onPick=${i => setPick(i)} selected=${pick} empty="No calls match." /></div>` : html`<${Waiting} store=${store} what="calls" error=${calls.error} />`}
      ${chosen && chosen.step && chosen.step.source_id ? html`<div class="frame small"><img src=${framePath(run, chosen.step.source_id)} alt=${`Frame produced by decision ${chosen.decision}`} /><span class="src">step ${chosen.step.seq} · viewer frame</span></div>
        <p><button type="button" class="btn" onClick=${() => jumpToSeq(chosen.step.seq)}>Open step ${chosen.step.seq} in Watch</button></p>` : chosen ? html`<${Insufficient}>This call produced no step.<//>` : null}<//>
    <${Panel} title="What follows what" note="tool transitions within each actor · diagonal = repeats" span="s5">
      ${(tools.transitions || []).length ? html`<${Chart} option=${option} epoch=${store.themeEpoch} label="Tool transition matrix" className="trans" />` : html`<${Insufficient}>No transitions recorded.<//>`}<//>`;
}

function Requests({run, data}) {
  const [sel, setSel] = useState(null);
  const cost = r => (r.reported_cost_usd !== null ? Number(r.reported_cost_usd) : r.estimated_dollars);
  const top = useMemo(() => [...data.requests].filter(r => cost(r) !== null).sort((a, b) => cost(b) - cost(a)).slice(0, 8), [data]);
  const row = data.requests.find(r => r.index === sel) || top[0];
  if (!row) return html`<${Panel} title="Costliest requests" span="s12"><${Insufficient}>No priced request recorded.<//><//>`;
  return html`<${Panel} title="Costliest requests" note="open one to replay its context" span="s6">
      <${Table} columns=${[{title: 'Request', render: r => r.request_id}, {title: 'Prompt', num: true, render: r => kilo(r.prompt_tokens)}, {title: 'Cache write', num: true, render: r => kilo(r.cache_write)},
        {title: 'Cost', num: true, render: r => `$${cost(r).toFixed(4)}`}, {title: 'Basis', render: r => html`<${Pv} source="recorded" detail=${r.reported_cost_usd !== null ? 'provider' : 'configured rate'} />`}]}
        rows=${top} onPick=${(i, r) => setSel(r.index)} selected=${top.findIndex(r => r.index === row.index)} /><//>
    <${Panel} title=${`Context of ${row.request_id}`} note=${`actor ${shortId(row.actor)}`} span="s6"><${RequestContext} key=${`${row.actor}-${row.request_id}`} run=${run} requestId=${row.request_id} actor=${row.actor} /><//>`;
}

/* ---------------------------------------------------------------- across runs */
export const CROSS = [['compare', 'Compare'], ['explore', 'Explore'], ['changes', 'Changes'], ['failures', 'Failure modes'], ['components', 'Components by arm']];
function CrossRuns({section}) {
  const current = CROSS.some(c => c[0] === section) ? section : 'compare';
  const body = {compare: Compare, explore: Explore, changes: Changes, failures: Failures, components: Components}[current];
  return html`<div class="s12"><${SubNav} tabs=${CROSS} base="diagnostics" current=${current} label="Across runs" /></div><${body} />`;
}

/* ---------------------------------------------------------------- the tab */
export function Diagnostics({section}) {
  const run = store.runId, s = store.summary;
  const live = !!(s && s.live);
  const telemetry = useView(run ? runPath(run, 'telemetry') : null, live ? 5000 : 0);
  const tools = useView(run ? runPath(run, 'tools') : null, live ? 10000 : 0);
  const ready = !!s;
  useEffect(() => {   // the Pause alert on Watch links here
    const box = section === 'pause' && document.querySelector('.pausebox');
    if (box) box.scrollIntoView({block: 'center'});
  }, [section, ready]);
  if (!run || !s) return html`<section class="grid" data-view="diagnostics" aria-label="Diagnostics"><${Panel} title="Diagnostics" span="s12"><${Waiting} store=${store} what="the run summary" /><//></section>`;
  return html`<section class="grid" data-view="diagnostics" aria-label="Diagnostics">
    <div class="kpis s12"><${SpendCard} s=${s} /><${ContextCard} s=${s} /><${RoutingCard} s=${s} tools=${tools.data} /><${CustodyCard} s=${s} /></div>
    ${telemetry.data ? html`<${ContextChart} data=${telemetry.data} /><${SpendChart} data=${telemetry.data} />` : html`<${Panel} title="Telemetry" span="s12"><${Waiting} store=${store} what="request telemetry" error=${telemetry.error} /><//>`}
    ${tools.data ? html`<${ToolTable} tools=${tools.data} />` : html`<${Panel} title="Tool usage" span="s12"><${Waiting} store=${store} what="tool statistics" error=${tools.error} /><//>`}
    <${PauseConditions} summary=${s} />
    <${GameState} summary=${s} span="s5" /><${Findings} s=${s} />
    <${Disclosure} id="more-calls" title="Tool calls and transitions">${() => (tools.data ? html`<${Calls} run=${run} tools=${tools.data} key=${run} />` : html`<${Waiting} store=${store} what="tool calls" error=${tools.error} />`)}<//>
    <${Disclosure} id="more-requests" title="Costliest requests and their context">${() => (telemetry.data ? html`<${Requests} run=${run} data=${telemetry.data} key=${run} />` : html`<${Waiting} store=${store} what="requests" error=${telemetry.error} />`)}<//>
    <${Disclosure} id="more-metrics" title="All metrics and the milestone ladder" note="with their provenance, n and missing data" open=${section === 'metrics'}>${() => html`<${Metrics} s=${s} />`}<//>
    <${Disclosure} id="more-readers" title="Reader coverage and validation" note="values from a reader below its floor are provisional" open=${section === 'readers'}>${() => html`<${ReaderCoverage} s=${s} />`}<//>
    ${(store.runs || []).length > 1 ? html`<${Disclosure} id="more-runs" title="Compare and explore runs" note=${plural(store.runs.length, 'run')} open=${CROSS.some(c => c[0] === section)}>${() => html`<${CrossRuns} section=${section} />`}<//>` : null}</section>`;
}
