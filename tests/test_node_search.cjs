const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor() { this.value = ''; this.children = []; this.listeners = {}; }
  replaceChildren() { this.children = []; }
  appendChild(child) { this.children.push(child); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
}
const context = { window: {}, document: { createElement: () => new Element() } };
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../apps/diagnostic-viewer/node-search.js'), 'utf8'), context);
const nodes = [
  { id: 'vector_space', name: 'Vector Space', nameZh: '向量空间' },
  { id: 'group', name: 'Group', nameZh: '群' },
];

test('Chinese, English and stable IDs select existing nodes without editing data', () => {
  const input = new Element(), select = new Element(), selected = [];
  const before = JSON.stringify(nodes);
  context.window.installNodeSearch(nodes, input, select, id => selected.push(id));
  assert.equal(select.children.length, 2);
  for (const query of ['向量', 'VECTOR', 'vector_space']) {
    input.value = query;
    input.listeners.input();
    assert.equal(select.children.length, 1);
    input.listeners.keydown({ key: 'Enter' });
    assert.equal(selected.at(-1), 'vector_space');
  }
  select.value = 'group'; select.listeners.change();
  assert.equal(selected.at(-1), 'group');
  assert.equal(JSON.stringify(nodes), before);
});

test('empty search results and invalid selection do not select nonexistent nodes', () => {
  const input = new Element(), select = new Element(), selected = [];
  context.window.installNodeSearch(nodes, input, select, id => selected.push(id));
  input.value = 'does-not-exist'; input.listeners.input();
  input.listeners.keydown({ key: 'Enter' });
  select.value = 'invalid'; select.listeners.change();
  assert.equal(select.children.length, 0);
  assert.equal(selected.length, 0);
});
