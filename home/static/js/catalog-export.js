(function () {
  'use strict';
  const form = document.getElementById('export-form');
  if (!form) return;
  const models = JSON.parse(document.getElementById('export-schema').textContent);
  const list = document.getElementById('export-tables');
  const editor = document.getElementById('export-editor');
  const previewButton = document.getElementById('preview-export');
  const downloadButton = document.getElementById('download-export');
  const status = document.getElementById('export-status');
  const error = document.getElementById('export-error');
  const sections = new Map();
  const maxTables = Number(document.getElementById('catalog-export').dataset.maxTables);
  let ticket = '', busy = false;
  const ops = {exact: 'Igual a', icontains: 'Contém'};
  function element(tag, text, attrs) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, value));
    return node;
  }
  function select(options, label) {
    const node = element('select', undefined, {'aria-label': label});
    options.forEach(([value, text]) => node.append(element('option', text, {value: value})));
    return node;
  }
  function invalidate() {
    ticket = ''; downloadButton.disabled = true;
    document.getElementById('export-preview').hidden = true;
    error.hidden = true; status.textContent = '';
  }
  function addFilter(model, host) {
    if (host.children.length >= 8) return;
    const row = element('div', undefined, {class: 'export-filter'});
    const fields = model.fields.filter(field => field.operators.length);
    const fieldSelect = select(fields.map(field => [field.name, field.name]), 'Campo do filtro');
    const opSelect = select([], 'Operação do filtro');
    let value;
    function updateOps() {
      opSelect.replaceChildren();
      const field = fields.find(item => item.name === fieldSelect.value);
      field.operators.forEach(op => opSelect.append(element('option', ops[op], {value: op})));
      const next = field.boolean ? select([['True', 'Sim'], ['False', 'Não']], 'Valor do filtro')
        : element('input', undefined, {'aria-label': 'Valor do filtro', maxlength: '500'});
      next.dataset.filterValue = '';
      if (value) value.replaceWith(next);
      value = next;
    }
    updateOps(); fieldSelect.addEventListener('change', updateOps);
    const remove = element('button', '×', {type: 'button', class: 'export-icon', title: 'Remover filtro', 'aria-label': 'Remover filtro'});
    remove.addEventListener('click', () => { row.remove(); host.nextElementSibling.disabled = false; invalidate(); });
    row.append(fieldSelect, opSelect, value, remove); host.append(row);
    host.nextElementSibling.disabled = host.children.length >= 8;
    invalidate();
  }
  function makeSection(model) {
    const section = element('section', undefined, {class: 'export-section', 'data-model': model.name});
    section.append(element('h2', model.label + ' · ' + model.table), element('h3', 'Campos'));
    const columns = element('div', undefined, {class: 'export-columns'});
    model.fields.forEach(field => {
      const label = element('label');
      const box = element('input', undefined, {type: 'checkbox', value: field.name, 'data-column': ''});
      box.checked = true; box.disabled = field.primary;
      label.append(box, document.createTextNode(field.name + (field.primary ? ' (PK)' : '')));
      columns.append(label);
    });
    section.append(columns);
    const dates = model.fields.filter(field => field.date);
    if (dates.length) {
      section.append(element('h3', 'Período'));
      const period = element('div', undefined, {class: 'export-period'});
      const dateField = select([['', 'Sem filtro de período'], ...dates.map(field => [field.name, field.name])], 'Campo de data');
      dateField.dataset.dateField = '';
      const first = element('label', 'De'), last = element('label', 'Até');
      const from = element('input', undefined, {type: 'date', 'data-from': ''});
      const to = element('input', undefined, {type: 'date', 'data-to': ''});
      from.disabled = to.disabled = true;
      dateField.addEventListener('change', () => {
        from.disabled = to.disabled = !dateField.value;
        if (!dateField.value) { from.value = ''; to.value = ''; }
      });
      first.append(from); last.append(to); period.append(dateField, first, last); section.append(period);
    }
    section.append(element('h3', 'Filtros'));
    const filters = element('div', undefined, {'data-filters': ''});
    const add = element('button', '+', {type: 'button', class: 'export-icon', title: 'Adicionar filtro', 'aria-label': 'Adicionar filtro'});
    add.addEventListener('click', () => addFilter(model, filters));
    section.append(filters, add);
    section.addEventListener('change', invalidate); section.addEventListener('input', invalidate);
    return section;
  }
  models.forEach(model => {
    const label = element('label', undefined, {class: 'export-table-option'});
    const box = element('input', undefined, {type: 'checkbox', value: model.name});
    const name = element('span', model.label); name.append(element('small', model.table));
    label.append(box, name); list.append(label);
    box.addEventListener('change', () => {
      invalidate();
      if (box.checked) { const section = makeSection(model); sections.set(model.name, section); editor.append(section); }
      else { sections.get(model.name).remove(); sections.delete(model.name); }
      editor.querySelector('.export-empty').hidden = !!sections.size;
      document.getElementById('selected-count').textContent = sections.size + '/' + maxTables + ' selecionadas';
      list.querySelectorAll('input').forEach(input => { input.disabled = !input.checked && sections.size >= maxTables; });
    });
  });
  document.getElementById('export-search').addEventListener('input', event => {
    const normalized = text => text.normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase();
    const text = normalized(event.target.value);
    list.querySelectorAll('label').forEach(label => { label.hidden = !normalized(label.textContent).includes(text); });
  });
  function specification() {
    return {tables: Array.from(sections, ([name, section]) => {
      const table = {model: name, fields: Array.from(section.querySelectorAll('[data-column]:checked'), box => box.value), filters: []};
      section.querySelectorAll('.export-filter').forEach(row => {
        const selects = row.querySelectorAll('select');
        table.filters.push({field: selects[0].value, op: selects[1].value, value: row.querySelector('[data-filter-value]').value});
      });
      const date = section.querySelector('[data-date-field]');
      if (date) { table.date_field = date.value; table.from = section.querySelector('[data-from]').value; table.to = section.querySelector('[data-to]').value; }
      return table;
    })};
  }
  async function send(action) {
    if (busy) return;
    busy = true; previewButton.disabled = downloadButton.disabled = true;
    error.hidden = true; status.textContent = action === 'preview' ? 'Conferindo…' : 'Gerando arquivo…';
    const body = new FormData(form);
    body.set('action', action);
    const submitted = JSON.stringify(specification());
    body.set('spec', submitted); body.set('ticket', ticket);
    try {
      const response = await fetch(form.action, {method: 'POST', body: body});
      if (!response.ok) {
        const type = response.headers.get('Content-Type') || '';
        const message = type.includes('json') ? (await response.json()).error : 'Acesso negado ou sessão expirada.';
        throw new Error(message);
      }
      if (action === 'download') {
        if (!(response.headers.get('Content-Type') || '').includes('spreadsheetml')) throw new Error('Sessão expirada; entre novamente.');
        const url = URL.createObjectURL(await response.blob());
        const link = element('a', '', {href: url, download: 'bonfire_catalogos.xlsx'});
        document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000);
        status.textContent = 'Arquivo gerado.';
      } else {
        if (!(response.headers.get('Content-Type') || '').includes('json')) throw new Error('Sessão expirada; entre novamente.');
        const data = await response.json();
        if (submitted !== JSON.stringify(specification())) { invalidate(); return; }
        ticket = data.ticket;
        const summary = document.getElementById('export-summary'); summary.replaceChildren(element('p', data.total + ' registros no total'));
        data.tables.forEach(table => {
          summary.append(element('h3', table.table + ' · ' + table.count + ' registros'));
          const wrapper = element('div', undefined, {class: 'export-preview-table'});
          const grid = element('table'), head = element('thead'), tr = element('tr');
          table.fields.forEach(field => tr.append(element('th', field))); head.append(tr); grid.append(head);
          const tbody = element('tbody');
          table.sample.forEach(values => { const line = element('tr'); values.forEach(value => line.append(element('td', value))); tbody.append(line); });
          grid.append(tbody); wrapper.append(grid); summary.append(wrapper);
        });
        document.getElementById('export-preview').hidden = false;
        status.textContent = 'Prévia pronta.';
      }
    } catch (exc) {
      ticket = ''; error.textContent = exc.message; error.hidden = false; status.textContent = '';
    } finally {
      busy = false; previewButton.disabled = false; downloadButton.disabled = !ticket;
    }
  }
  previewButton.addEventListener('click', () => send('preview'));
  downloadButton.addEventListener('click', () => send('download'));
  form.addEventListener('submit', event => { event.preventDefault(); send('preview'); });
}());
