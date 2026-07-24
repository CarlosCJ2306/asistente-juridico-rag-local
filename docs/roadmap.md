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
- Sin OCR, embeddings, FTS5 ni RAG.
- Validación manual: 28 páginas, 44 chunks, 71.111 caracteres y máximo de
  1.969 caracteres por chunk.

## Próxima fase: embeddings

1. **Embeddings:** instalación verificada de `multilingual-e5-small`, lotes e
   índice local, sin servicios externos.
2. **Recuperación textual:** FTS5, filtros y referencias a documento y página.
3. **Búsqueda semántica:** índice ChromaDB reconstruible.
4. **RAG local:** recuperación, contexto limitado, respuestas con fuentes y
   evaluación usando el adaptador Qwen3 ya disponible.
5. **Estructuras jurídicas:** relaciones entre hechos, pruebas y normas, con
   validación humana obligatoria.
6. **Escenarios preliminares:** métricas y explicaciones, nunca decisiones
   jurídicas automáticas.
7. **Seguridad operativa:** autenticación local si se requiere, respaldo,
   auditoría y políticas de retención.

Cada fase deberá incorporar pruebas, límites de privacidad, medición de
recursos y documentación antes de avanzar a la siguiente.
