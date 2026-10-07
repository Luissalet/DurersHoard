# Diseño / Design record

## Inherited Operate language

The interface follows the existing Gutenberg/Hoard Operate visual system: warm paper (`#f7f7f2`), white work panels, restrained green (`#566d48`), muted text, thin warm borders, Playfair Display headings, and DM Sans controls. The canvas uses a light checker surface and a clear artboard; the surrounding tools and inspector use compact panels.

This is an adaptation of the existing Hoard interface pattern for illustration work. It does not introduce an independent visual identity. The library remains visible before editing; the editor centers the canvas, keeps native operations discoverable, and places object/document inspection beside it. Desktop uses a tool rail, canvas, and inspector. At tablet widths the inspector moves below the canvas; at phone widths the rail and canvas remain usable and panels stack.

## Product decisions

- Luis and Faustus are the main users; projects stay local and editable.
- Common actions should be visible while the complete engine surface remains reachable.
- Native save, undo, redo, inspection, export, and schemas are the source of truth.
- English and Spanish are available in the same interface.
- No accounts or network service are required.

## Review status

The inherited palette and type choices were copied from the current Gutenberg Operate styles. A single desktop/mobile visual pass is required after implementation. Current feature parity against the underlying editor is unmeasured.


## Tamaño del lienzo

El diálogo de creación muestra ancho, alto y unidad. VectorCraft recibe las dimensiones numéricas en puntos; Dürer convierte desde la unidad elegida y configura esa unidad para la regla del documento. Así, 210 × 297 milímetros se convierte a 595,2756 × 841,8898 puntos y el PDF resultante tiene MediaBox A4. “Feet & Inches” se introduce en pies decimales. El valor inicial es 612 × 792 puntos, el tamaño predeterminado verificado de VectorCraft 0.3.1. REST, HoardLink y MCP aplican la misma conversión; si se omite el tamaño, se mantienen los valores predeterminados del motor.
