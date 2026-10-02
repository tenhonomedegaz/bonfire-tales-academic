(() => {
  const input = document.getElementById('dashboard-search-input');
  const clear = document.getElementById('dashboard-search-clear');
  const status = document.getElementById('dashboard-search-status');
  if (!input || !clear || !status) return;

  const normalize = value => (value || '').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').trim();
  const sections = Array.from(document.querySelectorAll('#content-main .bonfire-admin-tools'));
  const groups = Array.from(document.querySelectorAll('#content-main .app-list .module'));

  function filterNavigation() {
    const query = normalize(input.value);
    let count = 0;

    sections.forEach(section => {
      const groupMatch = query && normalize(section.querySelector('h2')?.textContent).includes(query);
      let visible = 0;
      section.querySelectorAll('.bonfire-admin-tools-grid > a').forEach(link => {
        link.hidden = Boolean(query) && !groupMatch && !normalize(link.textContent).includes(query);
        if (!link.hidden) visible += 1;
      });
      section.hidden = visible === 0;
      count += visible;
    });

    groups.forEach(group => {
      const heading = group.querySelector('caption, h2');
      const groupMatch = query && normalize(heading?.textContent).includes(query);
      let visible = 0;
      group.querySelectorAll('tr').forEach(row => {
        row.hidden = Boolean(query) && !groupMatch && !normalize(row.textContent).includes(query);
        if (!row.hidden) visible += 1;
      });
      group.hidden = visible === 0;
      count += visible;
    });

    clear.hidden = !query;
    status.textContent = query
      ? count ? `${count} ${count === 1 ? 'opção encontrada' : 'opções encontradas'}.`
        : 'Nenhuma tarefa ou cadastro encontrado. Tente outro termo.'
      : `${count} opções disponíveis.`;
  }

  input.addEventListener('input', filterNavigation);
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      input.value = '';
      filterNavigation();
    }
  });
  clear.addEventListener('click', () => {
    input.value = '';
    filterNavigation();
    input.focus();
  });
  filterNavigation();
})();
