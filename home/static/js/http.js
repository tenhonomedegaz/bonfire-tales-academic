/* Pequeno cliente compartilhado para comandos parciais. Nunca repete POST. */
(function (global) {
  'use strict';

  function HttpError(kind, message) {
    this.name = 'BonfireHttpError';
    this.kind = kind;
    this.message = message;
  }
  HttpError.prototype = Object.create(Error.prototype);

  async function postFormJson(url, formData, options) {
    var response;
    var timeoutMs = options && Number.isFinite(options.timeoutMs) ? options.timeoutMs : 15000;
    var controller = typeof AbortController === 'function' ? new AbortController() : null;
    var timedOut = false;
    var timeoutId = controller ? setTimeout(function () {
      timedOut = true;
      controller.abort();
    }, Math.max(0, timeoutMs)) : null;
    try {
      try {
        response = await fetch(url, {
          method: 'POST',
          body: formData,
          credentials: 'same-origin',
          headers: { Accept: 'application/json' },
          signal: controller ? controller.signal : undefined
        });
      } catch (error) {
        throw new HttpError(timedOut ? 'timeout' : 'network', timedOut ? 'Tempo esgotado sem confirmação da operação.' : 'Não foi possível confirmar a operação.');
      }
      var contentType = response.headers.get('content-type') || '';
      if (response.redirected || !/application\/json(?:;|$)/i.test(contentType)) {
        throw new HttpError('unexpected', 'O servidor não confirmou a operação em JSON.');
      }
      var payload;
      try {
        payload = await response.json();
      } catch (error) {
        if (timedOut) throw new HttpError('timeout', 'Tempo esgotado sem confirmação da operação.');
        throw new HttpError('unexpected', 'A resposta do servidor não é um JSON válido.');
      }
      return { status: response.status, payload: payload };
    } finally {
      if (timeoutId !== null) clearTimeout(timeoutId);
    }
  }

  global.BonfireHttp = { HttpError: HttpError, postFormJson: postFormJson };
})(window);
