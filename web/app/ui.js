// Shared UI pieces: htm bound to Preact, provenance chips, formatting, small components.
import {h, render, Fragment, createPortal} from '../vendor/preact.js';
import htm from '../vendor/htm.js';
import {useState as useStateHook, useRef as useRefHook, useLayoutEffect as useLayoutEffectHook} from '../vendor/hooks.js';
export {h, render, Fragment, createPortal};
export {useState, useEffect, useLayoutEffect, useRef, useMemo, useCallback} from '../vendor/hooks.js';
export const html = htm.bind(h);

/* ---------------------------------------------------------------- provenance */
const KINDS = {
  recorded: ['rec', 'recorded'], read: ['read', 'read'], derived: ['calc', 'derived'],
  player_claim: ['claim', 'player claim'], claim: ['claim', 'player claim'], human: ['human', 'human'],
  example: ['ex', 'example'], harness: ['rec', 'recorded'], reader: ['read', 'read'],
};
/** One chip per interpretive value: the word is the API's `source`, the hue repeats it. */
export function Pv({source, detail}) {
  const [kind, word] = KINDS[source] || ['unk', source ? String(source) : 'no source'];
  return html`<span class="pv ${kind}">${word}${detail ? html` <small>${detail}</small>` : null}</span>`;
}
/** Held-out validation of a reader: `{pass, accuracy, n, floor}` or null when the reader has none. */
export function validationText(check) {
  if (!check) return 'not validated';
  return check.pass === true ? 'passes floor' : check.pass === false ? 'below floor' : 'unmeasured';
}
/** Beside a metric's provenance chip: `validated` is false when a reader the value depends on has no passing validation. */
export function Unvalidated({metric}) {
  return metric.validated === false ? html` <span class="state watch" title="A reader this value depends on has not passed held-out validation">unvalidated</span>` : null;
}
export function readingNote(reading) {
  const bits = [];
  if (typeof reading.confidence === 'number') bits.push(`${Math.round(reading.confidence * 100)}%`);
  bits.push(validationText(reading.validation));
  return bits.join(' · ');
}
export const ReadChip = ({reading}) => html`<${Pv} source="read" detail=${readingNote(reading)} />`;

/* ---------------------------------------------------------------- formatting */
export const fmtH = x => (x === null || x === undefined ? '—' : Number(x).toFixed(2));
export const fmtMoney = (x, digits = 2) => (x === null || x === undefined ? '—' : `$${Number(x).toFixed(digits)}`);
export const pct = (x, digits = 0) => (x === null || x === undefined ? '—' : `${(x * 100).toFixed(digits)}%`);
export const trim = x => (x === null || x === undefined ? '—' : Number.isInteger(x) ? String(x) : String(+Number(x).toFixed(3)));
export const bytes = b => (b === null || b === undefined ? '—' : b >= 1e6 ? `${(b / 1e6).toFixed(2)} MB` : `${(b / 1e3).toFixed(1)} KB`);
/** Token counts in thousands, one decimal from 1,000 up. */
export const kilo = n => (n === null || n === undefined ? '—' : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));
export const count = n => (n === null || n === undefined ? '—' : Number(n).toLocaleString('en-US'));
export const plural = (n, noun) => `${count(n)} ${noun}${n === 1 ? '' : 's'}`;
export const mmss = seconds => `+${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
export const shortId = id => (typeof id === 'string' && id.length > 12 ? `${id.slice(0, 8)}…` : id);
export const runName = run => (run ? shortId(run.run) : '—');
export const clockTime = ms => new Date(ms).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'});
/** Game time is whole seconds from the game's epoch; the day counts from 1. */
export function gameClock(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  const day = Math.floor(seconds / 86400) + 1, rest = seconds % 86400;
  return `day ${day}, ${String(Math.floor(rest / 3600)).padStart(2, '0')}:${String(Math.floor(rest % 3600 / 60)).padStart(2, '0')}`;
}
/** One input as a person reads it: `key:ENTER` is ENTER, typed text is quoted, anything else keeps its kind. */
export function keyText(key) {
  if (key.startsWith('key:')) return key.slice(4);
  if (key.startsWith('text:')) return `“${key.slice(5)}”`;
  if (key.startsWith('wait:')) return `wait ${key.slice(5)}`;
  return key;
}
/** One comparable number from a stored metric value (mirrors the viewer's own reduction). */
export function scalar(value) {
  if (typeof value === 'boolean') return Number(value);
  if (typeof value === 'number') return value;
  if (value && typeof value === 'object') for (const key of ['hours', 'value', 'count']) if (typeof value[key] === 'number') return value[key];
  return null;
}
export const label = text => String(text).replace(/_/g, ' ');
/** Any recorded value as words: numbers trimmed, a list or an object as its parts, never raw JSON or `null`. */
export function plainValue(value, depth = 0) {
  if (value === null || value === undefined) return 'none';
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'number') return Math.abs(value) >= 100 ? count(Math.round(value)) : trim(+value.toFixed(3));
  if (typeof value === 'string') return label(value);
  if (Array.isArray(value)) return value.length ? value.slice(0, 8).map(v => plainValue(v, depth + 1)).join(', ') + (value.length > 8 ? ` +${value.length - 8}` : '') : 'none';
  if (depth > 1) return '…';
  const parts = Object.entries(value).filter(([, v]) => v !== null && v !== undefined && !(Array.isArray(v) && !v.length));
  return parts.length ? parts.map(([k, v]) => `${label(k)} ${plainValue(v, depth + 1)}`).join(' · ') : 'none';
}
/** Seconds as a short duration: `42 s`, `3 m 05 s`, `1 h 02 m`. */
export function secs(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—';
  const s = Math.max(0, Math.round(Number(value)));
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} m ${String(s % 60).padStart(2, '0')} s`;
  return `${Math.floor(s / 3600)} h ${String(Math.floor(s % 3600 / 60)).padStart(2, '0')} m`;
}
/** A recorded decimal amount (the provider's own text) at cents, or a dash. */
export const usd2 = text => (text === null || text === undefined || text === '' || !Number.isFinite(Number(text)) ? '—' : `$${Number(text).toFixed(2)}`);
/** Actors as the trace numbers them: `001`, `002`, in the order they first appear. */
export const actorNumber = index => String(index + 1).padStart(3, '0');
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

/** A closed section whose body mounts (and fetches) only once it is opened. `open` opens it from a link. */
export function Disclosure({id, title, note, open = false, children}) {
  const [shown, setShown] = useStateHook(open);
  const visible = shown || open;
  return html`<details class="disclosure s12" id=${id} open=${visible} onToggle=${e => { if (e.target === e.currentTarget) setShown(e.currentTarget.open); }}>
    <summary><span class="dtitle">${title}</span>${note ? html`<span class="note">${note}</span>` : null}</summary>
    ${visible ? html`<div class="grid dbody">${children()}</div>` : null}</details>`;
}

/** One choice of several, as a row of pressed buttons. */
export function Segmented({label: aria, options, value, onChange, className = ''}) {
  return html`<span class="seg ${className}" role="group" aria-label=${aria}>${options.map(o => html`<button type="button" id=${o.id} data-value=${o.value}
    aria-pressed=${o.value === value} title=${o.title} disabled=${o.disabled} onClick=${() => onChange(o.value)}>${o.text}${o.count !== undefined ? html` <span class="n">${o.count}</span>` : null}</button>`)}</span>`;
}

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

/** A row of parts whose widths are shares of their sum. Widths and colours go through the DOM style object: the page
 *  policy forbids inline style attributes. `parts` is [{key, value, title, colour}] with colour a CSS custom property. */
export function ShareBar({parts, label: aria, className = ''}) {
  const box = useRefHook(null);
  const sum = parts.reduce((a, p) => a + (p.value || 0), 0) || 1;
  useLayoutEffectHook(() => {
    const spans = box.current ? box.current.children : [];
    parts.forEach((p, i) => {
      const node = spans[i];
      if (!node) return;
      node.style.width = `${((p.value || 0) / sum * 100).toFixed(2)}%`;
      node.style.background = `var(${p.colour})`;
    });
  });
  return html`<div class="sharebar ${className}" ref=${box} role="img" aria-label=${aria}>${parts.map(p => html`<span key=${p.key} title=${p.title}></span>`)}</div>`;
}
/** A colour swatch for a legend, coloured through the DOM style object. */
export function Swatch({colour}) {
  const node = useRefHook(null);
  useLayoutEffectHook(() => { if (node.current) node.current.style.background = `var(${colour})`; }, [colour]);
  return html`<i class="swatch" ref=${node}></i>`;
}

export function SubNav({tabs, base, current, label: aria, id}) {
  return html`<nav class="subnav" id=${id} aria-label=${aria}>${tabs.map(([key, text]) => html`<a href=${`#${base}/${key}`} data-sub=${key} aria-current=${current === key ? 'page' : null}>${text}</a>`)}</nav>`;
}

export const Verdict = ({verdict}) => {
  const map = {moved: ['moved', 'moved'], wrong_way: ['worse', 'moved the wrong way'],
    no_effect_detected: ['', 'no effect detected'], untested: ['untested', 'untested']};
  const [klass, text] = map[verdict] || ['', verdict || 'unrated'];
  return html`<span class="verdict ${klass}">${text}</span>`;
};
