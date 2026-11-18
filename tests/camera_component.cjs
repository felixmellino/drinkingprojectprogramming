/* Dependency-free camera lifecycle checks with synthetic browser/media objects.
 * node tests/camera_component.cjs — never requests a real camera or location.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('components/drink_camera/index.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const flush = () => new Promise(resolve => setImmediate(resolve));

function setup({denied = false, pending = false} = {}) {
  const listeners = {}, documentListeners = {}, messages = [];
  let calls = 0, stops = 0, release;
  const elements = {};
  for (const id of ['video', 'photo', 'shutter', 'retake', 'retry', 'status']) {
    elements[id] = {hidden:['photo', 'retake', 'retry'].includes(id), disabled:id === 'shutter',
      videoWidth:1200, videoHeight:1600, handlers:{},
      addEventListener(event, handler) { this.handlers[event] = handler; },
      removeAttribute(name) { delete this[name]; }, play() { return Promise.resolve(); }};
  }
  const media = () => ({getTracks:() => [{stop() { stops++; }}]});
  const document = {hidden:false, body:{scrollHeight:580},
    getElementById:id => elements[id],
    addEventListener:(event, handler) => documentListeners[event] = handler,
    createElement:() => ({getContext:() => ({drawImage(){}}), toDataURL:() => 'data:image/jpeg;base64,AAAA'})};
  const window = {isSecureContext:true, parent:{postMessage:msg => messages.push(msg)},
    addEventListener:(event, handler) => listeners[event] = handler};
  const navigator = {mediaDevices:{getUserMedia:async constraints => {
    calls++;
    assert.equal(constraints.audio, false);
    assert.equal(constraints.video.facingMode.ideal, 'environment');
    if (denied) throw {name:'NotAllowedError'};
    if (pending) return new Promise(resolve => release = () => resolve(media()));
    return media();
  }}};
  vm.runInNewContext(script, {document, window, navigator,
    crypto:{randomUUID:() => '00000000-0000-4000-8000-000000000001'}});
  return {elements, listeners, document, documentListeners, messages,
    render:() => listeners.message({source:window.parent, data:{type:'streamlit:render'}}),
    click:id => elements[id].handlers.click(), calls:() => calls, stops:() => stops,
    allow:() => denied = false, release:() => { pending = false; release(); }};
}

(async () => {
  const app = setup();
  assert.equal(app.calls(), 0);
  app.listeners.message({source:{}, data:{type:'streamlit:render'}});
  assert.equal(app.calls(), 0);
  app.render(); await flush();
  assert.equal(app.calls(), 1, 'Camera starts on mount without an extra enable button');
  app.elements.video.handlers.loadeddata();
  assert.equal(app.elements.shutter.disabled, false);
  app.render(); await flush();
  assert.equal(app.calls(), 1, 'GPS rerenders must not reopen camera');
  app.click('shutter');
  assert.equal(app.stops(), 1, 'Capture stops the camera');
  assert.equal(app.elements.photo.hidden, false);
  assert.equal(app.elements.video.hidden, true);
  const saved = app.messages.filter(m => m.type === 'streamlit:setComponentValue');
  assert.equal(saved.length, 1);
  assert.equal(saved[0].value.capture_id, '00000000-0000-4000-8000-000000000001');
  app.render(); await flush();
  assert.equal(app.calls(), 1, 'Captured photo survives rerenders');
  app.click('retake'); await flush();
  assert.equal(app.calls(), 2);
  assert.equal(app.messages.filter(m => m.type === 'streamlit:setComponentValue').at(-1).value, null);
  app.listeners.pagehide();
  assert.equal(app.stops(), 2, 'Leaving the page releases camera');

  const blocked = setup({denied:true});
  blocked.render(); await flush();
  assert.equal(blocked.elements.retry.hidden, false);
  assert.match(blocked.elements.status.textContent, /blocked/);
  assert.equal(blocked.messages.some(m => m.type === 'streamlit:setComponentValue'), false);
  blocked.allow(); blocked.click('retry'); await flush();
  assert.equal(blocked.calls(), 2);

  const late = setup({pending:true});
  late.render();
  late.listeners.pagehide(); late.release(); await flush();
  assert.equal(late.stops(), 1, 'A late permission response cannot leave camera on after navigation');
  assert.equal(late.calls(), 1);

  const background = setup({pending:true});
  background.render();
  background.document.hidden = true; background.documentListeners.visibilitychange();
  background.document.hidden = false; background.documentListeners.visibilitychange();
  background.release(); await flush();
  assert.equal(background.stops(), 1);
  assert.equal(background.calls(), 2, 'Returning while permission is pending restarts a cancelled request');
  console.log('Camera lifecycle checks passed: automatic mount, rerender, capture, retake, denial/retry, navigation and background cancellation.');
})().catch(error => { console.error(error); process.exitCode = 1; });
