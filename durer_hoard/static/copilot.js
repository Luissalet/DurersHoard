/* Dürer's Hoard — the editor's side of the Faustus copilot (window.hoardCopilot).
 *
 * The floating "Faustus" button and its side panel come from /api/copilot/launcher.js (Hoard Link's install_copilot adds
 * it to every page). Before each turn the launcher calls hoardCopilot.context(base): the answer here is the illustration
 * open in the workspace, the objects selected in its inspector (read from the engine with inspect_document, so what an
 * agent changed earlier is already in it) and any form the person has half filled in. When a turn ends, onTurnEnd
 * re-reads the illustration, its objects and the library without touching what is typed.
 *
 * Plain classic script, no build. The builders are pure (node can load them); the wiring reads the editor's state through
 * window.__durerCopilot, defined at the end of app.js.
 */
(function (root) {
  'use strict';
  var MAX_OBJECTS = 60;

  function walkObjects(nodes, parent, out) {
    (nodes || []).forEach(function (node) {
      if (!node || typeof node !== 'object') return;
      if (node.kind !== 'Layer') out.push({ node: node, parent: parent });
      walkObjects(node.children, node.kind === 'Layer' ? parent : node.id, out);
    });
    return out;
  }

  function findObject(nodes, id) {
    var found = null;
    walkObjects(nodes, null, []).forEach(function (row) { if (!found && String(row.node.id) === String(id)) found = row; });
    return found;
  }

  function title(node) { return node.name || ('#' + node.id); }

  function small(value) {
    var n = Number(value);
    return Number.isFinite(n) ? Math.round(n * 100) / 100 : undefined;
  }

  /** The illustration open in the workspace: identity, size and its objects as ids, kinds and names (capped). */
  function illustrationObject(current, doc) {
    var out = { kind: 'illustration', object_id: String(current.id), title: current.title || String(current.id) };
    if (current.reference) out.reference = current.reference;
    if (doc && typeof doc === 'object') {
      var rows = walkObjects(doc.layers, null, []);
      out.object_count = doc.objects != null ? doc.objects : rows.length;
      if (Array.isArray(doc.artboards)) {
        out.artboards = doc.artboards.slice(0, 8).map(function (a) { return { width: small(a.width), height: small(a.height) }; });
      }
      out.objects = rows.slice(0, MAX_OBJECTS).map(function (row) {
        var item = { id: row.node.id, kind: row.node.kind || 'Object', title: title(row.node) };
        if (row.parent != null) item.parent_id = row.parent;
        return item;
      });
      if (rows.length > MAX_OBJECTS) out.objects_truncated = rows.length - MAX_OBJECTS;
    }
    return out;
  }

  /** One selected object: id, kind, name and its paint as the engine reports it. */
  function selectedObject(current, doc, id) {
    var row = doc ? findObject(doc.layers, id) : null;
    if (!row) return null;
    var node = row.node;
    var out = { kind: 'object', object_id: String(node.id), title: title(node), object_kind: node.kind || 'Object', illustration_id: String(current.id) };
    if (row.parent != null) out.parent_id = row.parent;
    ['fill', 'stroke'].forEach(function (key) { if (typeof node[key] === 'string') out[key] = node[key]; });
    if (Number.isFinite(Number(node.strokeWidth))) out.strokeWidth = small(node.strokeWidth);
    return out;
  }

  var TRANSFORM_DEFAULTS = { moveX: '0', moveY: '0', scaleValue: '100', rotationValue: '0' };

  /** Forms half filled in: the New / Import / Text dialog, else transform values typed but not applied. */
  function editorState(form, inWorkspace) {
    if (!form) return null;
    if (form.dialog && form.dialog.open) {
      var d = form.dialog, fields = {};
      var kind = d.purpose === 'import' ? 'import_illustration' : d.purpose === 'text' ? 'add_text' : 'new_illustration';
      var value = String(d.value || '').trim();
      fields[d.purpose === 'text' ? 'text' : 'title'] = value;
      if (d.purpose === 'create') { fields.width = d.width; fields.height = d.height; fields.units = d.units; }
      return { kind: kind, dirty: value !== '', fields: fields };
    }
    if (inWorkspace === false) return null;      // the transform fields live in the workspace: hidden in the library
    var typed = Object.assign({}, form.paint || {});
    Object.keys(TRANSFORM_DEFAULTS).forEach(function (id) {
      var v = form.transform && form.transform[id];
      if (v != null && String(v).trim() !== '' && String(v).trim() !== TRANSFORM_DEFAULTS[id]) typed[id] = String(v).trim();
    });
    return Object.keys(typed).length ? { kind: form.paint && Object.keys(form.paint).length ? 'paint' : 'transform', dirty: true, fields: typed } : null;
  }

  /**
   * The context additions for one turn. ``state`` = {current, selectedIds, doc, form, catalogOpen}. With no illustration
   * open (the library, or one that no longer exists) ``active_objects`` is [] and there is no project.
   */
  function buildContext(state) {
    state = state || {};
    var current = state.current && state.current.id ? state.current : null;
    var view = { page: current ? 'workspace' : 'library' };
    if (state.catalogOpen) view.catalog_open = true;
    var editor = editorState(state.form, !!current);
    if (editor) view.editor = editor;
    if (!current) return { active_objects: [], view: view };
    var objects = [illustrationObject(current, state.doc)];
    (state.selectedIds || []).slice(0, 20).forEach(function (id) {
      var obj = selectedObject(current, state.doc, id);
      if (obj) objects.push(obj);
    });
    return { project: { external_project_id: String(current.id), title: current.title || String(current.id) }, active_objects: objects, view: view };
  }

  var api = { buildContext: buildContext, illustrationObject: illustrationObject, selectedObject: selectedObject,
              editorState: editorState, walkObjects: walkObjects, MAX_OBJECTS: MAX_OBJECTS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.DurerCopilot = api;

  // ---- wiring (browser only) ----
  if (typeof root.document === 'undefined' || !root.document.getElementById) return;

  function app() { return root.__durerCopilot || null; }

  function readJson(url, options) {
    return root.fetch(url, options).then(function (r) {
      if (r.status === 404) return { gone: true };
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  function inspectDocument(id) {
    return readJson('/api/illustrations/' + encodeURIComponent(id) + '/actions', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actions: [{ name: 'inspect_document', arguments: {} }] }),
    }).then(function (res) {
      if (res.gone) return null;
      var row = (res.results || []).filter(function (x) { return x.name === 'inspect_document'; })[0];
      var text = row && row.result && row.result.content && row.result.content[0] && row.result.content[0].text;
      return text ? JSON.parse(text) : null;
    });
  }

  function formState(s) {
    var $ = function (id) { return root.document.getElementById(id); };
    var modal = $('inputModal');
    var transform = {};
    Object.keys(TRANSFORM_DEFAULTS).forEach(function (id) { if ($(id)) transform[id] = $(id).value; });
    var out = { transform: transform };
    out.paint = {};
    ['fillColor', 'strokeColor', 'strokeWidth'].forEach(function (id) {
      var input = $(id);
      if (input && input.dataset && input.dataset.reported === 'true' && input.value !== input.dataset.documentValue) {
        out.paint[id === 'fillColor' ? 'fill' : id === 'strokeColor' ? 'stroke' : id] = input.value;
      }
    });
    if (modal && !modal.classList.contains('hidden')) {
      out.dialog = { open: true, purpose: s.inputPurpose, value: $('inputValue') && $('inputValue').value,
                     width: $('canvasWidth') && $('canvasWidth').value, height: $('canvasHeight') && $('canvasHeight').value,
                     units: $('canvasUnits') && $('canvasUnits').value };
    }
    return out;
  }

  function catalogOpen() {
    var modal = root.document.getElementById('catalogModal');
    return !!modal && !modal.classList.contains('hidden');
  }

  async function context() {
    try {
      var s = app() && app().state();
      var form = s && formState(s), openCatalog = catalogOpen();
      if (!s || !s.current || !s.current.id) return buildContext({ form: s && formState(s), catalogOpen: catalogOpen() });
      var meta = null, doc = s.lastDocument || null;
      try { meta = await readJson('/api/illustrations/' + encodeURIComponent(s.current.id)); } catch (e) { meta = s.current; }
      if (meta && meta.gone) return buildContext({ form: form, catalogOpen: openCatalog });
      try { doc = (await inspectDocument(s.current.id)) || doc; } catch (e) { /* the engine may be busy: use the last inspection */ }
      var current = Object.assign({}, s.current, meta && meta.id ? { title: meta.title || s.current.title } : {});
      return buildContext({ current: current, selectedIds: s.selectedIds, doc: doc, form: form, catalogOpen: openCatalog });
    } catch (e) {
      return { active_objects: [], view: { page: 'library' } };
    }
  }

  var timer = 0, running = false;
  async function refreshAfterTurn() {
    var hooks = app();
    if (running || !hooks) return;
    running = true;
    try {
      var s = hooks.state();
      if (s.current && s.current.id) {
        var meta = await readJson('/api/illustrations/' + encodeURIComponent(s.current.id));
        if (hooks.state().current && hooks.state().current.id === s.current.id) {
          if (meta && meta.gone) hooks.closeIllustration();      // the agent deleted the open illustration
          else { await hooks.refresh(); }
        }
      }
      await hooks.projects();
    } catch (e) { /* the panel must never break the editor */ } finally {
      running = false;
    }
  }

  var lastId = null;
  function watchIllustration() {
    var check = function () {
      var s = app() && app().state();
      var id = s && s.current ? s.current.id : null;
      if (id === lastId) return;
      lastId = id;
      root.dispatchEvent(new root.Event('hoard:copilot-context-changed'));
    };
    var observe = function (id, options) {
      var node = root.document.getElementById(id);
      if (node && typeof root.MutationObserver === 'function') new root.MutationObserver(check).observe(node, options);
    };
    observe('workspace', { attributes: true, attributeFilter: ['class'] });
    observe('projectTitle', { childList: true, characterData: true, subtree: true });
  }

  root.hoardCopilot = {
    context: context,
    onTurnEnd: function () { clearTimeout(timer); timer = setTimeout(refreshAfterTurn, 150); },
  };
  watchIllustration();
})(typeof window !== 'undefined' ? window : globalThis);
