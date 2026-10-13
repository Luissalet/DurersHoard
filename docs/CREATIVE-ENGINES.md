# Owned Dürer illustration engine

The engine and complete desktop editor are incorporated as detached source in `native/`, maintained by this product. The source origin is VectorCraft v0.3.1, revision `7a39cb7b89505f7f6f19c83c66d46986d72d4aa9`, MIT OR Apache-2.0; licenses, copyright and open-asset attribution are retained. The source origin is historical evidence, not a runtime dependency.

The 25 native tool schemas and 659 commands remain discoverable through the owned CLI, API and MCP. All drawing, selection, paint, transforms, text, pathfinder, effects, file I/O and exports use those owned libraries. The browser's existing editing flow and the complete owned desktop editor both remain. Standard Rust libraries, fonts and the desktop/browser runtime are declared dependencies.

[OWNED-ENGINE.md](OWNED-ENGINE.md) describes build, documents, historical import, API/MCP, real checks and limitations. The complete registry is incorporated; the covered workflows do not certify all 659 commands or universal parity.
