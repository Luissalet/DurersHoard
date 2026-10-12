# Dürer's Hoard

A local vector illustration Hoard built around the verified Windows x64 VectorCraft 0.3.1 engine. It keeps native `.vectorcraft` projects and the full native MCP/command catalog available to people and agents.

## Install and run

Run `scripts/setup.ps1` in PowerShell. Setup creates this product's `.venv` and finds HoardLink in the sibling `HoardLink` checkout; set `HOARDLINK_DIR` when it lives elsewhere. VectorCraft is found from the existing ignored `local-config.json`, `DURER_VECTORCRAFT_CLI`, `DURER_NATIVE_BUNDLE_DIR`, or `PATH`; you can also pass `-VectorCraftCli 'C:\path\to\vectorcraft-cli.exe'`. Setup preserves the configured data directory and keeps an active Dürer port instead of moving it. Start the app with `scripts/launch.ps1`.

The checked-in plugin manifest uses port 5222 as its default. The runtime remains bound to `127.0.0.1`.

## Editing

New illustrations accept width, height, and units through the UI, REST, HoardLink, and `illustration_create` MCP tool. VectorCraft 0.3.1 `file.new` takes numeric width and height in points; Dürer interprets the requested values in the selected unit, converts them to points, and sets the document ruler unit. For example, 210 × 297 Millimeters becomes 595.2756 × 841.8898 points and exports with an A4 PDF MediaBox. Pixel dimensions map one to one to the release’s raster export size. “Feet & Inches” inputs are decimal feet. With dimensions supplied and no unit, Dürer uses points. Omitting all three keeps VectorCraft’s native defaults. The create UI starts at 612 × 792 points; dimensions refer to document units, not browser CSS pixels.

Create an illustration or import SVG, PNG, JPEG, WebP, or PDF. Imports are copied into that illustration's `sources/` folder before VectorCraft opens them. The current project is saved as `project.vectorcraft`; SVG, PNG, and PDF are native exports. Each illustration gets a stable Hoard ID and `hoard://durer/illustration/{id}` reference.

The editor keeps one VectorCraft MCP process for each active project, so undo and redo call the actual engine while the app remains running. Before each successful file change, Dürer's Hoard stores a native project snapshot. Those snapshots can restore undo and redo after a service restart; VectorCraft's in-memory undo stack itself is not preserved across process restarts. The browser UI offers drag-to-draw shapes, text, object inspection, paint, transforms, and the exact native tool schemas; `/api/catalog` returns every discovered tool and command. The optional desktop button uses the CLI documented `vectorcraft.exe --control <port>` and `vectorcraft-cli mcp --connect <address>` contract to open the same editable file. It is not started automatically.

## Faustus MCP

Run `.venv/Scripts/python.exe -m durer_hoard.mcp_server` over stdio. `vectorcraft_catalog` supplies the full native catalog. `vectorcraft_<tool>` forwards each native tool in a persistent illustration session, and `illustration_native_call` offers the same dispatch by tool name. `run_command` remains one of the native tools and its full parameter schema comes from VectorCraft.

## Faustus copilot

When the app is running, the MCP bridge uses its live native sessions through the existing API. `DURER_URL` selects the app endpoint (otherwise the configured host/port); its data directory must match the bridge's configured data directory. With the app offline, standalone MCP remains available. A sent request with no reply reports `outcome_unknown` and is never replayed in another engine. Preview/export read the document without resaving it. Fields typed while a turn-end refresh is pending stay in the editor; untouched paint fields follow the native document.

Every page has a floating **Faustus** button that opens a side panel with the Faustus chat. The agent sees the illustration you have open and the objects selected in the inspector, and works on them with the same native VectorCraft tools Faustus already reaches through the MCP bridge. Conversation, model, tools and memory live in Faustus; Dürer keeps no chat loop and no history.

What the panel sends with every turn (`window.hoardCopilot.context()` in [`durer_hoard/static/copilot.js`](durer_hoard/static/copilot.js)):

- `project`: the open illustration (`external_project_id` = illustration id, `title`). One conversation per illustration; the library has none.
- `active_objects`: the illustration (`kind: "illustration"`: id, title, `hoard://` reference, object count, artboards, and its objects as id / kind / name / parent, capped at 60) and one `kind: "object"` per selected object (id, name, kind, fill, stroke, stroke width as the engine reports them). It is read from the engine with `inspect_document` at the moment of the turn, so what an agent changed earlier is already in it. In the library, or for an illustration that no longer exists, it is `[]`.
- `view.editor`: a New / Import / Text dialog that is open (`new_illustration`, `import_illustration`, `add_text`: name and canvas size typed so far), transform values typed but not applied (`transform`), or changed paint fields (`paint`).

When a turn ends the editor re-reads the illustration, its preview and object list, and the library, drops a selection that no longer exists, closes an illustration the agent deleted, and puts back what you had typed in the paint and transform fields.

The relay is Hoard Link's `install_copilot` (`hoard_link.copilot`), called from `durer_hoard/api.py`; it adds these routes (see [`docs/API.md`](docs/API.md)) and the launcher script to every HTML page. It needs a Hoard Link that has it and `httpx` (a dependency now); with an older Hoard Link the app starts as before and `/api/health` says `"copilot": false`. Faustus is found through `HOARD_FAUSTUS_URL` (plus `HOARD_FAUSTUS_TOKEN`) or the Hoard Link config, falling back to `127.0.0.1:7000` / `7001`. **To turn it off** start the app with `HOARD_COPILOT=0`: no routes, no button, nothing injected. `faustus-plugin.json` declares it under `x-family.copilot`.

## Evidence and limits

The pinned local release is VectorCraft 0.3.1. Its verified CLI reports 659 commands; its MCP catalog contains 25 tools. The application delegates drawing, selection, painting, transforms, text, pathfinder, undo, redo, and export to VectorCraft. Its UI is a workspace around that engine, not a replacement for the engine's full desktop interface. No feature parity or performance advantage over VectorCraft, Inkscape, or Penpot is claimed. See `docs/CREATIVE-ENGINES.md` and `docs/DISEÑO.md` for implementation limits and evaluation status.
