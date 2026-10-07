# Integración de VectorCraft

## Evidencia de la versión

Esta Hoard usa el paquete portable Windows x64 de `storytold/vectorcraft` 0.3.1, verificado en este equipo. El ejecutable se configura localmente y no se copia al repositorio. El handshake MCP actual devuelve 25 herramientas; el registro CLI devuelve 659 comandos. `/api/catalog` y `vectorcraft_catalog` entregan sus esquemas completos.

Las herramientas nativas incluyen descubrimiento y ejecución de comandos, inspección del documento y de la interfaz, selección, gestos de puntero, trazados y formas, pintura, teclado y texto, menús y paneles, captura, apertura y guardado, exportación, efectos, Pathfinder, transformaciones, ajuste de texto, undo y redo. Los esquemas se leen desde el ejecutable; el ejecutor nativo de la interfaz reenvía los argumentos sin reducirlos.

La ayuda CLI confirma `.vectorcraft`, SVG, PDF, PNG, JPEG, WebP, GIF, TIFF, BMP, DXF, EPS, EMF, WMF, PSD y otros formatos. La interfaz ofrece SVG, PNG, PDF, WebP y descarga del proyecto nativo; los demás formatos siguen disponibles mediante el catálogo/API nativo.

La ayuda documenta `vectorcraft --control <puerto>` para abrir la GUI y `vectorcraft-cli mcp --connect <dirección>` para conectar la superficie nativa. El paquete contiene el ejecutable GUI Windows junto al CLI. El botón opcional abre el proyecto editable usando una sesión MCP conectada a esa ventana. Las pruebas automatizadas no abren ventanas.

## Persistencia y fuentes

Cada proyecto usa un ID hexadecimal aleatorio de 128 bits. Los metadatos viven en `illustrations/{id}/illustration.json`, el documento editable en `project.vectorcraft`, las fuentes copiadas en `sources/` y los archivos generados en `exports/`. La descarga de archivos limita las rutas a esas carpetas. Cada importación web se copia antes de abrirla y conserva nombre, hash y tamaño.

Mientras el servicio está abierto, un proceso MCP nativo persiste por proyecto y conserva el undo de VectorCraft entre llamadas. Antes de una modificación guardada, Dürer's Hoard conserva el archivo nativo previo bajo `snapshots/`; undo y redo pueden restaurar esas copias al reiniciar el servicio. Se guardan hasta 100 pasos de undo. Las llamadas simultáneas al mismo proyecto se serializan en esa sesión.

Las primeras peticiones de cada proyecto comparten un bloqueo de inicialización asíncrono para impedir procesos nativos duplicados. Los manifiestos y el historial JSON se sustituyen de forma atómica. La inspección de solo lectura no reescribe el documento. Si una llamada nativa supera el límite de tiempo, Dürer no la cancela porque VectorCraft podría estar modificando el archivo. El error incluye un ID de operación; consulta `/api/operations/{operation_id}` durante la vida del servicio antes de reintentar.

Deshacer/rehacer compara el archivo resultante con el snapshot de destino exacto. Si el historial en memoria de VectorCraft produce otro archivo o da error, Dürer restaura el snapshot, lo vuelve a abrir y entrega una inspección nativa nueva. Así también se cubren ediciones externas hechas antes de reabrir el proyecto.

Las respuestas MCP indican `CallToolResult.isError=true` cuando falla un
proyecto/herramienta, la validación, una acción/guardado/inspección nativa o una
excepción. Se conserva el texto JSON y las respuestas de objeto ofrecen el
mismo contenido en `structuredContent`, con resultados nativos completos e
IDs de operación si se supera el tiempo límite. Los fallos de acciones
devuelven HTTP 502 en la ruta del proyecto y en llamadas de agente directas o
mediante HoardLink; los éxitos siguen devolviendo HTTP 200. Antes de reintentar,
consulta los resultados y el recibo: un guardado/inspección posterior puede
haber funcionado y una operación que excedió el tiempo puede seguir en curso.

## Intercambio y alcance

La exportación SVG, PNG y PDF está conectada directamente al motor. Se permite importar SVG, PNG, JPEG, WebP y PDF; el resultado depende del comportamiento de apertura/importación de VectorCraft. La fuente copiada permanece disponible si el documento de trabajo se convierte o modifica. `hoard://durer/illustration/{id}` identifica el proyecto persistente.

La interfaz no reproduce toda la GUI de VectorCraft. Ofrece creación e importación, vista nativa, dibujo de formas arrastrando sobre el lienzo, texto, selección por ID en la lista nativa, pintura, movimiento, escala, rotación, undo/redo, esquemas MCP y exportación. No afirma el mismo hit-testing que la aplicación de escritorio.

## Compatibilidad

No se afirma paridad con VectorCraft, Inkscape ni Penpot. La matriz comparativa sigue desconocida salvo las capacidades comprobadas en los artefactos de las pruebas. Lo no probado debe seguir marcado como no verificado.
