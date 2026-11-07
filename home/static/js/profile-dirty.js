/* The original profile POST and live preview remain unchanged. No-JS keeps Save. */
(function () {
  'use strict';
  var form = document.getElementById('perfil-form');
  if (!form) return;
  var bar = form.querySelector('.profile-save-bar');
  if (!bar) return;
  function snapshot() {
    return JSON.stringify(Array.from(form.elements).filter(function (field) {
      return field.name && !['submit', 'button', 'hidden'].includes(field.type);
    }).map(function (field) {
      if (field.type === 'file') return [field.name, Array.from(field.files || []).map(function (file) {
        return [file.name, file.size, file.lastModified];
      })];
      if (field.type === 'checkbox' || field.type === 'radio') return [field.name, field.value, field.checked];
      if (field.multiple) return [field.name, Array.from(field.selectedOptions).map(function (option) { return option.value; })];
      return [field.name, field.value];
    }));
  }
  var initial = snapshot();
  var failedSave = form.dataset.saveError === 'true';
  function update() { bar.hidden = !failedSave && snapshot() === initial; }
  form.addEventListener('input', update);
  form.addEventListener('change', update);
  form.addEventListener('reset', function () { requestAnimationFrame(update); });
  window.addEventListener('pageshow', update);
  update();
})();

