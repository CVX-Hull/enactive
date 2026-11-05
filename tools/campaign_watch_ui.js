// Read the spectator's displayed state only on an explicit trusted operator click.
(() => {
  const button = document.querySelector('#watch-record');
  const message = document.querySelector('#watch-feedback');
  const read = id => document.getElementById(id);
  let next = Number(button.dataset.next);

  function inViewport(element) {
    const bounds = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return style.visibility === 'visible' && style.display !== 'none'
      && bounds.right > 0 && bounds.left < innerWidth
      && bounds.bottom > 0 && bounds.top < innerHeight && bounds.width > 0 && bounds.height > 0;
  }

  function observe() {
    const session = read('current-session-full').textContent.trim();
    const stamp = read('control-freshness').textContent.match(/^Last status received (\S+);/);
    const source = read('source-details').textContent.match(
      /^Session: (\S+)\nSource: (\S+)\nCapture: \S+\nSHA-256: ([a-f0-9]{64})\n/);
    const frame = read('frame');
    if (document.visibilityState !== 'visible' || read('watch').hidden
        || read('connection').dataset.state !== 'ok' || !read('status-error').hidden
        || !stamp || !source || source[1] !== session || frame.hidden
        || !frame.complete || !frame.naturalWidth || !inViewport(frame)
        || !inViewport(read('control-freshness'))) {
      throw new Error('Inspect a decoded frame and current status in the visible Watch first.');
    }
    return {sequence: next, session, observed: stamp[1], source: source[2], sha256: source[3]};
  }

  button.addEventListener('click', async event => {
    if (!event.isTrusted || button.disabled) return;
    button.disabled = true;
    try {
      const captured = observe();
      message.textContent = `Recording ${captured.source}`;
      const response = await fetch('/record', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(captured), signal: AbortSignal.timeout(6500),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error);
      if (result.accepted !== next || result.source !== captured.source) {
        throw new Error('Unmatched guard confirmation');
      }
      next += 1;
      message.textContent = `Check ${result.accepted} accepted for ${result.source}`;
    } catch (error) {
      message.textContent = `Check unconfirmed: ${error.message}`;
    } finally {
      button.disabled = false;
    }
  });
})();
