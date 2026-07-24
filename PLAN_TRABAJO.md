# Plan de trabajo — Asistente Jurídico RAG Local

**Última actualización:** 2026-07-23

## Objetivo general

Construir un asistente jurídico local que apoye el análisis de información
documental con fuentes trazables. El sistema no es un decisor jurídico: toda
conclusión requiere revisión y criterio de un profesional competente.

## Principios de trabajo

- Ejecución local y privacidad documental.
- Fuentes trazables y revisión profesional obligatoria.
- Carga diferida de modelos para no consumir recursos al iniciar la aplicación.
- Separación entre conocimiento, recuperación y generación.
- No registrar información sensible en logs.
- No usar APIs externas de inferencia ni OpenAI, Gemini, Ollama o LM Studio en
  la aplicación.
- No subir a Git modelos, documentos, bases de datos ni logs.
- No registrar prompts, respuestas, chunks o documentos completos.
- No avanzar de fase sin cumplir sus criterios de aceptación.
- No realizar operaciones Git automáticamente.
- Mantener `Log.py` y los imports desde `app.core.Log` como mecanismo de
  logging centralizado.

## Arquitectura resumida

- Backend: FastAPI.
- Frontend: React, TypeScript y Vite.
- Persistencia documental en progreso: SQLite; FTS5 textual implementado en
  validación.
- Índice semántico futuro: ChromaDB.
- Modelo generativo local: Qwen3-1.7B Q4_K_M en GGUF mediante
  `llama-cpp-python`.
- Embeddings locales completados: `multilingual-e5-small`; no hay indexación
  ni recuperación semántica.
- Extracción documental prevista: PyMuPDF.
- Red jurídica y visualización futuras: NetworkX y PyVis.

## Fases

| Nº | Nombre | Objetivo | Estado | Dependencias | Criterio de aceptación |
| --- | --- | --- | --- | --- | --- |
| 0 | Estructura inicial | Proveer base web, configuración, salud y observabilidad. | Completada | FastAPI, React, TypeScript, Vite | `/api/health`, logging centralizado, pruebas y analizadores disponibles. |
| 1 | Modelo generativo local | Gestionar, verificar y probar Qwen3 local bajo demanda. | Completada | GGUF Qwen3, `llama-cpp-python`, Hugging Face solo para descarga | Archivo verificado, carga diferida, estado seguro e inferencia conversacional controlada. |
| 2 | Persistencia y registro documental | Registrar metadatos y archivos PDF de forma controlada. | Completada | Fase 0 | Metadatos, carga PDF segura, hash, duplicados y borrado lógico; sin extracción de texto, páginas ni chunks. |
| 3 | Extracción, páginas y chunks | Extraer contenido y segmentarlo con trazabilidad documental. | Completada | Fase 2, PyMuPDF | Páginas y chunks persistidos con referencia a documento y página. |
| 4 | Embeddings | Instalar y gestionar `multilingual-e5-small` localmente. | Completada | Fase 3, Sentence Transformers | Embeddings reproducibles sin servicios externos. |
| 5 | Búsqueda textual | Implementar recuperación léxica con SQLite FTS5. | Completada | Fase 2 y Fase 3 | Consultas textuales trazables y cubiertas por pruebas. |
| 6 | Búsqueda semántica | Crear el índice semántico local reconstruible. | Pendiente | Fase 4, ChromaDB | Recuperación semántica local evaluada. |
| 7 | Recuperación híbrida | Combinar resultados textuales y semánticos. | Pendiente | Fase 5 y Fase 6 | Ranking híbrido medible y trazable. |
| 8 | Chat RAG | Construir contexto recuperado y respuestas locales asistidas. | Pendiente | Fase 1 y Fase 7 | Respuestas basadas en recuperación, sin historial no autorizado. |
| 9 | Citas y trazabilidad | Presentar fuentes, documentos y páginas que sustentan la respuesta. | Pendiente | Fase 3 y Fase 8 | Cada respuesta RAG muestra referencias verificables. |
| 10 | Matriz HPN | Modelar relaciones entre hechos, pruebas y normas. | Pendiente | Fase 2 y Fase 9 | Relaciones revisables por el profesional. |
| 11 | Red jurídica | Construir y visualizar relaciones jurídicas. | Pendiente | Fase 10, NetworkX, PyVis | Red local trazable sin decisiones automáticas. |
| 12 | Simulación | Explorar escenarios preliminares sobre la red jurídica. | Pendiente | Fase 11 | Resultados explicables y sujetos a revisión profesional. |
| 13 | OCR | Incorporar reconocimiento óptico para documentos que lo requieran. | Pendiente | Fase 3 | Flujo OCR controlado, medido y trazable. |
| 14 | Búsqueda web controlada | Añadir fuentes web bajo controles explícitos. | Pendiente | Fase 9 | Origen, fecha y trazabilidad de cada fuente externa. |
| 15 | Evaluación y posible especialización | Evaluar el sistema y decidir si procede una especialización futura. | Pendiente | Fases funcionales anteriores | Métricas, evaluación humana y decisión documentada. |

## Estado confirmado

La Fase 0 está completada: backend FastAPI, frontend React, `/api/health`,
middleware con `request_id`, logging mediante `app.core.Log` y validaciones de
pruebas, Ruff, mypy, lint y build.

La Fase 1 está completada: Qwen3-1.7B Q4_K_M está disponible en
`models/llm/qwen3-1.7b/Qwen3-1.7B-Q4_K_M.gguf`, con tamaño verificado de
1.282.439.264 bytes. Se verificaron nombre, extensión, tamaño, ruta y cabecera
GGUF; el modelo se carga de forma diferida, usa `create_chat_completion()` y
la plantilla de chat del GGUF, se libera tras la prueba y no utiliza APIs
externas de inferencia. La prueba controlada respondió `MODELO LOCAL
FUNCIONANDO`; los tiempos observados fueron aproximadamente 1,16 s de carga y
0,85 s de generación. El SHA-256 oficial permanece pendiente de fijarse en el
manifiesto.

## Delimitación de las fases 2 y 3

### Fase 2 — Persistencia y registro documental

- Persistencia mediante SQLite.
- Definición del esquema de datos y repositorios.
- Registro y almacenamiento controlado de archivos.
- Cálculo de hash SHA-256 y detección de duplicados.
- Estados de procesamiento.
- Sin extracción de texto, páginas o chunks.
- Dependencia técnica: Fase 0.

### Fase 3 — Extracción y segmentación documental

- Extracción con PyMuPDF.
- Persistencia de páginas.
- Segmentación y persistencia de chunks.
- Trazabilidad por documento y página.

## Próximo paso autorizado

Fase 6: búsqueda semántica local mediante ChromaDB.

## Fuera de alcance actual

Ya están implementados en los bloques 2A y 2B:

- SQLite como persistencia principal.
- El modelo de metadatos `documents`.
- El repositorio documental.
- La migración inicial de Alembic.

Todavía no están implementados:

- Persistencia de embeddings.
- ChromaDB.
- Indexación lexical.
- Indexación semántica.
- Búsqueda vectorial.
- Búsqueda híbrida.
- Reranking.
- RAG.
- Inferencia jurídica basada en recuperación.
- Citas.
- Matriz HPN.
- Red jurídica.
- Simulación.
- OCR.
- Búsqueda web controlada.
- Especialización del modelo.

Las Fases 2 y 3 están **Completadas**. La Fase 3 fue validada manualmente con
28 páginas persistidas, 44 chunks y 71.111 caracteres; el chunk máximo fue de
1.969 caracteres.

La Fase 4 está **Completada**. La validación final confirmó la instalación de
`sentence-transformers`, el modelo local `intfloat/multilingual-e5-small`,
verificación local exitosa, carga estrictamente offline en CPU, dimensión 384,
embeddings de una consulta y dos pasajes con prefijos `query:` y `passage:`,
normalización L2, vectores finitos y dimensiones consistentes, liberación de
memoria, estado final `unloaded` y archivos locales disponibles tras `unload`.
También se validaron los endpoints `status`, `load` y `unload`, la carga
idempotente, el uso de `get_embedding_dimension()` y la ausencia de fallback a
Internet. La descarga futura queda filtrada a los artefactos necesarios y usa
`safetensors`. El conjunto de 74 pruebas, Ruff y mypy terminó sin errores.

La Fase 4 no incluye persistencia de embeddings, ChromaDB, FTS5, indexación
lexical o semántica, búsqueda vectorial o híbrida, reranking, RAG ni inferencia
jurídica basada en recuperación.

La Fase 5 está **Completada**. La validación final confirmó la migración
`20260724_03` aplicada, Alembic en `head`, la tabla virtual
`document_chunks_fts`, tokenizer `unicode61 remove_diacritics 2`, triggers
`INSERT`, `UPDATE` y `DELETE`, y backfill completo de 44 chunks y 44 registros
FTS5. Los datos documentales originales se conservaron.

También se validaron `POST /api/search/text`, búsquedas con y sin tilde,
`all_terms`, `any_term` y `phrase`, filtros documentales y contención completa
de páginas, orden BM25 estable, snippets Unicode seguros, rechazos 422,
sintaxis FTS5 o SQL tratada como texto y respuestas sin SQL, traceback ni rutas
locales. El conjunto de 84 pruebas, Ruff y mypy terminó sin errores.

La Fase 6 permanece **Pendiente** y corresponde a búsqueda semántica local
mediante ChromaDB. Persistencia e indexación semántica, búsqueda vectorial,
búsqueda híbrida, reranking, RAG e inferencia jurídica basada en recuperación
siguen fuera de alcance.
