// Cross-run views: Explore (cohorts, what precedes death) and Compare (survival).
import {html, useState, useMemo, Panel, Pv, Waiting, Table, Insufficient, trim, fmtH} from './ui.js';
import {store, useView} from './data.js';
import {Chart, survivalOption} from './charts.js';

const METRICS = [['hours', 'Survival game h'], ['pace', 'Routine pace'], ['oop', 'Out-of-play share'], ['stall_longest', 'Longest stall'], ['setup', 'Setup decisions'], ['dollars', 'Spend $'], ['per_dec', '$ per decision']];

function Select({label, value, options, onChange}) {
  return html`<label>${label} <select data-cf=${label.toLowerCase()} value=${value} onChange=${e => onChange(e.target.value)}>${options.map(([v, l]) => html`<option value=${v}>${l}</option>`)}</select></label>`;
}

export function Explore() {
  const [f, setF] = useState({arm: '', start: '', outcome: '', metric: 'hours'});
  const q = `explore?arm=${encodeURIComponent(f.arm)}&start=${encodeURIComponent(f.start)}&outcome=${encodeURIComponent(f.outcome)}&metric=${encodeURIComponent(f.metric)}`;
  const {data, error} = useView(q, 10000);
  const runs = store.runs || [];
  const arms = [...new Set(runs.map(r => r.arm))], starts = [...new Set(runs.map(r => r.start))];
  const set = key => v => setF(old => ({...old, [key]: v}));
  const filters = html`<div class="filters" id="cohortf"><${Select} label="Arm" value=${f.arm} onChange=${set('arm')} options=${[['', 'all'], ...arms.map(a => [a, a])]} />
    <${Select} label="Start" value=${f.start} onChange=${set('start')} options=${[['', 'all'], ...starts.map(a => [a, a])]} />
    <${Select} label="Outcome" value=${f.outcome} onChange=${set('outcome')} options=${[['', 'all'], ['died', 'died'], ['censored', 'censored'], ['lost', 'lost']]} />
    <${Select} label="Metric" value=${f.metric} onChange=${set('metric')} options=${METRICS} /></div>`;
  const rows = data ? data.rows || [] : [];
  const cols = data ? data.columns || [] : [];
  const stat = data ? data.stat : null;
  const csv = useMemo(() => [cols.join(','), ...rows.map(r => cols.map(c => r[c] ?? '').join(','))].join('\n'), [data]);
  return html`<section class="grid" data-view="explore" aria-label="Explore">
    <${Panel} title="Cohort" note="filter runs, pick a metric, get n, median, spread and a bootstrap interval" span="s12">${filters}
      ${data ? html`<dl class="kv wide" id="cohortsum"><dt>Runs in cohort</dt><dd>${rows.length}</dd>
          <dt>${METRICS.find(m => m[0] === f.metric)?.[1]}: n with a value</dt><dd>${stat ? stat.n : '—'}</dd>
          <dt>Median [IQR] <${Pv} source=${stat?.source || 'derived'} /></dt><dd>${stat && stat.median !== null ? `${trim(stat.median)} [${trim(stat.q1)}–${trim(stat.q3)}]` : '—'}</dd>
          <dt>95% bootstrap interval for the median</dt><dd>${stat && stat.ci ? `${trim(stat.ci[0])} – ${trim(stat.ci[1])}` : `needs n ≥ ${stat?.min_n ?? 5}`}</dd></dl>
        <div class="scroll"><table class="data" id="cohorttable"><thead><tr>${cols.map(c => html`<th>${c}</th>`)}</tr></thead><tbody>${rows.map(r => html`<tr>${cols.map(c => html`<td class=${typeof r[c] === 'number' ? 'num' : ''}>${r[c] === null || r[c] === undefined ? '—' : typeof r[c] === 'number' ? trim(r[c]) : r[c]}</td>`)}</tr>`)}</tbody></table></div>
        <details><summary class="note">Copy as CSV</summary><textarea class="csv" readonly aria-label="Cohort as CSV" value=${csv}></textarea></details>` : html`<${Waiting} store=${store} what="the cohort" error=${error} />`}<//>
    <${Panel} title="What happened before each death" note="12 decisions aligned on the death event" span="s12">
      ${data ? ((data.before_death || []).length ? html`<div id="alignbody" class="aligned">${data.before_death.map(a => html`<div><div class="note"><b class="mono">${a.label || a.run}</b> · ${a.start} start</div>
        <div class="seq">${(a.rows || []).map(x => html`<span class=${x.mode || 'unknown'} title=${`decision ${x.decision}: ${x.mode}${x.keys ? ` · ${x.keys}` : ''}`}>${x.threat === 'lethal' ? 'L' : x.threat === 'high' ? 'H' : ''}</span>`)}</div></div>`)}
          <p class="note">L marks a lethal crowd and H a high one on the creature list <${Pv} source="read" detail="threat reader" />. With few deaths, any pattern here is a lead to check, not a finding.</p></div>` : html`<${Insufficient}>No deaths in this cohort.<//>`) : html`<${Waiting} store=${store} what="deaths" error=${error} />`}
      <div class="legend"><span><i class="s-in_play"></i>in play</span><span><i class="s-prompt"></i>prompt</span><span><i class="s-menu"></i>menu</span><span><i class="s-dead"></i>dead</span><span>L lethal · H high crowd</span></div><//></section>`;
}

export function Compare() {
  const [byStart, setByStart] = useState(false);
  const {data, error} = useView(`compare?group=${byStart ? 'start' : 'arm'}`, 10000);
  const groups = data ? data.groups || [] : [];
  const option = useMemo(() => (groups.length ? survivalOption(groups) : null), [data, store.themeEpoch]);
  const excluded = [...new Set(groups.flatMap(g => g.excluded || []))];
  return html`<section class="grid" data-view="compare" aria-label="Compare">
    <${Panel} title=${`Survival by ${byStart ? 'start' : 'arm'}`} note=${data ? `lost runs excluded: ${excluded.join(', ') || 'none'}` : ''} span="s12">
      <div class="filters"><label><input type="checkbox" id="strat" checked=${byStart} onChange=${e => setByStart(e.target.checked)} /> Split by start type instead of arm</label></div>
      ${data ? html`<${Table} columns=${[{title: byStart ? 'Start' : 'Arm', key: 'name'}, {title: 'n', num: true, key: 'n'}, {title: 'Deaths', num: true, key: 'deaths'}, {title: 'Censored', num: true, key: 'censored'},
          {title: 'Median', num: true, render: g => (g.median === 'not_reached' || g.median === null ? 'not reached' : fmtH(g.median))},
          {title: `Mean survival to ${trim(data.horizon)} h [95%]`, num: true, render: g => (g.rmst ? `${fmtH(g.rmst.value)} h [${fmtH(g.rmst.lo)}–${fmtH(g.rmst.hi)}]` : '—')},
          {title: 'Source', render: () => html`<${Pv} source="derived" detail="Kaplan–Meier, Greenwood" />`}]} rows=${groups} />
        <${Chart} option=${option} epoch=${store.themeEpoch} label="Kaplan–Meier survival curves with confidence bands" className="km" />
        <p class="note">Solid: Kaplan–Meier estimate. Dotted: lower 95% Greenwood bound.</p>${data.note ? html`<p class="note">${data.note}</p>` : null}`
        : html`<${Waiting} store=${store} what="survival curves" error=${error} />`}<//>
    <${Panel} title="Are these runs comparable?" note="computed from each run's frozen manifest" span="s12">
      ${data ? html`<${Table} columns=${[{title: 'Group', key: 'group'}, {title: 'Source commit', render: v => html`<span class="mono">${v.source_commit}</span>`}, {title: 'Start types', key: 'starts'}, {title: 'Model and route', key: 'model_route'}, {title: 'Evaluator', key: 'evaluator'}]} rows=${data.versions || []} empty="No version facts." />`
        : html`<${Waiting} store=${store} what="version facts" error=${error} />`}<//></section>`;
}
