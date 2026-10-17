/* Local image preview only: no upload until the owner submits the form. */
(() => {
  const input = document.querySelector('[data-mission-banner]');
  const preview = document.querySelector('[data-mission-banner-preview]');
  if (!input || !preview) return;
  const initialContent = Array.from(preview.childNodes, node => node.cloneNode(true));
  let objectUrl;
  input.addEventListener('change', () => {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    input.setCustomValidity('');
    const file = input.files[0];
    if (!file) {
      preview.replaceChildren(...initialContent.map(node => node.cloneNode(true)));
      return;
    }
    if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type) || file.size > 8 * 1024 * 1024) {
      input.setCustomValidity('Envie PNG, JPEG, WebP ou GIF de até 8 MB.');
      input.reportValidity();
      return;
    }
    input.setCustomValidity('');
    objectUrl = URL.createObjectURL(file);
    const img = document.createElement('img');
    img.alt = 'Prévia do banner da missão';
    img.src = objectUrl;
    preview.replaceChildren(img);
  });
})();
