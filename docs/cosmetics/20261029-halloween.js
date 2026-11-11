(() => {
  'use strict';
  const root = document.getElementById('preview-root');
  const banner = document.getElementById('preview-banner');
  const packs = window.BonfireHalloweenPreview;
  function update() {
    const theme = document.getElementById('toggle-theme').checked;
    root.classList.toggle('skin-illustrated', theme);
    root.classList.toggle('skin-vigilia-das-lanternas', theme);
    root.classList.toggle('preview-paused', !document.getElementById('toggle-motion').checked);
    window.CosmeticRenderer.render(banner, 'banner', document.getElementById('toggle-effect').checked ? [packs.efeito] : []);
    const frame = document.getElementById('toggle-frame').checked;
    document.querySelectorAll('[data-frame]').forEach(avatar => {
      avatar.classList.toggle('is-packaged', frame);
      window.CosmeticRenderer.render(avatar, 'avatar', frame ? [packs.moldura] : []);
    });
  }
  document.querySelectorAll('.controls input').forEach(input => input.addEventListener('change', update));
  update();
})();
