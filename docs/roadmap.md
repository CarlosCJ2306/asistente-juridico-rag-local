# Hoja de ruta

## Fase 0 — completada por este esqueleto

- Estructura del repositorio.
- Configuración centralizada y rutas absolutas.
- Logging rotativo y sanitización de contexto.
- Middleware de trazabilidad y endpoint de salud.
- Frontend de estado con React, Router y TanStack Query.
- Pruebas mínimas y documentación inicial.

## Fase 1 — completada: gestión del LLM local

- Manifiesto validado para Qwen3-1.7B Q4_K_M.
- Descarga explícita y controlada desde Hugging Face.
- Verificación de ruta, nombre, extensión, tamaño, firma GGUF y hash opcional.
- Adaptador `llama-cpp-python` con carga diferida por CPU.
- Prueba manual de inferencia y liberación de memoria.
- Estado seguro en `GET /api/models/status`.
- Pruebas unitarias con temporales y mocks, sin modelo real.

## Fase 3 — completada: extracción, páginas y chunks

- Extracción local con PyMuPDF mediante endpoint manual.
- Persistencia SQLite de páginas y chunks trazables.
- Limpieza conservadora y chunking jurídico determinista.
- Sin OCR, indexación semántica, FTS5 ni RAG.
- Validación manual: 28 páginas, 44 chunks, 71.111 caracteres y máximo de
  1.969 caracteres por chunk.

## Fase 4 — completada: embeddings locales

- Adaptador local de `multilingual-e5-small` con carga diferida, lotes,
  normalización y prefijos E5.
- Validación final local y offline: CPU, dimensión 384, prefijos E5,
  normalización L2, endpoints de ciclo de vida y liberación correcta.
- Sin persistencia de embeddings, indexación lexical o semántica, ChromaDB,
  FTS5, búsqueda vectorial o híbrida, reranking ni RAG.

## Fase 5 — completada: recuperación textual FTS5

- Índice derivado de `document_chunks` con backfill y triggers SQLite.
- Consulta segura con BM25, snippets, filtros, paginación y trazabilidad.
- La validación manual confirmó la migración en `head`, el backfill completo de
  44 chunks y 44 registros FTS5, la búsqueda, los filtros y el ranking BM25.
- La Fase 5 no combina FTS5 con el índice semántico; búsqueda híbrida,
  reranking, RAG e inferencia jurídica basada en recuperación siguen pendientes.

## Fase 6 — en validación: índice y búsqueda semántica local

- Cliente ChromaDB local con telemetría deshabilitada e imports perezosos.
- Índice persistente y reconstruible mediante colección temporal y activación
  atómica, sin almacenar texto completo en ChromaDB.
- Búsqueda por distancia coseno con filtros, snippets desde SQLite y descarte
  de resultados obsoletos.
- Pendiente instalar ChromaDB y validar offline el índice real, conteos,
  persistencia tras reinicio y búsqueda semántica real.

## Fase 7 — pendiente

1. **Recuperación híbrida:** combinar FTS5 y búsqueda semántica sin ampliar aún
   a reranking o RAG.

## Fases posteriores

2. **RAG local:** recuperación, contexto limitado, respuestas con fuentes y
   evaluación usando el adaptador Qwen3 ya disponible.
3. **Estructuras jurídicas:** relaciones entre hechos, pruebas y normas, con
   validación humana obligatoria.
4. **Escenarios preliminares:** métricas y explicaciones, nunca decisiones
   jurídicas automáticas.
5. **Seguridad operativa:** autenticación local si se requiere, respaldo,
   auditoría y políticas de retención.

Cada fase deberá incorporar pruebas, límites de privacidad, medición de
recursos y documentación antes de avanzar a la siguiente.
## Cierre de la Fase 6

**Completada.** ChromaDB local y offline fue validado como índice derivado
persistente y reconstruible, con telemetría deshabilitada, dimensión 384,
distancia cosine, 44 chunks activos, fingerprint SHA-256, activación atómica,
filtros y validación contra SQLite. La persistencia tras reinicio funcionó sin
rebuild posterior y el modelo terminó `unloaded`; el validador integral fue
aprobado con código 0, junto con 146 pruebas, Ruff y mypy en 70 archivos.

La Fase 7 sigue pendiente y queda limitada a recuperación híbrida combinando
FTS5 y búsqueda semántica. Fusión de rankings, reranking, RAG, generación con
contexto recuperado, citas finales e inferencia jurídica basada en recuperación
siguen pendientes.
