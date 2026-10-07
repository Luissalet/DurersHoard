# VectorCraft integration

## Release evidence

This Hoard targets the locally verified Windows x64 portable release `storytold/vectorcraft` 0.3.1. The executable is configured locally and never copied into this repository. The current MCP handshake returns 25 tools; the CLI `commands` registry returns 659 commands. The exact catalog is served by `/api/catalog` and the stdio `vectorcraft_catalog` tool.

Native tools include command discovery/dispatch, document and UI inspection, selection, pointer gestures, path and shape drawing, paint, keyboard/text input, menus and panels, screenshot, file open/save, export, effects, Pathfinder, transform, text wrap, undo, and redo. All tool schemas are read from the executable on discovery; the UI's raw tool runner forwards arguments without reducing them.

The CLI help confirms `.vectorcraft`, SVG, PDF, PNG, JPEG, WebP, GIF, TIFF, BMP, DXF, EPS, EMF, WMF, PSD, and related export modes. The focused UI exposes SVG, PNG, PDF, WebP, and native project download. Other formats remain available through the native catalog/API.

## Canvas dimensions

The native `file.new` schema documents numeric `width` and `height` in points; `units` chooses the document ruler display. Dürer accepts dimensions in the selected unit and converts them to the point values sent to VectorCraft. It supports Pixels (1 native pixel per value), Points, Picas, Inches, Millimeters, Centimeters, Feet, Yards, Meters, and Feet & Inches (entered as decimal feet). With dimensions but no unit, Points are used; with no size fields, Dürer calls `file.new` with `{}` and preserves the release default of 612 × 792 points. UI dimensions are document measurements, not CSS pixels.

CLI readback and PDF export confirmed 400 × 300 Points and physical A4: 210 × 297 Millimeters converts to a 595.2756 × 841.8898 point artboard and a `595.276 × 841.89 pt` PDF MediaBox. A native API test draws one rectangle at document coordinates (17, 23) and confirms its single painted path and the 400 × 300 SVG viewBox after export.

The CLI help documents the GUI command `vectorcraft --control <port>` and client command `vectorcraft-cli mcp --connect <address>`. The release bundle contains the sibling Windows GUI executable. The optional workspace button starts a separate GUI process with an isolated runtime folder, connects its complete MCP surface, and opens the same `.vectorcraft` project. This path was not launched during automated tests.

## Persistence and sources

Gallery cards use `/api/illustrations/{id}/thumbnail`, a cached PNG with a
512-pixel maximum long edge. A cache miss copies the saved native document
beside its original (retaining the directory used to resolve linked images),
then renders through a transient CLI converter. At most two thumbnail
converters run together and each exits after rendering; browsing does not add
persistent editor sessions. No preview converter receives the original native
file for writing. Source/native hashes remain unchanged in the real tests.

SHA-256 of the saved document and the configured executable's identity/stat
invalidate cached thumbnails, including external native file replacements that
leave Hoard metadata unchanged. Repeated gallery loads reuse the disk PNG.
`?refresh=true` explicitly rerenders when external fonts, preferences or linked
assets change without changing the native file. Current and previous PNG frames
are retained; older frames are pruned (files held by a Windows reader are retried
on a subsequent render). Temporary snapshots/full renders are cleaned on success
and failure. The existing `/preview` remains the selected editor's live preview,
so native undo and unsaved connected-desktop state retain their existing behavior.

Illustrations use random 128-bit lowercase hex IDs. Metadata is stored in each data directory under `illustrations/{id}/illustration.json`; the editable document is `project.vectorcraft`, source copies are under `sources/`, and generated files are under `exports/`. API file delivery constrains paths to these folders. The original browser upload is copied before native open; its name, hash, and size are retained in metadata.

One MCP stdio process is held open per project inside the running service. This preserves the engine's in-memory undo stack across calls while that process stays alive. Native saves are made after each action batch. Before a changed document is saved over, Dürer's Hoard saves its previous native file in `snapshots/`; undo/redo can restore these snapshots after service restart. Up to 100 undo snapshots are retained. Concurrent requests to one project share that native engine session and are serialized.

First requests for one project share a per-project async initialization lock, preventing duplicate native processes. Manifest and history JSON is replaced atomically. Read-only inspection does not rewrite the native file. If a native call exceeds its timeout, Dürer does not cancel it because VectorCraft may already be changing the document. The error returns an operation ID; check `/api/operations/{operation_id}` during the current service lifetime before retrying.

Undo/redo compares the resulting native file with the exact target snapshot. If VectorCraft's in-memory history produces a different file or errors, Dürer restores the snapshot, reopens it and returns a fresh native inspection. This covers edits made externally before reopening the project.

MCP replies use `CallToolResult.isError=true` for unknown projects/tools,
validation failures, native action/save/inspection failures, and exceptions.
The existing JSON text is retained and object responses also expose the same
payload as `structuredContent`, including complete native result arrays and
timeout operation IDs. Native action failures return HTTP 502 through the
project action endpoint and direct or HoardLink agent calls; successful actions
remain HTTP 200. Inspect native results and any operation receipt before
retrying: a failed action may be followed by a successful save/inspection,
and an operation that timed out may still complete.
The browser shows messages from structured `detail.message`/`detail.error`
objects or failed native result content, retaining timeout receipt IDs and URLs.

## Interchange and scope

SVG, PNG, and PDF export are explicit native operations. Import support is offered for SVG, PNG, JPEG, WebP, and PDF; import behavior depends on VectorCraft's open/import handling. Source copies remain available even if the editor changes or converts its working document. `hoard://durer/illustration/{id}` identifies the persistent Hoard record; the API returns this stable reference.

This UI does not recreate VectorCraft's full canvas GUI. It provides create/import, native preview, drag-to-draw shapes, text, object ID selection from native inspection, paint, position/scale/rotation, undo/redo, full raw tool/schema inspection, and export. Selection on the preview is through the native object list; it does not claim the same hit-testing as the desktop canvas. Automated tests deliberately do not launch a GUI window.

## Compatibility status

No capability parity is claimed against VectorCraft, Inkscape, or Penpot. The baseline matrix remains unknown except for direct evidence in the accompanying integration test receipts. Each untested feature should remain marked unverified.
