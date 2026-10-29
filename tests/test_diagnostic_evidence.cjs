const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const read = (name) => JSON.parse(fs.readFileSync(path.join(root, 'data/mathematics', name), 'utf8'));
const sources = read('manifest.json').sources;
const source = sources[0];
const alignment = {
  nodes: read('nodes.json').nodes,
  mappings: read('mappings.json').mappings,
  declarations: read('declarations.json').declarations.map(d => ({
    ...d, url: `${sources.find(s => s.id === d.source_id).repository}/blob/${sources.find(s => s.id === d.source_id).revision}/${d.path}#L${d.line_start}`,
  })),
  assertions: read('assertions.json').assertions,
};

// A small DOM contract test; this deliberately does not claim browser/layout coverage.
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.textContent = ''; }
  appendChild(child) { this.children.push(child); }
  get innerHTML() { throw new Error('Untrusted evidence must use textContent'); }
  set innerHTML(value) { throw new Error('Untrusted evidence must use textContent'); }
}
const flatten = (element) => [element, ...element.children.flatMap(flatten)];
const context = { window: {}, document: { createElement: tag => new Element(tag) } };
vm.runInNewContext(fs.readFileSync(path.join(root, 'apps/diagnostic-viewer/formal-evidence.js'), 'utf8'), context);
function render(id, data = alignment) {
  const container = new Element('div');
  context.window.showFormalEvidence(container, { id, semanticKind: 'concept' }, { formalAlignment: data });
  return flatten(container);
}

test('vector-space evidence retains field assumptions and immutable source links', () => {
  const elements = render('vector_space');
  assert(elements.some(e => e.textContent.includes('Field K')));
  assert(elements.some(e => e.textContent.includes('未运行 Lean')));
  const links = elements.filter(e => e.tag === 'a');
  assert.equal(links.length, 1);
  assert(links[0].href.includes(source.revision));
  assert.equal(links[0].rel, 'noopener noreferrer');
});

test('derivative evidence retains the default-zero caveat and separate roles', () => {
  const text = render('derivative').map(e => e.textContent).join('\n');
  assert(text.includes('取值算子'));
  assert(text.includes('具体形式'));
  assert(text.includes('不可微时按约定返回零'));
});

test('external URLs are not made clickable and markup stays literal text', () => {
  const malicious = structuredClone(alignment);
  const mapping = malicious.mappings.find(m => m.node_id === 'vector_space');
  mapping.expression = '<img src=x onerror=alert(1)>';
  malicious.declarations.find(d => d.id === mapping.declaration_id).url = 'javascript:alert(1)';
  const elements = render('vector_space', malicious);
  assert(elements.some(e => e.textContent === mapping.expression));
  assert.equal(elements.filter(e => e.tag === 'a').length, 0);
});

test('legacy field-only snapshots require no formal-evidence payload', () => {
  const container = new Element('div');
  context.window.showFormalEvidence(container, { id: 'mathematics' }, {});
  assert.equal(container.children.length, 0);
});

test('Lean-core links and unassessed relation values retain their meaning', () => {
  const natural = render('natural_numbers');
  assert(natural.some(e => e.tag === 'a' && e.href.startsWith('https://github.com/leanprover/lean4/blob/')));
  const group = render('group').map(e => e.textContent).join('\n');
  assert(group.includes('未知'));
  assert(group.includes('candidate'));
  const summability = render('summability').map(e => e.textContent).join('\n');
  assert(summability.includes('to_additive'));
});
