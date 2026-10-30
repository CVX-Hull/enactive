/* The same passive reader mounts in the live shell and the generated recorded HTML. */
(function (global) {
  'use strict';
  const KINDS = ['request', 'tool', 'program', 'operation', 'native', 'source', 'statement', 'observer'];
  const PIXEL_BUDGET = 64 * 1024 * 1024;
  const short = value => value === null ? 'unavailable' : value.length > 28 ? `${value.slice(0, 12)}…${value.slice(-6)}` : value;
  const duration = ms => ms === null ? 'unavailable' : ms >= 1000 ? `${(ms / 1000).toFixed(3)}s` : `${ms.toFixed(3)}ms`;
  let nextMount = 0;
  function mount(root, options = {}) {
    const doc = root.ownerDocument || document;
    const prefix = `investigation-${++nextMount}`;
    let destroyed = false, worker = null, workerBlob = null, watchdog = null, generation = 0;
    let model = null, caseIndex = 0, selectedId = null, page = 0, pageToken = 0, interval = null;
    let imageGeneration = 0, decoding = null, displayed = null, wantedImage = null;
    root.classList.add('investigation-reader');
    function el(tag, text, className) {
      const node = doc.createElement(tag);
      if (text !== undefined) node.textContent = text;
      if (className) node.className = className;
      return node;
    }
    function append(parent, ...nodes) { parent.append(...nodes); return parent; }
    function button(text, action, className) {
      const node = el('button', text, className); node.type = 'button'; node.addEventListener('click', action); return node;
    }
    function field(label, input, suffix) {
      input.id = `${prefix}-${suffix}`;
      const wrap = el('label', undefined, 'ir-field'); wrap.htmlFor = input.id;
      const title = el('span', label); title.id = `${input.id}-label`;
      input.setAttribute('aria-labelledby', title.id);
      return append(wrap, title, input);
    }
    function details(title, body) { return append(el('details'), el('summary', title), body); }
    function json(value) { return el('pre', JSON.stringify(value, null, 2)); }
    function status(text, error = false) { state.textContent = text; state.classList.toggle('ir-error', error); }
    const heading = append(el('div', undefined, 'ir-heading'), el('div', 'RECORDED EVIDENCE', 'ir-eyebrow'),
      el('h2', 'Investigate an interval'), el('p', 'Original records, public statements and attributed assessments. Imported evidence never controls the current player.', 'ir-muted'));
    const file = el('input'); file.type = 'file'; file.accept = '.json,application/json';
    file.addEventListener('change', () => { if (file.files[0]) loadFile(file.files[0]); });
    const cancel = button('Cancel import', () => { stopWorker(); status('Import cancelled. Select a recorded bundle to continue.'); cancel.disabled = true; });
    cancel.disabled = true;
    const state = el('p', 'Select a closed-case investigation JSON bundle (up to 16 MiB).', 'ir-status');
    state.setAttribute('role', 'status'); state.setAttribute('aria-live', 'polite');
    const importBar = append(el('div', undefined, 'ir-import'), field('Import recorded bundle', file, 'file'), cancel);
    const content = el('div', undefined, 'ir-content'); content.hidden = true;
    const scope = el('select');
    scope.addEventListener('change', () => { caseIndex = Number(scope.value); selectedId = null; page = 0; interval = null; renderCase(); });
    const scopeFact = el('p', '', 'ir-muted');
    const scopeBar = append(el('div', undefined, 'ir-scope'), field('Recorded case', scope, 'scope'), scopeFact);
    const summary = el('div', undefined, 'ir-summary');
    const assessmentSummary = el('section', undefined, 'ir-assessment-summary');
    const chart = el('div', undefined, 'ir-chart');
    const chartNote = el('p', '', 'ir-muted');
    const timingSummary = el('p', '', 'ir-timing');
    const from = el('input'); from.type = 'number'; from.step = 'any'; from.min = '0';
    const to = el('input'); to.type = 'number'; to.step = 'any'; to.min = '0';
    const intervalState = el('p', '', 'ir-muted'); intervalState.setAttribute('role', 'status');
    const apply = button('Select interval', () => {
      const bounds = model.indexes[caseIndex].bounds;
      const a = from.value === '' ? NaN : Number(from.value), b = to.value === '' ? NaN : Number(to.value);
      const extent = bounds ? (bounds[1] - bounds[0]) / 1000 : 0;
      if (!bounds || !Number.isFinite(a) || !Number.isFinite(b) || a < 0 || b < a || b > extent) {
        intervalState.textContent = 'Enter finite start/end seconds inside the case, with end at or after start.'; return;
      }
      interval = [bounds[0] + a * 1000, bounds[0] + b * 1000]; page = 0;
      intervalState.textContent = `Selected ${a}–${b} seconds. Rows without a valid recorded timestamp or span are excluded; original fields remain available in the whole case.`;
      renderChart(); requestPage();
    });
    const clearIntervalButton = button('Whole case', () => { interval = null; page = 0; setIntervalFields(); renderChart(); requestPage(); });
    const intervalBar = append(el('div', undefined, 'ir-interval'), field('Start (seconds)', from, 'from'),
      field('End (seconds)', to, 'to'), apply, clearIntervalButton);
    const kind = el('select'); append(kind, newOption('Every record kind', ''));
    for (const value of KINDS) kind.append(newOption(value, value));
    const search = el('input'); search.type = 'search'; search.placeholder = 'ID, actor or retained text'; search.maxLength = 4000;
    const filterChange = () => { page = 0; requestPage(); };
    kind.addEventListener('change', filterChange); search.addEventListener('input', filterChange);
    const filterBar = append(el('div', undefined, 'ir-filters'), field('Record kind', kind, 'kind'), field('Find exact records', search, 'search'));
    const rows = el('ol', undefined, 'ir-rows');
    const pageInfo = el('p', '', 'ir-muted'); pageInfo.setAttribute('role', 'status');
    const previous = button('Previous', () => { page--; requestPage(); });
    const next = button('Next', () => { page++; requestPage(); });
    const paging = append(el('div', undefined, 'ir-paging'), previous, pageInfo, next);
    const records = append(el('section', undefined, 'ir-records'), el('h3', 'Exact records'), filterBar, rows, paging);
    const inspectHeading = el('h3', 'Original evidence');
    const inspect = el('div');
    const sourceSelect = el('select');
    sourceSelect.addEventListener('change', () => showSource(sourceSelect.value));
    const frame = el('div', undefined, 'ir-frame'); frame.tabIndex = 0; frame.setAttribute('aria-label', 'Original recorded image; scroll to inspect full size');
    const frameNote = el('p', '', 'ir-muted'); frameNote.setAttribute('role', 'status');
    const actual = el('input'); actual.type = 'checkbox';
    actual.addEventListener('change', () => frame.classList.toggle('ir-actual-pixels', actual.checked));
    const sourceFacts = el('div');
    const inspector = append(el('section', undefined, 'ir-inspector'), inspectHeading, inspect,
      el('h4', 'Original image'), field('Exact source ID', sourceSelect, 'source'),
      field('Actual pixels (scroll image)', actual, 'actual'), frameNote, frame, sourceFacts);
    const caseDetails = el('div', undefined, 'ir-case-details');
    append(content, scopeBar, assessmentSummary, summary, chartNote, chart, intervalBar, intervalState, timingSummary,
      append(el('div', undefined, 'ir-layout'), records, inspector), caseDetails);
    root.replaceChildren(heading, importBar, state, content);
    function newOption(text, value) { const option = el('option', text); option.value = value; return option; }
    function currentCase() { return model.cases[caseIndex]; }
    function stopWorker() {
      ++generation; ++pageToken;
      if (worker) worker.terminate(); worker = null;
      if (watchdog !== null) global.clearTimeout(watchdog); watchdog = null;
      if (workerBlob) global.URL.revokeObjectURL(workerBlob); workerBlob = null;
    }
    function loadFile(selectedFile) { return load({file: selectedFile}); }
    function load(payload) {
      if (destroyed) return;
      stopWorker(); clearImage(); model = null; content.hidden = true; cancel.disabled = false;
      status('Validating recorded evidence in a dedicated worker…');
      const version = generation;
      try {
        let url = options.workerURL;
        if (typeof options.workerSource === 'string') {
          workerBlob = global.URL.createObjectURL(new Blob([options.workerSource], {type: 'text/javascript'})); url = workerBlob;
        }
        if (!url) throw new Error('A workerURL or workerSource is required.');
        worker = new global.Worker(url);
        const importing = worker;
        importing.onmessage = ({data}) => {
          if (destroyed || version !== generation || importing !== worker) return;
          if (data.type === 'loaded') {
            global.clearTimeout(watchdog); watchdog = null; cancel.disabled = true;
            model = data.model; caseIndex = 0; selectedId = null; page = 0; interval = null;
            scope.replaceChildren(...model.cases.map((c, i) => newOption(c.title || c.id, String(i)))); scope.value = '0';
            content.hidden = false; status(`Loaded ${model.cases.length} recorded case(s). Integrity checks establish internal consistency, not trusted authorship.`);
            renderCase();
          } else if (data.type === 'page' && data.token === pageToken) renderRows(data);
          else if (data.type === 'error') { stopWorker(); clearImage(); content.hidden = true; cancel.disabled = true; status(`Recorded evidence unavailable: ${data.message}`, true); }
        };
        importing.onerror = () => { if (version === generation) { stopWorker(); cancel.disabled = true; status('Recorded evidence unavailable: worker failed.', true); } };
        watchdog = global.setTimeout(() => { if (version === generation) { stopWorker(); cancel.disabled = true; status('Recorded evidence unavailable: import exceeded 30 seconds.', true); } }, 30000);
        importing.postMessage({type: 'load', ...payload});
      } catch (error) { stopWorker(); cancel.disabled = true; status(`Recorded evidence unavailable: ${error.message}`, true); }
    }
    function setIntervalFields() {
      const bounds = model.indexes[caseIndex].bounds;
      from.value = '0'; to.value = bounds ? String((bounds[1] - bounds[0]) / 1000) : '';
      from.max = to.max = to.value; from.disabled = to.disabled = apply.disabled = !bounds;
      intervalState.textContent = 'Whole recorded case. Missing or invalid clocks remain available in the exact rows.';
    }
    function renderCase() {
      const c = currentCase(), index = model.indexes[caseIndex];
      const assessment = c.assessments[0];
      assessmentSummary.replaceChildren(...(assessment ? [el('h3', assessment.label),
        el('p', `Attributed interpretation · ${assessment.attribution ?? 'unavailable'}`, 'ir-muted'),
        el('p', assessment.text, 'ir-retained-text'), el('p', assessment.reference ?? 'Reference unavailable', 'ir-muted')] :
        [el('p', 'No reviewed outcome/interpretation selected in this bundle. Recorded completion is not gameplay success.', 'ir-muted')]));
      scopeFact.textContent = `Recorded session ${short(c.session)} · source ${c.source_commit?.slice(0, 8) ?? 'unavailable'} · full provenance below`;
      summary.replaceChildren(el('span', `${c.events.length} retained records`), el('span', `${c.sources.length} selected image entries`),
        el('span', `${index.unplottedIds.length} records without plotted time`), el('span', `${index.danglingLinks} unavailable linked records`));
      setIntervalFields(); renderChart();
      sourceSelect.replaceChildren(newOption('Select original source', ''), ...c.sources.map(s => newOption(s.source_id, s.source_id)));
      sourceSelect.value = ''; clearImage(); sourceFacts.replaceChildren(); frameNote.textContent = 'Select an original source. Unselected source IDs have no bytes in this bundle.';
      inspect.replaceChildren(el('p', 'Select a record to inspect its original fields and explicit links.', 'ir-muted'));
      caseDetails.replaceChildren(details('Coverage and original omissions', json(c.coverage)),
        details('Original case / actor provenance', json({id: c.id, session: c.session, source_commit: c.source_commit, configuration: c.configuration})),
        details('Usage and cost details — estimates / reservations, not an invoice', json(c.accounting)));
      const notes = el('div');
      for (const a of c.assessments) {
        const article = append(el('article'), el('h4', a.label), el('p', a.text, 'ir-retained-text'),
          el('p', `Attribution: ${a.attribution ?? 'unavailable'} · Reference: ${a.reference ?? 'unavailable'}`, 'ir-muted'));
        for (const id of a.evidence_ids) article.append(linkButton(id));
        notes.append(article);
      }
      if (!c.assessments.length) notes.append(el('p', 'No existing assessments selected.', 'ir-muted'));
      caseDetails.append(details('Attributed assessments / player claims (fallible)', notes));
      requestPage();
    }
    function requestPage() {
      if (!worker || !model) return;
      worker.postMessage({type: 'page', caseIndex, token: ++pageToken,
        filters: {page, kind: kind.value, query: search.value, start: interval ? interval[0] : null, end: interval ? interval[1] : null}});
    }
    function renderRows(data) {
      page = data.page;
      const t = data.timing;
      const seconds = n => `${(n / 1000).toFixed(3)}s`;
      timingSummary.textContent = t ? `Selected wall interval ${seconds(t.elapsed_ms)} · request union ${seconds(t.request_wall_union_ms)} · tool union ${seconds(t.tool_wall_union_ms)} · overlap ${seconds(t.overlap_ms)} · uncovered by those spans ${seconds(t.uncovered_ms)}. ${t.no_full_wall_span} request/tool records lack a full wall span in this case. Kind/text filters affect exact rows only. These are observed wall intervals, not server inference, idle time or useful-goal latency.` : 'No bounded timing summary available. Missing clocks remain unknown.';
      rows.replaceChildren(...data.rows.map(e => {
        const item = el('li');
        const choose = button(`${e.label || e.kind} · ${short(e.id)}`, () => selectEvent(e.id), 'ir-row');
        choose.dataset.eventId = e.id; choose.setAttribute('aria-pressed', String(e.id === selectedId));
        append(choose, el('span', `${e.kind} · ${e.disposition ?? 'disposition unknown'} · actor ${short(e.actor_id)} · original elapsed ${duration(e.elapsed_ms)}`, 'ir-row-meta'));
        return append(item, choose);
      }));
      if (!data.rows.length) rows.append(el('li', 'No records match this selection.', 'ir-muted'));
      pageInfo.textContent = `${data.total} matching · page ${data.page + 1} / ${data.pages} · ≤50 rows/page`;
      previous.disabled = page === 0; next.disabled = page + 1 >= data.pages;
    }
    function linkButton(id) {
      const target = currentCase().events.find(e => e.id === id);
      const node = button(target ? `${target.label || target.kind} · ${short(id)}` : `${short(id)} (omitted / unavailable)`, () => selectEvent(id, true), 'ir-link'); node.disabled = !target; return node;
    }
    function selectEvent(id, navigate = false) {
      const e = currentCase().events.find(entry => entry.id === id);
      if (!e) return;
      const moveFocus = navigate || inspect.contains(doc.activeElement);
      selectedId = id;
      for (const row of rows.querySelectorAll('[data-event-id]')) row.setAttribute('aria-pressed', String(row.dataset.eventId === id));
      inspect.replaceChildren(el('h4', e.label || e.kind), el('p', e.text || 'No public text recorded.', 'ir-retained-text'),
        el('p', `Recorded disposition: ${e.disposition ?? 'unavailable'}. A recorded completion is not a gameplay success verdict.`, 'ir-muted'),
        el('p', `Original omitted bytes: ${e.original_omitted_bytes ?? 'unknown'} · Additional export truncation: ${e.text_omitted_chars} characters`, 'ir-muted'),
        el('p', `Clock: ${e.clock ?? 'missing'} · wall start: ${e.start_wall_ms ?? 'missing'} · wall end: ${e.end_wall_ms ?? 'missing'} · original elapsed: ${e.elapsed_ms ?? 'missing'} ms`, 'ir-muted'));
      const clockState = model.indexes[caseIndex].pointIds.includes(e.id) ? 'Recorded timestamp only: a point, not a measured zero-duration execution.' :
        model.indexes[caseIndex].plottableIds.includes(e.id) ? 'Plotted approximate wall span; original same-domain duration remains separate.' :
        'Unplotted: clock domain or wall bounds missing / invalid. No zero-duration replacement.';
      inspect.append(el('p', clockState, 'ir-muted'));
      if (e.kind === 'program') inspect.append(el('p', 'This export retains the program result identity, disposition, elapsed time and explicit child IDs. Program body, raw error details and authoring arguments are not included; preparation or repair is independently inspectable only where retained public records establish it.', 'ir-muted'));
      const relationships = append(el('div', undefined, 'ir-links'), el('h4', 'Explicit related records'));
      if (!e.links.length) relationships.append(el('p', 'No explicit related event IDs recorded.', 'ir-muted'));
      for (const link of e.links) relationships.append(linkButton(link));
      const incoming = currentCase().events.filter(other => other.id !== id && other.links.includes(id));
      if (incoming.length) {
        relationships.append(el('h4', 'Records explicitly referencing this record'),
          el('p', 'Reverse navigation follows retained IDs. Reference direction does not establish causality.', 'ir-muted'));
        for (const other of incoming.slice(0, 50)) relationships.append(linkButton(other.id));
        if (incoming.length > 50) relationships.append(el('p', `${incoming.length - 50} further references: search exact rows by this record ID.`, 'ir-muted'));
      }
      const runChildren = e.run_id === null ? [] : currentCase().events.filter(other => other.run_id === e.run_id && other.id !== e.id && !e.links.includes(other.id) && !incoming.some(reference => reference.id === other.id));
      if (e.run_id !== null) {
        relationships.append(el('p', `Original program run: ${e.run_id}. Shared run ID is grouping evidence; links do not infer causality.`, 'ir-muted'));
        // At most 50 controls; the full run remains searchable in exact rows.
        for (const child of runChildren.slice(0, 50)) relationships.append(linkButton(child.id));
        if (runChildren.length > 50) relationships.append(el('p', `${runChildren.length - 50} further same-run records: filter exact rows by the run ID.`, 'ir-muted'));
      }
      inspect.append(relationships, details('All retained record fields and metrics', json(e)));
      renderChart();
      if (moveFocus) { inspectHeading.tabIndex = -1; inspectHeading.focus(); }
      if (e.source_id !== null) {
        const source = currentCase().sources.find(s => s.source_id === e.source_id);
        sourceSelect.value = source ? source.source_id : '';
        showSource(e.source_id);
      } else { sourceSelect.value = ''; showSource(''); }
    }
    function renderChart() {
      const c = currentCase(), index = model.indexes[caseIndex], bounds = interval || index.bounds;
      chart.replaceChildren();
      chartNote.textContent = 'Approximate shared wall axis: dots are recorded timestamps; bars are recorded wall spans. Actor epochs are not subtracted. Overlap and links do not establish causality. Exact rows retain original same-domain durations.';
      if (!bounds) { chart.append(el('p', 'No valid wall spans were recorded. Inspect original rows and clock coverage below.', 'ir-muted')); return; }
      const ns = 'http://www.w3.org/2000/svg';
      function svgNode(tag, attributes, text) {
        const node = doc.createElementNS(ns, tag);
        for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
        if (text !== undefined) node.textContent = text; return node;
      }
      const plotted = c.events.filter(e => index.ranges[e.id] && index.ranges[e.id].start <= bounds[1] && index.ranges[e.id].end >= bounds[0]);
      const lanes = KINDS.filter(k => plotted.some(e => e.kind === k));
      const height = 45 + lanes.length * 34;
      const style = global.getComputedStyle?.(chart);
      const padding = style ? parseFloat(style.paddingLeft) + parseFloat(style.paddingRight) : 0;
      const width = Math.max(180, (chart.clientWidth || 1000) - padding);
      const left = width < 500 ? 76 : 100, right = width - 20;
      const svg = svgNode('svg', {viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': 'Recorded original event spans and timestamp points by kind. Keyboard and exact-value alternatives are in Exact records.'});
      const extent = Math.max(1, bounds[1] - bounds[0]);
      const x = value => left + (value - bounds[0]) / extent * (right - left);
      const origin = index.bounds[0];
      const ticks = width < 500 ? [0, 1] : [0, 1 / 3, 2 / 3, 1];
      for (const fraction of ticks) {
        const at = bounds[0] + fraction * (bounds[1] - bounds[0]);
        svg.append(svgNode('text', {x: x(at), y: 16, 'text-anchor': fraction === 0 ? 'start' : fraction === 1 ? 'end' : 'middle'}, `${((at - origin) / 1000).toFixed(1)}s`));
      }
      chartNote.textContent += ` Offset 0 = ${Math.abs(origin) <= 8640000000000000 ? new Date(origin).toISOString() : `wall ms ${origin}`}.`;
      for (const [i, lane] of lanes.entries()) {
        const y = 33 + i * 34;
        svg.append(svgNode('text', {x: 3, y: y + 13}, lane), svgNode('line', {x1: left, x2: right, y1: y + 20, y2: y + 20, class: 'ir-axis'}));
        for (const e of plotted.filter(e => e.kind === lane)) {
          const range = index.ranges[e.id], start = Math.max(bounds[0], range.start), end = Math.min(bounds[1], range.end);
          const rect = range.point ? svgNode('circle', {cx: x(start), cy: y + 9, r: 3}) :
            svgNode('rect', {x: x(start), y, width: Math.min(right - x(start), Math.max(1, x(end) - x(start))), height: 18, rx: 2});
          rect.setAttribute('class', `ir-span ir-span-${lane}${selectedId === e.id ? ' ir-selected' : ''}`);
          rect.setAttribute('aria-hidden', 'true');
          rect.append(svgNode('title', {}, `${e.id} · ${e.label} · ${range.point ? 'timestamp only' : 'wall span; may be clipped'} · ${e.clock} · original elapsed ${e.elapsed_ms ?? 'unavailable'} ms`));
          rect.addEventListener('click', () => selectEvent(e.id)); svg.append(rect);
        }
      }
      chart.append(svg);
    }
    const chartResize = typeof global.ResizeObserver === 'function' ? new global.ResizeObserver(() => { if (model && !destroyed) renderChart(); }) : null;
    chartResize?.observe(chart);
    function releaseImage(job) {
      if (!job || job.released) return;
      job.released = true; job.image.removeAttribute('src'); global.URL.revokeObjectURL(job.url);
    }
    function clearImage() {
      ++imageGeneration; wantedImage = null;
      releaseImage(displayed); displayed = null; releaseImage(decoding); frame.replaceChildren();
    }
    function showSource(id) {
      clearImage(); sourceFacts.replaceChildren();
      if (!id) { frameNote.textContent = 'This record has no original source ID.'; return; }
      const s = currentCase().sources.find(entry => entry.source_id === id);
      if (!s) { frameNote.textContent = `Source ${id} was not selected / is unavailable in this bundle. No latest-image substitution.`; return; }
      const {bytes, ...facts} = s;
      sourceFacts.append(details('Original source identity, geometry and digest', json(facts)));
      if (!bytes) { frameNote.textContent = s.unavailable_reason || 'Original image bytes unavailable.'; return; }
      wantedImage = {source: s, version: imageGeneration}; frameNote.textContent = `Decoding original ${s.source_id}…`; pumpImage();
    }
    function pumpImage() {
      // A cancelled decode holds its budget until its platform promise settles.
      if (destroyed || decoding || !wantedImage) return;
      const {source: s, version} = wantedImage; wantedImage = null;
      if (s.width * s.height * 4 > PIXEL_BUDGET) { frameNote.textContent = 'Image unavailable: decoded pixel budget exceeded.'; return; }
      const image = new global.Image(); image.alt = `Original recorded source ${s.source_id}`;
      const url = global.URL.createObjectURL(new Blob([s.bytes], {type: 'image/png'}));
      const job = {image, url, released: false, timer: null}; decoding = job;
      job.timer = global.setTimeout(() => {
        if (decoding !== job) return;
        releaseImage(job);
        if (!destroyed && (version === imageGeneration || wantedImage)) frameNote.textContent = 'Image unavailable: decode exceeded 8 seconds. Its pixel reservation remains held until the platform decode settles; other recorded evidence and current Pause remain available.';
      }, 8000);
      image.src = url;
      image.decode().then(() => {
        if (destroyed || version !== imageGeneration || job.released) return;
        if (image.naturalWidth !== s.width || image.naturalHeight !== s.height) throw new Error('Decoded geometry differs from original PNG.');
        displayed = job; frame.replaceChildren(image);
        frameNote.textContent = `Original ${s.width} × ${s.height} PNG · source ${s.source_id} · digest verified. Internal consistency is not authorship.`;
      }).catch(() => {
        if (!destroyed && version === imageGeneration) frameNote.textContent = `Original source ${s.source_id} unavailable: PNG decode failed.`;
      }).finally(() => {
        global.clearTimeout(job.timer);
        if (displayed !== job) releaseImage(job);
        decoding = null; pumpImage();
      });
    }
    function destroy() {
      if (destroyed) return; destroyed = true; chartResize?.disconnect(); stopWorker();
      if (decoding) global.clearTimeout(decoding.timer);
      clearImage(); root.replaceChildren(); root.classList.remove('investigation-reader');
    }
    if (options.initialText !== undefined) load({text: options.initialText});
    return {loadFile, destroy};
  }
  global.EnactiveInvestigation = Object.freeze({mount});
})(typeof window !== 'undefined' ? window : globalThis);
