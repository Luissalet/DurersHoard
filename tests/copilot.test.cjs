// What the Faustus copilot learns about the editor, and how it refreshes after a turn. Run: node --test tests/
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SOURCE = fs.readFileSync(path.join(__dirname, '..', 'durer_hoard', 'static', 'copilot.js'), 'utf8');
const plain = (value) => JSON.parse(JSON.stringify(value));   // objects made inside the vm have another prototype
const { buildContext, illustrationObject, selectedObject, editorState, MAX_OBJECTS } = require('../durer_hoard/static/copilot.js');

const CURRENT = { id: 'ill_01', title: 'Dragon crest', reference: 'hoard://durer/illustration/ill_01' };
const DOC = {
  title: 'Dragon crest', objects: 3, artboards: [{ width: 612, height: 792 }],
  layers: [{ kind: 'Layer', id: 1, name: 'Layer 1', children: [
    { kind: 'Rectangle', id: 11, name: 'Shield', fill: '#112233', stroke: '#ffffff', strokeWidth: 2, children: [] },
    { kind: 'Group', id: 12, name: 'Wings', children: [{ kind: 'Path', id: 13, name: '', fill: '#ff0000', strokeWidth: 1.234, children: [] }] },
  ] }],
};

test('the open illustration is the project and an object with its objects as ids and names', () => {
  const ctx = buildContext({ current: CURRENT, selectedIds: [], doc: DOC });
  assert.deepEqual(ctx.project, { external_project_id: 'ill_01', title: 'Dragon crest' });
  assert.equal(ctx.view.page, 'workspace');
  assert.equal(ctx.active_objects.length, 1);
  const ill = ctx.active_objects[0];
  assert.deepEqual([ill.kind, ill.object_id, ill.title, ill.reference], ['illustration', 'ill_01', 'Dragon crest', 'hoard://durer/illustration/ill_01']);
  assert.equal(ill.object_count, 3);
  assert.deepEqual(ill.artboards, [{ width: 612, height: 792 }]);
  assert.deepEqual(ill.objects.map((o) => [o.id, o.kind, o.title, o.parent_id]), [[11, 'Rectangle', 'Shield', undefined], [12, 'Group', 'Wings', undefined], [13, 'Path', '#13', 12]]);
});

test('selected objects carry their paint as the engine reports it', () => {
  const ctx = buildContext({ current: CURRENT, selectedIds: [11, 13, 999], doc: DOC });
  assert.deepEqual(ctx.active_objects.map((o) => [o.kind, o.object_id]), [['illustration', 'ill_01'], ['object', '11'], ['object', '13']]);
  assert.deepEqual(selectedObject(CURRENT, DOC, 11), { kind: 'object', object_id: '11', title: 'Shield', object_kind: 'Rectangle', illustration_id: 'ill_01', fill: '#112233', stroke: '#ffffff', strokeWidth: 2 });
  const path13 = selectedObject(CURRENT, DOC, 13);
  assert.equal(path13.parent_id, 12);
  assert.equal(path13.strokeWidth, 1.23);
  assert.equal('stroke' in path13, false);
});

test('without an illustration (the library, or one that is gone) there are no objects and no project', () => {
  for (const current of [null, undefined, {}]) {
    const ctx = buildContext({ current, selectedIds: [11], doc: DOC });
    assert.deepEqual(ctx.active_objects, []);
    assert.equal('project' in ctx, false);
    assert.equal(ctx.view.page, 'library');
  }
  assert.deepEqual(buildContext().active_objects, []);
});

test('an illustration whose inspection failed still names itself', () => {
  const ctx = buildContext({ current: CURRENT, selectedIds: [11], doc: null });
  assert.deepEqual(ctx.active_objects.map((o) => o.kind), ['illustration']);
  assert.equal(ctx.active_objects[0].objects, undefined);
});

test('a long object list is capped and says how much was left out', () => {
  const children = Array.from({ length: MAX_OBJECTS + 5 }, (_, i) => ({ kind: 'Path', id: 100 + i, name: 'p' + i, children: [] }));
  const ill = illustrationObject(CURRENT, { objects: children.length, artboards: [], layers: [{ kind: 'Layer', id: 1, children }] });
  assert.equal(ill.objects.length, MAX_OBJECTS);
  assert.equal(ill.objects_truncated, 5);
});

test('transform values are ignored in the library, where their fields are hidden', () => {
  const ctx = buildContext({ current: null, form: { transform: { moveX: '5' } } });
  assert.equal(ctx.view.editor, undefined);
  assert.deepEqual(ctx.active_objects, []);
});

test('a half filled New dialog travels in view.editor', () => {
  const state = editorState({ dialog: { open: true, purpose: 'create', value: ' Poster ', width: '612', height: '792', units: 'Points' }, transform: {} });
  assert.deepEqual(state, { kind: 'new_illustration', dirty: true, fields: { title: 'Poster', width: '612', height: '792', units: 'Points' } });
  const empty = editorState({ dialog: { open: true, purpose: 'import', value: '' }, transform: {} });
  assert.deepEqual(empty, { kind: 'import_illustration', dirty: false, fields: { title: '' } });
  assert.deepEqual(editorState({ dialog: { open: true, purpose: 'text', value: 'Hello' } }), { kind: 'add_text', dirty: true, fields: { text: 'Hello' } });
});

test('transform values typed but not applied travel in view.editor, defaults do not', () => {
  assert.equal(editorState({ transform: { moveX: '0', moveY: '', scaleValue: '100', rotationValue: '0' } }), null);
  assert.deepEqual(editorState({ transform: { moveX: '12', moveY: '0', scaleValue: '150', rotationValue: '0' } }),
    { kind: 'transform', dirty: true, fields: { moveX: '12', scaleValue: '150' } });
  const ctx = buildContext({ current: CURRENT, doc: DOC, catalogOpen: true, form: { transform: { moveX: '5' } } });
  assert.equal(ctx.view.catalog_open, true);
  assert.equal(ctx.view.editor.kind, 'transform');
});

// ---- window.hoardCopilot wiring: the script run against a fake page ----

function page({ state, routes = {} }) {
  const values = { fillColor: '#123456', moveX: '7', inputValue: '', scaleValue: '100' };
  const hidden = new Set(['inputModal', 'catalogModal']);
  const elements = {};
  const el = (id) => (elements[id] ||= { id, get value() { return values[id] ?? ''; }, set value(v) { values[id] = v; }, classList: { contains: (c) => c === 'hidden' && hidden.has(id) } });
  const calls = [];
  const events = [];
  const win = {
    document: { getElementById: (id) => (['workspace', 'projectTitle'].includes(id) ? null : el(id)) },
    fetch: async (url, options = {}) => {
      calls.push(`${options.method || 'GET'} ${url}`);
      const handler = routes[`${options.method || 'GET'} ${url}`] || routes[url];
      if (!handler) throw new Error('unexpected ' + url);
      const out = typeof handler === 'function' ? await handler(options) : handler;
      return { ok: out.status === undefined || out.status < 400, status: out.status ?? 200, json: async () => out.body };
    },
    Event: class { constructor(type) { this.type = type; } },
    dispatchEvent: (e) => events.push(e.type),
    __durerCopilot: {
      state: () => state,
      refreshed: 0, projectsCalled: 0, closed: 0,
      async refresh() { this.refreshed += 1; },
      async projects() { this.projectsCalled += 1; },
      closeIllustration() { this.closed += 1; },
    },
    setTimeout, clearTimeout, Object, JSON, Number, Math, Error, Array, String, Promise,
  };
  win.window = win;
  vm.runInNewContext(SOURCE, win);
  return { win, values, calls, events, hidden };
}

const inspectRoute = (doc) => ({ body: { results: [{ name: 'inspect_document', result: { content: [{ text: JSON.stringify(doc) }] } }] } });

test('context() reads the illustration and its objects from the server at the time of the turn', async () => {
  const fresh = { ...DOC, objects: 4, layers: [{ kind: 'Layer', id: 1, children: [{ kind: 'Star', id: 21, name: 'Added by the agent', children: [] }] }] };
  const { win, calls } = page({
    state: { current: CURRENT, selectedIds: [21], lastDocument: DOC, inputPurpose: 'create' },
    routes: { '/api/illustrations/ill_01': { body: { ...CURRENT, title: 'Dragon crest v2' } }, 'POST /api/illustrations/ill_01/actions': inspectRoute(fresh) },
  });
  const ctx = plain(await win.hoardCopilot.context({}));
  assert.deepEqual(calls, ['GET /api/illustrations/ill_01', 'POST /api/illustrations/ill_01/actions']);
  assert.equal(ctx.project.title, 'Dragon crest v2');
  assert.equal(ctx.active_objects[0].objects[0].title, 'Added by the agent');
  assert.deepEqual(ctx.active_objects[1], { kind: 'object', object_id: '21', title: 'Added by the agent', object_kind: 'Star', illustration_id: 'ill_01' });
  assert.equal(ctx.view.editor.fields.moveX, '7');
});

test('context() for an illustration the server no longer has returns no objects', async () => {
  const { win } = page({ state: { current: CURRENT, selectedIds: [11], lastDocument: DOC }, routes: { '/api/illustrations/ill_01': { status: 404, body: {} } } });
  const ctx = plain(await win.hoardCopilot.context({}));
  assert.deepEqual(ctx.active_objects, []);
  assert.equal('project' in ctx, false);
  assert.equal(ctx.view.page, 'library');
});

test('context() falls back to the last inspection when the engine cannot be asked, and never rejects', async () => {
  const { win } = page({
    state: { current: CURRENT, selectedIds: [], lastDocument: DOC },
    routes: { '/api/illustrations/ill_01': { body: CURRENT }, 'POST /api/illustrations/ill_01/actions': { status: 503, body: {} } },
  });
  const ctx = plain(await win.hoardCopilot.context({}));
  assert.equal(ctx.active_objects[0].object_count, 3);
  const broken = page({ state: null });
  assert.deepEqual(plain(await broken.win.hoardCopilot.context({})).active_objects, []);
  const throwing = page({ state: { get current() { throw new Error('boom'); } } });
  assert.deepEqual(plain(await throwing.win.hoardCopilot.context({})).active_objects, []);
});

test('context() in the library is empty but still sees the dialog being filled in', async () => {
  const { win, values, hidden } = page({ state: { current: null, selectedIds: [], lastDocument: null, inputPurpose: 'create' } });
  hidden.delete('inputModal');
  values.inputValue = 'New poster';
  const ctx = plain(await win.hoardCopilot.context({}));
  assert.deepEqual(ctx.active_objects, []);
  assert.equal('project' in ctx, false);
  assert.equal(ctx.view.page, 'library');
  assert.equal(ctx.view.editor.kind, 'new_illustration');
  assert.equal(ctx.view.editor.fields.title, 'New poster');
});

test('onTurnEnd refreshes once and keeps what is typed', async () => {
  const { win, values } = page({ state: { current: CURRENT, selectedIds: [], lastDocument: DOC }, routes: { '/api/illustrations/ill_01': { body: CURRENT } } });
  win.hoardCopilot.onTurnEnd({});
  win.hoardCopilot.onTurnEnd({});
  await new Promise((resolve) => setTimeout(resolve, 400));
  assert.equal(win.__durerCopilot.refreshed, 1);
  assert.equal(win.__durerCopilot.projectsCalled, 1);
  assert.equal(values.fillColor, '#123456');
  assert.equal(values.moveX, '7');
});

test('typing while the turn-end library request is pending is kept', async () => {
  const { win, values } = page({ state: { current: CURRENT, selectedIds: [], lastDocument: DOC }, routes: { '/api/illustrations/ill_01': { body: CURRENT } } });
  let finish, started;
  const waiting = new Promise((resolve) => { started = resolve; });
  win.__durerCopilot.projects = () => new Promise((resolve) => { finish = resolve; started(); });
  win.hoardCopilot.onTurnEnd({});
  await waiting;
  values.moveX = '28';
  values.inputValue = 'typed during reload';
  finish();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(values.moveX, '28');
  assert.equal(values.inputValue, 'typed during reload');
});

test('a context read keeps the form snapshot from before its native reads', async () => {
  let finish, started;
  const waiting = new Promise((resolve) => { started = resolve; });
  const { win, values } = page({ state: { current: CURRENT, selectedIds: [], lastDocument: DOC }, routes: {
    '/api/illustrations/ill_01': () => new Promise((resolve) => { finish = () => resolve({ body: CURRENT }); started(); }),
    'POST /api/illustrations/ill_01/actions': inspectRoute(DOC),
  } });
  const pending = win.hoardCopilot.context();
  await waiting;
  values.moveX = '42';
  finish();
  const ctx = await pending;
  assert.equal(ctx.view.editor.fields.moveX, '7');
});

test('onTurnEnd closes an illustration the agent deleted', async () => {
  const { win } = page({ state: { current: CURRENT, selectedIds: [], lastDocument: DOC }, routes: { '/api/illustrations/ill_01': { status: 404, body: {} } } });
  win.hoardCopilot.onTurnEnd({});
  await new Promise((resolve) => setTimeout(resolve, 400));
  assert.equal(win.__durerCopilot.closed, 1);
  assert.equal(win.__durerCopilot.refreshed, 0);
});
