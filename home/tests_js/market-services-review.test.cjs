const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const listeners = {};
const elements = Object.fromEntries([
  '[data-service-subject-label]', '[data-service-subject]', '[data-service-amount]',
  '[data-service-note]', '#service-review-title', '[data-service-confirm]',
  '[data-service-back]',
].map(key => [key, { textContent: '', addEventListener(type, callback) { listeners[`${key}:${type}`] = callback; } }]));
const dialog = {
  open: false,
  querySelector(key) { return elements[key]; },
  addEventListener(type, callback) { listeners[`dialog:${type}`] = callback; },
  showModal() { this.open = true; },
  close() { this.open = false; listeners['dialog:close'](); },
};
const input = { value: '' };
const partial = { name: '', textContent: 'Pagar valor', formNoValidate: false, focus() {} };
const full = { name: 'valor_po', textContent: 'Quitar tudo', formNoValidate: true, focus() {} };
let validity = false;
let submitted = null;
const form = {
  classList: { contains(name) { return name === 'loan-payment'; } },
  dataset: { character: 'Aprendiz', counterpart: 'Credor', balance: '10 PO', balancePc: '1000' },
  addEventListener(type, callback) { listeners[`form:${type}`] = callback; },
  querySelector() { return input; },
  reportValidity() { return validity; },
  requestSubmit(button) {
    submitted = button;
    listeners['form:submit']({ submitter: button, preventDefault() {} });
  },
};
const document = {
  querySelector(key) { return key === '#service-review' ? dialog : null; },
  querySelectorAll() { return [form]; },
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'static', 'js', 'market-services-review.js'), 'utf8'), { document });

const submit = button => listeners['form:submit']({ submitter: button, preventDefault() {} });
submit(partial);
assert.equal(dialog.open, false, 'invalid partial payment must not open review');
assert.equal(submitted, null);

input.value = '0';
submit(full);
assert.equal(dialog.open, true, 'full settlement must open review despite invalid partial amount');
assert.equal(elements['[data-service-subject-label]'].textContent, 'Ficha debitada e credor');
assert.equal(elements['[data-service-subject]'].textContent, 'Aprendiz → Credor');
assert.equal(elements['[data-service-amount]'].textContent, '10 PO');
listeners['[data-service-confirm]:click']();
assert.equal(submitted, full, 'confirmation must preserve the full settlement submitter');

submitted = null;
validity = true;
input.value = '2';
submit(partial);
assert.equal(dialog.open, true);
assert.match(elements['[data-service-amount]'].textContent, /2 PO/);
listeners['[data-service-confirm]:click']();
assert.equal(submitted, partial, 'confirmation must preserve the partial payment submitter');

submitted = null;
input.value = '20';
submit(partial);
assert.equal(dialog.open, true);
assert.equal(elements['[data-service-amount]'].textContent, '10 PO', 'review must show the capped debit');
assert.equal(elements['#service-review-title'].textContent, 'Revisar quitação');
assert.match(elements['[data-service-note]'].textContent, /quitado/);
listeners['[data-service-back]:click']();
assert.equal(submitted, null, 'going back must not submit the capped payment');

form.classList.contains = () => false;
const accept = { name: 'acao', value: 'aceitar', textContent: 'Aceitar', formNoValidate: false, focus() {} };
submit(accept);
assert.equal(elements['[data-service-subject-label]'].textContent, 'Ficha selecionada e contraparte');
assert.equal(elements['[data-service-subject]'].textContent, 'Aprendiz → Credor');
listeners['[data-service-back]:click']();
assert.equal(submitted, null, 'going back must not accept the loan');
