(() => {
  const kind = document.getElementById('id_modalidade');
  if (!kind) return;
  const fields = document.querySelectorAll('[data-offer-field]');
  function update() {
    const paid = kind.value === 'paga';
    fields.forEach(field => {
      field.hidden = !paid;
      field.querySelectorAll('input, select, textarea').forEach(control => {
        control.disabled = !paid;
      });
    });
  }
  kind.addEventListener('change', update);
  update();
})();
