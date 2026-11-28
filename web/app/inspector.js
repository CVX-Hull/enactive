// Step Inspector: everything mechanical about one step, in a drawer over the story, below the Mission Control bar.
import {html, useEffect, useRef, useState, Pv, Insufficient, ShareBar, Swatch, bytes, count, keyText, label} from './ui.js';
import {store, set, runPath, viewerGet} from './data.js';
import {agendaAt, toolLabel, sourceReadText} from './continuity.js';

const PART_COLOURS = ['--series-1', '--p-claim', '--teal', '--watch', '--violet', '--series-2', '--quiet'];

/** What one request carried, by kind of part. `exact` contexts are replayed from the recorded manifest. */
export function ContextComposition({context}) {
  const kinds = Object.entries(context.bytes_by_kind || {});
  const images = (context.parts || []).filter(p => p.kind === 'image');
  const colour = i => PART_COLOURS[i % PART_COLOURS.length];
  return html`<div><${Pv} source=${context.exact ? 'recorded' : 'derived'} detail=${context.exact ? 'exact: replayed from the recorded manifest' : 'reconstructed: frozen inputs plus recorded tool results'} /></div>
    <${ShareBar} className="ctx-bar" label="Context composition" parts=${kinds.map(([n, b], i) => ({key: n, value: b, title: `${label(n)} · ${bytes(b)}`, colour: colour(i)}))} />
    <dl class="kv">${kinds.map(([n, b], i) => html`<dt><${Swatch} colour=${colour(i)} />${label(n)}</dt><dd>${bytes(b)}</dd>`)}
      <dt>Parts</dt><dd>${context.part_count}</dd><dt>Images</dt><dd>${images.filter(p => p.state !== 'omitted').length} kept · ${images.filter(p => p.state === 'omitted').length} omitted</dd></dl>
    ${(context.missing || []).length ? html`<p class="note">Not recorded: ${context.missing.map(label).join(', ')}.</p>` : null}
    ${context.omissions_capped ? html`<p class="note">The omitted-image list is capped by the viewer.</p>` : null}`;
}

/** Fetched only on request: the context of one request can be large. */
export function RequestContext({run, requestId, actor}) {
  const [state, setState] = useState({data: null, error: null, busy: false});
  const load = async () => {
    setState({data: null, error: null, busy: true});
    try {
      const data = await viewerGet(`${runPath(run, `context/${encodeURIComponent(requestId)}`)}${actor ? `?actor=${encodeURIComponent(actor)}` : ''}`);
      setState({data, error: null, busy: false});
    } catch (error) { setState({data: null, error, busy: false}); }
  };
  if (state.data) return html`<div data-context><${ContextComposition} context=${state.data} /></div>`;
  return html`<button type="button" class="btn" id="load-context" disabled=${state.busy} onClick=${load}>${state.busy ? 'Reading…' : 'Load exact request context'}</button>
    ${state.error ? html`<p class="note" role="status">${state.error.message}</p>` : null}`;
}

const shown = value => (value === null || value === undefined || value === '' ? 'unavailable' : value);
function pretty(text) {
  try { return JSON.stringify(JSON.parse(text), null, 1); } catch { return text; }   // a cut preview is shown as it is
}

/** The agenda the player had committed when it made this request. */
function AgendaSnapshot({entry, handoffs}) {
  const {state, change, carried} = agendaAt(entry.seq, store.feed, store.summary, handoffs);
  const threads = state ? state.threads : [];
  return html`<section id="inspect-agenda"><h3>Agenda at this request <${Pv} source="player_claim" detail="player_agenda" /></h3>
    ${threads.length ? html`<ul class="threads compact">${threads.map(t => html`<li data-status=${t.status}><span class="tstat">${t.status}</span><b>${t.title}</b></li>`)}</ul>`
      : html`<p class="note">No committed threads${state ? ` (${state.cut_count} cuts so far)` : ''}.</p>`}
    <p class="note">${change && change.seq !== null ? `Last changed at step ${change.seq}${change.op ? ` (${label(change.op)})` : ''}.` : 'Unchanged since the run started.'}${carried ? ` Carried at the handoff at step ${carried.seq}.` : ''}</p></section>`;
}

function Body({entry, handoffs}) {
  const result = entry.result;
  const read = entry.source_read;
  return html`<div class="drawerbody">
    <section><h3>Intent</h3>${entry.intent ? html`<p class="intent">${entry.intent}</p><div><${Pv} source="player_claim" detail="unverified" /></div>` : html`<p class="note">No intent recorded.</p>`}
      ${entry.intent_omitted_characters ? html`<p class="note">${count(entry.intent_omitted_characters)} more characters not shown.</p>` : null}</section>
    <section><h3>Input</h3><dl class="kv"><dt>Tool</dt><dd>${shown(entry.tool)}</dd><dt>Reads as</dt><dd>${toolLabel(entry.tool)}</dd><dt>Keys</dt><dd>${(entry.keys || []).map(keyText).join(' ') || 'none'}</dd></dl>
      ${entry.arguments_preview ? html`<pre id="inspect-arguments">${pretty(entry.arguments_preview)}</pre>` : html`<p class="note">No arguments recorded.</p>`}
      ${entry.arguments_omitted_characters ? html`<p class="note">${count(entry.arguments_omitted_characters)} more characters not shown.</p>` : null}</section>
    ${read ? html`<section id="inspect-source"><h3>Source read <${Pv} source="recorded" /></h3><dl class="kv wide"><dt>Real frame</dt><dd class="mono wrapany">${shown(read.source_id)}</dd>
      <dt>Player saw</dt><dd>${sourceReadText(read)}</dd><dt>Origin</dt><dd>${shown(read.origin)}</dd></dl>
      <p class="note">The player names this frame by its alias; it is not a frame the player could open from here (non-clickable).</p></section>` : null}
    <section><h3>Mechanical result <${Pv} source="recorded" /></h3><dl class="kv"><dt>Call</dt><dd>${shown(entry.status)}</dd>
      <dt>Operation</dt><dd>${shown(result && result.status)}</dd><dt>Reason</dt><dd class="wrapany">${shown(result && result.reason)}</dd>
      <dt>Latency</dt><dd>${entry.latency_ms === null ? 'unavailable' : `${Math.round(entry.latency_ms)} ms`}</dd><dt>Result text</dt><dd>${result ? bytes(result.result_bytes) : 'unavailable'}</dd></dl>
      ${result && result.receipts.length ? html`<h4>Receipts</h4>${result.receipts.map(r => html`<p class="note wrapany"><b>${shown(r.disposition)}</b> · ${r.emitted_events === null ? 'events unrecorded' : `${r.emitted_events} events`} · ${shown(r.reason)}</p>`)}` : null}
      ${result && result.receipts_omitted ? html`<p class="note">${result.receipts_omitted} more receipts not shown.</p>` : null}</section>
    <section><h3>Request</h3><dl class="kv"><dt>Prompt tokens</dt><dd>${count(entry.prompt_tokens)}</dd><dt>— uncached input</dt><dd>${count(entry.input_tokens)}</dd><dt>— cache read</dt><dd>${count(entry.cache_read)}</dd>
      <dt>— cache write</dt><dd>${count(entry.cache_write)}</dd><dt>Output tokens</dt><dd>${count(entry.output_tokens)}</dd>
      <dt>Provider-reported cost</dt><dd>${entry.reported_cost_usd === null ? 'unavailable' : `$${entry.reported_cost_usd}`}</dd><dt>Endpoint</dt><dd>${shown(entry.reported_provider)}</dd>
      <dt>Service tier</dt><dd>${shown(entry.applied_service_tier)}</dd></dl>
      <p class="note">One request may issue several calls; its tokens and cost are the request's, not this call's alone.</p></section>
    <${AgendaSnapshot} entry=${entry} handoffs=${handoffs} />
    <section><h3>Identity</h3><dl class="kv wide ids"><dt>Step</dt><dd>${entry.seq === null ? 'unavailable' : `${entry.seq}${entry.exact_step ? '' : ' (the latest before it; this call made no step)'}`}</dd><dt>Decision of the step</dt><dd>${shown(entry.step_decision)}</dd><dt>Decision of the call</dt><dd>${shown(entry.decision)}</dd>
      ${[['source_id', 'Source'], ['operation_id', 'Operation'], ['request_id', 'Request'], ['tool_call_id', 'Tool call'], ['actor', 'Actor']].map(([key, name]) => html`<dt>${name}</dt><dd class="mono wrapany">${shown(entry[key])}</dd>`)}</dl></section>
    <section><h3>Context composition</h3>${entry.request_id ? html`<${RequestContext} key=${entry.id} run=${store.runId} requestId=${entry.request_id} actor=${entry.actor} />` : html`<${Insufficient}>No request is recorded for this step.<//>`}</section></div>`;
}

export function Inspector({handoffs = []}) {
  const box = useRef(null), back = useRef(null);
  const entry = store.inspect === null ? null : store.feed.find(e => e.id === store.inspect) || null;
  const open = !!entry;
  useEffect(() => {
    if (!open) return undefined;
    back.current = document.activeElement;
    if (box.current) box.current.querySelector('.drawerclose').focus();
    return () => { if (back.current && back.current.isConnected) back.current.focus(); };
  }, [open]);
  useEffect(() => {   // for as long as Watch is open, so a drawer closes from its first frame on; the Pause sheet's Escape comes first
    const onKey = event => {
      const sheet = document.getElementById('sheet');
      if (event.key === 'Escape' && store.inspect !== null && !event.defaultPrevented && !(sheet && !sheet.hidden)) { event.preventDefault(); set({inspect: null}); }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); if (store.inspect !== null) set({inspect: null}); };
  }, []);
  if (!entry) return null;
  const at = store.feed.filter(e => e.entry_kind === 'step');
  const i = at.findIndex(e => e.id === entry.id);
  const go = next => { if (next) set({inspect: next.id, ...(next.seq === null ? {} : {cursor: next.seq})}); };
  return html`<aside class="drawer" id="inspector" ref=${box} role="dialog" aria-modal="false" aria-label="Step inspector">
    <header><h2>Step ${entry.seq ?? '—'}</h2><span class="note">${entry.exact_step ? `decision ${entry.step_decision ?? '—'}` : `call decision ${entry.decision ?? '—'}`} · ${toolLabel(entry.tool)}</span><span class="gap"></span>
      <button type="button" class="btn" aria-label="Previous entry" disabled=${i <= 0} onClick=${() => go(at[i - 1])}>◀</button>
      <button type="button" class="btn" aria-label="Next entry" disabled=${i < 0 || i >= at.length - 1} onClick=${() => go(at[i + 1])}>▶</button>
      <button type="button" class="btn drawerclose" aria-label="Close the inspector" onClick=${() => set({inspect: null})}>Close</button></header>
    <${Body} entry=${entry} handoffs=${handoffs} /></aside>`;
}
