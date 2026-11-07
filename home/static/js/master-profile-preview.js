(() => {
  const form = document.querySelector('[data-master-profile-form]');
  const preview = form?.querySelector('[data-master-profile-preview]');
  if (!form || !preview) return;

  const fields = ['apresentacao', 'estilo', 'disponibilidade', 'experiencia', 'combinados'];
  function update() {
    for (const name of fields) {
      const value = form.elements.namedItem(name)?.value.trim() || '';
      const target = preview.querySelector(`[data-master-preview-field="${name}"]`);
      target.textContent = name === 'apresentacao' && !value
        ? 'Este mestre ainda está preparando sua apresentação.' : value;
      const group = preview.querySelector(`[data-master-preview-group="${name}"]`);
      if (group) group.hidden = !value;
    }
    preview.querySelector('.mh-public-meta').hidden = !fields.slice(1, 3).some(name =>
      form.elements.namedItem(name)?.value.trim());
    const listed = form.elements.namedItem('listado')?.checked;
    const state = preview.querySelector('[data-master-preview-state]');
    state.textContent = listed ? 'Visível após salvar' : 'Fora da vitrine';
    state.dataset.state = listed ? 'publicado' : 'pendente';
  }

  form.addEventListener('input', update);
  form.addEventListener('change', update);
  update();
})();
