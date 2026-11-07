(() => {
  'use strict';
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-profile-wall]').forEach(wall => {
      function render(element, text) {
        if (typeof renderBonfireMarkdownElement === 'function') {
          renderBonfireMarkdownElement(element, text, {enableOptions: false});
          element.querySelectorAll('a[href]').forEach(link => {
            link.rel = 'nofollow ugc noopener noreferrer';
          });
          element.querySelectorAll('img').forEach(image => {
            image.referrerPolicy = 'no-referrer';
            image.decoding = 'async';
          });
        } else element.textContent = text;
      }
      wall.querySelectorAll('[data-markdown-source]').forEach(element => render(element, element.dataset.markdownRaw ?? element.textContent));
      const form = wall.querySelector('[data-wall-composer]');
      if (form) {
        const text = form.querySelector('textarea[name="texto"]');
        const preview = form.querySelector('#wall-preview');
        const previewButton = form.querySelector('[data-wall-preview]');
        const status = form.querySelector('[data-wall-editor-status]');
        const count = form.querySelector('[data-wall-count]');
        const emojis = form.querySelector('#wall-emojis');
        const emojiButton = form.querySelector('[data-wall-emojis]');
        const urlTool = form.querySelector('[data-wall-url-tool]');
        const urlInput = form.querySelector('#wall-url');
        let tool = 'image', selection = [0, 0];
        function update() {
          count.textContent = text.value.length.toLocaleString('pt-BR') + ' / 4.000';
          if (!preview.hidden) render(preview, text.value);
        }
        function insert(value, start = text.selectionStart, end = text.selectionEnd) {
          if (text.value.length - (end - start) + value.length > text.maxLength) {
            status.textContent = 'O comentário pode ter até 4.000 caracteres.';return;
          }
          text.setRangeText(value, start, end, 'end');text.focus();status.textContent = '';update();
        }
        form.addEventListener('click', event => {
          const format = event.target.closest('[data-wall-format]');
          if (format) {
            const delimiter = format.dataset.wallFormat === 'bold' ? '**' : '*';
            const start = text.selectionStart, end = text.selectionEnd;
            insert(delimiter + (text.value.slice(start, end) || 'texto') + delimiter, start, end);
          }
          const open = event.target.closest('[data-wall-tool]');
          if (open) {
            tool = open.dataset.wallTool;selection = [text.selectionStart, text.selectionEnd];
            urlTool.hidden = false;urlInput.value = '';urlInput.focus();
          }
          if (event.target.closest('[data-wall-close-tool]')) {urlTool.hidden = true;text.focus();}
          if (event.target.closest('[data-wall-insert-url]')) {
            try {
              const url = new URL(urlInput.value.trim());
              if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw Error('URL');
              const href = url.href.replace(/\(/g, '%28').replace(/\)/g, '%29');
              const label = text.value.slice(...selection).replace(/[\[\]<>\n]/g, '') || (tool === 'image' ? 'Imagem' : 'Link');
              insert((tool === 'image' ? '!' : '') + '[' + label + '](' + href + ')', ...selection);
              urlTool.hidden = true;
            } catch {status.textContent = 'Informe um endereço HTTP ou HTTPS válido.';urlInput.focus();}
          }
          if (event.target.closest('[data-wall-emojis]')) {
            emojis.hidden = !emojis.hidden;emojiButton.setAttribute('aria-expanded', String(!emojis.hidden));
          }
          const emoji = event.target.closest('[data-wall-emoji]');
          if (emoji) insert(emoji.dataset.wallEmoji);
          if (event.target.closest('[data-wall-preview]')) {
            preview.hidden = !preview.hidden;
            previewButton.setAttribute('aria-expanded', String(!preview.hidden));update();
          }
        });
        text.addEventListener('input', update);
        form.addEventListener('keydown', event => {
          if (event.key === 'Escape') {
            urlTool.hidden = true;emojis.hidden = true;emojiButton.setAttribute('aria-expanded', 'false');text.focus();
          }
          if (event.target === urlInput && event.key === 'Enter') {
            event.preventDefault();form.querySelector('[data-wall-insert-url]').click();
          }
        });
        form.addEventListener('submit', event => {
          if (!text.value.trim()) {event.preventDefault();status.textContent = 'Escreva uma mensagem antes de publicar.';return;}
          form.querySelector('[type="submit"]').disabled = true;
        });
        window.addEventListener('pageshow', () => {form.querySelector('[type="submit"]').disabled = false;});
        update();
      }
      wall.querySelectorAll('[data-wall-like]').forEach(like => {
        like.addEventListener('submit', async event => {
          event.preventDefault();const button = like.querySelector('button');
          if (button.disabled) return;
          const status = like.closest('.wall-comment-actions').querySelector('[data-wall-like-status]');
          button.disabled = true;status.textContent = '';
          try {
            const response = await fetch(like.action, {
              method: 'POST', credentials: 'same-origin',
              body: JSON.stringify({curtido: like.querySelector('[name="curtido"]').value === 'true'}),
              headers: {'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json',
                'Content-Type': 'application/json', 'X-CSRFToken': like.querySelector('[name="csrfmiddlewaretoken"]').value}
            });
            const payload = await response.json();
            if (!response.ok || payload.ok !== true) throw Error(payload.erro || 'Não foi possível registrar a curtida.');
            button.setAttribute('aria-pressed', String(payload.curtido));
            button.classList.toggle('is-liked', payload.curtido);
            button.setAttribute('aria-label', payload.curtido ? 'Descurtir comentário' : 'Curtir comentário');
            like.querySelector('[name="curtido"]').value = String(!payload.curtido);
            like.querySelector('[data-wall-like-count]').textContent = payload.curtidas;
          } catch {status.textContent = 'Não foi possível registrar a curtida. Tente novamente.';}
          finally {button.disabled = false;}
        });
      });
      wall.querySelectorAll('[data-wall-remove]').forEach(remove => {
        remove.addEventListener('submit', event => {
          if (!window.confirm('Remover este comentário do perfil?')) event.preventDefault();
        });
      });
    });
  });
})();
