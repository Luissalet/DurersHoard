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

## Copiloto de Faustus

Cuando la app está abierta, el puente MCP usa sus sesiones nativas vivas por el API existente. `DURER_URL` elige el endpoint (si no, host/puerto configurado) y la carpeta de datos debe coincidir con la del puente. Con la app apagada sigue disponible el MCP independiente. Una petición enviada sin respuesta devuelve `outcome_unknown` y no se repite en otro motor. La vista previa y la exportación leen el documento sin volver a guardarlo. Los campos escritos mientras llega el refresco se conservan; la pintura no modificada sigue los valores nativos.

Todas las páginas tienen un botón flotante **Faustus** que abre un panel lateral con el chat de Faustus. El agente ve la ilustración que tienes abierta y los objetos seleccionados en el inspector, y trabaja sobre ellos con las mismas herramientas nativas de VectorCraft a las que Faustus ya llega por el puente MCP. La conversación, el modelo, las herramientas y la memoria viven en Faustus; Dürer no guarda ningún bucle de chat ni historial.

Lo que el panel envía en cada turno (`window.hoardCopilot.context()` en [`durer_hoard/static/copilot.js`](durer_hoard/static/copilot.js)):

- `project`: la ilustración abierta (`external_project_id` = id de la ilustración, `title`). Una conversación por ilustración; la biblioteca no tiene ninguna.
- `active_objects`: la ilustración (`kind: "illustration"`: id, título, referencia `hoard://`, número de objetos, mesas de trabajo y sus objetos con id / tipo / nombre / padre, hasta 60) y un `kind: "object"` por cada objeto seleccionado (id, nombre, tipo, relleno, trazo y ancho de trazo tal como los informa el motor). Se lee del motor con `inspect_document` en el momento del turno, así que un cambio anterior del agente ya está dentro. En la biblioteca, o con una ilustración que ya no existe, es `[]`.
- `view.editor`: un diálogo Nueva / Importar / Texto abierto (`new_illustration`, `import_illustration`, `add_text`: nombre y tamaño del lienzo escritos hasta ahora), valores de transformación escritos y no aplicados (`transform`) o campos de pintura modificados (`paint`).

Al terminar un turno el editor vuelve a leer la ilustración, su vista previa, la lista de objetos y la biblioteca, quita una selección que ya no existe, cierra una ilustración que el agente haya borrado y devuelve a los campos de pintura y transformación lo que tenías escrito.

El relé es `install_copilot` de Hoard Link (`hoard_link.copilot`), llamado desde `durer_hoard/api.py`; añade estas rutas (véase [`docs/API.md`](docs/API.md)) y el script del lanzador a cada página HTML. Necesita un Hoard Link que lo incluya y `httpx` (ahora es dependencia); con un Hoard Link anterior la app arranca como antes y `/api/health` dice `"copilot": false`. Faustus se encuentra con `HOARD_FAUSTUS_URL` (más `HOARD_FAUSTUS_TOKEN`) o con la configuración de Hoard Link, y si no, `127.0.0.1:7000` / `7001`. **Para desactivarlo** arranca la app con `HOARD_COPILOT=0`: sin rutas, sin botón y sin nada inyectado. `faustus-plugin.json` lo declara en `x-family.copilot`.

## Evidencia y límites

La versión local verificada es VectorCraft 0.3.1. Su CLI declara 659 comandos y el catálogo MCP contiene 25 herramientas. Dürer's Hoard delega dibujo, selección, pintura, transformaciones, texto, Pathfinder, undo, redo y exportación en VectorCraft. La interfaz es un espacio de trabajo alrededor del motor, no una sustitución de su escritorio completo. No se afirma paridad ni ventaja de rendimiento frente a VectorCraft, Inkscape o Penpot. Consulta `docs/CREATIVE-ENGINES.es.md` y `docs/DISEÑO.md` para límites y evaluación.
