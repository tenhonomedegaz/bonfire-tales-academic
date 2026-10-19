/* Local image preview only: no upload until the owner submits the form. */
(() => {
  const input = document.querySelector('[data-mission-banner], .mh-work-form input[name="imagem"]');
  const preview = document.querySelector('[data-mission-banner-preview], [data-master-work-image-preview]');
  if (!input || !preview) return;
  const isWork = input.name === 'imagem';
  const imageName = isWork ? 'imagem' : 'banner';
  const remove = input.form?.elements.namedItem(isWork ? 'remover_imagem' : 'remover_banner');
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
        preview.replaceChildren(document.createTextNode(isWork
          ? 'A imagem atual será removida ao salvar.'
          : 'O banner atual será removido ao salvar.'));
      } else {
        preview.replaceChildren(...initialContent.map(node => node.cloneNode(true)));
      }
      return;
    }
    if (!['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type) || file.size > 8 * 1024 * 1024) {
      input.setCustomValidity('Envie PNG, JPEG, WebP ou GIF de até 8 MB.');
      preview.replaceChildren(document.createTextNode(`Arquivo inválido para ${imageName}. Escolha PNG, JPEG, WebP ou GIF de até 8 MB.`));
      input.reportValidity();
      return;
    }
    if (remove) remove.checked = false;
    objectUrl = URL.createObjectURL(file);
    const img = document.createElement('img');
    img.alt = isWork ? 'Prévia da imagem do trabalho' : 'Prévia do banner da missão';
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
