/* Slots de magia: atualização confirmada pelo servidor, sem retry automático. */
(function () {
  'use strict';

  function uuid() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
    var bytes = new Uint8Array(16);
    if (!window.crypto || typeof window.crypto.getRandomValues !== 'function') throw new Error('Gerador seguro de operação indisponível.');
    window.crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    return Array.prototype.map.call(bytes, function (byte, index) {
      return (index === 4 || index === 6 || index === 8 || index === 10 ? '-' : '') + byte.toString(16).padStart(2, '0');
    }).join('');
  }

  function message(card, text, ok) {
    var output = card.querySelector('[data-spell-slot-feedback]');
    if (!output) return;
    output.textContent = text || '';
    output.hidden = !text;
    output.classList.toggle('is-ok', !!ok);
    output.classList.toggle('is-err', !ok);
  }

  function setBusy(card, busy, retryForm) {
    card.setAttribute('aria-busy', busy ? 'true' : 'false');
    card.querySelectorAll('[data-spell-slot-form] button[type="submit"]').forEach(function (button) {
      if (busy) {
        button.disabled = true;
      } else if (retryForm && button.form === retryForm) {
        button.disabled = false;
      } else if (retryForm) {
        button.disabled = true;
      }
    });
  }

  function validPayload(result, operationId, level) {
    var payload = result && result.payload;
    var slot = payload && payload.slot;
    var validSlot = slot && Number.isSafeInteger(slot.nivel) && slot.nivel === Number(level) &&
      Number.isSafeInteger(slot.atual) && Number.isSafeInteger(slot.total) &&
      slot.atual >= 0 && slot.total >= 0 && slot.atual <= slot.total;
    var allowedError = result && (result.status === 400 || result.status === 409);
    if (!payload || typeof payload.ok !== 'boolean') return null;
    if (!payload.ok && result.status === 503 && payload.code === 'disabled' && !slot && !payload.operation_id) return { payload: payload, noSnapshot: true };
    if (payload.operation_id !== operationId || typeof payload.version !== 'string' || payload.version.length === 0 || !validSlot) return null;
    if (payload.ok && result.status >= 200 && result.status < 300) return { payload: payload, noSnapshot: false };
    if (!payload.ok && allowedError) return { payload: payload, noSnapshot: false };
    return null;
  }

  function applySnapshot(card, payload) {
    var slot = payload.slot;
    card.setAttribute('data-slot-version', payload.version);
    card.querySelectorAll('input[name="expected_version"]').forEach(function (input) { input.value = payload.version; });
    var atual = card.querySelector('[data-slot-atual]');
    var total = card.querySelector('[data-slot-total]');
    if (atual) atual.textContent = slot.atual;
    if (total) total.textContent = slot.total;
    document.querySelectorAll('[data-slot-summary="' + slot.nivel + '"]').forEach(function (summary) {
      summary.textContent = slot.atual + '/' + slot.total;
    });
    setAvailability(card, slot);
  }

  function setAvailability(card, slot) {
    card.querySelectorAll('[data-slot-action]').forEach(function (button) {
      var action = button.getAttribute('data-slot-action');
      button.disabled = action === 'gastar' ? Number(slot.atual) <= 0 : Number(slot.atual) >= Number(slot.total);
    });
  }

  function restoreFocus(card, submitter) {
    var active = document.activeElement;
    var userMovedFocus = active !== submitter && active !== document.body && active !== document.documentElement;
    if (userMovedFocus) return;
    if (!submitter.disabled) {
      try { submitter.focus({ preventScroll: true }); } catch (error) { submitter.focus(); }
      return;
    }
    try { card.focus({ preventScroll: true }); } catch (error) { card.focus(); }
  }

  function init(card) {
    var inFlight = false;
    var recovery = null;
    card.querySelectorAll('[data-spell-slot-form]').forEach(function (form) {
      form.addEventListener('submit', async function (event) {
        event.preventDefault();
        if (inFlight) return;
        var submitter = event.submitter || form.querySelector('button[type="submit"]');
        if (!submitter || submitter.disabled) return;
        if (recovery && recovery.form !== form) {
          message(card, 'Repita a ação anterior para confirmar seu resultado.', false);
          return;
        }
        var operationInput = form.querySelector('input[name="operation_id"]');
        var operationId = recovery ? recovery.operationId : uuid();
        operationInput.value = operationId;
        inFlight = true;
        setBusy(card, true);
        message(card, 'Confirmando…', true);
        try {
          var result = await window.BonfireHttp.postFormJson(form.action, new FormData(form));
          var validated = validPayload(result, operationId, card.getAttribute('data-slot-level'));
          if (!validated) throw new window.BonfireHttp.HttpError('unexpected', 'A resposta do servidor não confirmou este slot.');
          var payload = validated.payload;
          if (!validated.noSnapshot) applySnapshot(card, payload);
          recovery = null;
          card.querySelectorAll('input[name="operation_id"]').forEach(function (input) { input.value = ''; });
          if (validated.noSnapshot) {
            window.location.reload();
            return;
          }
          message(card, payload.message || (payload.ok ? 'Slot atualizado.' : 'Não foi possível atualizar o slot.'), payload.ok);
          if (!payload.ok && result.status === 409) message(card, payload.message || 'O slot foi alterado em outra sessão; dados atualizados.', false);
          restoreFocus(card, submitter);
        } catch (error) {
          recovery = { form: form, operationId: operationId };
          setAvailability(card, {
            atual: Number((card.querySelector('[data-slot-atual]') || {}).textContent),
            total: Number((card.querySelector('[data-slot-total]') || {}).textContent)
          });
          message(card, 'Resultado não confirmado. Repita esta mesma ação para reconciliar.', false);
        } finally {
          inFlight = false;
          setBusy(card, false, recovery && recovery.form);
        }
      });
    });
  }

  function start() {
    if (!window.BonfireHttp) return;
    document.querySelectorAll('[data-spell-slot-card]').forEach(init);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
