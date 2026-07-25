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
- `ai/embedding_model.py`: adaptador de embeddings local, perezoso y solo de
  archivos locales; no persiste vectores.
- `services/embedding_service.py`: aplica prefijos de consulta y pasaje y
  devuelve vectores normalizados en memoria.
- `vector_store/`: cliente ChromaDB perezoso y estado atómico del índice
  semántico derivado.
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
No hay OCR, búsqueda híbrida, reranking ni RAG.

## Flujo de recuperación textual

```text
document_chunks
        │ triggers SQLite
        ▼
document_chunks_fts
        │ BM25
        ▼
TextSearchService
        ▼
resultados trazables
```

SQLite y `document_chunks` siguen siendo la fuente de verdad. FTS5 es un índice
derivado y reconstruible: no reemplaza los chunks ni contiene embeddings. La
consulta se compila en modos cerrados, se ejecuta con parámetros enlazados y
excluye documentos con borrado lógico.

Los filtros de página aplican contención completa del chunk: página inicial
mayor o igual al mínimo y página final menor o igual al máximo. Los solapamientos
parciales quedan fuera del resultado.

## Flujo local de embeddings

```text
chunks persistidos
        │
        ▼
EmbeddingService (passage:) / consulta (query:)
        │
        ▼
EmbeddingModel → Sentence Transformers local → vectores normalizados en memoria
```

El adaptador de embeddings no escribe vectores por sí mismo. La Fase 6 los
persiste únicamente en ChromaDB durante una reconstrucción explícita. La carga
y descarga son explícitas mediante `/api/models/embeddings/load` y
`/api/models/embeddings/unload`; el estado no carga pesos ni importa la
dependencia opcional.

## Flujo de recuperación semántica

```text
document_chunks + documents activos
                ↓
        EmbeddingService (passage:)
                ↓
      colección temporal ChromaDB
                ↓ validación de modelo, dimensión, métrica y conteo
       estado activo reemplazado atómicamente
                ↓
       consulta con embedding query:
                ↓
       validación final contra SQLite
                ↓
          resultados trazables
```

SQLite sigue siendo la fuente de verdad. ChromaDB es un índice local,
persistente, derivado, reemplazable y reconstruible: almacena vectores y
metadatos mínimos, no textos completos. Los snippets se producen con el texto
vigente en SQLite. FTS5 y ChromaDB todavía no se combinan; esa integración
pertenece a una fase posterior.

La reconstrucción conserva la colección activa mientras construye una nueva y
solo cambia el archivo de estado tras verificarla. El estado incluye un
fingerprint SHA-256 determinista de la fuente activa para detectar cambios aun
cuando el conteo permanezca igual; no incluye textos ni identificadores
individuales. Si la fuente no contiene chunks, un rebuild explícito activa un
índice vacío válido.

El índice anterior se elimina después de activar el nuevo. Si esa limpieza
falla, el nuevo sigue activo y la colección anterior queda huérfana para
revisión manual; no se enumeran ni eliminan colecciones desconocidas. El
proceso local debe usar un único worker durante el rebuild: la protección
concurrente es interna al proceso y no afirma coordinación multiproceso.

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

SQLite es la fuente de verdad documental. La Fase 5 completó la recuperación
léxica con FTS5. La Fase 6 implementa persistencia e indexación semántica en
ChromaDB y búsqueda vectorial, pero permanece en validación hasta instalar la
dependencia y comprobar offline el índice real, sus conteos y su persistencia
tras reiniciar el backend.

Qwen3-1.7B GGUF y `multilingual-e5-small` conservan sus ciclos de vida
explícitos e independientes. La búsqueda híbrida, el reranking, RAG y la
inferencia jurídica basada en recuperación siguen pendientes.
## Cierre de Fase 6

La validación real confirmó ChromaDB local y offline, telemetría anonimizada
deshabilitada, dimensión dinámica 384, 44 chunks activos, distancia cosine,
fingerprint SHA-256 y activación atómica. SQLite sigue siendo la fuente de
verdad; ChromaDB es un índice derivado reconstruible con metadatos mínimos, y
los candidatos y snippets se validan u obtienen desde SQLite. La persistencia
tras reinicio funcionó sin rebuild posterior y el modelo terminó `unloaded`.

Fase 7 queda pendiente para recuperación híbrida mediante FTS5 y búsqueda
semántica; no incluye aún fusión de rankings, reranking, RAG, generación con
contexto recuperado, citas finales ni inferencia jurídica basada en recuperación.
