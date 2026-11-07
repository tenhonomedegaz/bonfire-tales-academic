/* Mutações rápidas do PAINEL DA STAFF (aventuras + concessão de item). Mantém POST
 * clássico como fallback e usa fetch quando JS está disponível.
 * Onda C: recursos, magias preparadas e a LOJA saíram desta página — o que sobrou aqui
 * mexe só no ledger de aventuras, nas concessões e nos derivados que elas alteram. */
(function () {
  'use strict';

  function setText(selector, value) {
    var el = document.querySelector(selector);
    if (el && value !== undefined && value !== null) el.textContent = value;
  }

  function submitForm(form) {
    var data = new FormData(form);
    return fetch(form.action, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': data.get('csrfmiddlewaretoken') || ''
      },
      body: data,
      credentials: 'same-origin'
    }).then(function (response) {
      return response.json().then(function (json) {
        return { ok: response.ok, json: json };
      });
    });
  }

  function setFeedback(id, message, ok) {
    var el = document.getElementById(id);
    if (!el) return;
    el.textContent = message || '';
    el.hidden = !message;
    el.classList.toggle('is-ok', !!ok);
    el.classList.toggle('is-err', !ok);
  }

  function setActionFeedback(form, message) {
    var note = form.nextElementSibling;
    if (!note || !note.hasAttribute('data-action-feedback')) {
      note = document.createElement('p');
      note.className = 'lvl-note-cap';
      note.setAttribute('data-action-feedback', '');
      note.setAttribute('role', 'alert');
      form.after(note);
    }
    note.textContent = message || '';
    note.hidden = !message;
  }

  var uncertainResult = 'Não foi possível confirmar a operação. Atualize a ficha antes de tentar novamente.';
  var networkFailure = 'A conexão falhou. Confira a ficha antes de reenviar esta operação.';

  function applyInventory(payload) {
    // O inventário saiu daqui na onda B (vive na aba Mochila da ficha); esta página só
    // precisa refletir carteira e os derivados que a concessão mexe.
    setText('[data-carteira-display]', payload.carteira_display);
    if (payload.ficha) {
      setText('[data-ficha-ca]', payload.ficha.ca);
      setText('[data-ficha-pv]', payload.ficha.pv_maximo);
    }
  }

  // O seletor da staff usa o mesmo catálogo do Mercado, mas registra a
  // proficiência diretamente. O select original continua funcional sem JS.
  var trainingForm = document.querySelector('[data-staff-training-form]');
  if (trainingForm) {
    var trainingSearch = trainingForm.querySelector('[data-staff-training-search]');
    var trainingGroup = trainingForm.querySelector('[data-staff-training-group]');
    var trainingChoice = trainingForm.querySelector('[data-staff-training-choice]');
    var trainingStatus = trainingForm.querySelector('[data-staff-training-status]');
    var trainingSubmit = trainingForm.querySelector('button[type="submit"]');
    var trainingGroups = Array.prototype.map.call(trainingChoice.querySelectorAll('optgroup'), function (group) {
      return {
        label: group.label,
        options: Array.prototype.map.call(group.querySelectorAll('option'), function (option) {
          return { value: option.value, label: option.textContent };
        })
      };
    });
    function normalizeTraining(value) {
      return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
    }
    function filterTraining() {
      var query = normalizeTraining(trainingSearch.value.trim());
      var category = trainingGroup.value;
      var selected = trainingChoice.value;
      trainingChoice.replaceChildren(new Option('Selecione um idioma ou ferramenta', ''));
      var count = 0;
      trainingGroups.forEach(function (group) {
        if (category && category !== group.label) return;
        var matches = group.options.filter(function (option) {
          return normalizeTraining(option.label).includes(query);
        });
        if (!matches.length) return;
        var optgroup = document.createElement('optgroup');
        optgroup.label = group.label;
        matches.forEach(function (option) { optgroup.append(new Option(option.label, option.value)); });
        trainingChoice.append(optgroup);
        count += matches.length;
      });
      if (selected && Array.prototype.some.call(trainingChoice.options, function (option) {
        return option.value === selected;
      })) trainingChoice.value = selected;
      else trainingChoice.value = '';
      if (!count) trainingChoice.append(new Option('Nenhum treinamento encontrado', ''));
      trainingChoice.disabled = !count;
      trainingSubmit.disabled = !count;
      trainingStatus.textContent = count
        ? count + ' treinamento' + (count === 1 ? ' disponível.' : 's disponíveis.')
        : 'Nenhum treinamento encontrado. Ajuste a busca ou limpe os filtros.';
    }
    trainingSearch.addEventListener('input', filterTraining);
    trainingGroup.addEventListener('change', filterTraining);
    trainingForm.querySelector('[data-staff-training-clear]').addEventListener('click', function () {
      trainingSearch.value = '';
      trainingGroup.value = '';
      filterTraining();
      trainingSearch.focus();
    });
  }

  // Quais <details> de missão estão ABERTOS agora (por id de lançamento). O staffbox volta
  // do servidor inteiro e fechado; sem isto, corrigir/consumir fechava o bloco na cara da
  // staff no meio do trabalho.
  function missoesAbertas() {
    return Array.prototype.filter.call(
      document.querySelectorAll('[data-missao-details]'), function (d) { return d.open; }
    ).map(function (d) { return d.getAttribute('data-missao-details'); });
  }

  function reabrirMissoes(ids) {
    (ids || []).forEach(function (id) {
      var el = document.querySelector('[data-missao-details="' + id + '"]');
      if (el) el.open = true;
    });
  }

  // Todo formulário do staffbox de missões (lançar, reverter, corrigir, consumo) devolve
  // o MESMO fragmento re-renderizado — um handler só cobre os quatro.
  document.addEventListener('submit', function (event) {
    var form = event.target.closest(
      'form[data-aventura-form], form[data-aventura-reverter],' +
      'form[data-aventura-editar], form[data-aventura-consumo]'
    );
    if (!form || event.defaultPrevented) return;
    event.preventDefault();
    setActionFeedback(form, '');
    var button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    // A linha EDITADA reabre mesmo que estivesse fechada (o staff acabou de agir nela).
    var editada = form.closest('[data-missao-details]');
    var abertas = missoesAbertas();
    if (editada) {
      var idEditada = editada.getAttribute('data-missao-details');
      if (abertas.indexOf(idEditada) === -1) abertas.push(idEditada);
    }
    submitForm(form).then(function (result) {
      var payload = result.json || {};
      if (typeof payload.staffbox_html === 'string') {
        var box = document.getElementById('lvl-aventuras-staffbox');
        if (box) box.outerHTML = payload.staffbox_html;
        reabrirMissoes(abertas);
      } else {
        setActionFeedback(form, uncertainResult);
      }
      if (result.ok && payload.progressao) {
        setText('[data-ficha-aventuras]', payload.progressao.aventuras);
        setText('[data-ficha-teto]', payload.progressao.nivel_label);
        setText('[data-ficha-braseiros]', payload.progressao.braseiros);
      }
      if (result.ok) setText('[data-carteira-display]', payload.carteira_display);
      if (button && document.body.contains(button)) button.disabled = false;
    }).catch(function () {
      setActionFeedback(form, networkFailure);
      if (button) button.disabled = false;
    });
  });

  document.addEventListener('submit', function (event) {
    var form = event.target.closest(
      'form[data-conceder-form], form[data-concessao-reverter]'
    );
    if (!form || event.defaultPrevented) return;
    event.preventDefault();
    setActionFeedback(form, '');
    var button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;

    submitForm(form).then(function (result) {
      var payload = result.json || {};
      if (result.ok && typeof payload.inventario_html === 'string') applyInventory(payload);
      if (typeof payload.concessoes_html === 'string') {
        var ledger = document.getElementById('ficha-concessoes-dinamico');
        if (ledger) ledger.outerHTML = payload.concessoes_html;
      } else {
        setActionFeedback(form, uncertainResult);
      }
      if (button && document.body.contains(button)) button.disabled = false;
    }).catch(function () {
      setActionFeedback(form, networkFailure);
      if (button) button.disabled = false;
    });
  });
})();
