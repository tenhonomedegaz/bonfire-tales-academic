(() => {
  'use strict';
  const form = document.querySelector('[data-slot-selection]');
  if (!form) return;
  const inputs = [...form.querySelectorAll('input[name="characters"]')];
  const status = form.querySelector('[data-selection-status]');
  const button = form.querySelector('button[type="submit"]');
  const limit = Number(form.dataset.limit);
  function update() {
    const count = inputs.filter(input => input.checked).length;
    status.textContent = `${count} selecionadas Â· atÃ© ${limit === 99999 ? 'ilimitadas' : limit} ativas`;
    button.disabled = count > limit;
    if (count > limit) status.textContent += '. Desmarque uma ficha para continuar.';
  }
  form.addEventListener('change', update);
  if (form.dataset.demo === 'true') form.addEventListener('submit', event => {
    event.preventDefault();
    status.textContent = 'SeleÃ§Ã£o demonstrativa conferida. Nenhuma ficha real foi alterada.';
  });
  update();
})();

