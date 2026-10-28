document.addEventListener('DOMContentLoaded', () => {
  const file = new URL('../../home/static/cosmetics/proposal-blood-moon-v1.png', document.baseURI).href;
  for (const preview of document.querySelectorAll('.hero.moon')) {
    window.CosmeticRenderer.render(preview, 'banner', [{banner: [{
      url: file, fallback: file, width: 2117, height: 743,
      anchor: 'right', sprite: 'full', motion: 'breeze',
    }]}]);
    preview.classList.add('has-breeze');
  }
});
