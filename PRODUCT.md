# Dürer's Hoard

## Product

Dürer's Hoard is a local vector illustration workspace for Luis and Faustus. Its core workflow is to create or import an owned editable `.durer` document, inspect and edit vector objects, undo or reopen work, and export reusable SVG, PNG, or PDF assets. Its complete Rust engine and desktop editor are built from the source versioned in this repository.

## Product choices

- Platform: local Windows desktop, presented as a responsive browser application.
- Stack: Python/FastAPI and static HTML/JavaScript, following the existing Hoard and Gutenberg Operate pattern.
- Engine: the owned Rust engine and complete desktop editor built from detached, versioned native/ source. The product keeps the native MCP tool and command catalogs available instead of replacing them with a reduced imitation.
- Persistence: each illustration has a stable Hoard ID, a native `.durer` project, saved source copies, export files, and a `hoard://durer/illustration/{id}` reference.
- Session behavior: one native MCP process remains open per active project so native undo state can span requests; saved native files are reopened after an application restart.
- Access: loopback service and local Faustus integration. No accounts or remote service are required.
- Language: English and Spanish.
- Source safety: imports are copied into the project before engine use; the source copy is retained.

## Users and use

The primary user is Luis, with Faustus acting through the local Hoard/MCP contract. The central task is persistent vector illustration and asset production, rather than placing artwork in another editor.

## Evidence and limits

The owned engine is verified locally with 25 native MCP tools and 659 commands, plus 57 public workflow/alias MCP tools. Its source origin is VectorCraft v0.3.1, pinned in native/PROVENANCE.json. The CLI help confirms SVG, PNG, PDF, and `.vectorcraft` file support. This release evidence does not establish feature parity with VectorCraft, Inkscape, or Penpot. Keep each capability unverified until tested on real artifacts.

## Owned-engine delivery

Ágora 514 incorporates the complete pinned Rust source as an owned engine and desktop editor, with `.durer` documents, owned resource/tool names and historical aliases. Historical originals are imported into a separate editable copy. The runtime ignores external CLI/GUI configuration. See docs/OWNED-ENGINE.md for build, conservation, verified workflows and exact review/activation state.
