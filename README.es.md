# Dürer's Hoard

Una Hoard local de ilustración vectorial basada en el motor VectorCraft 0.3.1 Windows x64 verificado. Conserva proyectos nativos `.vectorcraft` y ofrece el catálogo completo de herramientas MCP y comandos del motor.

## Instalar y ejecutar

Ejecuta `scripts/setup.ps1` en PowerShell. Crea el `.venv` propio y busca HoardLink en el checkout hermano `HoardLink`; define `HOARDLINK_DIR` si está en otro lugar. VectorCraft se descubre desde `local-config.json` (ignorado), `DURER_VECTORCRAFT_CLI`, `DURER_NATIVE_BUNDLE_DIR` o `PATH`; también puedes pasar `-VectorCraftCli 'C:\ruta\a\vectorcraft-cli.exe'`. Setup conserva el directorio de datos y el puerto de Dürer si ya está activo. Inicia la aplicación con `scripts/launch.ps1`.

El manifiesto versionado propone el puerto 5222. El servicio permanece ligado a `127.0.0.1`.

## Edición

Las ilustraciones nuevas aceptan ancho, alto y unidades desde la interfaz, REST, HoardLink y la herramienta MCP `illustration_create`. `file.new` de VectorCraft 0.3.1 recibe ancho y alto numéricos en puntos; Dürer interpreta los valores introducidos en la unidad elegida, los convierte a puntos y configura esa unidad para la regla del documento. Por ejemplo, 210 × 297 milímetros se convierten en 595,2756 × 841,8898 puntos y producen un PDF con MediaBox A4. Los píxeles corresponden uno a uno al tamaño de la exportación raster de esta versión. En “Feet & Inches”, introduce pies decimales. Si se indican dimensiones sin unidad, Dürer usa puntos. Si se omiten los tres campos, se mantienen los valores nativos de VectorCraft. La interfaz empieza en 612 × 792 puntos; son unidades del documento, no píxeles CSS.

Crea una ilustración o importa SVG, PNG, JPEG, WebP o PDF. Cada importación se copia a la carpeta `sources/` antes de abrirse en VectorCraft. El proyecto actual se guarda como `project.vectorcraft`; SVG, PNG y PDF son exportaciones nativas. Cada ilustración recibe un ID estable y una referencia `hoard://durer/illustration/{id}`.

El editor conserva un proceso MCP de VectorCraft por proyecto activo; así undo y redo llaman al motor real mientras la aplicación sigue abierta. Antes de guardar un cambio, Dürer's Hoard conserva una copia nativa previa para permitir undo/redo después de reiniciar el servicio. El undo interno de VectorCraft es de proceso y no se conserva al reiniciar. La interfaz permite dibujar arrastrando, editar texto, inspeccionar objetos, aplicar pintura y transformaciones, y consultar los esquemas nativos exactos. `/api/catalog` devuelve todas las herramientas y comandos. El botón opcional de escritorio usa `vectorcraft.exe --control <puerto>` y `vectorcraft-cli mcp --connect <dirección>` para abrir el mismo archivo editable; no abre ventanas automáticamente.

## MCP de Faustus

Ejecuta `.venv/Scripts/python.exe -m durer_hoard.mcp_server` por stdio. `vectorcraft_catalog` devuelve el catálogo completo. `vectorcraft_<herramienta>` reenvía cada herramienta nativa dentro de una sesión persistente; `illustration_native_call` permite la misma ejecución por nombre. `run_command` sigue disponible como herramienta nativa con el esquema proporcionado por VectorCraft.

## Evidencia y límites

La versión local verificada es VectorCraft 0.3.1. Su CLI declara 659 comandos y el catálogo MCP contiene 25 herramientas. Dürer's Hoard delega dibujo, selección, pintura, transformaciones, texto, Pathfinder, undo, redo y exportación en VectorCraft. La interfaz es un espacio de trabajo alrededor del motor, no una sustitución de su escritorio completo. No se afirma paridad ni ventaja de rendimiento frente a VectorCraft, Inkscape o Penpot. Consulta `docs/CREATIVE-ENGINES.es.md` y `docs/DISEÑO.md` para límites y evaluación.
