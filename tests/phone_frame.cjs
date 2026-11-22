// Laptops open the app inside the phone frame; phones, tablets and the frame itself do not.
// node tests/phone_frame.cjs — pure functions only, no browser or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const component = fs.readFileSync('components/theme_switch/index.html', 'utf8')
  .match(/<script>([\s\S]*?)<\/script>/)[1];
const context = { window: { parent: { postMessage() {} }, addEventListener() {} }, URL, URLSearchParams };
vm.runInNewContext(component, context);
const target = context.phoneFrameTarget;
const CLOUD = 'https://wegopubnow.streamlit.app';

// Phones, tablets and narrow windows: the normal app.
assert.equal(target(`${CLOUD}/~/+/Map`, false, '/', false), null);
// The player asked for the wide view in this tab.
assert.equal(target(`${CLOUD}/~/+/Map`, true, '/', true), null);
// Already inside the phone: never again (no loop).
assert.equal(target(`${CLOUD}/~/+/Map`, true, '/~/+/app/static/phone.html', false), null);
// Laptop on Streamlit Cloud (inside Cloud's own page): the frame, same address, same page.
assert.equal(target(`${CLOUD}/~/+/Map`, true, '/', false), `${CLOUD}/~/+/app/static/phone.html?to=Map`);
assert.equal(target(`${CLOUD}/~/+/`, true, '/', false), `${CLOUD}/~/+/app/static/phone.html`);
// An invitation link keeps its page and query.
assert.equal(target(`${CLOUD}/~/+/Lobby?lobby_invite=ab-12`, true, '/', false),
  `${CLOUD}/~/+/app/static/phone.html?to=Lobby%3Flobby_invite%3Dab-12`);
// Local run without a surrounding page.
assert.equal(target('http://localhost:8501/Ranks', true, null, false), 'http://localhost:8501/app/static/phone.html?to=Ranks');

// The frame opens only pages of this app (no open redirect to another site).
const phone = fs.readFileSync('static/phone.html', 'utf8');
const source = phone.match(/function appPath\(search\) \{[\s\S]*?\n  \}/)[0];
const appPath = vm.runInNewContext(`(${source})`, { URLSearchParams });
assert.equal(appPath('?to=Map'), 'Map');
assert.equal(appPath('?to=Lobby%3Flobby_invite%3Dab-12'), 'Lobby?lobby_invite=ab-12');
assert.equal(appPath(''), '');
for (const bad of ['https%3A%2F%2Fevil.example', '%2F%2Fevil.example', 'javascript%3Aalert(1)', '..%2F..%2Fsecrets', 'Map%2F..%2Fx']) {
  assert.equal(appPath(`?to=${bad}`), '', bad);
}
console.log('Phone frame: laptops only, no loop, deep links kept, other sites refused.');
