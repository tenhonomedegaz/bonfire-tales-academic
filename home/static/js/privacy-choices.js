(() => {
  const button = document.querySelector('[data-privacy-choices]');
  if (!button) return;
  window.googlefc = window.googlefc || {};
  window.googlefc.callbackQueue = window.googlefc.callbackQueue || [];
  button.addEventListener('click', () => {
    window.googlefc.callbackQueue.push({CONSENT_API_READY: () => {
      if (typeof window.googlefc.showRevocationMessage === 'function') {
        window.googlefc.showRevocationMessage();
      }
    }});
  });
  // The certified Google CMP owns consent, storage and region detection.
  // No CMP or unknown region: do not expose a nonfunctional settings button.
  window.googlefc.callbackQueue.push({CONSENT_API_READY: () => {
    if (typeof window.__tcfapi !== 'function') return;
    window.__tcfapi('addEventListener', 0, (data, success) => {
      button.hidden = !(success && data && data.gdprApplies === true &&
        typeof window.googlefc.showRevocationMessage === 'function');
    });
  }});
})();
