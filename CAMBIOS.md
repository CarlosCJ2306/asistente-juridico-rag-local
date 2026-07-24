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
