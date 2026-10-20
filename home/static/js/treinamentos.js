/* Presentation over the native training select and existing server command. */
(() => {
  'use strict';
  const root = document.querySelector('.services-shell');
  const choice = document.getElementById('training-choice');
  const search = document.getElementById('training-search');
  const group = document.getElementById('training-group');
  const status = document.getElementById('training-search-status');
  if (!root || !choice || !search || !group || !status) return;

  const list = root.querySelector('[data-training-options]');
  const checkout = root.querySelector('.training-checkout');
  const empty = root.querySelector('[data-training-noresults]');
  const shortcuts = [...root.querySelectorAll('[data-training-category]')];
  const enhanced = !!(list && checkout && empty && shortcuts.length);
  const icons = {Idiomas:'#training-language', Ferramentas:'#training-tools', Instrumentos:'#training-music', Jogos:'#training-game'};
  const descriptions = {
    Idiomas:'Aprenda um novo idioma. Essa proficiência será registrada na sua ficha ao concluir o treinamento.',
    Ferramentas:'Desenvolva proficiência nas ferramentas deste ofício. O aprendizado será registrado ao fim do prazo.',
    Instrumentos:'Desenvolva proficiência neste instrumento musical. O aprendizado será registrado ao fim do prazo.',
    Jogos:'Desenvolva proficiência neste conjunto de jogo. O aprendizado será registrado ao fim do prazo.'
  };
  const groups = [...choice.querySelectorAll('optgroup')].map(section => ({
    label:section.label,
    options:[...section.querySelectorAll('option')].map(option => ({value:option.value, label:option.textContent}))
  }));
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');

  function updateSelection() {
    if (!enhanced) return;
    const selected = choice.selectedOptions[0];
    const valid = !!(selected && selected.value && !choice.disabled);
    const category = valid ? selected.parentElement.label : '';
    root.querySelector('#training-selected-name').textContent = valid ? selected.textContent : 'Escolha o que deseja aprender';
    root.querySelector('[data-training-selected-group]').textContent = category || 'Um novo caminho';
    root.querySelector('[data-training-selected-description]').textContent = descriptions[category] || 'Selecione uma opção para conferir sua matrícula.';
    root.querySelector('[data-training-selected-icon]').setAttribute('href', icons[category] || '#training-learn');
    checkout.classList.toggle('has-selection', valid);
    checkout.querySelector('button[type="submit"]').disabled = !valid;
    const buttons = [...list.querySelectorAll('[data-training-token]')];
    buttons.forEach(button => {
      const active = valid && button.dataset.trainingToken === choice.value;
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
    });
    if (!buttons.some(button => button.tabIndex === 0) && buttons.length) buttons[0].tabIndex = 0;
    shortcuts.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.trainingCategory === group.value)));
  }

  function renderList() {
    if (!enhanced) return;
    const fragment = document.createDocumentFragment();
    [...choice.querySelectorAll('optgroup')].forEach(section => {
      [...section.querySelectorAll('option')].forEach(option => {
        const button = document.createElement('button');
        button.type = 'button';
        button.setAttribute('role', 'option');
        button.dataset.trainingToken = option.value;
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('aria-hidden', 'true');
        const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
        use.setAttribute('href', icons[section.label] || '#training-learn');
        svg.appendChild(use);
        const text = document.createElement('span');
        const name = document.createElement('strong'); name.textContent = option.textContent;
        const category = document.createElement('small'); category.textContent = section.label;
        text.append(name, category);
        button.append(svg, text);
        button.addEventListener('click', () => {
          choice.value = button.dataset.trainingToken;
          choice.dispatchEvent(new Event('change', {bubbles:true}));
          if (window.matchMedia('(max-width: 900px)').matches) {
            checkout.scrollIntoView({block:'start'});
            root.querySelector('#training-selected-name').focus({preventScroll:true});
          }
        });
        fragment.append(button);
      });
    });
    list.replaceChildren(fragment);
    empty.hidden = !!list.children.length;
    updateSelection();
  }

  function filterTraining() {
    const query = normalize(search.value.trim());
    const category = group.value;
    const selected = choice.value;
    choice.replaceChildren(new Option('Selecione um treinamento', ''));
    let count = 0;
    groups.forEach(section => {
      if (category && category !== section.label) return;
      const matches = section.options.filter(option => normalize(option.label).includes(query));
      if (!matches.length) return;
      const optgroup = document.createElement('optgroup');
      optgroup.label = section.label;
      matches.forEach(option => optgroup.append(new Option(option.label, option.value)));
      choice.append(optgroup);
      count += matches.length;
    });
    choice.value = selected && [...choice.options].some(option => option.value === selected) ? selected : '';
    if (!count) choice.append(new Option('Nenhum treinamento encontrado', ''));
    choice.disabled = !count;
    choice.form.querySelector('.training-native-submit').disabled = !count;
    status.textContent = count ? `${count} treinamento${count === 1 ? '' : 's'} ${count === 1 ? 'disponível' : 'disponíveis'}.` : 'Nenhum treinamento encontrado. Ajuste a busca ou limpe os filtros.';
    renderList();
  }

  search.addEventListener('input', filterTraining);
  group.addEventListener('change', filterTraining);
  root.querySelector('[data-training-clear]')?.addEventListener('click', () => {
    search.value = '';
    group.value = '';
    filterTraining();
    search.focus();
  });
  choice.addEventListener('change', updateSelection);
  if (enhanced) {
    list.id = 'training-options';
    list.setAttribute('aria-required', 'true');
    search.setAttribute('aria-controls', list.id);
    shortcuts.forEach(button => {
      button.setAttribute('aria-controls', list.id);
      button.addEventListener('click', () => {
        group.value = group.value === button.dataset.trainingCategory ? '' : button.dataset.trainingCategory;
        group.dispatchEvent(new Event('change', {bubbles:true}));
      });
    });
    list.addEventListener('keydown', event => {
      const buttons = [...list.querySelectorAll('button')];
      const current = buttons.indexOf(document.activeElement);
      if (current < 0) return;
      let next;
      if (event.key === 'ArrowDown') next = Math.min(current + 1, buttons.length - 1);
      else if (event.key === 'ArrowUp') next = Math.max(current - 1, 0);
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = buttons.length - 1;
      else return;
      event.preventDefault();
      buttons[next].focus();
      choice.value = buttons[next].dataset.trainingToken;
      choice.dispatchEvent(new Event('change', {bubbles:true}));
    });
    root.querySelector('[data-training-change-choice]').addEventListener('click', () => {
      const selected = list.querySelector('[aria-selected="true"]') || list.firstElementChild;
      if (selected) { selected.scrollIntoView({block:'nearest'}); selected.focus({preventScroll:true}); }
    });
    list.hidden = false;
    checkout.hidden = false;
    root.classList.add('training-enhanced');
    renderList();
  }
})();
