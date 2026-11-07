const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../static/js/privacy-choices.js'),'utf8');

function setup({hasButton=true}={}) {
  const listeners={};
  const button={hidden:true,addEventListener:(event,fn)=>{listeners[event]=fn;}};
  const window={};
  Object.defineProperty(window,'localStorage',{get(){throw Error('Do not store consent here');}});
  const context={window,document:{querySelector:()=>hasButton?button:null}};
  vm.runInNewContext(source,context);
  return {window,button,listeners};
}

test('no ads/privacy control: no CMP global is initialized',()=>{
  const {window}=setup({hasButton:false});assert.equal(window.googlefc,undefined);
});
test('CMP absent or blocked: button stays hidden, no fallback consent',()=>{
  const {window,button}=setup();assert.equal(button.hidden,true);
  window.googlefc.callbackQueue.shift().CONSENT_API_READY();
  assert.equal(button.hidden,true);
});
test('only a ready CMP with applicable region reveals control; click uses its queue',()=>{
  const {window,button,listeners}=setup();let onConsent,reopened=0;
  window.__tcfapi=(command,version,callback)=>{
    assert.equal(command,'addEventListener');assert.equal(version,0);onConsent=callback;
  };
  window.googlefc.showRevocationMessage=()=>reopened++;
  window.googlefc.callbackQueue.shift().CONSENT_API_READY();
  for(const [data,success] of [[null,false],[{},true],[{gdprApplies:false},true]]){
    onConsent(data,success);assert.equal(button.hidden,true);
  }
  onConsent({gdprApplies:true},true);assert.equal(button.hidden,false);
  listeners.click();assert.equal(reopened,0);
  window.googlefc.callbackQueue.shift().CONSENT_API_READY();assert.equal(reopened,1);
  onConsent(null,false);assert.equal(button.hidden,true);
});
test('regional data without revocation API never reveals a broken control',()=>{
  const {window,button}=setup();
  window.__tcfapi=(_command,_version,callback)=>callback({gdprApplies:true},true);
  window.googlefc.callbackQueue.shift().CONSENT_API_READY();assert.equal(button.hidden,true);
});
