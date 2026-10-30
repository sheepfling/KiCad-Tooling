const status = document.getElementById('viewer-status');
const started = performance.now();
const poll = setInterval(() => {
  if (!status.textContent.startsWith('Fitted;')) {
    if (performance.now() - started > 6500) {
      clearInterval(poll);
      const result = document.createElement('pre');
      result.id = 'viewer-probe-result';
      result.textContent = JSON.stringify({ error: status.textContent });
      document.body.appendChild(result);
    }
    return;
  }
  clearInterval(poll);
  const canvas = document.querySelector('#viewport canvas');
  const initial = status.textContent;
  document.querySelector('[data-view="top"]').click();
  const top = status.textContent;
  document.querySelector('[data-action="zoom-in"]').click();
  const zoom = status.textContent;
  canvas.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', bubbles: true }));
  const keyboard = status.textContent;
  const enclosureButton = document.querySelector('[data-model="enclosure"]');
  let enclosure = null;
  if (enclosureButton) {
    const initialVisible = enclosureButton.getAttribute('aria-pressed');
    enclosureButton.click();
    const hidden = enclosureButton.getAttribute('aria-pressed');
    enclosureButton.click();
    const restored = enclosureButton.getAttribute('aria-pressed');
    enclosure = { initialVisible, hidden, restored };
  }
  const result = document.createElement('pre');
  result.id = 'viewer-probe-result';
  result.textContent = JSON.stringify({
    canvas: !!canvas,
    focusable: canvas.getAttribute('tabindex') === '0',
    initial, top, zoom, keyboard, enclosure,
    resources: performance.getEntriesByType('resource').map((entry) => entry.name),
  });
  document.body.appendChild(result);
}, 50);
