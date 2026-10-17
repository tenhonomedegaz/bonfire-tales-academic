/* Read-only art and source-content explorer; no character or gameplay writes. */
window.initVastierenPage = function (root) {
  if (!root || root.dataset.bound === 'true') return;
  root.dataset.bound = 'true';
  const data = JSON.parse(root.querySelector('#vastierenData').textContent);
  const find = selector => root.querySelector(selector);
  const replaceParagraphs = (target, texts) => {
    target.replaceChildren(...texts.map(text => {
      const paragraph = document.createElement('p');
      paragraph.textContent = text;
      return paragraph;
    }));
  };
  const dialog = find('#vastierenArtDialog');
  let artOpener = find('[data-v-art-open]');
  function updateExplorer() {
    const markNumber = Number(find('[name="vastieren-marks"]:checked').value);
    const mark = data.marks.find(item => item.count === markNumber);
    const form = find('[name="vastieren-form"]:checked').value;
    const estirpeKey = find('[data-v-estirpe]')?.value;
    const estirpe = data.estirpes.find(item => item.slug === estirpeKey);
    const art = data.art_by_estirpe[estirpeKey || 'default']?.[form] || data.art[form];
    find('[data-v-mark-label]').textContent = markNumber === 6 ? '6 MARCAS · ASCENSÃO OPCIONAL' : `${markNumber} ${markNumber === 1 ? 'MARCA' : 'MARCAS'} · NÍVEL ${mark.level}`;
    replaceParagraphs(find('[data-v-manifestation]'), mark.manifestations.map(item => data.slug === 'kitsune' ? `${item.name}: ${item.text}` : item.text));
    const wings = find('[data-v-wing-result]');
    wings.replaceChildren();
    if (mark.wings) {
      const heading = document.createElement('h3');
      heading.textContent = mark.wings.name;
      const paragraph = document.createElement('p');
      paragraph.textContent = mark.wings.text;
      wings.append(heading, paragraph);
    }
    find('[data-v-ascension]').hidden = markNumber !== 6;
    if (estirpe) {
      find('[data-v-estirpe-title]').textContent = estirpe.name;
      replaceParagraphs(find('[data-v-estirpe-description]'), estirpe.paragraphs);
    }
    find('[data-v-art]').src = art.url;
    find('[data-v-art]').alt = `${art.description} Referência ilustrativa: ${art.reference}.`;
    find('[data-v-art-label]').textContent = art.label;
    find('[data-v-art-reference]').textContent = `Referência ilustrativa: ${art.reference}`;
    find('[data-v-art-full]').src = art.url;
    find('[data-v-art-full]').alt = find('[data-v-art]').alt;
    find('[data-v-art-dialog-caption]').textContent = `${art.label} · ${art.reference}`;
  }
  root.querySelectorAll('[name="vastieren-form"], [name="vastieren-marks"], [data-v-estirpe]').forEach(input => input.addEventListener('change', updateExplorer));
  root.querySelectorAll('[data-v-art-open]').forEach(button => button.addEventListener('click', () => {
    artOpener = button;
    dialog.showModal();
  }));
  find('[data-v-art-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => artOpener.focus());
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  const tabs = [...root.querySelectorAll('[data-v-tab]')];
  function activateTab(button) {
    tabs.forEach(tab => {
      const active = tab === button;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      find(`[data-v-panel="${tab.dataset.vTab}"]`).hidden = !active;
    });
  }
  tabs.forEach((button, index) => {
    button.addEventListener('click', () => activateTab(button));
    button.addEventListener('keydown', event => {
      const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length :
        event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length :
        event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : -1;
      if (next < 0) return;
      event.preventDefault();
      activateTab(tabs[next]);
      tabs[next].focus();
    });
  });
  updateExplorer();
};
