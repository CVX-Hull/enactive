// Cross-run views: Explore (cohorts, what precedes death) and Compare (survival).
import {html, useState, useMemo, Panel, Pv, Waiting, Table, Insufficient, trim, fmtH, fmtMoney, label} from './ui.js';
import {store, useView} from './data.js';
import {Chart, survivalOption} from './charts.js';

const METRICS = [['survival.game_hours', 'Survival game h'], ['pace.routine_seconds_per_decision', 'Routine pace (game s / decision)'], ['mode.out_of_play_share', 'Out-of-play share'],
  ['stall.longest', 'Longest stall'], ['stall.count', 'Stalls'], ['host.dollars_per_decision', '$ per decision'], ['host.large_rewrite_share', 'Large-rewrite share of spend']];
const COLUMNS = ['run', 'arm', 'start', 'outcome', 'reason', 'game_h', 'decisions', 'dollars', 'value'];

function Select({name, text, value, options, onChange}) {
  return html`<label>${text} <select data-cf=${name} value=${value} onChange=${e => onChange(e.target.value)}>${options.map(([v, l]) => html`<option value=${v}>${l}</option>`)}</select></label>`;
}
const cohortRow = r => ({run: r.run, arm: r.labels.arm, start: r.labels.start, outcome: r.outcome.lost ? 'lost' : r.outcome.outcome, reason: r.outcome.censor_reason,
  game_h: r.outcome.hours === null ? null : +r.outcome.hours.toFixed(3), decisions: r.decisions, dollars: +(r.dollars || 0).toFixed(3), value: r.value});

export function Explore() {
  const [f, setF] = useState({arm: '', start: '', outcome: '', metric: 'survival.game_hours'});
  const q = `explore?arm=${encodeURIComponent(f.arm)}&start=${encodeURIComponent(f.start)}&outcome=${encodeURIComponent(f.outcome)}&metric=${encodeURIComponent(f.metric)}`;
  const {data, error} = useView(q, 10000);
  const runs = store.runs || [];
  const arms = [...new Set(runs.map(r => r.labels.arm).filter(Boolean))], starts = [...new Set(runs.map(r => r.labels.start).filter(Boolean))];
  const set = key => v => setF(old => ({...old, [key]: v}));
  const rows = data ? data.cohort.map(cohortRow) : [];
  const stat = data ? data.stats : null;
  const csv = useMemo(() => [COLUMNS.join(','), ...rows.map(r => COLUMNS.map(c => r[c] ?? '').join(','))].join('\n'), [data]);
  const filters = html`<div class="filters" id="cohortf"><${Select} name="arm" text="Arm" value=${f.arm} onChange=${set('arm')} options=${[['', 'all'], ...arms.map(a => [a, a])]} />
    <${Select} name="start" text="Start" value=${f.start} onChange=${set('start')} options=${[['', 'all'], ...starts.map(a => [a, a])]} />
    <${Select} name="outcome" text="Outcome" value=${f.outcome} onChange=${set('outcome')} options=${[['', 'all'], ['died', 'died'], ['censored', 'censored'], ['lost', 'lost']]} />
    <${Select} name="metric" text="Metric" value=${f.metric} onChange=${set('metric')} options=${METRICS} /></div>`;
  return html`<section class="grid" data-view="explore" aria-label="Explore">
    <${Panel} title="Cohort" note="filter runs, pick a metric, get n, median, spread and a bootstrap interval" span="s12">${filters}
      ${data ? html`<dl class="kv wide" id="cohortsum"><dt>Runs in cohort</dt><dd>${rows.length} (${rows.filter(r => r.outcome === 'died').length} died, ${rows.filter(r => r.outcome === 'lost').length} lost)</dd>
          <dt>${(METRICS.find(m => m[0] === f.metric) || [])[1]}: n with a value</dt><dd>${stat.n}</dd>
          <dt>Median [IQR] <${Pv} source="derived" /></dt><dd>${stat.median !== null ? `${trim(+stat.median.toFixed(4))} [${trim(+stat.iqr[0].toFixed(4))}–${trim(+stat.iqr[1].toFixed(4))}]` : '—'}</dd>
          <dt>95% bootstrap interval for the median</dt><dd>${stat.bootstrap ? `${trim(+stat.bootstrap.low.toFixed(4))} – ${trim(+stat.bootstrap.high.toFixed(4))} (${stat.bootstrap.resamples} resamples)` : stat.bootstrap_note || '—'}</dd></dl>
        <div class="scroll"><table class="data" id="cohorttable"><thead><tr>${COLUMNS.map(c => html`<th>${label(c)}</th>`)}</tr></thead><tbody>${rows.map(r => html`<tr>${COLUMNS.map(c => html`<td class=${typeof r[c] === 'number' ? 'num' : ''}>${r[c] === null || r[c] === undefined ? '—' : typeof r[c] === 'number' ? trim(+r[c].toFixed(4)) : r[c]}</td>`)}</tr>`)}</tbody></table></div>
        <details><summary class="note">Copy as CSV</summary><textarea class="csv" readonly aria-label="Cohort as CSV" value=${csv}></textarea></details>` : html`<${Waiting} store=${store} what="the cohort" error=${error} />`}<//>
    <${Panel} title="What happened before each death" note="the 12 decisions before the death event, and the death step" span="s12">
      ${data ? (data.before_death.length ? html`<div id="alignbody" class="aligned">${data.before_death.map(a => html`<div><div class="note"><b class="mono">${a.run}</b> · ${a.start} start</div>
        <div class="seq">${a.decisions.map(x => html`<span class=${x.mode || 'unknown'} title=${`decision ${x.decision}: ${x.mode}${x.keys && x.keys.length ? ` · ${x.keys.join(' ')}` : ''}${x.creatures ? ` · ${x.creatures} creatures` : ''}`}>${x.threat === 'lethal' ? 'L' : x.threat === 'high' ? 'H' : ''}</span>`)}</div></div>`)}
          <p class="note">L marks a lethal crowd and H a high one on the creature list <${Pv} source="read" detail="threat reader" />. With few deaths, any pattern here is a lead to check, not a finding.</p></div>` : html`<${Insufficient}>No deaths in this cohort.<//>`) : html`<${Waiting} store=${store} what="deaths" error=${error} />`}
      <div class="legend"><span><i class="s-in_play"></i>in play</span><span><i class="s-prompt"></i>prompt</span><span><i class="s-menu"></i>menu</span><span><i class="s-dead"></i>dead</span><span>L lethal · H high crowd</span></div><//></section>`;
}

export function Compare() {
  const [byStart, setByStart] = useState(false);
  const {data, error} = useView(`compare?group=${byStart ? 'start' : 'arm'}`, 10000);
  const groups = data ? Object.entries(data.groups).map(([name, g]) => ({name, ...g})) : [];
  const option = useMemo(() => (groups.length ? survivalOption(groups) : null), [data, store.themeEpoch]);
  const excluded = data ? data.excluded : [];
  return html`<section class="grid" data-view="compare" aria-label="Compare">
    <${Panel} title=${`Survival by ${byStart ? 'start' : 'arm'}`} note=${data ? `lost runs excluded: ${excluded.map(e => e.run).join(', ') || 'none'}` : ''} span="s12">
      <div class="filters"><label><input type="checkbox" id="strat" checked=${byStart} onChange=${e => setByStart(e.target.checked)} /> Split by start type instead of arm</label></div>
      ${data ? html`<${Table} columns=${[{title: byStart ? 'Start' : 'Arm', key: 'name'}, {title: 'n', num: true, key: 'n'}, {title: 'Deaths', num: true, key: 'deaths'}, {title: 'Censored', num: true, key: 'censored'},
          {title: 'Median', num: true, render: g => (g.median === 'not_reached' || g.median === null ? 'not reached' : fmtH(g.median))},
          {title: `Mean survival to ${trim(data.horizon_hours)} h [95%]`, num: true, render: g => (g.rmst.value === null || g.rmst.value === undefined ? `n/a (${label(g.rmst.reason || 'no estimate')})` : `${fmtH(g.rmst.value)} h [${fmtH(g.rmst.low)}–${fmtH(g.rmst.high)}]`)},
          {title: 'Source', render: () => html`<${Pv} source="derived" detail="Kaplan–Meier, Greenwood" />`}]} rows=${groups} />
        <${Chart} option=${option} epoch=${store.themeEpoch} label="Kaplan–Meier survival curves with confidence bands" className="km" />
        <p class="note">Solid: Kaplan–Meier estimate. Dotted: lower 95% Greenwood bound.</p>
        ${excluded.length ? html`<p class="note">Excluded from this comparison: ${excluded.map(e => `${e.run} (${label(e.reason)})`).join(', ')}.</p>` : null}`
        : html`<${Waiting} store=${store} what="survival curves" error=${error} />`}<//>
    <${Panel} title="Are these runs comparable?" note="computed from each run's frozen manifest" span="s12">
      ${data ? html`<${Table} columns=${[{title: 'Group', key: 'name'}, {title: 'Source commits', render: g => html`<span class="mono">${g.versions.source_commits.map(c => c.slice(0, 7)).join(', ')}</span>`},
          {title: 'Start types', render: g => Object.entries(g.versions.starts).map(([k, v]) => `${v} ${k}`).join(' · ')}, {title: 'Model', render: g => g.versions.models.join(', ')},
          {title: 'Effort', render: g => g.versions.efforts.join(', ')}, {title: 'Evaluator binding', render: g => g.versions.binding_versions.join(', ')}]} rows=${groups} empty="No version facts." />`
        : html`<${Waiting} store=${store} what="version facts" error=${error} />`}<//></section>`;
}
