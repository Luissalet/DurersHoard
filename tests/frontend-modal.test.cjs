const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class FakeElement {
  constructor(id = '') {
    this.id = id; this.classList = new FakeClassList(); this.dataset = {};
    this.style = {}; this.value = ''; this.textContent = ''; this.innerHTML = '';
    this.children = []; this.files = []; this.attributes = {};
  }
  addEventListener(name, fn) { this['on' + name] = fn; }
  append(child) { this.children.push(child); }
  querySelector() { return new FakeElement(); }
  focus() { this.focused = true; }
  setPointerCapture() {}
  getBoundingClientRect() { return {left: 0, top: 0, width: 100, height: 100}; }
  click() { this.clicked = true; }
}
class FakeClassList {
  constructor() { this.values = new Set(['hidden']); }
  add(value) { this.values.add(value); }
  remove(value) { this.values.delete(value); }
  toggle(value, force) {
    const next = force === undefined ? !this.values.has(value) : Boolean(force);
    next ? this.values.add(value) : this.values.delete(value);
    return next;
  }
  contains(value) { return this.values.has(value); }
}

async function main() {
  const appPath = path.join(__dirname, '..', 'durer_hoard', 'static', 'app.js');
  const htmlPath = path.join(__dirname, '..', 'durer_hoard', 'static', 'index.html');
  const app = fs.readFileSync(appPath, 'utf8');
  const html = fs.readFileSync(htmlPath, 'utf8');
  assert.match(html, /id="inputModal"/);
  assert.match(html, /id="canvasFields"/);
  assert.match(html, /id="canvasWidth"/);
  assert.match(html, /id="canvasHeight"/);
  assert.match(html, /id="canvasUnits"/);
  assert.doesNotMatch(app, /\bprompt\s*\(/, 'UI must use the modal instead of unsupported prompt()');

  const elements = new Map();
  const get = selector => {
    const key = selector.startsWith('#') ? selector.slice(1) : selector;
    if (!elements.has(key)) elements.set(key, new FakeElement(key));
    return elements.get(key);
  };
  get('#canvasWidth').value = '612';
  get('#canvasHeight').value = '792';
  get('#canvasUnits').value = 'Points';
  const calls = [];
  const item = {id: 'project-1', title: 'Canvas sample', reference: 'hoard://durer/illustration/project-1'};
  const doc = {title: 'Canvas sample', objects: 0, artboards: [], layers: []};
  const response = body => ({ok: true, statusText: 'OK', json: async () => body});
  const fetch = async (url, options = {}) => {
    calls.push({url: String(url), options});
    if (url === '/api/health') return response({engine_configured: true});
    if (url === '/api/illustrations' && !options.method) return response([]);
    if (url === '/api/catalog') return response({tools: [], commands: []});
    if (url === '/api/illustrations' && options.method === 'POST') return response(item);
    if (url === '/api/illustrations/project-1' && !options.method) return response(item);
    if (url === '/api/illustrations/import?title=Reference' && options.method === 'POST') return response(item);
    if (url.endsWith('/actions') && options.method === 'POST') {
      return response({results: [{name: 'inspect_document', result: {content: [{text: JSON.stringify(doc)}]}}]});
    }
    throw new Error(`Unexpected request ${options.method || 'GET'} ${url}`);
  };
  const document = {
    documentElement: {lang: ''},
    querySelector: get,
    querySelectorAll: () => [],
    createElement: tag => new FakeElement(tag),
  };
  const sandbox = {
    document, localStorage: {getItem: () => 'en', setItem() {}}, fetch,
    FormData, File, URLSearchParams, console, setTimeout, clearTimeout,
    prompt: () => { throw new Error('prompt() was called'); },
    Date, JSON, Math, Number, String, Error, encodeURIComponent,
  };
  vm.runInNewContext(app, sandbox, {filename: appPath});
  await new Promise(resolve => setImmediate(resolve));
  assert(calls.some(call => call.url === '/api/health'));
  assert(calls.some(call => call.url === '/api/illustrations'));

  get('#createButton').onclick();
  assert.equal(get('#inputModal').classList.contains('hidden'), false);
  assert.equal(get('#canvasFields').classList.contains('hidden'), false);
  assert.equal(get('#inputValue').focused, true);
  get('#inputValue').value = 'Canvas sample';
  get('#canvasWidth').value = '400';
  get('#canvasHeight').value = '300';
  get('#canvasUnits').value = 'Millimeters';
  await get('#inputForm').onsubmit({preventDefault() {}});
  const createCall = calls.find(call => call.url === '/api/illustrations' && call.options.method === 'POST');
  assert.deepEqual(JSON.parse(createCall.options.body), {
    title: 'Canvas sample', width: 400, height: 300, units: 'Millimeters',
  });

  get('#importFile').onchange({target: {files: [new File(['<svg/>'], 'Reference.svg')], value: 'picked'}});
  assert.equal(get('#canvasFields').classList.contains('hidden'), true);
  get('#inputValue').value = 'Reference';
  await get('#inputForm').onsubmit({preventDefault() {}});
  assert(calls.some(call => call.url === '/api/illustrations/import?title=Reference' && call.options.body instanceof FormData));

  get('#textTool').onclick();
  assert.equal(get('#canvasFields').classList.contains('hidden'), true);
  get('#inputValue').value = 'A title';
  await get('#inputForm').onsubmit({preventDefault() {}});
  const actionCall = calls.filter(call => call.url.endsWith('/actions') && call.options.method === 'POST')
    .find(call => JSON.parse(call.options.body).actions[0].name === 'add_text');
  assert(actionCall, 'text submit must dispatch the native add_text action');
  const payload = JSON.parse(actionCall.options.body);
  assert.equal(payload.actions[0].name, 'add_text');
  assert.equal(payload.actions[0].arguments.text, 'A title');
  console.log('DOM modal workflow passed: boot, create canvas, import, and add text');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
