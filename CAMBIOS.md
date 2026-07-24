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
