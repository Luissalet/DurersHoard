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

## Evidence and limits

The pinned local release is VectorCraft 0.3.1. Its verified CLI reports 659 commands; its MCP catalog contains 25 tools. The application delegates drawing, selection, painting, transforms, text, pathfinder, undo, redo, and export to VectorCraft. Its UI is a workspace around that engine, not a replacement for the engine's full desktop interface. No feature parity or performance advantage over VectorCraft, Inkscape, or Penpot is claimed. See `docs/CREATIVE-ENGINES.md` and `docs/DISEÑO.md` for implementation limits and evaluation status.
