# Dürer's Hoard

A local vector illustration workspace with its own Rust engine, desktop editor, editable `.durer` documents and complete native tool/command catalog. Historical illustration documents and source files are preserved.

## Install and run

Run `scripts/setup.ps1` in PowerShell. Setup creates the product's `.venv`, installs HoardLink, builds the owned engine/editor from `native/` with Rust 1.95.0 and configures the existing data folder and port. Set `HOARDLINK_DIR` when the sibling checkout lives elsewhere. Start with `scripts/launch.ps1`. The default is loopback port 5222.

For a separate engine build, run `python scripts/build_engine.py` (`--debug` for a development build) with this Hoard's service and desktop editor stopped. No external application or configured historical CLI is used. See [owned-engine.md](docs/OWNED-ENGINE.md) for provenance, build, import and evidence.

## Editing

New illustrations accept width, height, and units through the UI, REST, HoardLink, and `illustration_create` MCP tool. The owned `file.new` takes numeric width and height in points; Dürer interprets the requested values in the selected unit, converts them to points, and sets the document ruler unit. For example, 210 × 297 Millimeters becomes 595.2756 × 841.8898 points and exports with an A4 PDF MediaBox. Pixel dimensions map one to one to the release’s raster export size. “Feet & Inches” inputs are decimal feet. With dimensions supplied and no unit, Dürer uses points. Omitting all three keeps Dürer’s native defaults. The create UI starts at 612 × 792 points; dimensions refer to document units, not browser CSS pixels.

Create an illustration or import SVG, PNG, JPEG, WebP, or PDF. Imports are copied into that illustration's `sources/` folder before Dürer opens them. The current project is saved as `project.durer`; SVG, PNG, and PDF are native exports. Each illustration gets a stable Hoard ID and `hoard://durer/illustration/{id}` reference.

The editor keeps one Dürer MCP process for each active project, so undo and redo call the actual engine while the app remains running. Before each successful file change, Dürer's Hoard stores a native project snapshot. Those snapshots can restore undo and redo after a service restart; Dürer's in-memory undo stack itself is not preserved across process restarts. The browser UI offers drag-to-draw shapes, text, object inspection, paint, transforms, and the exact native tool schemas; `/api/catalog` returns every discovered tool and command. The optional desktop button opens the complete owned Dürer editor over its native control channel, using the same `.durer` project. It is not started automatically. Browser drawing prevents the preview image's default drag, and the transform form sends percentage values unchanged.

## Faustus MCP

Run `.venv/Scripts/python.exe -m durer_hoard.mcp_server` over stdio. `durer_catalog` supplies 25 native tools and 659 commands. `durer_<tool>` dispatches each tool in a persistent project session; `illustration_native_call` accepts the same tool name and arguments. The existing `vectorcraft_catalog` and `vectorcraft_<tool>` names remain aliases. There are 57 public MCP tools in total.

## Faustus copilot

When the app is running, the MCP bridge uses its live native sessions through the existing API. `DURER_URL` selects the app endpoint (otherwise the configured host/port); its data directory must match the bridge's configured data directory. With the app offline, standalone MCP remains available. A sent request with no reply reports `outcome_unknown` and is never replayed in another engine. Preview/export read the document without resaving it. Fields typed while a turn-end refresh is pending stay in the editor; untouched paint fields follow the native document.

Every page has a floating **Faustus** button that opens a side panel with the Faustus chat. The agent sees the illustration you have open and the objects selected in the inspector, and works on them with the same native Dürer tools Faustus already reaches through the MCP bridge. Conversation, model, tools and memory live in Faustus; Dürer keeps no chat loop and no history.

What the panel sends with every turn (`window.hoardCopilot.context()` in [`durer_hoard/static/copilot.js`](durer_hoard/static/copilot.js)):

- `project`: the open illustration (`external_project_id` = illustration id, `title`). One conversation per illustration; the library has none.
- `active_objects`: the illustration (`kind: "illustration"`: id, title, `hoard://` reference, object count, artboards, and its objects as id / kind / name / parent, capped at 60) and one `kind: "object"` per selected object (id, name, kind, fill, stroke, stroke width as the engine reports them). It is read from the engine with `inspect_document` at the moment of the turn, so what an agent changed earlier is already in it. In the library, or for an illustration that no longer exists, it is `[]`.
- `view.editor`: a New / Import / Text dialog that is open (`new_illustration`, `import_illustration`, `add_text`: name and canvas size typed so far), transform values typed but not applied (`transform`), or changed paint fields (`paint`).

When a turn ends the editor re-reads the illustration, its preview and object list, and the library, drops a selection that no longer exists, closes an illustration the agent deleted, and puts back what you had typed in the paint and transform fields.

The relay is Hoard Link's `install_copilot` (`hoard_link.copilot`), called from `durer_hoard/api.py`; it adds these routes (see [`docs/API.md`](docs/API.md)) and the launcher script to every HTML page. It needs a Hoard Link that has it and `httpx` (a dependency now); with an older Hoard Link the app starts as before and `/api/health` says `"copilot": false`. Faustus is found through `HOARD_FAUSTUS_URL` (plus `HOARD_FAUSTUS_TOKEN`) or the Hoard Link config, falling back to `127.0.0.1:7000` / `7001`. **To turn it off** start the app with `HOARD_COPILOT=0`: no routes, no button, nothing injected. `faustus-plugin.json` declares it under `x-family.copilot`.

## Evidence and limits

The incorporated source is recorded by revision and hash in `native/PROVENANCE.json`, with original license notices retained. Drawing, selection, painting, transforms, text, effects, Pathfinder, undo, redo, file I/O and export run in the owned engine. Both the browser workflow and complete desktop editor remain available. Historical `.vectorcraft` and `.drawcraft` documents are imported into an owned editable copy without changing the original. The full native command catalog is maintained; no universal feature-parity or performance ranking is claimed. Verification and remaining activation state are described in [OWNED-ENGINE.md](docs/OWNED-ENGINE.md) and Ágora 514.
