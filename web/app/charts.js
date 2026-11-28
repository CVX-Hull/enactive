// ECharts wrapper and option builders. ECharts is vendored (web/vendor/echarts.js).
import * as echarts from '../vendor/echarts.js';
import {html, useEffect, useRef, css, kilo} from './ui.js';

export function palette() {
  const get = name => css(name);
  return {fg: get('--fg'), muted: get('--muted'), line: get('--line'), accent: get('--accent'), quiet: get('--quiet'),
    watch: get('--watch'), alert: get('--alert'), sunk: get('--sunk'), surface: get('--surface'), calc: get('--violet'),
    series1: get('--series-1'), series2: get('--series-2'), teal: get('--teal'), mono: get('--mono') || 'monospace'};
}

/** A chart that owns one ECharts instance. `option` should be memoised by the caller. */
export function Chart({option, label, className = '', onReady, epoch}) {
  const box = useRef(null), chart = useRef(null);
  useEffect(() => {
    const instance = echarts.init(box.current, null, {renderer: 'canvas'});
    chart.current = instance;
    let raf = 0;
    const resize = () => {
      if (raf) return;
      raf = requestAnimationFrame(() => { raf = 0; if (chart.current) chart.current.resize(); });
    };
    addEventListener('resize', resize);
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null;
    if (observer) observer.observe(box.current);
    if (onReady) onReady(instance);
    return () => { if (raf) cancelAnimationFrame(raf); removeEventListener('resize', resize); if (observer) observer.disconnect(); instance.dispose(); chart.current = null; };
  }, [epoch]);
  useEffect(() => { if (chart.current && option) chart.current.setOption(option); }, [option, epoch]);
  return html`<div class="chart ${className}" ref=${box} role="img" aria-label=${label}></div>`;
}

/** ECharts renders tooltip strings as HTML, so every run, tool or key name goes through this first. */
export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

const tooltipBase = C => ({backgroundColor: C.surface, borderColor: C.line, textStyle: {color: C.fg, fontSize: 11}});
const valueAxis = (C, formatter) => ({type: 'value', axisLabel: {color: C.muted, fontSize: 10, formatter}, axisLine: {show: false}, axisTick: {show: false},
  splitLine: {lineStyle: {color: C.line, width: 1, opacity: 0.7}}});
const requestAxis = (C, range = {}) => ({type: 'value', ...range, name: 'request', nameLocation: 'middle', nameGap: 22, nameTextStyle: {color: C.muted, fontSize: 10},
  axisLabel: {color: C.muted, fontSize: 10}, axisLine: {lineStyle: {color: C.line}}, axisTick: {show: false}, splitLine: {show: false}});

/* ---------------------------------------------------------------- Diagnostics: context and spend */
/** A cut the curator did not keep up with: it removed turns no briefing covered (#1037), or it was a rescue. */
const uncovered = c => (c.uncovered_turns || 0) > 0 || c.cut_result === 'rescue';

/** Prompt tokens per player request, cached and uncached stacked: shaded bands where requests were held waiting for
 *  coverage, a teal line at each covered cut, an amber one at each uncovered cut, and a faint divider at each handoff. */
export function contextOption(requests, cuts, waits = [], handoffs = []) {
  const C = palette();
  const known = requests.filter(r => r.prompt_tokens !== null);   // one category per request: stacking needs a category axis
  const at = new Map(known.map((r, i) => [r.index, i]));
  // A wait or handoff may begin at a request drawn on no category (a recall, or one without usage): the next one drawn.
  const nearest = index => {
    if (index === null || index === undefined) return null;
    if (at.has(index)) return at.get(index);
    const next = known.findIndex(r => r.index >= index);
    return next < 0 ? (known.length ? known.length - 1 : null) : next;
  };
  const marked = cuts.filter(c => at.has(c.index));
  const byIndex = new Map(marked.map(c => [c.index, c]));
  const bands = waits.map(w => [nearest(w.start_index), w.active ? known.length - 1 : nearest(w.end_index ?? w.start_index), w]).filter(([a, b]) => a !== null && b !== null);
  const area = (name, data, color, extra) => ({name, type: 'line', stack: 'prompt', data, symbol: 'none', lineStyle: {color, width: 1}, itemStyle: {color},
    areaStyle: {color, opacity: 0.35}, emphasis: {disabled: true}, ...extra});
  const lines = (list, color, type, opacity = 0.95) => ({silent: true, symbol: 'none', animation: false, label: {show: false}, lineStyle: {color, width: 1.5, type, opacity}, data: list});
  return {animation: false, aria: {enabled: true}, textStyle: {fontFamily: 'system-ui, sans-serif'},
    legend: {top: 0, left: 0, icon: 'rect', itemWidth: 12, itemHeight: 8, textStyle: {color: C.fg, fontSize: 11}, data: ['Cache read', 'Not cached']},
    grid: {left: 48, right: 14, top: 30, bottom: 36},
    tooltip: {trigger: 'axis', ...tooltipBase(C), axisPointer: {lineStyle: {color: C.muted}}, formatter: ps => {
      const r = known[ps[0].dataIndex];
      if (!r) return '';
      const cut = byIndex.get(r.index);
      const wait = bands.find(([a, b]) => ps[0].dataIndex >= a && ps[0].dataIndex <= b);
      return `<b>${esc(r.request_id)}</b>${r.seq === null ? '' : ` · step ${esc(r.seq)}`}<br>${esc(kilo(r.prompt_tokens))} prompt tokens<br>${esc(kilo(r.cache_read))} cache read`
        + `${cut ? `<br>${uncovered(cut) ? 'uncovered cut' : 'cut'}: ${esc(kilo(cut.tokens_before))} → ${esc(kilo(cut.tokens_after))} (${esc(cut.removed_turns)} turns${cut.uncovered_turns ? `, ${esc(cut.uncovered_turns)} uncovered` : ''})` : ''}`
        + `${wait ? `<br>coverage wait: ${esc(wait[2].requests)} requests held${wait[2].active ? ', still waiting' : ''}` : ''}`;
    }},
    xAxis: {...requestAxis(C), type: 'category', boundaryGap: false, data: known.map(r => r.index), axisLabel: {color: C.muted, fontSize: 10, interval: Math.ceil(known.length / 8) - 1}},
    yAxis: valueAxis(C, v => (v >= 1000 ? `${v / 1000}k` : v)),
    series: [area('Cache read', known.map(r => r.cache_read || 0), C.series1, {
        markArea: {silent: true, itemStyle: {color: C.watch, opacity: 0.16}, data: bands.map(([a, b]) => [{xAxis: a}, {xAxis: b}])},
        markLine: lines(handoffs.map(h => nearest(h.index)).filter(i => i !== null).map(i => ({xAxis: i})), C.muted, 'dotted', 0.7)}),
      area('Not cached', known.map(r => r.prompt_tokens - (r.cache_read || 0)), C.series2, {
        markLine: lines(marked.map(c => (uncovered(c) ? {xAxis: at.get(c.index), name: 'uncovered', lineStyle: {color: C.watch, type: 'solid', width: 2}}
          : {xAxis: at.get(c.index), name: 'covered'})), C.teal, 'dashed')})]};
}

/** Cumulative spend by request: the provider's own figure where any is recorded, else the configured-rate estimate.
 *  Each curator session is marked at the request nearest its start, with what it cost. */
export function spendOption(requests, limit, sessions = []) {
  const C = palette();
  const reported = requests.some(r => r.reported_cost_usd !== null);
  let total = 0;
  const points = requests.map(r => {
    total += reported ? Number(r.reported_cost_usd || 0) : r.estimated_dollars || 0;
    return [r.index, +total.toFixed(6)];
  });
  const near = typeof limit === 'number' && total >= limit * 0.5;   // a far-off limit would flatten the curve
  const placed = sessions.filter(s => typeof s.started_wall === 'number').map(s => {
    let k = requests.findIndex(r => typeof r.wall === 'number' && r.wall >= s.started_wall);
    if (k < 0) k = points.length - 1;
    return k < 0 ? null : {coord: points[k], session: s};
  }).filter(Boolean);
  return {animation: false, aria: {enabled: true}, textStyle: {fontFamily: 'system-ui, sans-serif'}, grid: {left: 52, right: 18, top: 16, bottom: 36},
    tooltip: {trigger: 'axis', ...tooltipBase(C), axisPointer: {lineStyle: {color: C.muted}}, formatter: ps => `request ${esc(ps[0].value[0])}<br>$${esc(ps[0].value[1].toFixed(4))}`},
    xAxis: requestAxis(C, {min: 0, max: points.length ? points[points.length - 1][0] : 1}),
    yAxis: {...valueAxis(C, v => `$${+v.toFixed(2)}`), ...(near ? {max: Math.ceil(limit)} : {})},
    series: [{name: 'Player', type: 'line', data: points, symbol: 'none', lineStyle: {color: C.series1, width: 2}, itemStyle: {color: C.series1}, areaStyle: {color: C.series1, opacity: 0.1},
      markPoint: points.length ? {symbol: 'circle', symbolSize: 8, itemStyle: {color: C.series1, borderColor: C.surface, borderWidth: 2},
        data: [{coord: points[points.length - 1], name: 'total'}, ...placed.map(p => ({coord: p.coord, name: `curator ${p.session.session_kind || 'session'}`, symbol: 'diamond', symbolSize: 10,
          itemStyle: {color: C.calc, borderColor: C.surface, borderWidth: 1}, label: {show: false}}))],
        label: {show: true, position: 'left', color: C.fg, fontSize: 11, formatter: `$${total.toFixed(2)}`}} : undefined,
      markLine: near ? {silent: true, symbol: 'none', animation: false, lineStyle: {color: C.muted, width: 1, type: 'dashed'}, label: {position: 'insideStartTop', color: C.muted, fontSize: 10, formatter: `limit $${limit}`}, data: [{yAxis: limit}]} : undefined}]};
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
    visualMap: {show: false, dimension: 3, min: 0, max: Math.log10(max + 1), inRange: {color: [C.sunk, C.series1]}},
    series: [{type: 'heatmap', data: transitions.map(([a, b, n]) => [names.indexOf(b), names.indexOf(a), n, Math.log10(n + 1)]),
      label: {show: true, color: C.fg, fontSize: 9, formatter: p => p.value[2]}}]};
}

/* ---------------------------------------------------------------- across runs */
export function dotsOption(arms, threshold, metricName) {
  const C = palette();
  const names = arms.map(a => a.arm);
  const data = [];
  arms.forEach((a, k) => a.runs.forEach(r => { if (r.target !== null && r.target !== undefined) data.push({value: [r.target, k], name: r.run}); }));
  return {animation: false, aria: {enabled: true}, grid: {left: 110, right: 20, top: 10, bottom: 34}, tooltip: {...tooltipBase(C), formatter: p => `${esc(p.name)}: ${esc(p.value[0])}`},
    xAxis: {type: 'value', name: metricName, nameLocation: 'middle', nameGap: 22, nameTextStyle: {color: C.muted}, axisLabel: {color: C.muted}, splitLine: {lineStyle: {color: C.line, opacity: 0.4}}},
    yAxis: {type: 'category', data: names, axisLabel: {color: C.fg}},
    series: [{type: 'scatter', symbolSize: 12, data, itemStyle: {color: p => (p.value[1] ? C.series2 : C.series1)},
      markLine: threshold === null || threshold === undefined ? undefined : {silent: true, symbol: 'none', lineStyle: {color: C.muted, type: 'dashed'}, label: {formatter: String(threshold), color: C.muted}, data: [{xAxis: threshold}]}}]};
}

export function survivalOption(groups) {
  const C = palette();
  const colours = [C.series1, C.series2, C.teal, C.calc];
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
