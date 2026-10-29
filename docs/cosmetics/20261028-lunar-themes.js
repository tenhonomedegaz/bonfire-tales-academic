(function () {
    'use strict';
    const themes = [
        ['vermelha', 'Lua Vermelha'], ['negra', 'Lua Negra'], ['cristal', 'Lua de Cristal']
    ];
    const grid = document.getElementById('theme-grid');
    themes.forEach(([key, label]) => {
        const column = document.createElement('section');
        column.className = 'preview-column skin-lua-' + key;
        column.innerHTML = `
          <h2>${label}</h2>
          <section class="public-profile-page theme-data skin-illustrated skin-lua-${key}" data-view="public">
            <div class="public-profile-card">
              <div class="public-profile-banner"><div class="public-profile-banner-media"></div></div>
              <div class="public-profile-body">
                <div class="public-profile-avatar"><img src="../../home/static/brand/human.webp" alt="Retrato do aventureiro"></div>
                <div class="public-profile-main">
                  <div class="public-profile-name-row"><h2>Aventureiro</h2></div>
                  <p class="public-profile-handle">@aventureiro</p>
                  <p class="public-profile-bio">Entre ruínas antigas e novas histórias, a próxima aventura começa ao redor da fogueira.</p>
                </div>
              </div>
            </div>
            <section class="public-profile-section">
              <div class="public-profile-section-head"><h2>Conquistas</h2><span>3 / 7</span></div>
              <ul class="achievement-list"><li>Rank Obsidiana <small>Conquistado</small></li><li>Rank Ametista <small>Conquistado</small></li><li>Rank Topázio <small>Conquistado</small></li></ul>
            </section>
            <section class="public-profile-section">
              <div class="public-profile-section-head"><h2>Personagens</h2><span>1</span></div>
              <div class="character-line"><img src="../../home/static/brand/dwarf.webp" alt=""><div><strong>Guardião de Cinéria</strong><p>Anão · Guerreiro · Nível 12</p></div></div>
            </section>
          </section>
          <section class="profile-page theme-data skin-illustrated skin-lua-${key}" data-view="editor" hidden>
            <section class="profile-editor-group">
              <h2 class="profile-section-title">Dados do Perfil</h2>
              <div class="profile-field"><label class="profile-label" for="name-${key}">Nome de usuário</label><input class="profile-input" id="name-${key}" value="Aventureiro"></div>
              <div class="profile-field"><label class="profile-label" for="bio-${key}">Bio pública</label><textarea class="profile-input" id="bio-${key}" rows="4">Entre ruínas antigas e novas histórias, a próxima aventura começa ao redor da fogueira.</textarea></div>
            </section>
            <section class="profile-editor-group"><h2 class="profile-section-title">Aparência</h2><div class="profile-field"><label class="profile-label" for="banner-${key}">Banner</label><input class="profile-input" id="banner-${key}" placeholder="https://..."></div></section>
          </section>
          <section class="ficha theme-data skin-illustrated skin-lua-${key}" data-view="sheet" hidden>
            <section class="ficha-card"><h2 class="ficha-card-title">Guardião de Cinéria</h2><p>Anão · Guerreiro · Nível 12</p><dl class="sheet-stats"><div><dt>FOR</dt><dd>20</dd></div><div><dt>DES</dt><dd>14</dd></div><div><dt>CON</dt><dd>18</dd></div></dl></section>
            <section class="ficha-card"><h2 class="ficha-card-title">Habilidades</h2><p><strong>Segundo Fôlego</strong></p><p>O guardião recupera suas forças antes de retornar ao combate.</p></section>
            <section class="ficha-card"><h2 class="ficha-card-title">Equipamento</h2><p>Machado de batalha<br>Escudo<br>Cota de malha</p></section>
          </section>`;
        grid.append(column);
    });
    document.querySelectorAll('[name="view"]').forEach(radio => {
        radio.addEventListener('change', () => {
            document.querySelectorAll('[data-view]').forEach(panel => {
                panel.hidden = panel.dataset.view !== radio.value;
            });
        });
    });
}());
