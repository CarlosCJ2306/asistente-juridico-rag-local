# Seguridad y privacidad

## Catálogo local de modelos

- La API acepta únicamente identificadores presentes y habilitados en el
  catálogo versionado; nunca rutas, URL o repositorios arbitrarios.
- Seleccionar un modelo no descarga archivos, no ejecuta red y no lo carga
  automáticamente.
- Las respuestas públicas omiten rutas, hashes, credenciales y configuración
  interna. La resolución rechaza traversal y escapes de las raíces autorizadas.
- El frontend envía únicamente `model_id`; no conserva la selección en
  `localStorage` o `sessionStorage`, porque la fuente de verdad operacional es
  el backend local.

## Procesamiento local

Los documentos, embeddings, índices y generación se procesan localmente. SQLite conserva la fuente de verdad; FTS5 y ChromaDB son índices derivados. No se usan servicios externos para inferencia jurídica.

## Fuentes y gobernanza

El producto distingue corpus administrado, biblioteca privada, documentos temporales y futuras fuentes web verificadas. Los documentos privados no pasan automáticamente al corpus general. Las fuentes web futuras requerirán procedencia, vigencia, permisos, conservación y revisión.

La elegibilidad documental es calculada y no se persiste como autorización. La
expiración de un documento temporal lo excluye, pero no elimina automáticamente
su registro, páginas, chunks ni archivo. La API comunica únicamente indicadores
y códigos técnicos tipados, sin rutas, contenido documental ni errores
internos. El borrado lógico, el archivo técnico y el retiro editorial son
condiciones distintas, aunque cualquiera excluye el documento de RAG.

FTS5 y ChromaDB solo proponen candidatos. SQLite vuelve a decidir antes del
resultado, del contexto y de cada cita, incluso cuando el cliente suministra
un `document_id` o una capa. Los documentos vencidos, retirados, rechazados,
archivados, no vigentes, no indexados o candidatos globales se excluyen de
inmediato aunque persistan entradas antiguas en un índice derivado. Los cambios
de gobernanza invalidan de forma detectable el índice semántico; nunca disparan
una reconstrucción automática ni eliminan PDF, páginas o chunks.

## Documentos y rutas

La carga acepta PDF con límites de tamaño, validación de MIME, extensión y firma. Los nombres se normalizan y las rutas se validan para impedir traversal y escapes del almacenamiento autorizado. Los PDF pueden contener contenido malicioso o instrucciones no confiables; nunca se tratan como instrucciones del sistema.

La extracción documental se ejecuta localmente con PyMuPDF y no activa OCR de
forma automática. La interfaz solo presenta estados y totales, nunca texto de
páginas o fragmentos, rutas, hashes ni contenido documental en notificaciones.

La interfaz envía el PDF únicamente mediante `FormData` al backend local y no
conserva el archivo, su contenido, hashes ni rutas en el navegador. Solo expone
la carga explícita para biblioteca privada o consulta temporal con expiración
futura. El backend conserva la validación autoritativa y encola de forma
controlada la extracción e indexación; la elegibilidad sigue derivándose de la
gobernanza vigente.

El staging del corpus administrado se ubica bajo `storage/staging`, permanece
ignorado y no es una carpeta observada. Solo la CLI explícita puede validar o
importar; copiar archivos no altera SQLite. Se rechazan rutas absolutas,
traversal y symlinks, y las salidas no muestran rutas ni hashes completos. La
importación nunca aprueba, procesa o indexa automáticamente una fuente.

## RAG y modelo

El texto recuperado se delimita y neutraliza antes de construir el prompt. Los documentos no reentrenan Qwen y el conocimiento previo del modelo no es una fuente jurídica verificable. Las preguntas, respuestas, prompts y contenido documental no deben registrarse ni persistirse accidentalmente.

## Matrices HPN y revisión profesional

Las relaciones HPN y la Red jurídica son herramientas de organización y revisión. Las propuestas futuras de IA serán borradores. No se debe afirmar automáticamente que un hecho está probado, que una prueba es suficiente ni que una norma es aplicable.

## Información no expuesta en frontend

El contrato público ordinario de documentos no devuelve nombres almacenados,
rutas relativas o absolutas, hashes ni mensajes técnicos internos. Esos datos
permanecen disponibles únicamente para los servicios internos que coordinan
almacenamiento, duplicados y extracción.

Tampoco se deben mostrar secretos, prompts, vectores, identificadores
restringidos, contenido no autorizado o HTML no confiable. Las respuestas y
errores deben usar contratos sanitizados.

La política técnica de logs está en [logging.md](logging.md).

### Bandejas y sidecars locales

Las bandejas se limitan a raíces fijas bajo `storage/inbox`; no se reciben
rutas por API, no se siguen symlinks y no se observan carpetas externas. Solo
se ejecuta lógica sobre PDF y JSON, nunca los archivos recibidos. Los sidecars
rechazan campos adicionales y no pueden fijar rutas, hashes, estados internos,
URLs ni capas distintas de la bandeja.

El escáner limita la cantidad inspeccionada por ciclo, exige estabilidad antes
de abrir un PDF y pone en cuarentena los archivos que continúan cambiando más
allá del tiempo permitido. Los sidecars tienen un límite de tamaño configurable.

La cola conserva una ruta relativa interna exclusivamente para reanudación.
Las respuestas y logs omiten esa ruta, contenido, chunks, consultas, hashes y
vectores. Los conjuntos inválidos se mueven a cuarentena y no se eliminan
automáticamente.
