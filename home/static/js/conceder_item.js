/* Staff — painel de CONCESSÃO de item na ficha. Alterna o <select> mágico/mundano
 * conforme o tipo escolhido e filtra as opções do select ativo por nome. É apenas
 * aprimoramento progressivo: sem JS o form ainda concede itens mágicos (o select
 * nativo aceita type-ahead; o select mundano fica `disabled` e não é enviado). */
(function () {
  var form = document.querySelector('[data-conceder-form]');
  if (!form || form.dataset.concInit === '1') return;
  form.dataset.concInit = '1';

  var tipo = form.querySelector('[data-conceder-tipo]');
  var busca = form.querySelector('[data-conceder-busca]');
  var selects = {
    magico: form.querySelector('[data-conceder-select="magico"]'),
    mundano: form.querySelector('[data-conceder-select="mundano"]')
  };

  function norm(s) {
    return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }
  function activeSelect() { return (tipo && selects[tipo.value]) || selects.magico; }

  function filter() {
    var s = activeSelect();
    if (!s) return;
    var q = norm(busca ? busca.value.trim() : '');
    var firstVisible = null;
    Array.prototype.forEach.call(s.options, function (o) {
      var hit = !q || norm(o.getAttribute('data-nome') || o.text).indexOf(q) !== -1;
      o.hidden = !hit;
      if (hit && firstVisible === null) firstVisible = o;
    });
    // se a opção atualmente selecionada ficou oculta pelo filtro, salta pra 1ª visível
    if (s.selectedOptions && s.selectedOptions.length &&
        s.selectedOptions[0].hidden && firstVisible) {
      s.value = firstVisible.value;
    }
  }

  function syncTipo() {
    ['magico', 'mundano'].forEach(function (k) {
      var s = selects[k];
      if (!s) return;
      var on = tipo && k === tipo.value;
      s.disabled = !on;   // controle `disabled` não é submetido: só o select ativo vai
      s.hidden = !on;
    });
    filter();
  }

  if (tipo) tipo.addEventListener('change', syncTipo);
  if (busca) busca.addEventListener('input', filter);
  syncTipo();
})();
