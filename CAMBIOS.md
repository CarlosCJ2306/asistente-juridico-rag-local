# Historial técnico de cambios

Este documento registra cambios funcionales, decisiones técnicas y validaciones
relevantes por fase. Las categorías usadas son: **Añadido**, **Modificado**,
**Corregido**, **Seguridad**, **Validaciones**, **Pendiente** y **Estado**.

## 2026-07-23 — Fase 0: Estructura inicial

- **Añadido:** estructura separada para backend FastAPI y frontend React con
  TypeScript y Vite.
- **Añadido:** configuración centralizada, rutas estables del proyecto y
  `Log.py` como logging centralizado mediante imports desde `app.core.Log`.
- **Añadido:** endpoint `GET /api/health` y middleware de trazabilidad con
  `request_id`.
- **Seguridad:** política de logs para evitar contenido documental, prompts,
  respuestas y datos sensibles.
- **Validaciones:** pruebas iniciales, Ruff, mypy, lint y build disponibles.
- **Estado:** completada.

## 2026-07-23 — Fase 1: Modelo generativo local

- **Añadido:** manifiesto del modelo Qwen3-1.7B Q4_K_M y scripts de descarga,
  verificación y prueba local.
- **Añadido:** gestor centralizado de modelos con verificación de nombre,
  extensión, tamaño mínimo, cabecera GGUF y SHA-256 cuando esté definido.
- **Seguridad:** validación de rutas y protección contra path traversal dentro
  de `models/`.
- **Añadido:** `LocalLLM` con carga diferida mediante `llama-cpp-python`,
  reutilización de instancia y liberación explícita de memoria.
- **Añadido:** endpoint seguro `GET /api/models/status`, sin descarga, carga ni
  inferencia.
- **Corregido:** se sustituyó el completado de texto crudo por
  `create_chat_completion()`; la generación usa la plantilla de chat incluida
  en el GGUF y extrae `choices[0].message.content`.
- **Modificado:** la prueba utiliza `/no_think`, tolera etiquetas de
  razonamiento vacías y exige que el contenido útil corresponda a
  `MODELO LOCAL FUNCIONANDO`.
- **Validaciones:** la prueba real confirmó el archivo en
  `models/llm/qwen3-1.7b/Qwen3-1.7B-Q4_K_M.gguf`, de 1.282.439.264 bytes;
  verificó carga diferida, inferencia conversacional correcta, liberación del
  modelo y ausencia de APIs externas de inferencia. Se observaron cerca de
  1,16 s de carga y 0,85 s de generación.
- **Pendiente:** fijar el SHA-256 oficial en el manifiesto cuando exista una
  fuente verificable.
- **Estado:** completada.

## 2026-07-23 — Fase 2A: Persistencia documental

- **Añadido:** configuración segura de SQLite, base declarativa SQLAlchemy 2,
  engine y sesiones asíncronas de creación diferida.
- **Añadido:** modelo `documents`, enums documentales, repositorio con borrado
  lógico, esquemas Pydantic seguros y migración inicial de Alembic.
- **Seguridad:** `DATABASE_FILE` queda limitado a `storage/database`; no se
  exponen rutas absolutas ni se almacenan contenidos documentales.
- **Validaciones:** pruebas SQLite temporales para creación, consultas,
  duplicados, filtros, paginación, borrado lógico y serialización segura.
- **Estado:** bloque 2A implementado.

## 2026-07-23 — Fase 2B: Carga controlada de PDF

- **Añadido:** endpoints `POST`, `GET` y `DELETE /api/documents` para carga,
  consulta y borrado lógico de metadatos documentales.
- **Seguridad:** validación de nombre, extensión, MIME, firma `%PDF-`, tamaño
  máximo, rutas seguras, hash SHA-256 y duplicados incluso tras borrado lógico.
- **Añadido:** escritura por bloques en temporal y movimiento atómico hacia
  `storage/documents/<categoría>/`, coordinados con la transacción SQLite.
- **Validaciones:** pruebas aisladas con SQLite y almacenamiento temporales,
  sin base, documentos ni modelo local reales.
- **Validación manual:** se confirmó carga real de PDF con HTTP 201,
  almacenamiento en `jurisprudencia`, estado `pending_extraction`, consulta
  individual con HTTP 200, detección de duplicado con HTTP 409 y conservación
  del documento original.
- **Alcance:** no se realizó extracción ni creación de chunks.
- **Estado:** Fase 2 completada.

## 2026-07-23 — Fase 3: Extracción, páginas y chunks

- **Añadido:** migración `20260723_02` para `document_pages` y
  `document_chunks`, con trazabilidad e índices por documento.
- **Añadido:** extracción local mediante PyMuPDF, limpieza conservadora y
  chunking jurídico determinista sin OCR, modelos ni servicios externos.
- **Añadido:** estados `extracting`, `extracted` y `extraction_failed`, con
  códigos de error estables para errores de PDF.
- **Añadido:** endpoints de extracción manual y consulta paginada de páginas y
  chunks.
- **Validaciones:** pruebas sintéticas con PyMuPDF, SQLite y almacenamiento
  temporal para lector, limpieza, segmentación, persistencia y API.
- **Validación manual:** se confirmó la aplicación de `20260723_02`, la cadena
  Alembic sincronizada en `head`, extracción exitosa, estado `extracted`,
  `error_code` nulo, 28 páginas, 44 chunks, 71.111 caracteres, máximo de 1.969
  caracteres por chunk, rangos de página válidos y texto Unicode almacenado.
- **Calidad:** se confirmó reconstrucción mediante palabras de PyMuPDF,
  corrección de palabras concatenadas y overlap ajustado a límites de palabras.
- **Control:** un segundo intento de extracción fue bloqueado con HTTP 409 y
  el PDF original permaneció conservado e inmutable.
- **Estado:** Fase 3 completada.

## 2026-07-23 — Fase 4: Embeddings locales

- **Añadido:** adaptador local y de carga diferida para
  `intfloat/multilingual-e5-small` mediante Sentence Transformers, sin acceso
  a red durante la carga.
- **Añadido:** configuración de ruta local, CPU, lotes, normalización y
  prefijos `query:` y `passage:`.
- **Añadido:** scripts explícitos para descarga, verificación y prueba manual
  del modelo, más endpoints de estado, carga y liberación.
- **Seguridad:** la ruta queda limitada a `models/embeddings/`; no se registran
  textos, vectores, prompts ni respuestas completas.
- **Validación final:** `sentence-transformers` quedó instalado y
  `intfloat/multilingual-e5-small` fue descargado y verificado localmente con
  código de salida 0. La carga fue estrictamente local y offline, en CPU, con
  dimensión dinámica 384.
- **Validación funcional:** se generó correctamente un embedding de consulta y
  dos de pasajes, con prefijos `query:` y `passage:`, normalización L2,
  vectores finitos y dimensiones consistentes. Se validaron `status`, `load`,
  carga idempotente y `unload`; el estado final fue `unloaded` y los archivos
  locales siguieron disponibles.
- **Seguridad:** no existe fallback a Internet. La descarga futura es selectiva
  y conserva los artefactos necesarios, incluido `safetensors`, excluyendo
  formatos alternativos.
- **Calidad:** se utilizó `get_embedding_dimension()` y se aprobaron 74
  pruebas; Ruff y mypy finalizaron sin errores.
- **Alcance:** los vectores solo existen en memoria; no hay persistencia de
  embeddings, indexación lexical o semántica, ChromaDB, FTS5, búsqueda
  vectorial o híbrida, reranking, RAG ni inferencia jurídica basada en
  recuperación.
- **Estado:** Fase 4 completada.

## 2026-07-24 — Fase 5: Recuperación textual FTS5

- **Añadido:** migración `20260724_03` con índice FTS5 derivado exclusivamente
  de `document_chunks`, tokenizer `unicode61 remove_diacritics 2`, backfill y
  triggers de inserción, actualización y borrado.
- **Añadido:** búsqueda textual local parametrizada con compilación cerrada de
  consultas, modos `all_terms`, `any_term` y `phrase`, BM25, snippets seguros,
  filtros documentales, paginación y trazabilidad por documento, chunk y páginas.
- **Seguridad:** no se acepta sintaxis FTS5 libre ni se registran consultas,
  expresiones MATCH, textos o snippets. Los errores de disponibilidad son
  controlados.
- **Validación final:** la migración `20260724_03` se aplicó correctamente y
  Alembic quedó sincronizado en `head`. Se confirmó la tabla virtual,
  tokenizer `unicode61 remove_diacritics 2`, triggers `INSERT`, `UPDATE` y
  `DELETE`, y backfill completo de 44 chunks y 44 registros FTS5. Los datos
  documentales originales se conservaron.
- **Validación funcional:** `POST /api/search/text`, búsquedas con y sin tilde,
  modos `all_terms`, `any_term` y `phrase`, filtro `document_type`, contención
  completa por páginas, BM25 ascendente con desempates estables y snippets
  Unicode con marcadores seguros.
- **Seguridad:** consultas vacías y rangos invertidos devuelven HTTP 422;
  sintaxis semejante a FTS5 o SQL se trata como texto. Las respuestas no
  contienen SQL, traceback ni rutas locales.
- **Pruebas:** 84 pruebas aprobadas; Ruff y mypy finalizaron sin errores.
- **Alcance:** persisten como pendientes la persistencia e indexación semántica,
  ChromaDB, búsqueda vectorial, búsqueda híbrida, reranking, RAG e inferencia
  jurídica basada en recuperación.
- **Estado:** Fase 5 completada.

## 2026-07-24 — Fase 6: Índice y búsqueda semántica local

- **Añadido:** dependencia separada para ChromaDB y cliente `PersistentClient`
  local de carga perezosa, sin servidor remoto y con telemetría anonimizada
  deshabilitada.
- **Añadido:** índice vectorial persistente y reconstruible desde chunks de
  documentos activos en SQLite, con distancia coseno y metadatos mínimos de
  trazabilidad; ChromaDB no almacena el texto completo.
- **Seguridad:** la reconstrucción utiliza una colección temporal, valida
  dimensión, modelo, métrica y conteo, y activa el índice mediante un archivo
  de estado reemplazado atómicamente. Un fallo conserva el índice anterior.
- **Añadido:** endpoints tipados de estado, reconstrucción explícita y búsqueda
  semántica, con filtros documentales y contención completa por páginas.
- **Validación:** cada candidato vectorial se contrasta con SQLite; chunks
  inexistentes, eliminados o con metadatos obsoletos se descartan sin exponer
  identificadores, consultas, textos o vectores en logs.
- **Pruebas:** cobertura con SQLite, almacenamiento y embeddings sintéticos,
  además de una integración opcional que se omite si ChromaDB no está
  instalado.
- **Pendiente:** instalar ChromaDB y validar offline el índice real, sus
  conteos, persistencia tras reinicio y búsqueda semántica sobre datos locales.
- **Alcance:** no incluye búsqueda híbrida, reranking, RAG ni generación con
  Qwen.
- **Estado:** en validación; no se afirma que el índice real haya sido creado.
- **Corregido tras auditoría:** `needs_rebuild` compara ahora un fingerprint
  SHA-256 determinista de la fuente activa, además del conteo. Detecta cambios
  de texto, páginas, tipo documental, sustituciones y compensaciones entre
  altas y borrados sin guardar textos ni identificadores individuales.
- **Seguridad transaccional:** se reforzó la validación del estado, timestamps,
  vectores, ids y respuestas de Chroma. Los fallos parciales intentan retirar
  únicamente la colección temporal y registran de forma segura si queda
  huérfana; un fallo al retirar el índice anterior no invalida el nuevo.
- **Cero chunks:** un rebuild explícito activa un índice vacío válido, con
  conteo cero y fingerprint de fuente vacía, y reemplaza el índice anterior
  solo después de completar la activación atómica.
- **Cierre Fase 6 (validación real):** ChromaDB local y offline, telemetría
  anonimizada deshabilitada, modelo en CPU con dimensión 384, índice de 44
  chunks activos con distancia cosine, fingerprint SHA-256, colección temporal
  y activación atómica. SQLite permaneció como fuente de verdad y el índice
  anterior se conservó ante fallos.
- **Seguridad y trazabilidad:** metadatos mínimos sin texto completo en
  ChromaDB, candidatos validados contra SQLite, snippets obtenidos desde
  SQLite y filtros documentales y de páginas comprobados.
- **Persistencia:** la búsqueda semántica funcionó tras reiniciar sin rebuild;
  el modelo terminó `unloaded`. Los conteos iniciales y finales no cambiaron:
  1 documento, 28 páginas, 44 chunks y 44 registros FTS5.
- **Calidad:** validador integral aprobado con código 0; 146 pruebas aprobadas,
  Ruff sin errores y mypy sin errores en 70 archivos.
- **Estado:** Fases 0 a 6 completadas; Fase 7 pendiente. Quedan fuera de
  alcance búsqueda híbrida, fusión de rankings, reranking, RAG, generación con
  contexto recuperado, citas finales e inferencia jurídica basada en recuperación.
## 2026-07-25 — Fase 7: Recuperación híbrida RRF

- **Añadido:** servicio híbrido que reutiliza las búsquedas FTS5 y ChromaDB de
  forma secuencial y aplica los mismos filtros a ambas fuentes.
- **Añadido:** fusión RRF ponderada configurable, candidatos limitados,
  deduplicación por chunk y ranking estable con trazabilidad de origen.
- **Seguridad:** revalidación final de candidatos contra SQLite, descarte de
  resultados obsoletos, snippets desde SQLite y logging sólo de metadatos.
- **API:** `POST /api/search/hybrid` con request y response tipados, errores
  controlados y sin fallback silencioso a una sola fuente.
- **Pruebas:** cobertura sintética de configuración, fusión, pesos, límites,
  deduplicación, filtros, resultados obsoletos, HTML, API y privacidad.
- **Pendiente:** validación manual real con ambos índices y embeddings locales.
  No incluye reranking, RAG, generación ni citas finales.
## 2026-07-25 — Cierre de Fase 7: Recuperación híbrida

- **Validación final:** recuperación local mediante FTS5 y ChromaDB, con SQLite como fuente de verdad e índices derivados persistentes.
- **RRF:** fusión determinista ponderada por posiciones iniciadas en 1; BM25 y cosine distance no participan directamente en `hybrid_score`.
- **Resultados:** candidatos limitados, deduplicación por chunk, trazabilidad, filtros documentales y de página con contención completa, y snippets desde SQLite tras validación final.
- **Operación:** errores de disponibilidad controlados, sin fallback silencioso; persistencia de FTS5 y ChromaDB confirmada tras reinicio.
- **Validación:** conteos SQLite sin cambios (1 documento, 28 páginas, 44 chunks y 44 registros FTS5), modelo `unloaded`, Uvicorn cerrado y puertos liberados. Validador aprobado con código 0, 206 pruebas, Ruff y mypy sin errores en 72 archivos.
- **Pendiente:** selección de contexto, presupuestos de tokens, prompts, generación con Qwen, RAG, prevención de instrucciones documentales, citas, reranking, historial persistente, HPN, red jurídica, OCR y búsqueda web.
## 2026-07-25 — Fase 8: Chat RAG local y contexto controlado

- **Añadido:** servicio RAG stateless que reutiliza una única recuperación
  híbrida y recupera el texto vigente desde SQLite.
- **Añadido:** selección determinista de chunks y presupuesto estricto mediante
  el tokenizer del GGUF, reservando salida y margen de seguridad.
- **Seguridad:** prompt fijo con evidencia documental no confiable, tokens de
  roles neutralizados y ausencia de prompts, preguntas, contexto o respuestas
  en logs.
- **Añadido:** generación Qwen local bajo demanda, sin carga automática,
  streaming, Internet ni historial persistente.
- **Añadido:** respuesta controlada `insufficient_context` sin invocar Qwen y
  endpoint tipado `POST /api/chat/rag`.
- **Validaciones:** pruebas con recuperación, SQLite, tokenizer y Qwen falsos;
  validador integral preparado sin ejecución real.
- **Alcance:** no incluye citas finales, reranking, Fase 9 ni frontend.
- **Estado:** en validación; no se afirma generación real todavía.

## 2026-07-25 — Cierre de la Fase 8

- **Estado:** Fase 8 completada tras la validación integral real.
- **Chat RAG:** `POST /api/chat/rag` opera localmente y de forma stateless,
  con una recuperación híbrida única por petición y texto vigente obtenido
  desde SQLite.
- **Contexto:** selección determinista, tres chunks validados, deduplicación
  por `chunk_id`, neutralización de evidencia no confiable y límites de tokens
  comprobados (`4096`, `512`, `128`, `1728` y máximo de prompt `3456`).
- **Generación:** Qwen local con tokenizer y plantilla GGUF, `/no_think`
  controlado, ejecución fuera del event loop, lock de generación y salida
  pública sin razonamiento interno ni HTML ejecutable.
- **Casos validados:** `answered` HTTP 200 e `insufficient_context` HTTP 200
  sin invocar Qwen cuando no hay evidencia suficiente; persistencia de FTS5 y
  ChromaDB tras reinicio sin rebuild.
- **Integridad:** conteos SQLite sin cambios (1 documento, 28 páginas,
  44 chunks y 44 registros FTS5); Qwen y embeddings finalizaron `unloaded` y
  el entorno quedó sin procesos propios pendientes.
- **Calidad:** validador aprobado con código 0, 281 pruebas aprobadas, Ruff sin
  errores y mypy sin errores en 76 archivos.
- **Alcance pendiente:** citas finales, referencias visibles, reranking,
  historial persistente, frontend, HPN, red jurídica, simulación, OCR y
  búsqueda web.

La siguiente fase autorizada es la Fase 9 — Citas y trazabilidad de las
fuentes utilizadas por las respuestas RAG.

## 2026-07-25 — Fase 9: Citas visibles y trazabilidad estructural

- **Añadido:** registro efímero de fuentes seleccionadas para contexto con
  markers deterministas `[F1]..[Fn]`, sin persistencia ni control desde HTTP.
- **Modificado:** el prompt incorpora evidencia marcada e instrucciones fijas
  para que Qwen utilice únicamente markers permitidos.
- **Seguridad:** neutralización de markers inyectados en documentos y pregunta,
  parser cerrado, rechazo de formatos ambiguos, fuentes inventadas, enlaces y
  respuestas sin cobertura por elemento sustantivo.
- **Añadido:** revalidación posterior a la generación mediante una sesión
  SQLite nueva, con comprobación de documento activo, chunk, metadata, nombre
  de presentación y contenido vigente.
- **API:** ampliación aditiva de `POST /api/chat/rag` con `citation_count` y
  `citations`; `insufficient_context` devuelve cero citas y no invoca Qwen.
- **Privacidad:** nombres sanitizados y metadata pública limitada; no se
  exponen rutas, nombres almacenados, hashes, texto, snippets, prompts, scores,
  vectores ni identificadores internos de chunk.
- **Errores:** `RAG_CITATION_OUTPUT_INVALID`,
  `RAG_CITATION_SOURCE_STALE` y `RAG_CITATION_METADATA_INVALID` con respuestas
  controladas.
- **Pruebas:** cobertura sintética de configuración, registro, nombres,
  prompt, inyección, presupuesto, parser, cobertura, respuesta pública,
  revalidación, errores, API, sesiones y logging.
- **Validador:** `validate_phase9_end_to_end.py` preparado con informe atómico
  sanitizado; no fue ejecutado durante la implementación.
- **Estado:** en validación. No se afirma todavía validación real de Chat RAG
  con citas ni correspondencia sobre los datos locales.
- **Alcance:** no incluye reranking, historial persistente, frontend, HPN,
  red jurídica, simulación, OCR ni búsqueda web.

## 2026-07-25 — Cierre de la Fase 9

- **Estado:** Fase 9 completada tras validación integral real; código de salida
  0.
- **Citas:** markers efímeros `[F1]..[Fn]`, parser cerrado, cobertura por
  elemento sustantivo, correspondencia exacta y revalidación estricta en
  SQLite. La metadata pública procede únicamente de SQLite y no incluye texto,
  rutas, hashes, scores, vectores ni identificadores internos.
- **Privacidad y seguridad:** registro de fuentes por solicitud no persistido
  ni registrado; evidencia no confiable; sin reparación automática ni segunda
  generación; revisión profesional obligatoria.
- **Validación:** Chat RAG `answered` HTTP 200, `insufficient_context` HTTP
  200 sin Qwen, persistencia de índices tras reinicio, conteos SQLite sin
  cambios (1 / 28 / 44 / 44), modelos `unloaded` y puertos liberados.
- **Calidad:** 443 pruebas aprobadas, Ruff sin errores y mypy sin errores en
  77 archivos.
- **Alcance pendiente:** Fase 10 — Matriz HPN. También permanecen pendientes
  reranking, historial persistente, frontend de chat, red jurídica,
  simulación, OCR y búsqueda web.

## 2026-07-25 — Fase 10: Matriz HPN manual y revisable

- Se agregó la migración `20260725_04` con las tablas `hpn_matrices`,
  `hpn_nodes`, `hpn_node_sources` y `hpn_relations`, restricciones e índices.
- Se implementaron matrices, nodos `fact`, `evidence` y `norm`, estados de
  revisión cerrados, relaciones dirigidas compatibles y borrado lógico.
- Las fuentes se resuelven contra SQLite por `document_id` y `chunk_index`;
  conservan una snapshot mínima y un fingerprint SHA-256 sin almacenar texto.
- Las lecturas clasifican fuentes como `valid`, `stale` o `unavailable` sin
  reemplazarlas ni actualizar su snapshot automáticamente.
- Se incorporó validación estructural antes de marcar una matriz `reviewed` y
  retorno explícito a `in_review` después de modificarla.
- Se expuso una API CRUD tipada bajo `/api/hpn`, sin campos internos, rutas,
  hashes, chunks, scores, vectores ni contenido de otros nodos.
- Se agregaron pruebas sintéticas con SQLite temporal y se preparó
  `validate_phase10_end_to_end.py` para una validación futura sobre una copia
  aislada. El validador no fue ejecutado y la migración no fue aplicada a la
  base real.
- **Auditoría:** se reforzaron las claves foráneas de las snapshots, el enum de
  tipo documental, los límites coherentes, la activación de claves foráneas en
  SQLite y la verificación aislada de la cascada lógica. Triggers locales de
  INSERT y UPDATE impiden asociar un chunk con un documento que no le pertenece.
- **Consistencia:** `archived` es un estado visible de solo lectura distinto de
  `deleted_at`; una fuente posterior `stale` o `unavailable` no modifica la
  revisión humana del nodo, pero impide `valid_for_review`.
- **Privacidad:** la sanitización de nombres se comparte con citas y las rutas
  registradas se reducen a plantillas seguras, sin identificadores completos.
- No se incorporaron IA automática, NetworkX, PyVis, simulación ni frontend.
## 2026-07-25 — Cierre de Fase 10

- **ValidaciÃ³n:** la funcionalidad HPN, persistencia, reinicio, limpieza
  objetiva e integridad de la base original quedaron aprobados en la Ãºltima
  ejecuciÃ³n integral.
- **Resultados previos:** 526 pruebas aprobadas, Ruff limpio y mypy limpio en
  82 archivos.
- **DisposiciÃ³n:** el centinela se conserva como instrumentaciÃ³n diagnÃ³stica;
  su ausencia genera una advertencia y no invalida la liberaciÃ³n objetiva.
- **Estado:** Fase 10 completada. Fase 11 — Red jurÃ­dica — queda como Ãºnico
  siguiente paso pendiente.
## 2026-07-25 — Fase 11A: Dominio NetworkX

- **Añadido:** proyección estructural HPN bajo demanda mediante `MultiDiGraph`.
- **Seguridad:** nodos, aristas y resúmenes sin statements, rationales, texto
  documental, fingerprints ni identificadores internos de chunks.
- **Auditoría 11A:** el hilo recibe DTOs mínimos e inmutables, las fuentes
  sintéticas duplicadas se deduplican por identidad, los warnings usan códigos
  cerrados y los errores internos de importación no se confunden con ausencia
  de NetworkX.
- **Alcance:** sin API, PyVis, HTML, frontend, caché ni persistencia gráfica.
- **Estado:** Fase 11 en desarrollo; bloque 11A en validación. Próximo bloque:
  11B — contratos y API JSON.
