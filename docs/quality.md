# Calidad y validación

El catálogo y la selección de modelos se validan con manifiestos, artefactos y
archivos operacionales temporales. Las pruebas no cargan modelos reales, no
usan red y no escriben en los directorios principales de modelos o storage.

## Validaciones configuradas

- Backend: `python -m pytest`, `python -m ruff check app tests` y `python -m mypy app` desde `backend`.
- Frontend: `npm run lint`, `npx tsc -b` y `npm run build` desde `frontend`.

Las pruebas usan fixtures, mocks y SQLite temporal cuando corresponde. Está prohibido usar, resetear o modificar la SQLite principal durante pruebas automatizadas. Tampoco se deben usar documentos jurídicos reales, modelos reales o índices locales salvo en una validación manual explícitamente autorizada.

La recuperación gobernada se prueba con SQLite y FTS5 temporales, ChromaDB
temporal o falso, embeddings simulados y contenido sintético. La cobertura
comprueba expiración, retiro, vigencia, capas, bypass por identificador,
fingerprint, transiciones de indexación, revalidación previa al prompt y retiro
de citas, sin modificar las persistencias locales principales.

El núcleo Chat RAG se prueba con recuperación, tokenizer y LLM falsos. La
cobertura incluye contexto insuficiente sin cargar Qwen, carga bajo demanda
única, reutilización, modo manual, descarga por inactividad, protección de
generaciones, timeouts y cancelación. También verifica citas inventadas o
retiradas, documentos que pierden elegibilidad, inyección desde evidencia,
solicitudes de revelación y ausencia de preguntas, respuestas, chunks o prompts
en logs.

La automatización se valida con filesystem y SQLite temporales, PDF sintéticos,
adaptadores de embeddings falsos y colecciones Chroma temporales o simuladas.
Las pruebas cubren estabilidad de archivos, sidecars estrictos, recuperación
de cola, reintentos, exclusión por gobernanza, carga concurrente, descarga por
inactividad, activación batch y privacidad de API. La validación operativa con
persistencias principales se ejecutó por separado con backups, contenido
sintético y comprobación de conservación de los datos preexistentes.

El corpus administrado se prueba con manifiestos y PDF mínimos sintéticos,
SQLite y directorios temporales. Las pruebas cubren validación dry-run,
traversal y symlinks, duplicados, idempotencia, rollback, revisión, promoción,
versionado y migración reversible, sin usar el staging ni el almacenamiento
principal.

## Informes locales de validación

`local_validation_reports/` no se versiona ni es una fuente de verdad del proyecto. La política inicial es conservar temporalmente `latest` y ejecuciones relevantes, revisar periódicamente los informes obsoletos y eliminarlos manualmente cuando ya no sean necesarios. Esta política no autoriza su borrado automático.
