document.addEventListener('DOMContentLoaded', () => {
  for (const preview of document.querySelectorAll('.hero.moon')) {
    window.CosmeticRenderer.render(preview, 'banner', [window.BonfireMoonPreview]);
    preview.classList.add('has-breeze');
  }
  document.getElementById('toggle-wind').addEventListener('click', event => {
    const paused = event.currentTarget.getAttribute('aria-pressed') !== 'true';
    event.currentTarget.setAttribute('aria-pressed', String(paused));
    event.currentTarget.textContent = paused ? 'Retomar nuvens' : 'Pausar nuvens';
    document.querySelectorAll('.hero.moon').forEach(hero => hero.classList.toggle('preview-paused', paused));
  });
  for (const control of document.querySelectorAll('[data-layer-toggle]')) {
    control.addEventListener('change', () => {
      for (const image of document.querySelectorAll('.moon .cosmetic-layer')) {
        if (image.src.includes('blood-moon-' + control.dataset.layerToggle + '-')) {
          image.style.visibility = control.checked ? '' : 'hidden';
        }
      }
    });
  }
});
