# Historial técnico de cambios

## 2026-07-27 — Fase 12A-0C: Recuperación gobernada

- **Modificado:** búsqueda textual, semántica e híbrida aceptan filtros
  `knowledge_layers` y revalidan cada chunk y documento mediante la política
  central cargada desde SQLite.
- **Modificado:** contexto RAG y citas vuelven a comprobar elegibilidad antes
  del prompt y de la respuesta; las citas incorporan nombre visible y capa sin
  exponer metadatos internos.
- **Añadido:** ChromaDB conserva `knowledge_layer` como metadata mínima y el
  fingerprint incluye capa, revisión, vigencia, expiración, archivo, borrado y
  versión del esquema vectorial.
- **Añadido:** el rebuild explícito controla `pending → indexing → indexed`,
  confirma `indexed` solo tras persistir y validar la proyección, y registra
  `failed` ante errores iniciados sin invalidar un índice anterior útil.
- **Seguridad:** SQLite conserva la decisión final; FTS5, ChromaDB,
  `document_id` y filtros públicos no pueden omitir la gobernanza. No existe
  rebuild automático.
- **Validaciones:** 695 pruebas aprobadas; Ruff y mypy sin errores.
- **Pendiente:** la proyección semántica de esquema anterior requiere una
  reconstrucción explícita y validación operativa en 12A-0D.
- **Estado:** completada.

## 2026-07-27 — Fase 12A-0B: Políticas y ciclo de vida documental

- **Añadido:** política central de elegibilidad RAG calculada por capa,
  extracción, revisión, vigencia, expiración, archivo e indexación.
- **Añadido:** matrices explícitas para transiciones de revisión, vigencia e
  indexación, junto con validaciones de capas ordinarias y versionado sin
  ciclos simples.
- **Modificado:** carga, listado y detalle documentales exponen únicamente
  `rag_eligible`, motivos técnicos tipados e `is_expired`, calculados con los
  campos ya cargados y sin consultas N+1.
- **Seguridad:** la expiración solo detecta y excluye; no elimina documentos,
  páginas, chunks ni archivos. Los errores y logs no incluyen contenido o
  metadatos documentales.
- **Validaciones:** 676 pruebas aprobadas; Ruff y mypy sin errores.
- **Pendiente:** FTS5, ChromaDB, búsqueda y Chat RAG consumirán esta política
  exclusivamente en 12A-0C.
- **Estado:** completada.

## 2026-07-26 — Fase 12A-0A: Fundamentos de gobernanza documental

- **Añadido:** capas de conocimiento, procedencia, revisión, vigencia,
  indexación, metadatos editoriales y relación opcional entre versiones.
- **Añadido:** migración aditiva `20260726_05`, validada mediante
  upgrade, downgrade y nuevo upgrade sobre SQLite temporal.
- **Seguridad:** listado, detalle y carga documental ya no exponen nombre
  almacenado, ruta relativa, SHA-256 ni mensajes técnicos internos.
- **Validaciones:** pruebas documentales y de migración, Ruff y mypy aprobados.
- **Pendiente:** políticas completas de ciclo de vida y elegibilidad en
  12A-0B; integración con recuperación e índices en 12A-0C.
- **Estado:** implementada.

## 2026-07-26 — Reorganización documental

- Se consolidaron las fuentes canónicas de producto, seguridad, calidad, arquitectura, instalación y plan activo.
- Se actualizó la hoja de ruta hacia los bloques 12A-0 a 12F y se archivó el roadmap histórico.
- No se modificaron código, pruebas, configuración, SQLite, modelos ni índices.

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
- **Estado:** bloque 11A completado dentro de la Fase 11 en desarrollo.

## 2026-07-25 — Fase 11B: Contratos y API JSON

- **Añadido:** `GET /api/hpn/matrices/{matrix_id}/graph`, de solo lectura y
  tipado con `HpnGraphProjection`.
- **Integración:** delegación única en `HpnGraphService`, sin duplicar la
  construcción NetworkX ni abrir sesiones adicionales.
- **Errores:** mapeo seguro de errores estructurales a HTTP 409, 413, 500 y
  503; los errores HPN conservan su semántica existente.
- **Auditoría 11B:** los códigos de error desconocidos se reducen a
  `GRAPH_BUILD_FAILED`; se verificaron una sola construcción, una sola llamada
  a `HpnService.detail()`, registro único de ruta, privacidad recursiva y
  reutilización segura de `request_id`.
- **Alcance:** sin PyVis, HTML, exportación, frontend, caché ni persistencia
  gráfica.
- **Estado:** bloques 11A y 11B completados dentro de la Fase 11 en desarrollo.

## 2026-07-25 — Fase 11C: Exportación PyVis segura

- **Añadido:** `GET /api/hpn/matrices/{matrix_id}/graph/export` genera una
  visualización HTML completamente en memoria desde una única
  `HpnGraphProjection`.
- **Privacidad:** DTO visual inmutable con aliases efímeros deterministas, sin
  UUID HPN, statements, rationales, referencias documentales, rutas ni objetos
  NetworkX.
- **Operación local:** PyVis 0.3.2 usa recursos vis-network locales embebidos,
  sin CDN, red, archivos temporales o persistencia de HTML.
- **Seguridad:** plantilla Jinja controlada, serialización JSON segura, estilos
  y opciones cerrados, CSP con nonce criptográfico y cabeceras restrictivas.
- **Límites:** tamaño del DTO y HTML, longitud de tooltip y concurrencia de
  render configurables; PyVis se ejecuta fuera del event loop con capacidad
  limitada.
- **Estado:** Fase 11 continúa en desarrollo; 11C implementada y en validación.
  Próximo bloque: 11D — frontend y accesibilidad.

## 2026-07-26 — Auditoría de seguridad de Fase 11C

- **Recursos offline:** se retiraron del bundle público la metadata con URLs,
  `sourceMappingURL` y una rama heredada que construía scripts y utilizaba el
  esquema `javascript:`. El namespace SVG requerido por vis-network se conserva
  como dato técnico no navegable y se valida de forma cerrada.
- **Validación fail-closed:** CSS y JavaScript locales se inspeccionan después
  de normalizar entidades y escapes; CSS solo admite imágenes PNG `data:`
  incluidas en el paquete y rechaza imports, fuentes y esquemas externos.
- **Tooltips y XSS:** la versión fijada de vis-network debe conservar la
  asignación mediante `innerText`; un cambio a interpretación HTML impide el
  render. El DTO visual ya no conserva markup de tooltip precompuesto.
- **Multiaristas:** las relaciones paralelas reciben curvaturas cerradas y
  deterministas para evitar superposición visual sin alterar sus datos.
- **Pruebas:** se amplió la cobertura de importación diferida, CSP y nonce,
  serialización de secuencias problemáticas, límites UTF-8, event loops,
  recursos locales, aliases, errores y ausencia de archivos residuales.
- **Estado:** 11C permanece implementada y en validación; Fase 11 continúa en
  desarrollo y 11D — frontend y accesibilidad — sigue como próximo bloque.

## 2026-07-26 — Fase 11D-0: planificación de producto frontend

- Se detuvo la implementación directa del frontend para definir primero una
  arquitectura de producto, UX/UI, sistema de diseño y estrategia responsive.
- Se creó el documento rector `docs/frontend-product-architecture.md` con la
  arquitectura de información, shell, capas de componentes, reglas React,
  estado asíncrono, sesión local, chat temporal, notificaciones, preferencias,
  accesibilidad, privacidad e integración futura de la red jurídica.
- La Fase 11 se dividió documentalmente en 11D-0 a 11D-5, con objetivo,
  alcance, exclusiones, entregables, dependencias, riesgos, pruebas y criterio
  de cierre para cada bloque.
- 11A y 11B permanecen completadas. 11C queda completada en su alcance de
  backend y seguridad; su integración real en navegador se verificará en
  11D-5.
- **Estado:** la Fase 11 continúa en desarrollo. 11D-0 es el único bloque
  autorizado; 11D-1 no está autorizado todavía.
- **Alcance:** cambio exclusivamente documental; no se implementaron páginas,
  componentes, estilos, dependencias, autenticación ni almacenamiento de
  contenido jurídico en el navegador.

## 2026-07-26 — Fase 11D-1: Design System y componentes base

- **Fundamentos:** tokens CSS semánticos para color, tipografía, espacio,
  tamaños, radios, sombras, capas, movimiento, breakpoints y contenedores.
- **Personalización:** temas light, dark y system, junto con densidad
  comfortable y compact, sin persistir preferencias.
- **Primitivas y layout:** botones, controles nativos, estados, tipografía,
  superficies, Container, Stack, Inline, ResponsiveGrid y Cluster.
- **Componentes:** Card, Alert, Modal y Drawer basados en `<dialog>`, Tabs con
  patrón ARIA, Tooltip textual, Skeleton, EmptyState, ErrorState y FormField.
- **Patrones:** AsyncContent con estados cerrados, PageHeader responsive y
  ProfessionalReviewNotice con mensaje esencial invariable.
- **Accesibilidad y seguridad:** foco visible, teclado, retorno de foco,
  reduced motion, objetivos táctiles, texto React sin HTML interpretado y
  ausencia de API, almacenamiento, telemetría o recursos remotos.
- **Documentación:** se creó `docs/frontend-design-system.md` y se enlazó con
  la arquitectura de producto.
- **Validación disponible:** ESLint y build con TypeScript estricto aprobados.
  El proyecto no declara Vitest ni React Testing Library, por lo que no se
  instalaron dependencias ni se afirmaron pruebas de interacción inexistentes.
- **Estado:** 11D-0 completada; 11D-1 implementada y en validación; 11D-2
  pendiente. La Fase 11 continúa en desarrollo.
- **Fuera de alcance:** App Shell, sidebar, topbar, páginas, cliente API
  compartido, notificaciones globales, documentos, búsqueda, chat, HPN, red
  jurídica, sesión real, cuentas, autenticación y backend.

## 2026-07-26 — Corrección estructural de Fase 11D-1

- **Ambigüedad resuelta:** los componentes genéricos compuestos del Design
  System se trasladaron de `design-system/components` a
  `design-system/composites`.
- **Layout:** las primitivas Container, Stack, Inline, ResponsiveGrid y Cluster
  pasaron de `design-system/layout` a `design-system/layout-primitives`; la
  carpeta superior `src/layouts` queda reservada para composición futura.
- **Utilidades internas:** `design-system/utils` se renombró a
  `design-system/internal` y dejó de formar parte de cualquier API pública.
- **Componente de producto:** `ProfessionalReviewNotice` se trasladó a
  `src/components/ProfessionalReviewNotice`, con export público desde
  `src/components`; el Design System ya no lo importa ni lo reexporta.
- **Dependencias:** `components → design-system` es válida; la dirección
  inversa y los imports desde `design-system/internal` fuera del núcleo quedan
  prohibidos. Las features futuras consumirán componentes propios desde
  `features/<feature>/components`.
- **Compatibilidad:** se actualizaron imports, CSS Modules y exports reales;
  no se dejaron aliases, reexports de rutas antiguas ni archivos duplicados.
- **Estado:** 11D-0 completada; 11D-1 implementada y en validación; 11D-2
  pendiente. La Fase 11 continúa en desarrollo.

## 2026-07-26 — Auditoría estática de Fase 11D-1

- **Contratos React:** `FormField`, `Alert`, `AsyncContent`, `Modal` y `Drawer`
  impiden combinaciones incompatibles mediante tipos discriminados; los
  controles conservan `aria-invalid` y los iconos fijan su semántica accesible.
- **Interacción estructural:** `Tabs` conserva IDs ARIA estables y roving
  tabindex ante reordenamientos; Modal y Drawer sincronizan el evento nativo de
  cierre, restauran foco y exigen una razón accesible cuando bloquean el cierre.
- **Responsive y temas:** se corrigieron la container query de `PageHeader`, el
  tamaño grande de Modal, los objetivos de 44 px en densidad compacta y los
  tokens de borde, acción y peligro que fallaban el contraste calculado.
- **Seguridad y estructura:** sin rutas antiguas activas, ciclos evidentes,
  llamadas de red, almacenamiento del navegador, HTML interpretado, colores
  fuera de tokens ni referencias CSS inválidas.
- **Validación:** ESLint, TypeScript estricto y build Vite aprobados. No existen
  Vitest ni React Testing Library; teclado, foco, Escape, lector de pantalla,
  responsive visual, zoom al 200 % y contraste renderizado se difieren a
  11D-5.
- **Estado:** 11D-1 completada en implementación estática; 11D-2 es el
  siguiente bloque autorizado. La Fase 11 continúa en desarrollo.

## 2026-07-26 — Fase 11D-2: App Shell y navegación

- **Shell:** `AppLayout` integra skip link, sidebar de escritorio, topbar,
  Drawer móvil, un único contenido principal y `Outlet` de React Router.
- **Navegación:** configuración tipada única para agrupación, disponibilidad,
  iconos, rutas, matching, títulos seguros y breadcrumbs. Solo Inicio está
  activo; los ocho módulos futuros permanecen ocultos y no crean enlaces.
- **Responsive:** navegación móvil por debajo de escritorio, sidebar local
  expandida o compacta, targets de 44 px, scroll interno y layouts con ancho
  controlado o container queries.
- **Layouts:** `ContentLayout`, `FullWidthLayout` y `SplitPanelLayout` componen
  primitivas del Design System y ofrecen variantes cerradas.
- **Rutas:** se conserva la consulta real de salud en `/`; el comodín presenta
  una página 404 segura sin pathname ni detalles técnicos.
- **Privacidad:** sin cuentas, sesión, notificaciones funcionales, datos
  simulados, llamadas API nuevas, almacenamiento web ni persistencia del shell.
- **Estado:** 11D-2 implementada y en validación; 11D-3 permanece pendiente y
  la Fase 11 continúa en desarrollo. La validación interactiva se difiere a
  11D-5.

## 2026-07-26 — Auditoría estática de Fase 11D-2

- **Breakpoint seguro:** un listener de `matchMedia` con cleanup cierra el
  Drawer móvil si el viewport entra en escritorio, evitando conservar el
  overlay modal sobre la sidebar persistente.
- **Accesibilidad:** breadcrumbs con separadores explícitamente decorativos,
  marca larga y compacta centralizada, ayudas compactas sin descripción ARIA
  duplicada y paneles neutrales sin landmarks no titulados.
- **Responsive:** se eliminó el ancho mínimo global que podía provocar scroll
  horizontal con zoom y se habilitó wrap en topbar y acciones.
- **Contratos:** configuración de producto y navegación readonly; el matching
  puro ignora query y hash y conserva estrategias exact/prefix explícitas.
- **Estructura:** un solo router y provider, una ruta funcional, una fuente de
  navegación para desktop/móvil, un solo main y ningún elemento hidden en DOM.
- **Estado:** 11D-2 completada en implementación estática; interacción y
  visualización real diferidas a 11D-5. 11D-3 es el siguiente bloque
  autorizado y la Fase 11 continúa en desarrollo.

## 2026-07-26 — Fase 11D-3: servicios compartidos del frontend

- **API:** cliente HTTP nativo único con configuración validada, URLs y queries
  seguras, JSON, `FormData`, cancelación, timeout y errores normalizados. La
  consulta real de `/api/health` fue migrada sin duplicar acceso.
- **Composición:** `AppProviders` centraliza error boundary, preferencias,
  sesión local, QueryClient único y notificaciones en memoria; `main.tsx` solo
  monta esta composición y el router existente.
- **Sesión:** modo local sin usuario, credenciales, tokens, expiración ni red.
  El modo authenticated queda reservado y las capacidades futuras de UI no son
  autorización ni seguridad.
- **Preferencias:** tema system/light/dark y densidad comfortable/compact con
  aplicación inmediata. `localStorage` queda limitado a esos dos valores y la
  versión del esquema mediante lectura defensiva y reset.
- **Notificaciones y conectividad:** avisos efímeros con límite, deduplicación,
  cierre y timers con cleanup; advertencias revisables sin expiración. El aviso
  offline distingue conectividad del navegador de disponibilidad del backend.
- **Seguridad:** mensajes públicos cerrados, sin cuerpos de respuesta, URLs,
  credenciales, telemetría, HTML interpretado ni contenido jurídico; límite
  global de render sin stacks o detalles técnicos.
- **Alcance:** no se añadieron rutas, cuentas, autenticación ni funcionalidades
  de documentos, búsqueda, chat, HPN o red jurídica.
- **Validación:** ESLint, TypeScript estricto y build Vite aprobados; los
  barridos confirman un solo `fetch` encapsulado, un solo QueryClient, un solo
  health y ausencia de almacenamiento, credenciales, logs o HTML inseguro fuera
  de las políticas declaradas.
- **Estado:** 11D-3 implementada y en validación; 11D-4 permanece pendiente. La
  interacción real, timers, storage bloqueado, foco, lector de pantalla y
  responsive visual se difieren a 11D-5.

## 2026-07-26 — Auditoría estática de Fase 11D-3

- **Respuestas HTTP:** se diferencia una respuesta realmente vacía de JSON
  inválido o contenido inesperado; 204 y 205 se aceptan sin cuerpo, mientras
  una respuesta 2xx no vacía e incompatible falla con un error seguro.
- **Cancelación:** timeout y `AbortSignal` externo conservan su causa según el
  primer evento, con controller, listener y timer propios por petición y
  cleanup incondicional.
- **Configuración y URL:** la resolución válida o inválida de la base queda
  cacheada; se rechazan barras dobles en paths y se mantienen host, protocolo,
  credenciales, query y hash bajo las restricciones cerradas existentes.
- **Notificaciones:** los timers pasan al provider para cubrir también avisos
  temporalmente fuera del límite visual; dismissal, desborde, clear y unmount
  eliminan sus timers. La deduplicación ignora una repetición con la misma clave
  sin reiniciar el timer del aviso existente.
- **Encapsulación:** el índice API dejó de exponer clases internas y el índice
  de componentes dejó el toast como detalle del viewport. El provider de
  preferencias protege además el acceso a `document` y el aviso offline no
  intercepta navegación subyacente.
- **Seguridad y estructura:** una sola llamada `fetch`, health, QueryClient y
  AppProviders; sin ciclos evidentes, almacenamiento sensible, sesión
  persistida, credenciales, HTML interpretado, logs, telemetría, colores fuera
  de tokens ni recursos externos.
- **Validación:** ESLint, TypeScript estricto y build Vite aprobados; 183 módulos
  transformados. No hay test runner ni navegador, por lo que timeout, abort,
  timers, storage, contexts, foco, ARIA y responsive real se validarán en
  11D-5.
- **Estado:** 11D-3 completada en implementación estática; 11D-4 — Matriz HPN —
  es el siguiente bloque autorizado. La Fase 11 continúa en desarrollo.

## 2026-07-26 — Fase 11D-4: módulo frontend de Matrices HPN

- **Contratos:** se auditó la API HPN real y se derivaron tipos cerrados y
  guards manuales para matrices, nodos, fuentes, relaciones, paginación y
  resumen estructural.
- **Feature:** se creó `src/features/hpn-matrices` con API sobre el cliente
  compartido, keys y hooks TanStack Query, componentes, formularios, páginas y
  estilos encapsulados.
- **Operaciones:** listado, detalle y CRUD de matrices, nodos y relaciones;
  consulta y desvinculación de fuentes; confirmaciones y actualizaciones solo
  después de respuesta del backend.
- **Rutas:** se activaron `/matrices-hpn` y `/matrices-hpn/:matrixId`, junto con
  navegación y breadcrumbs cerrados que no muestran UUID. Red jurídica sigue
  oculta.
- **Estados y seguridad:** carga, vacío, error, offline, validación, conflictos,
  modo archivado de solo lectura y advertencias `stale`/`unavailable`, sin
  payloads, rutas, persistencia web, HTML interpretado ni contenido HPN en
  notificaciones.
- **Alcance:** no se añadió vinculación de fuentes porque requiere un selector
  documental todavía no autorizado; tampoco se consumen grafo, exportación,
  PyVis o validación separada ya incluida en el detalle.
- **Validación estática:** ESLint, TypeScript estricto y build Vite aprobados;
  204 módulos transformados. No existe test runner ni se ejecutó navegador o
  backend; esas comprobaciones permanecen en 11D-5.
- **Estado:** 11D-4 implementada y en validación; 11D-5 pendiente. La Fase 11
  continúa en desarrollo.

## 2026-07-26 — Auditoría estática de la Fase 11D-4

- **Contrato:** se contrastaron rutas, estados HTTP, DTO, enums, límites,
  paginación, orden, reglas de archivado y resumen estructural con el backend
  HPN vigente. La API frontend exige ahora el código de éxito exacto y reconoce
  también el tipo documental `otro`.
- **Comportamiento:** se corrigieron la eliminación permitida de una matriz
  archivada, el ajuste de página tras cambios del listado, la reapertura limpia
  de formularios, los PATCH vacíos y el manejo de rechazos de mutations sin
  perder los valores introducidos.
- **Presentación:** el resumen muestra por separado los once contadores reales,
  sin sumar categorías que pueden superponerse; las relaciones distinguen
  nodos homónimos mediante tipo y orden, sin mostrar UUID.
- **Seguridad y alcance:** se verificaron guards, query keys, cancelación de
  lecturas, invalidaciones limitadas, ausencia de persistencia HPN, HTML
  inseguro, logs, telemetría, clientes duplicados y consumo de endpoints de
  grafo. La vinculación de fuentes y el selector documental siguen aplazados.
- **Validación:** ESLint, TypeScript estricto y build Vite aprobados; 204 módulos
  transformados. No se ejecutaron backend ni navegador y la validación
  interactiva, visual y de integración permanece diferida a 11D-5.
- **Estado:** 11D-4 completada en implementación estática; 11D-5 es el siguiente
  bloque autorizado. La Fase 11 continúa en desarrollo.

## 2026-07-26 — Fase 11D-5: integración frontend de Red jurídica

- **Rutas:** se activaron `/legal-network` y `/legal-network/:matrixId`; una
  matriz HPN permite abrir su red sin exponer su identificador como texto.
- **Integración:** la página consume únicamente la proyección JSON HPN y carga
  la exportación PyVis mediante un iframe con `sandbox="allow-scripts"`,
  `referrerPolicy="no-referrer"` y título accesible. En desarrollo, Vite reenvía
  la ruta relativa `/api` hacia el backend HTTP local para respetar la CSP de la
  exportación sin copiar ni modificar el HTML.
- **Accesibilidad y privacidad:** se añadió resumen técnico, advertencias y una
  alternativa textual obligatoria. No se persisten grafo ni HTML, no se muestran
  UUID como contenido, y no hay HTML interpretado por React, recursos remotos,
  credenciales, telemetría ni almacenamiento HPN.
- **Validación disponible:** ESLint, TypeScript estricto y build Vite aprobaron;
  219 módulos fueron transformados. Los barridos estáticos confirmaron cliente
  HTTP único, ausencia de `fetch` fuera de él y ausencia de ciclos.
- **Pendiente real:** no hay navegador, Playwright, Cypress ni Puppeteer en el
  entorno, y no se inició backend contra la base principal. La validación de
  iframe, PyVis, Drawer, diálogos, foco, zoom, responsive y requests reales
  requiere un navegador local y una base temporal aislada.
- **Estado:** 11D-5 está implementada y en validación integrada; la Fase 11 no
  se marca como completada todavía.
