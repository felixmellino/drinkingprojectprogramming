// The initial theme bridge stays quiet unless the browser has a saved choice.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const component = fs.readFileSync('components/theme_switch/index.html', 'utf8')
  .match(/<script>([\s\S]*?)<\/script>/)[1];

function reportedValues(savedChoice) {
  const messages = [];
  const parent = { postMessage: message => messages.push(message) };
  let receive;
  vm.runInNewContext(component, {
    localStorage: { getItem: () => savedChoice },
    window: { parent, addEventListener: (_, callback) => { receive = callback; } },
  });
  const render = { source: parent, data: { type: 'streamlit:render', args: { mode: 'reader' } } };
  receive(render);
  receive(render);
  return messages.filter(message => message.type === 'streamlit:setComponentValue')
    .map(message => message.value);
}

assert.deepEqual(reportedValues(null), []);
assert.deepEqual(reportedValues('invalid'), []);
assert.deepEqual(reportedValues('dark'), ['dark']);
assert.deepEqual(reportedValues('light'), ['light']);
console.log('Theme reader: no redundant rerun for an unset choice; saved themes report once.');
