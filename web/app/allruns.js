// All runs: the workspace above any one run. Lineages and their admissions, the cross-run comparisons, change records,
// failure modes, and the archive with the lineage's operator sources.
import {html, Panel, Pv, Waiting, Disclosure, SubNav, Insufficient, fmtH, count, plural, label, runName, usd2} from './ui.js';
import {store, useStore, useView, runPath, selectRun} from './data.js';
import {spendParts} from './diagnostics.js';
import {Explore, Compare} from './crossrun.js';
import {Changes, Failures, Components} from './improve.js';
import {Archive} from './records.js';

export const RUNS_SECTIONS = [['lineage', 'Lineage'], ['compare', 'Compare'], ['explore', 'Explore'], ['changes', 'Changes'], ['failures', 'Failures'], ['archive', 'Archive']];

const admissionOf = r => (r.labels && typeof r.labels.admission === 'number' ? r.labels.admission : null);
const admissionText = n => (n === null ? '—' : `a${String(n).padStart(2, '0')}`);
const openRun = r => { selectRun(r.session); location.hash = '#watch'; };

/** One admission, with the figures only its own summary states: loop spend, the head version and the agenda it ended on. */
function AdmissionRow({run, previous}) {
  const {data, error} = useView(runPath(run.session, 'summary'), run.state === 'live' ? 10000 : 0);
  const p = data ? spendParts(data) : null;
  const host = data && data.host_telemetry;
  const head = host ? (host.knowledge_deliveries && host.knowledge_deliveries.latest_version) || host.knowledge_updates.latest_version : null;
  const agenda = data && data.agenda ? data.agenda.final || data.agenda.latest : null;
  return html`<tr data-admission=${run.session}><td><button type="button" class="link" onClick=${() => openRun(run)}>${admissionText(admissionOf(run))} · ${runName(run)}</button></td>
    <td>${run.state === 'live' ? html`<span class="state clear">live</span>` : label(run.state)}${run.outcome.lost ? html` <span class="state alert">lost</span>` : null}</td>
    <td class="num">${fmtH(run.outcome.hours)}</td><td class="num">${previous === null ? '—' : fmtH(previous)}</td>
    <td class="num">${!data ? (error ? 'unavailable' : '…') : p.sum !== null ? usd2(p.sum) : `~${usd2(data.dollars)} est`}</td>
    <td>${head ? html`<a href=${`#memory?version=${encodeURIComponent(head)}`} onClick=${() => selectRun(run.session)}>${head}</a>` : '—'}</td>
    <td>${agenda ? plural(agenda.thread_count, 'thread') : 'none'}</td></tr>`;
}

function LineageTable({runs}) {
  let hours = 0;
  const rows = runs.map(r => { const before = hours; hours += r.outcome.hours || 0; return {r, cumulative: before + (r.outcome.hours || 0)}; });
  return html`<div class="scroll s12"><table class="data lineage-table"><thead><tr><th>Admission</th><th>State</th><th class="num">Game h</th><th class="num">Cumulative h</th><th class="num">Loop spend</th><th>Head version</th><th>Agenda carried</th></tr></thead>
    <tbody>${rows.map(({r, cumulative}) => html`<${AdmissionRow} run=${r} previous=${cumulative} key=${r.session} />`)}</tbody></table></div>`;
}

function Lineage() {
  useStore();
  const runs = store.runs;
  if (!runs) return html`<${Panel} title="Lineages" span="s12"><${Waiting} store=${store} what="the run list" /><//>`;
  const lineages = new Map();
  for (const r of runs) {
    const name = r.labels && r.labels.lineage;
    if (!name) continue;
    if (!lineages.has(name)) lineages.set(name, []);
    lineages.get(name).push(r);
  }
  const single = runs.filter(r => !(r.labels && r.labels.lineage));
  const skipped = store.skippedNonCurrent;
  return html`<section class="grid s12" data-section="lineage" aria-label="Lineage">
    ${skipped ? html`<p class="note s12" id="runs-skipped">${plural(skipped, 'run store')} from an older evaluator core ${skipped === 1 ? 'is' : 'are'} not listed.</p>` : null}
    ${lineages.size ? [...lineages.entries()].map(([name, list]) => {
      const sorted = [...list].sort((a, b) => (admissionOf(a) ?? 0) - (admissionOf(b) ?? 0));
      const hours = sorted.reduce((a, r) => a + (r.outcome.hours || 0), 0);
      const estimate = sorted.reduce((a, r) => a + (r.dollars || 0), 0);
      const live = sorted.some(r => r.state === 'live');
      return html`<${Panel} title=${`Lineage ${name}`} note=${`${plural(sorted.length, 'admission')}${live ? ' · one live' : ''}`} span="s12" className="lineage">
        <p class="progression" data-lineage=${name}>${sorted.map((r, i) => html`${i ? html`<span class="arrow" aria-hidden="true">→</span>` : null}<button type="button" class=${`adm ${r.state}`} title=${`${runName(r)} · ${r.state}`} onClick=${() => openRun(r)}>${admissionText(admissionOf(r))}</button>`)}</p>
        <dl class="kv lineage-facts"><dt>Cumulative game hours</dt><dd>${fmtH(hours)} <${Pv} source="derived" /></dd><dt>Configured-rate estimate</dt><dd>${usd2(estimate)}</dd></dl>
        <${Disclosure} id=${`lineage-${name}`} title="Admissions" note="loop spend, head knowledge version and carried agenda, read from each admission's summary">${() => html`<${LineageTable} runs=${sorted} />`}<//><//>`;
    }) : html`<${Panel} title="Lineages" span="s12"><${Insufficient}>No run in this catalog belongs to a lineage.<//><//>`}
    ${single.length ? html`<${Panel} title="Runs outside a lineage" note=${plural(single.length, 'run')} span="s12"><p class="chips" id="single-runs">${single.map(r => html`<button type="button" class="factpill" onClick=${() => openRun(r)}>${runName(r)}${r.state === 'live' ? ' · live' : ''}</button>`)}</p><//>` : null}
    <p class="note s12">${count(store.runsTotal || runs.length)} runs listed by the viewer.</p></section>`;
}

function CompareAll() {
  return html`<${Compare} /><div class="grid s12"><${Components} /></div>`;
}

export function AllRuns({section, sub}) {
  const current = RUNS_SECTIONS.some(([id]) => id === section) ? section : 'lineage';
  const body = {lineage: Lineage, compare: CompareAll, explore: Explore, changes: Changes, failures: Failures, archive: Archive}[current];
  return html`<section class="grid" data-view="runs" aria-label="All runs">
    <div class="s12"><${SubNav} id="runs-nav" tabs=${RUNS_SECTIONS} base="runs" current=${current} label="All runs" /></div>
    <${body} section=${sub || ''} /></section>`;
}
