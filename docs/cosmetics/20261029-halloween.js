(() => {
  'use strict';
  const root = document.getElementById('preview-root');
  const banner = document.getElementById('preview-banner');
  const packs = window.BonfireHalloweenPreview;
  const fireFile = 'vigilia-jack-fire-textured-v32.webp';
  const lightFile = 'vigilia-jack-light-v29.webp';
  document.getElementById('light-control').hidden = false;
  document.getElementById('fire-control').hidden = false;
  function update() {
    const theme = document.getElementById('toggle-theme').checked;
    root.classList.toggle('skin-illustrated', theme);
    root.classList.toggle('skin-vigilia-das-lanternas', theme);
    root.classList.toggle('preview-paused', !document.getElementById('toggle-motion').checked);
    const light = document.getElementById('toggle-light').checked;
    const fire = document.getElementById('toggle-fire').checked;
    const effect = {...packs.efeito, banner: packs.efeito.banner
      .filter(layer => fire || layer.file !== fireFile)
      .map(layer => layer.parts && !light ? {...layer, parts: layer.parts.filter(part => part.file !== lightFile)} : layer)};
    window.CosmeticRenderer.render(banner, 'banner', document.getElementById('toggle-effect').checked ? [effect] : []);
    const frame = document.getElementById('toggle-frame').checked;
    document.querySelectorAll('[data-frame]').forEach(avatar => {
      avatar.classList.toggle('is-packaged', frame);
      window.CosmeticRenderer.render(avatar, 'avatar', frame ? [packs.moldura] : []);
    });
  }
  document.querySelectorAll('.controls input').forEach(input => input.addEventListener('change', update));
  update();
})();
