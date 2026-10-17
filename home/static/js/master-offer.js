(() => {
  const kind = document.getElementById('id_modalidade');
  if (!kind) return;
  const fields = document.querySelectorAll('[data-offer-field]');
  function update() { fields.forEach(field => { field.hidden = kind.value !== 'paga'; }); }
  kind.addEventListener('change', update);
  update();
})();
