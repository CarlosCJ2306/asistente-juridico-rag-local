# Arquitectura inicial

## Principios

El sistema se diseña para ejecución local, separación de responsabilidades y
trazabilidad sin exponer información jurídica. Las rutas del sistema de
archivos se calculan desde la ubicación de `paths.py`, por lo que no dependen
del directorio desde el que se invoque CMD.

## Flujo implementado

```text
Navegador en localhost:5173
        │ GET /api/health o /api/models/status
        ▼
FastAPI en localhost:8000
        │
        ├── CORS limitado al origen del frontend
        ├── middleware de request_id y duración
        ├── router /api
        ├── respuesta de salud
        ├── estado físico seguro del modelo, sin cargarlo
        └── carga, extracción manual y consulta documental controladas
```

El frontend usa TanStack Query para representar carga, disponibilidad o error.
React Router deja preparado el crecimiento por páginas sin añadir todavía
funcionalidad jurídica simulada.

## Backend

- `api/`: contratos HTTP de salud y estado de modelos. No acepta prompts.
- `core/`: configuración, rutas, logging, seguridad de logs, middleware y
  manejo global de excepciones.
- `services/document_service.py`: valida PDF, escribe por bloques en temporal,
  calcula SHA-256, detecta duplicados y coordina el movimiento atómico con
  SQLite sin registrar contenido documental.
- `services/document_extraction_service.py`: coordina el flujo PDF → páginas
  limpias → chunks jurídicos en una transacción SQLite.
- `database/`: base declarativa, modelo `documents`, repositorio y sesiones
  SQLAlchemy asíncronas creadas bajo demanda. No conecta, crea tablas ni migra
  durante imports o inicio de FastAPI.
- `vector_store/`: límite de persistencia semántica futuro, hoy inerte.
- `ai/model_manager.py`: valida el manifiesto, contiene rutas dentro de
  `models/` y verifica el archivo GGUF.
- `ai/local_llm.py`: encapsula `llama_cpp.Llama` con carga diferida, una
  instancia reutilizable y liberación explícita.
- `ingestion/`, `retrieval/`, `legal/` y `graph/`: módulos futuros que solo
  documentan su responsabilidad actual.

La configuración se obtiene mediante `pydantic-settings` desde variables de
entorno y el `.env` de la raíz. `PROJECT_ROOT` se deriva de `Path(__file__)`.
`DATABASE_FILE` se resuelve únicamente dentro de `storage/database`; la base
local prevista es `storage/database/asistente_juridico.db`.

Las tablas se crean exclusivamente mediante Alembic. La migración inicial crea
solo `documents`, sus índices y restricciones; FastAPI no ejecuta migraciones
ni crea la base al iniciar. El bloque 2B recibe PDF por `POST /api/documents`,
valida nombre, MIME, extensión, firma y límite, y conserva el original bajo
`storage/documents/<categoría>/`. La extracción se solicita manualmente, usa
PyMuPDF y persiste páginas y chunks; SQLite sigue siendo la fuente de verdad.
No hay OCR, embeddings, FTS5 ni RAG.

## Ciclo del modelo local

```text
manifest.json
     │
     ▼
ModelManager ── verifica ruta, tamaño, firma y hash opcional
     │
     ▼
LocalLLM.load() ── import diferido de llama_cpp ── CPU
     │
     ├── generate(prompt) mediante script manual
     └── unload() y liberación de memoria
```

FastAPI no llama `load()` durante su inicio. `/api/models/status` solo consulta
metadatos, `stat` y los cuatro bytes de firma; no descarga, no calcula hashes
grandes no declarados y no ejecuta inferencia. La consulta de estado tampoco
crea la instancia compartida de `LocalLLM` cuando aún no existe.

La configuración inicial utiliza `n_ctx=4096`, `n_gpu_layers=0` y
`verbose=False`. Cuando `LOCAL_LLM_THREADS=0`, se conserva al menos un núcleo y
se limita automáticamente el número de hilos.

## Evolución prevista

SQLite es la fuente de verdad para metadatos documentales. SQLite FTS5 atenderá
recuperación léxica y ChromaDB será un índice semántico reconstruible en fases
posteriores. Qwen3-1.7B GGUF ya cuenta con gestión y adaptador local; los
La Fase 3 está completada y validada manualmente: SQLite contiene 28 páginas y
44 chunks, con reconstrucción de palabras de PyMuPDF y overlap en límites de
palabra. Embeddings con `multilingual-e5-small`, indexación semántica, FTS5,
ChromaDB, RAG e inferencia jurídica aún no están implementados.
