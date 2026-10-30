/* Current-session snapshot transport; no actor capability or control dependency. */
(function (global) {
  'use strict';
  const MAX_RESPONSE = 16 * 1024 * 1024 + 4096;
  function mount(root, {status, refreshButton, getSession}) {
    let version = 0, network = null, activated = false, intent = false, evidence = false, mode = 'current', attached = null, scope = null, busy = false, destroyed = false;
    function cancel() {
      ++version; network?.abort(); network = null; reader.cancelPending(); busy = false; refreshButton.disabled = false;
    }
    const reader = global.EnactiveInvestigation.mount(root, {workerURL: '/investigation-worker.js',
      acceptSnapshot: session => session === getSession(),
      onImport() {
        cancel(); intent = true; mode = 'recorded';
        status.textContent = 'Opening optional recorded evidence. Current-target control remains separate.';
      },
      onLoadFailed(data) {
        if (data.kind === 'file') status.textContent = `Recorded import ${data.cancelled ? 'cancelled' : 'failed'}; the previous snapshot remains inspectable. Current-target control remains separate.`;
      },
      onLoaded(data) {
        evidence = true;
        if (data.kind === 'snapshot') {
          mode = 'current'; attached = data.snapshot.session;
          const at = data.snapshot.wall_ms;
          status.textContent = `Session ${attached} · snapshot completed ${at <= 8640000000000000 ? new Date(at).toISOString() : `wall ms ${at}`}. Individual producer cutoffs and omissions are below. Refresh explicitly; inspection does not follow new activity.`;
        } else {
          mode = 'recorded'; attached = null;
          status.textContent = 'Imported recorded evidence. Current-target control remains separate; attach the current session when ready.';
        }
      }});
    async function body(response, maximum) {
      // The selected server always sends an uncompressed Content-Length. Rely on
      // that HTTP framing contract, reject unbounded/encoded responses, and leave
      // potentially large JSON parsing to the dedicated validation worker.
      const length = response.headers.get('Content-Length'), encoding = response.headers.get('Content-Encoding');
      if (!length || !/^\d+$/.test(length) || Number(length) > maximum || (encoding && encoding !== 'identity')) {
        throw new Error('Snapshot response exceeds its bounded HTTP contract');
      }
      const text = await response.text();
      if (new TextEncoder().encode(text).byteLength > maximum) throw new Error('Snapshot response exceeds its encoded bound');
      return text;
    }
    async function retrieve(controller) {
      let method = 'POST';
      for (;;) {
        const response = await global.fetch('/api/investigation', {method, cache: 'no-store', credentials: 'same-origin',
          ...(method === 'POST' ? {headers: {'Content-Type': 'application/json'}, body: '{}'} : {}), signal: controller.signal});
        if (response.status === 200) return body(response, MAX_RESPONSE);
        await body(response, 4096);
        if (response.status !== 202) throw new Error(`Snapshot unavailable (HTTP ${response.status})`);
        await new Promise((resolve, reject) => {
          if (controller.signal.aborted) { reject(new Error('Snapshot request cancelled')); return; }
          const abort = () => { global.clearTimeout(timer); reject(new Error('Snapshot request cancelled')); };
          const timer = global.setTimeout(() => { controller.signal.removeEventListener('abort', abort); resolve(); }, 150);
          controller.signal.addEventListener('abort', abort, {once: true});
        });
        method = 'GET';
      }
    }
    async function refresh() {
      if (destroyed) return;
      const session = getSession();
      if (!session) { status.textContent = 'Current session is not identified yet. Independent Pause remains available.'; return; }
      cancel(); intent = true; mode = 'current'; scope = session;
      const token = version, controller = new global.AbortController(); network = controller;
      busy = true; refreshButton.disabled = true;
      refreshButton.textContent = 'Refresh current session';
      status.textContent = `Reading existing evidence for session ${session}… Previous evidence remains recorded until validation succeeds.`;
      let timer;
      try {
        const timeout = new Promise((resolve, reject) => { timer = global.setTimeout(() => { controller.abort(); reject(new Error('Snapshot request exceeded 12 seconds')); }, 12000); });
        const text = await Promise.race([retrieve(controller), timeout]);
        global.clearTimeout(timer); timer = null;
        if (token !== version || session !== getSession()) return;
        const accepted = await reader.loadSnapshot(text, session);
        if (token !== version) return;
        if (!accepted) status.textContent = 'Snapshot validation failed or was cancelled. Previously loaded evidence remains recorded; see reader feedback below.';
      } catch (error) {
        if (token === version) status.textContent = `${error.message}. Previously loaded evidence remains recorded; no current control was changed.`;
      } finally {
        if (timer !== null) global.clearTimeout(timer);
        if (token === version) { busy = false; network = null; refreshButton.disabled = false; }
      }
    }
    refreshButton.addEventListener('click', () => { void refresh(); });
    return {
      activate() { if (destroyed) return; activated = true; if (!intent && getSession()) void refresh(); },
      sessionChanged(session) {
        if (destroyed) return;
        const superseded = busy && scope !== session;
        if (superseded) cancel();
        if (superseded || evidence && (mode === 'recorded' || attached !== session)) {
          status.textContent = evidence ? 'Loaded evidence is recorded history; the serving target changed or an older bundle is selected. Attach the current session explicitly to replace this inspection.' :
            'The serving session changed; its earlier snapshot request was cancelled. Attach the current session to read its evidence.';
          refreshButton.textContent = 'Attach current session';
        } else if (activated && !intent) void refresh();
      },
      destroy() { destroyed = true; cancel(); reader.destroy(); }
    };
  }
  global.EnactiveInvestigationSession = Object.freeze({mount});
})(typeof window !== 'undefined' ? window : globalThis);
