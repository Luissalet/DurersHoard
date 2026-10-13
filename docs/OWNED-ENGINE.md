# Dürer engine and editor

The Rust engine and complete desktop editor live in `native/`. They are a detached incorporation of VectorCraft v0.3.1, revision `7a39cb7b89505f7f6f19c83c66d46986d72d4aa9`. Original copyright, MIT/Apache licenses and asset attribution are retained. Fonts and open icons are incorporated; the desktop application uses this Hoard's existing family icon. No upstream checkout, executable, MCP service or future compatibility is needed.

## Build and operation

Install Rust 1.95.0 and its Windows MSVC toolchain, then run `python scripts/build_engine.py`. The script builds `durer-cli` and `durer` from the locked local workspace and installs them in `native/bin/`. `--debug` selects the development profile. Stop this Hoard's active editor and service before replacing binaries; Windows keeps a running executable open. The build receipt records each binary's SHA-256 and profile. These generated binaries and the compilation directory are not tracked in Git.

`scripts/setup.ps1` builds the engine before configuring the Hoard. Existing data paths, port and other configuration are preserved. Historical `vectorcraft_cli`, `vectorcraft_gui`, `DURER_VECTORCRAFT_CLI` and `DURER_VECTORCRAFT_GUI` values do not select an engine. This is verified with those variables pointing to absent files.

The browser keeps the existing editor, raw command/tool runner, object properties, drag-to-draw shapes, text, paint, transforms, previews, gallery and undo/redo. The desktop button starts the owned `durer` executable and connects to its control channel. It opens the same editable document and retains the full menus, panels and tools. The engine runs one serialized session per active project. Gallery converters remain transient and independent of editor sessions.

## Documents and historical import

New editable documents are `project.durer`, UTF-8 JSON or the format's compressed representation, with the `durer` header. A historical project's `project.vectorcraft` is opened and saved to a new `project.durer` on first editing or download; the historical file and its original metadata remain intact. Historical snapshots, source copies, IDs, dimensions, units, linked assets and export files are retained. Uploads accept `.durer`, `.vectorcraft` and `.drawcraft` as well as existing SVG/raster/PDF imports. SVG/PDF/EPS editing payloads from the incorporated revision remain readable. This imports historical data; it does not promise compatibility with future upstream formats.

Saved-file snapshots support undo and redo after service restart. An editor session itself remains in memory. The gallery can render a historical file without creating its editable copy. Preview and export do not save source files. An explicit native save command writes the path the caller chose, so callers should use the owned project path when editing a historical project.

## API and MCP

`GET /api/engine/catalog` and the existing `/api/catalog` discover 25 owned native tools and 659 commands. The public stdio MCP adds preferred `durer_catalog` and `durer_<tool>` names. All 31 historical workflow/tool names remain aliases; 57 tools are discoverable in total. Existing `illustration_*` workflows use the owned engine. Native resource URIs use `durer://`. Tool parameter semantics are preserved: transform scale is a percentage, while raster export scale is pixels per point.

## Evidence and limits

The initial implementation passes 46 Python workflow/configuration/API/MCP tests, 17 frontend checks, and 69 Rust format/MCP tests. Real browser checks create a 400 × 300 document, drag a rectangle, change paint and position, reopen after service restart and export a PDF on a 390 px viewport. The PDF reopens as editable artwork. The complete owned desktop was opened and inspected through its native MCP control channel. Exact-source independent review and activation are tracked in Ágora task 514; a test count is not evidence of integration or activation.

Initial negatives are retained in the task evidence: the PDF editing hash needed an ASCII marker after the name change; the browser image's default drag prevented drawing; the form incorrectly converted 100% to 1%. All three have concrete reproductions and were corrected. Tests exercise real saved files and exports with the old application unavailable. The full reference's 659 commands have been incorporated and remain discoverable, but these checks do not certify every command or universal vector-editor parity.
