(() => {
  'use strict';
  const root = document.querySelector('.ts-page');
  if (!root) return;
  const choices = [...root.querySelectorAll('[data-theme-choice]')];
  const products = [...root.querySelectorAll('[data-theme-product]')];
  const note = root.querySelector('[data-preview-note]');
  const showTheme = (key) => {
    const choice = choices.find(item => item.dataset.themeChoice === key) || choices[0];
    if (!choice) return;
    choices.forEach(other => {
      const selected = other === choice;
      other.classList.toggle('is-selected', selected);
      if (selected) other.setAttribute('aria-current', 'true');
      else other.removeAttribute('aria-current');
    });
    products.forEach(product => product.hidden = product.dataset.themeProduct !== choice.dataset.themeChoice);
    note.textContent = `${choice.querySelector('strong').textContent} em prévia. Nenhuma aparência foi salva.`;
  };
  choices.forEach(choice => choice.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (choice.classList.contains('is-selected')) return;
    const url = new URL(window.location.href);
    url.searchParams.set('tema', choice.dataset.themeChoice);
    history.pushState(history.state, '', url);
    showTheme(choice.dataset.themeChoice);
  }));
  window.addEventListener('popstate', () => {
    showTheme(new URL(window.location.href).searchParams.get('tema'));
  });
  const buttons = [...root.querySelectorAll('[data-preview-context]')];
  buttons.forEach(button => button.addEventListener('click', () => {
    const context = button.dataset.previewContext;
    buttons.forEach(other => other.setAttribute('aria-pressed', String(other === button)));
    root.querySelectorAll('.ts-preview-surface').forEach(surface => {
      surface.dataset.context = context;
      surface.querySelector('.bt-sample-person h3').textContent = context === 'ficha' ? 'Lyra da Fogueira' : 'Lyra · perfil ilustrativo';
      surface.querySelector('.bt-sample-person p').textContent = context === 'ficha' ? 'Mística · Nível 5' : context === 'mestre' ? 'Portfólio de mestre · exemplo' : 'Aventureira de Cinéria · exemplo';
      surface.querySelector('.bt-sample-rule>strong').textContent = context === 'mestre' ? 'Minha maneira de contar histórias' : context === 'perfil' ? 'Sobre esta aventureira' : 'Uma história em Cinéria';
    });
    note.textContent = `Prévia de ${context === 'mestre' ? 'portfólio de mestre' : context} · nenhum dado foi salvo.`;
  }));
})();
