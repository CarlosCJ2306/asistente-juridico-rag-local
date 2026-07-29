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

La interfaz del Chat se valida con contratos tipados y guards de respuestas
`answered` e `insufficient_context`, filtros de corpus, citas públicas y
errores sanitizados. La comprobación manual cubre teclado, contador accesible,
foco tras la respuesta, estados de carga y cancelación, copia local, temas,
ancho móvil y ausencia de preguntas, respuestas o datos internos en consola,
URL y almacenamiento del navegador.

El flujo conversacional añade guards para conversación, mensajes, claims y
snapshots de citas; creación diferida, idempotencia por intento y cancelación
real de la petición. La validación manual debe comprobar aislamiento visual de
invitados, historial tras recarga, interacción de citas, estados de cobertura,
retención informada y responsive sin almacenamiento web.

La validación visual del Chat cubre rail expandido y contraído, Drawer de
evidencia y retorno de foco, Enter para enviar, Shift+Enter para nueva línea,
composición IME, scroll independiente, ausencia de tercera columna y
responsive en 360, 768, 1024 y 1440 px.

La aceptación visual exige workspace full-width y full-height, crecimiento
inmediato del hilo al contraer el rail, scroll interno de conversaciones y
mensajes, composer visible y ausencia de márgenes, recortes o superposiciones
con sidebar global expandido o compacto y zoom al 200 %.

Las conversaciones se prueban con SQLite y modelos simulados: cookie HttpOnly,
hash irreversible, aislamiento IDOR, paginación, archivo, eliminación,
expiración y limpieza. La cobertura multi-turn comprueba recuperación nueva,
contexto no probatorio, orden e idempotencia; las citas comprueban literalidad,
snapshots, claims y disponibilidad posterior. Casos positivos y negativos de
relevancia verifican que evidencia irrelevante —incluida minería lunar— no
invoque Qwen ni produzca claims o citas.

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

## Evaluación de casos planificada

El [CaseEvaluationHarness](evaluation-harness.md) reemplazará gradualmente la
duplicación de validadores integrales para capacidades nuevas. Usará SQLite,
storage e índices temporales, fixtures sintéticas, golden cases y productores
falsos deterministas. Comparará schemas, cobertura estructural, fuentes
ausentes, relaciones inválidas, duplicados, recuperación y privacidad.

Sus métricas no evaluarán acierto jurídico, suficiencia probatoria o
probabilidad de éxito. Actualizar un golden case requerirá revisión explícita;
el harness nunca aceptará diferencias automáticamente.

## Comprobaciones arquitectónicas 12D-1

La suite inspecciona imports Python mediante AST, verifica ausencia de side
effects al importar `app.cases`, conformidad estructural de adapters con sus
`Protocol`, DTO congelados, privacidad recursiva, delegación única, errores
cerrados y resolución documental batch. Desde 12E-2, OpenAPI se compara como
conjunto normalizado método+ruta e incorpora el namespace `/api/cases` y las
cinco operaciones anidadas de pertenencia sin alterar contratos anteriores.

ESLint rechaza imports profundos entre features y accesos a
`design-system/internal`. Una comprobación adicional conserva el conjunto de
rutas frontend, permite únicamente `/cases` como ruta estática de Casos y
confirma que la feature no incorpora API, hooks ni queries. Las pruebas de
`Case` y `CaseDocument` cubren dominio, migraciones reversibles, ownership,
transacciones con FK activas, locking, auditoría, retiro y nueva asociación,
privacidad y API mediante SQLite temporal. La prueba anti-N+1 lista 1, 10 y 50
asociaciones y mantiene exactamente cuatro consultas `SELECT`.

## Compatibilidad legacy 12D-3

La suite verifica clasificación global, manifiesto versionado, referencias
inmutables, políticas sin efectos laterales, deprecación y retiro desactivados,
ausencia de `case_id`, paridad OpenAPI y conservación de rutas frontend.
