# VectorCraft integration

## Release evidence

This Hoard targets the locally verified Windows x64 portable release `storytold/vectorcraft` 0.3.1. The executable is configured locally and never copied into this repository. The current MCP handshake returns 25 tools; the CLI `commands` registry returns 659 commands. The exact catalog is served by `/api/catalog` and the stdio `vectorcraft_catalog` tool.

Native tools include command discovery/dispatch, document and UI inspection, selection, pointer gestures, path and shape drawing, paint, keyboard/text input, menus and panels, screenshot, file open/save, export, effects, Pathfinder, transform, text wrap, undo, and redo. All tool schemas are read from the executable on discovery; the UI's raw tool runner forwards arguments without reducing them.

The CLI help confirms `.vectorcraft`, SVG, PDF, PNG, JPEG, WebP, GIF, TIFF, BMP, DXF, EPS, EMF, WMF, PSD, and related export modes. The focused UI exposes SVG, PNG, PDF, WebP, and native project download. Other formats remain available through the native catalog/API.

The CLI help documents the GUI command `vectorcraft --control <port>` and client command `vectorcraft-cli mcp --connect <address>`. The release bundle contains the sibling Windows GUI executable. The optional workspace button starts a separate GUI process with an isolated runtime folder, connects its complete MCP surface, and opens the same `.vectorcraft` project. This path was not launched during automated tests.

## Persistence and sources

Illustrations use random 128-bit lowercase hex IDs. Metadata is stored in each data directory under `illustrations/{id}/illustration.json`; the editable document is `project.vectorcraft`, source copies are under `sources/`, and generated files are under `exports/`. API file delivery constrains paths to these folders. The original browser upload is copied before native open; its name, hash, and size are retained in metadata.

One MCP stdio process is held open per project inside the running service. This preserves the engine's in-memory undo stack across calls while that process stays alive. Native saves are made after each action batch. Before a changed document is saved over, Dürer's Hoard saves its previous native file in `snapshots/`; undo/redo can restore these snapshots after service restart. Up to 100 undo snapshots are retained. Concurrent requests to one project share that native engine session and are serialized.

First requests for one project share a per-project async initialization lock, preventing duplicate native processes. Manifest and history JSON is replaced atomically. Read-only inspection does not rewrite the native file. If a native call exceeds its timeout, Dürer does not cancel it because VectorCraft may already be changing the document. The error returns an operation ID; check `/api/operations/{operation_id}` during the current service lifetime before retrying.

Undo/redo compares the resulting native file with the exact target snapshot. If VectorCraft's in-memory history produces a different file or errors, Dürer restores the snapshot, reopens it and returns a fresh native inspection. This covers edits made externally before reopening the project.

## Interchange and scope

SVG, PNG, and PDF export are explicit native operations. Import support is offered for SVG, PNG, JPEG, WebP, and PDF; import behavior depends on VectorCraft's open/import handling. Source copies remain available even if the editor changes or converts its working document. `hoard://durer/illustration/{id}` identifies the persistent Hoard record; the API returns this stable reference.

This UI does not recreate VectorCraft's full canvas GUI. It provides create/import, native preview, drag-to-draw shapes, text, object ID selection from native inspection, paint, position/scale/rotation, undo/redo, full raw tool/schema inspection, and export. Selection on the preview is through the native object list; it does not claim the same hit-testing as the desktop canvas. Automated tests deliberately do not launch a GUI window.

## Compatibility status

No capability parity is claimed against VectorCraft, Inkscape, or Penpot. The baseline matrix remains unknown except for direct evidence in the accompanying integration test receipts. Each untested feature should remain marked unverified.
