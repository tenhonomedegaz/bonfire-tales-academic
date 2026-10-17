/* Presentation over the original select, filters and server command. */
(function () {
  'use strict';
  function elapsedPercent(start, end, now) {
    start = Date.parse(start); end = Date.parse(end);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return null;
    return Math.max(0, Math.min(100, (now - start) / (end - start) * 100));
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {elapsedPercent: elapsedPercent};
  if (typeof document === 'undefined') return;
  const root = document.querySelector('.services-shell');
  if (!root) return;
  const choice = document.getElementById('training-choice');
  const icons = {Idiomas:'#training-language', Ferramentas:'#training-tools', Instrumentos:'#training-music', Jogos:'#training-game'};
  const descriptions = {
    Idiomas: 'Aprenda um novo idioma. Essa proficiência será registrada na sua ficha ao concluir o treinamento.',
    Ferramentas: 'Desenvolva proficiência nas ferramentas deste ofício. O aprendizado será registrado ao fim do prazo.',
    Instrumentos: 'Desenvolva proficiência neste instrumento musical. O aprendizado será registrado ao fim do prazo.',
    Jogos: 'Desenvolva proficiência neste conjunto de jogo. O aprendizado será registrado ao fim do prazo.'
  };
  if (choice) {
    const group = document.getElementById('training-group');
    const list = root.querySelector('[data-training-options]');
    list.id = 'training-options'; list.setAttribute('aria-required','true');
    document.getElementById('training-search').setAttribute('aria-controls',list.id);
    const empty = root.querySelector('[data-training-noresults]');
    const title = document.getElementById('training-selected-name');
    const submit = choice.form.querySelector('button[type=submit]');
    const shortcuts = [...root.querySelectorAll('[data-training-category]')];
    shortcuts.forEach(button => button.setAttribute('aria-controls',list.id));
    function updateSelection() {
      const selected = choice.options[choice.selectedIndex];
      const valid = selected && selected.value && !choice.disabled;
      const category = valid ? selected.parentElement.label : '';
      title.textContent = valid ? selected.textContent : 'Escolha o que deseja aprender';
      root.querySelector('[data-training-selected-group]').textContent = category || 'Um novo caminho';
      root.querySelector('[data-training-selected-description]').textContent = descriptions[category] || 'Selecione uma opção para conferir sua matrícula.';
      root.querySelector('[data-training-selected-icon]').setAttribute('href', icons[category] || '#training-learn');
      root.querySelector('.training-checkout').classList.toggle('has-selection', !!valid);
      submit.disabled = !valid;
      list.querySelectorAll('[data-training-token]').forEach(button => {
        const active = valid && button.dataset.trainingToken === choice.value;
        button.setAttribute('aria-selected', String(!!active));
        button.tabIndex = active ? 0 : -1;
      });
      if (!valid && list.firstElementChild) list.firstElementChild.tabIndex = 0;
      shortcuts.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.trainingCategory === group.value)));
    }
    function choose(button, move) {
      choice.value = button.dataset.trainingToken;
      choice.dispatchEvent(new Event('change', {bubbles:true}));
      if (move && window.matchMedia('(max-width: 900px)').matches) {
        root.querySelector('.training-checkout').scrollIntoView({block:'start'});
        title.focus({preventScroll:true});
      }
    }
    function renderList() {
      const fragment = document.createDocumentFragment();
      [...choice.querySelectorAll('optgroup')].forEach(section => [...section.querySelectorAll('option')].forEach(option => {
        const button = document.createElement('button');
        button.type = 'button'; button.setAttribute('role', 'option'); button.dataset.trainingToken = option.value;
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('aria-hidden', 'true');
        const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
        use.setAttribute('href', icons[section.label] || '#training-learn'); svg.appendChild(use);
        const text = document.createElement('span');
        const name = document.createElement('strong'); name.textContent = option.textContent;
        const category = document.createElement('small'); category.textContent = section.label;
        text.append(name,category); button.append(svg,text);
        button.addEventListener('click', () => choose(button,true)); fragment.appendChild(button);
      }));
      list.replaceChildren(fragment); empty.hidden = !!list.children.length; updateSelection();
    }
    shortcuts.forEach(button => button.addEventListener('click', () => {
      group.value = group.value === button.dataset.trainingCategory ? '' : button.dataset.trainingCategory;
      group.dispatchEvent(new Event('change', {bubbles:true}));
    }));
    choice.addEventListener('change', updateSelection);
    list.addEventListener('keydown', event => {
      const buttons = [...list.querySelectorAll('button')];
      const current = buttons.indexOf(document.activeElement);
      if (current < 0) return;
      let next;
      if (event.key === 'ArrowDown') next = Math.min(current+1, buttons.length-1);
      else if (event.key === 'ArrowUp') next = Math.max(current-1,0);
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = buttons.length-1;
      else return;
      event.preventDefault(); buttons[next].focus(); choose(buttons[next],false);
    });
    root.querySelector('[data-training-change-choice]').addEventListener('click', () => {
      const selected = list.querySelector('[aria-selected=true]') || list.firstElementChild;
      if (selected) { selected.scrollIntoView({block:'nearest'}); selected.focus({preventScroll:true}); }
    });
    new MutationObserver(renderList).observe(choice,{childList:true,subtree:true});
    list.hidden = false; root.classList.add('training-enhanced'); renderList();
  }
  const active = root.querySelector('[data-training-start]');
  if (active) {
    function progress() {
      const percent = elapsedPercent(active.dataset.trainingStart,active.dataset.trainingEnd,Date.now());
      if (percent === null) return;
      const bar = active.querySelector('[data-training-progress]');
      bar.setAttribute('aria-valuenow',String(Math.round(percent)));
      bar.firstElementChild.style.width = percent+'%';
      active.querySelector('[data-training-progress-text]').textContent = Math.round(percent)+'% do prazo';
    }
    progress(); window.setInterval(progress,60000);
  }
  if (root.dataset.trainingPreview) {
    const picker = root.querySelector('[data-shop-picker]');
    if (picker && root.dataset.trainingDemo) {
      const input = document.createElement('input'); input.type='hidden'; input.name='demo'; input.value='andamento'; picker.appendChild(input);
    }
    root.addEventListener('submit', event => {
      if (event.target.method.toLowerCase() !== 'post') return;
      event.preventDefault();
      const note = root.querySelector('[data-training-preview-message]');
      note.textContent = 'Prévia visual: a ação não foi executada. Nenhum ouro, treinamento ou contrato foi alterado.';
      note.hidden=false; note.scrollIntoView({block:'nearest'});
    });
  }
})();
