/* Local image preview only: no upload until the owner submits the form. */
(() => {
  const input = document.querySelector('[data-mission-banner]');
  const preview = document.querySelector('[data-mission-banner-preview]');
  if (!input || !preview) return;
  const remove = input.form?.elements.namedItem('remover_banner');
  const initialContent = Array.from(preview.childNodes, node => node.cloneNode(true));
  let objectUrl;
  function releasePreview() {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = undefined;
  }
  function updatePreview() {
    releasePreview();
    input.setCustomValidity('');
    const file = input.files[0];
    if (!file) {
      if (remove?.checked) {
        preview.replaceChildren(document.createTextNode('O banner atual será removido ao salvar.'));
      } else {
        preview.replaceChildren(...initialContent.map(node => node.cloneNode(true)));
      }
      return;
    }
    if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type) || file.size > 8 * 1024 * 1024) {
      input.setCustomValidity('Envie PNG, JPEG, WebP ou GIF de até 8 MB.');
      preview.replaceChildren(document.createTextNode('Arquivo inválido. Escolha PNG, JPEG, WebP ou GIF de até 8 MB.'));
      input.reportValidity();
      return;
    }
    if (remove) remove.checked = false;
    objectUrl = URL.createObjectURL(file);
    const img = document.createElement('img');
    img.alt = 'Prévia do banner da missão';
    img.src = objectUrl;
    preview.replaceChildren(img);
  }
  input.addEventListener('change', updatePreview);
  remove?.addEventListener('change', () => {
    if (remove.checked && input.files.length) input.value = '';
    updatePreview();
  });
  window.addEventListener('pagehide', releasePreview);
})();
