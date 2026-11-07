// Shared UI pieces: htm bound to Preact, provenance chips, formatting, small components.
import {h, render, Fragment, createPortal} from '../vendor/preact.js';
import htm from '../vendor/htm.js';
export {h, render, Fragment, createPortal};
export {useState, useEffect, useRef, useMemo, useCallback} from '../vendor/hooks.js';
export const html = htm.bind(h);

/* ---------------------------------------------------------------- provenance */
const KINDS = {
  recorded: ['rec', 'recorded'], read: ['read', 'read'], derived: ['calc', 'derived'],
  player_claim: ['claim', 'player claim'], claim: ['claim', 'player claim'], human: ['human', 'human'],
  example: ['ex', 'example'],
};
/** One chip per interpretive value: the word is the API's `source`, the hue repeats it. */
export function Pv({source, detail}) {
  const [kind, word] = KINDS[source] || ['unk', source ? String(source) : 'no source'];
  return html`<span class="pv ${kind}">${word}${detail ? html` <small>${detail}</small>` : null}</span>`;
}
const VALIDATION = {passes: 'passes floor', below_floor: 'below floor', fails_floor: 'fails floor'};
export const validationText = status => (status ? VALIDATION[status] || String(status) : '');
export function ReadChip({reading}) {
  const bits = [];
  if (typeof reading.confidence === 'number') bits.push(`${Math.round(reading.confidence * 100)}%`);
  if (reading.validation) bits.push(validationText(reading.validation));
  return html`<${Pv} source=${reading.source || 'read'} detail=${bits.join(' · ')} />`;
}

/* ---------------------------------------------------------------- formatting */
export const fmtH = x => (x === null || x === undefined ? '—' : Number(x).toFixed(2));
export const fmtMoney = (x, digits = 2) => (x === null || x === undefined ? '—' : `$${Number(x).toFixed(digits)}`);
export const pct = (x, digits = 0) => (x === null || x === undefined ? '—' : `${(x * 100).toFixed(digits)}%`);
export const trim = x => (x === null || x === undefined ? '—' : Number.isInteger(x) ? String(x) : String(+Number(x).toFixed(3)));
export const bytes = b => (b === null || b === undefined ? '—' : b >= 1e6 ? `${(b / 1e6).toFixed(2)} MB` : `${(b / 1e3).toFixed(1)} KB`);
export const mmss = seconds => `+${Math.floor(seconds / 60)}:${String(Math.round(seconds % 60)).padStart(2, '0')}`;
export const shortId = id => (typeof id === 'string' && id.length > 12 ? `${id.slice(0, 8)}…` : id);
export const runName = run => (run ? run.label || shortId(run.run) : '—');
export function median(values) {
  const sorted = values.filter(v => v !== null && v !== undefined).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const mid = sorted.length / 2;
  return sorted.length % 2 ? sorted[Math.floor(mid)] : (sorted[mid - 1] + sorted[mid]) / 2;
}
export function quantile(values, p) {
  const sorted = values.filter(v => v !== null && v !== undefined).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const at = (sorted.length - 1) * p, lo = Math.floor(at), hi = Math.ceil(at);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (at - lo);
}
export const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/* ---------------------------------------------------------------- components */
export function Panel({title, note, span = 's12', children, className = ''}) {
  return html`<section class="panel interp ${span} ${className}">
    ${title ? html`<header><h2>${title}</h2>${note ? html`<span class="note">${note}</span>` : null}</header>` : null}
    ${children}</section>`;
}
export const Insufficient = ({children}) => html`<div class="insuf">${children}</div>`;
export const Callout = ({children}) => html`<div class="callout">${children}</div>`;

/** Waiting or unavailable placeholder for a viewer-backed panel that has no data yet. */
export function Waiting({store, what = 'data', error}) {
  if (!store.viewerOk) return html`<div class="insuf" role="status">Viewer unavailable. ${what} will appear when it returns.</div>`;
  if (error) return html`<div class="insuf" role="status">${error.message}</div>`;
  return html`<div class="insuf" role="status">Loading ${what}…</div>`;
}

export function Table({columns, rows, onPick, selected, empty = 'Nothing recorded.'}) {
  if (!rows.length) return html`<${Insufficient}>${empty}<//>`;
  return html`<div class="scroll"><table class="data"><thead><tr>${columns.map(c => html`<th class=${c.num ? 'num' : ''}>${c.title}</th>`)}</tr></thead>
    <tbody>${rows.map((row, i) => html`<tr class=${selected === i ? 'sel' : ''}>${columns.map((c, k) => html`<td class="${c.num ? 'num' : ''} ${c.wrap ? 'wrapcell' : ''}">${
      onPick && k === 0 ? html`<button type="button" class="link" aria-pressed=${selected === i} onClick=${() => onPick(i, row)}>${c.render ? c.render(row, i) : row[c.key]}</button>` : c.render ? c.render(row, i) : row[c.key]}</td>`)}</tr>`)}</tbody></table></div>`;
}

export const Verdict = ({verdict}) => {
  const map = {moved: ['moved', 'moved'], wrong_way: ['worse', 'moved the wrong way'],
    no_effect_detected: ['', 'no effect detected'], untested: ['untested', 'untested']};
  const [klass, text] = map[verdict] || ['', verdict || 'unrated'];
  return html`<span class="verdict ${klass}">${text}</span>`;
};
