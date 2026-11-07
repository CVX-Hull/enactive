// ECharts wrapper and option builders. ECharts is vendored (web/vendor/echarts.js).
import * as echarts from '../vendor/echarts.js';
import {html, useEffect, useRef, css} from './ui.js';

export function palette() {
  const get = name => css(name);
  return {fg: get('--fg'), muted: get('--muted'), line: get('--line'), accent: get('--accent'), quiet: get('--quiet'),
    watch: get('--watch'), alert: get('--alert'), sunk: get('--sunk'), surface: get('--surface'), calc: get('--p-calc'),
    mono: get('--mono') || 'monospace'};
}

/** A chart that owns one ECharts instance. `option` should be memoised by the caller. */
export function Chart({option, label, className = '', onReady, epoch, tabindex, role = 'img', onKeyDown, extra = {}}) {
  const box = useRef(null), chart = useRef(null);
  useEffect(() => {
    const instance = echarts.init(box.current, null, {renderer: 'canvas'});
    chart.current = instance;
    const resize = () => instance.resize();
    addEventListener('resize', resize);
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null;
    if (observer) observer.observe(box.current);
    if (onReady) onReady(instance);
    return () => { removeEventListener('resize', resize); if (observer) observer.disconnect(); instance.dispose(); chart.current = null; };
  }, [epoch]);
  useEffect(() => { if (chart.current && option) chart.current.setOption(option); }, [option, epoch]);
  return html`<div class="chart ${className}" ref=${box} role=${role} aria-label=${label} tabindex=${tabindex} onKeyDown=${onKeyDown} ...${extra}></div>`;
}

/** ECharts renders tooltip strings as HTML, so every run, tool or key name goes through this first. */
export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

const axisBase = C => ({axisLine: {lineStyle: {color: C.line}}, axisLabel: {color: C.muted, fontFamily: C.mono, fontSize: 10}, splitLine: {show: false}});
const tooltipBase = C => ({backgroundColor: C.surface, borderColor: C.line, textStyle: {color: C.fg, fontSize: 11}});

/* ---------------------------------------------------------------- Supervise timeline */
export function timelineOption({steps, requests, markers, t0, cursorSeq}) {
  const C = palette(), base = axisBase(C);
  const rel = wall => (wall - t0) / 60;
  const clocked = steps.filter(s => s.game_time !== null && s.game_time !== undefined);
  const first = clocked.length ? clocked[0].game_time : 0;
  const clock = clocked.map(s => [rel(s.wall), (s.game_time - first) / 3600]);
  const mode = steps.map((s, k) => [rel(s.wall), rel(steps[k + 1] ? steps[k + 1].wall : s.wall + 7), s.mode === 'in_play' ? 1 : 0]);
  const writes = requests.map(r => [rel(r.wall), (r.cache_write || 0) / 1000]);
  let total = 0;
  const spend = requests.map(r => { total += r.dollars || 0; return [rel(r.wall), +total.toFixed(3)]; });
  const evictions = markers.filter(m => m.kind === 'context_eviction' && m.wall !== null).map(m => ({xAxis: rel(m.wall)}));
  const handoffs = markers.filter(m => m.kind === 'handoff' && m.wall !== null).map(m => ({xAxis: rel(m.wall), label: {show: true, formatter: 'handoff', color: C.muted, fontSize: 10}}));
  const cursor = steps.find(s => s.seq === cursorSeq) || steps[steps.length - 1];
  const xMax = Math.max(1, Math.ceil(Math.max(steps.length ? rel(steps[steps.length - 1].wall) : 1, ...(requests.length ? [rel(requests[requests.length - 1].wall)] : [0]))));
  const grids = [{top: 14, height: 100}, {top: 134, height: 20}, {top: 174, height: 80}, {top: 276, height: 46}];
  const yname = n => ({name: n, nameLocation: 'middle', nameRotate: 0, nameGap: 54, nameTextStyle: {color: C.muted, fontSize: 10, align: 'right'}});
  return {
    animation: false, aria: {enabled: true}, textStyle: {fontFamily: C.mono},
    axisPointer: {link: [{xAxisIndex: 'all'}], lineStyle: {color: C.muted}},
    tooltip: {trigger: 'axis', ...tooltipBase(C), formatter: ps => {
      const x = ps[0].axisValue;
      const s = steps.reduce((a, b) => (Math.abs(rel(b.wall) - x) < Math.abs(rel(a.wall) - x) ? b : a), steps[0]);
      return s ? `Step ${s.seq} · +${(+x).toFixed(1)} min<br>${s.mode === 'in_play' ? 'in play' : 'out of play'}<br>${esc((s.keys || []).join(' '))}` : '';
    }},
    grid: grids.map(g => ({...g, left: 96, right: 16})),
    xAxis: grids.map((g, k) => ({...base, type: 'value', gridIndex: k, min: 0, max: xMax, axisLabel: {...base.axisLabel, show: k === 3, formatter: v => `+${v} min`}})),
    yAxis: [{...base, gridIndex: 0, ...yname('Game h'), splitLine: {show: true, lineStyle: {color: C.line, opacity: 0.4}}},
      {...base, gridIndex: 1, min: 0, max: 1, axisLabel: {show: false}, ...yname('Mode')},
      {...base, gridIndex: 2, ...yname('Cache write k')}, {...base, gridIndex: 3, splitNumber: 2, ...yname('Spend $')}],
    dataZoom: [{type: 'slider', xAxisIndex: [0, 1, 2, 3], bottom: 4, height: 18, borderColor: C.line, textStyle: {color: C.muted}},
      {type: 'inside', xAxisIndex: [0, 1, 2, 3]}],
    series: [
      {id: 'clock', type: 'line', step: 'end', xAxisIndex: 0, yAxisIndex: 0, data: clock, symbol: 'none', lineStyle: {color: C.fg, width: 1.6},
        markLine: {silent: true, symbol: 'none', animation: false, lineStyle: {color: C.accent, width: 2}, label: {formatter: 'playhead', color: C.accent, fontSize: 10},
          data: cursor ? [{xAxis: rel(cursor.wall)}] : []}},
      {id: 'mode', type: 'custom', xAxisIndex: 1, yAxisIndex: 1, data: mode, renderItem: (p, api) => {
        const a = api.coord([api.value(0), 1]), b = api.coord([api.value(1), 0]), inplay = api.value(2);
        return {type: 'rect', shape: {x: a[0], y: a[1] + (inplay ? 0 : 4), width: Math.max(1, b[0] - a[0]), height: b[1] - a[1] - (inplay ? 0 : 8)}, style: {fill: inplay ? C.quiet : C.watch}};
      }},
      {id: 'writes', type: 'bar', xAxisIndex: 2, yAxisIndex: 2, data: writes, barWidth: 2, itemStyle: {color: C.calc},
        markLine: {silent: true, symbol: 'none', lineStyle: {color: C.watch, width: 1, type: 'dotted', opacity: 0.4}, label: {show: false}, data: evictions}},
      {id: 'spend', type: 'line', xAxisIndex: 3, yAxisIndex: 3, data: spend, symbol: 'none', lineStyle: {color: C.quiet, width: 1.5},
        markLine: {silent: true, symbol: 'none', lineStyle: {color: C.accent, type: 'dashed'}, data: handoffs}}],
  };
}
export function legendItems() {
  const C = palette();
  return [['Game clock', C.fg], ['In play (full bar)', C.quiet], ['Out of play (thin bar)', C.watch], ['Cache-write tokens per request', C.calc],
    ['Image eviction (dotted)', C.watch], ['Handoff (dashed)', C.accent], ['Spend', C.quiet]];
}
export function nearestStep(chart, steps, t0, x, y) {
  const point = chart.convertFromPixel({gridIndex: 0}, [x, y]);
  if (!point || Number.isNaN(point[0])) return null;
  let best = null, gap = Infinity;
  for (let i = 0; i < steps.length; i++) {
    const d = Math.abs((steps[i].wall - t0) / 60 - point[0]);
    if (d < gap) { gap = d; best = i; }
  }
  return best;
}

/* ---------------------------------------------------------------- Diagnose */
export function requestsOption(requests, markers, t0) {
  const C = palette();
  const rel = wall => (wall - t0) / 60;
  return {animation: false, aria: {enabled: true}, legend: {top: 0, textStyle: {color: C.fg}}, tooltip: {trigger: 'axis', ...tooltipBase(C)},
    grid: {left: 56, right: 16, top: 34, bottom: 30},
    xAxis: {type: 'value', axisLabel: {color: C.muted, formatter: v => `+${Math.round(v)} min`}, axisLine: {lineStyle: {color: C.line}}},
    yAxis: {type: 'value', axisLabel: {color: C.muted, formatter: v => `${v / 1000}k`}, splitLine: {lineStyle: {color: C.line, opacity: 0.4}}},
    series: [{name: 'Input tokens', type: 'line', data: requests.map(r => [rel(r.wall), (r.input_tokens + r.cache_read + r.cache_write)]), symbol: 'none', lineStyle: {color: C.quiet}},
      {name: 'Cache-write tokens', type: 'bar', barWidth: 2, data: requests.map(r => [rel(r.wall), r.cache_write]), itemStyle: {color: C.calc},
        markLine: {silent: true, symbol: 'none', lineStyle: {color: C.watch, type: 'dotted', opacity: 0.4}, label: {show: false},
          data: markers.filter(m => m.kind === 'context_eviction' && m.wall !== null).map(m => ({xAxis: rel(m.wall)}))}}]};
}

export function transitionsOption(tools, transitions, label) {
  const C = palette();
  const order = new Map(tools.map(t => [t.tool, t.calls]));
  const names = [...new Set(transitions.flatMap(t => [t[0], t[1]]))].sort((a, b) => (order.get(b) || 0) - (order.get(a) || 0));
  const max = Math.max(1, ...transitions.map(t => t[2]));
  return {animation: false, aria: {enabled: true},
    tooltip: {...tooltipBase(C), formatter: p => `${esc(label(names[p.value[1]]))} → ${esc(label(names[p.value[0]]))}: ${esc(p.value[2])}`},
    grid: {left: 110, right: 16, top: 10, bottom: 70},
    xAxis: {type: 'category', data: names.map(label), axisLabel: {color: C.muted, rotate: 40, fontSize: 10}, name: 'next', nameTextStyle: {color: C.muted}},
    yAxis: {type: 'category', inverse: true, data: names.map(label), axisLabel: {color: C.muted, fontSize: 10}, name: 'previous', nameTextStyle: {color: C.muted}},
    visualMap: {show: false, dimension: 3, min: 0, max: Math.log10(max + 1), inRange: {color: [C.sunk, C.accent]}},
    series: [{type: 'heatmap', data: transitions.map(([a, b, n]) => [names.indexOf(b), names.indexOf(a), n, Math.log10(n + 1)]),
      label: {show: true, color: C.fg, fontSize: 9, formatter: p => p.value[2]}}]};
}

/* ---------------------------------------------------------------- Improve and Compare */
export function dotsOption(arms, threshold, metricName) {
  const C = palette();
  const names = arms.map(a => a.arm);
  const data = [];
  arms.forEach((a, k) => a.runs.forEach(r => { if (r.target !== null && r.target !== undefined) data.push({value: [r.target, k], name: r.run}); }));
  return {animation: false, aria: {enabled: true}, grid: {left: 110, right: 20, top: 10, bottom: 34}, tooltip: {...tooltipBase(C), formatter: p => `${esc(p.name)}: ${esc(p.value[0])}`},
    xAxis: {type: 'value', name: metricName, nameLocation: 'middle', nameGap: 22, nameTextStyle: {color: C.muted}, axisLabel: {color: C.muted}, splitLine: {lineStyle: {color: C.line, opacity: 0.4}}},
    yAxis: {type: 'category', data: names, axisLabel: {color: C.fg}},
    series: [{type: 'scatter', symbolSize: 12, data, itemStyle: {color: p => (p.value[1] ? C.watch : C.accent)},
      markLine: threshold === null || threshold === undefined ? undefined : {silent: true, symbol: 'none', lineStyle: {color: C.muted, type: 'dashed'}, label: {formatter: String(threshold), color: C.muted}, data: [{xAxis: threshold}]}}]};
}

export function survivalOption(groups) {
  const C = palette();
  const colours = [C.fg, C.accent, C.watch, C.calc];
  const series = [];
  groups.forEach((g, k) => {
    const colour = colours[k % colours.length], km = g.curve || {times: [], survival: [], lower: []};
    series.push({name: g.name, type: 'line', step: 'end', data: km.times.map((t, i) => [t, km.survival[i]]), symbol: 'none', lineStyle: {color: colour, width: 2}, itemStyle: {color: colour}});
    series.push({name: g.name, type: 'line', step: 'end', data: km.times.map((t, i) => [t, km.lower[i]]), symbol: 'none', lineStyle: {color: colour, width: 1, type: 'dotted', opacity: 0.7}, tooltip: {show: false}});
  });
  return {animation: false, aria: {enabled: true}, legend: {top: 0, textStyle: {color: C.fg}, data: groups.map(g => g.name)},
    grid: {left: 48, right: 16, top: 34, bottom: 36}, tooltip: {trigger: 'item', ...tooltipBase(C)},
    xAxis: {type: 'value', name: 'game hours', nameLocation: 'middle', nameGap: 24, nameTextStyle: {color: C.muted}, axisLabel: {color: C.muted}, splitLine: {lineStyle: {color: C.line, opacity: 0.4}}},
    yAxis: {type: 'value', min: 0, max: 1, name: 'alive', nameTextStyle: {color: C.muted}, axisLabel: {color: C.muted}, splitLine: {lineStyle: {color: C.line, opacity: 0.4}}}, series};
}
