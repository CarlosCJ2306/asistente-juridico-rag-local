# Asistente Jurídico RAG Local

Aplicación local que, en fases posteriores, permitirá consultar documentos
jurídicos mediante recuperación aumentada por generación (RAG). El estado
actual incorpora la gestión y carga diferida del modelo generativo local y la
carga controlada de PDF y extracción local. La Fase 4 incorpora el adaptador
local de embeddings; todavía no incluye indexación ni RAG.

> **Advertencia profesional:** esta aplicación será una herramienta de apoyo.
> No toma decisiones jurídicas definitivas ni sustituye el análisis, la
> responsabilidad o el criterio de un abogado u otro profesional competente.

## Arquitectura

- **Backend:** Python 3.12, FastAPI, Pydantic y `pydantic-settings`. Expone
  `GET /api/health` y el estado seguro `GET /api/models/status`.
- **Frontend:** React, TypeScript y Vite, con React Router y TanStack Query.
  La página inicial muestra el estado real de conexión con el backend.
- **Extracción documental (Fase 3 completada):** PyMuPDF extrae texto por
  solicitud manual, SQLite persiste páginas y chunks trazables. La validación
  real confirmó 28 páginas, 44 chunks y 71.111 caracteres. No hay OCR;
  los PDF escaneados sin capa de texto fallan de forma controlada.
- **LLM local:** Qwen3-1.7B Q4_K_M en formato GGUF, ejecutado directamente con
  `llama-cpp-python` sobre CPU. La carga es diferida y nunca ocurre al importar
  módulos ni al iniciar FastAPI.
- **Embeddings locales (Fase 4 completada):**
  `intfloat/multilingual-e5-small` usa Sentence Transformers bajo demanda,
  archivos estrictamente locales, CPU, lotes, dimensión 384 y vectores
  normalizados. La validación confirmó prefijos `query:` y `passage:`, carga y
  descarga mediante los endpoints previstos y ausencia de fallback a Internet.
  La Fase 6 reutiliza este servicio para el índice vectorial local; su
  validación real permanece pendiente.
- **RAG futuro:** ingestión, segmentación jurídica, recuperación híbrida,
  construcción de contexto y presentación de fuentes. Todos estos módulos son
  únicamente estructura documental en el estado actual.
- **Búsqueda textual (Fase 5 completada):** SQLite FTS5 recupera chunks
  activos con BM25, filtros y trazabilidad. No usa embeddings ni búsqueda
  semántica.

Más detalle en [arquitectura](docs/architecture.md) y
[hoja de ruta](docs/roadmap.md).

El seguimiento operativo se mantiene en el [plan de trabajo](PLAN_TRABAJO.md)
y el historial técnico en [cambios](CAMBIOS.md).

## Requisitos

Para la fase actual:

- Windows con CMD, Python 3.12 y Node.js 20 o posterior.
- 4 GB de RAM para los servicios base y al menos 2 GB de espacio libre para
  el GGUF y las dependencias de esta fase.

Para las fases locales de IA se recomiendan, de manera preliminar, 16 GB de
RAM, CPU moderna de 64 bits y varios GB adicionales de almacenamiento. Los
requisitos definitivos dependerán de modelos, índices y volumen documental.

## Preparación manual desde CMD

No se han instalado dependencias automáticamente. Desde la raíz del proyecto:

```bat
copy .env.example .env
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r backend\requirements.txt
python -m pip install -r backend\requirements-dev.txt
```

Para habilitar únicamente la gestión y ejecución del LLM:

```bat
python -m pip install -r backend\requirements-llm.txt
```

Para habilitar únicamente embeddings locales, sin instalar ningún índice
vectorial:

```bat
python -m pip install -r backend\requirements-embeddings.txt
```

Para habilitar el índice vectorial local, después de instalar embeddings:

```bat
python -m pip install -r backend\requirements-vector.txt
```

Para instalar el frontend manualmente:

```bat
cd frontend
npm install
cd ..
```

Consulta la [guía de instalación](docs/installation.md) para todos los comandos.

## Inicio del backend

Con el entorno virtual activo:

```bat
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Los endpoints disponibles son:

- `http://localhost:8000/api/health`
- `http://localhost:8000/api/models/status`
- `GET http://localhost:8000/api/models/embeddings/status`
- `POST http://localhost:8000/api/models/embeddings/load`
- `POST http://localhost:8000/api/models/embeddings/unload`
- `POST http://localhost:8000/api/search/text`
- `GET http://localhost:8000/api/search/semantic/status`
- `POST http://localhost:8000/api/search/semantic/rebuild`
- `POST http://localhost:8000/api/search/semantic`
- `POST http://localhost:8000/api/documents`
- `GET http://localhost:8000/api/documents`
- `POST http://localhost:8000/api/documents/{document_id}/extract`
- `GET http://localhost:8000/api/documents/{document_id}/pages`
- `GET http://localhost:8000/api/documents/{document_id}/chunks`

Consultar el estado no descarga ni carga el modelo y nunca expone rutas
absolutas. Si el adaptador compartido aún no existe, esta consulta tampoco lo
crea.

## Modelo generativo local

El artefacto seleccionado es:

```text
Repositorio: ggml-org/Qwen3-1.7B-GGUF
Archivo: Qwen3-1.7B-Q4_K_M.gguf
Ruta: models/llm/qwen3-1.7b/Qwen3-1.7B-Q4_K_M.gguf
```

Desde la raíz del proyecto y con el entorno virtual activo, el propietario
puede ejecutar manualmente y en este orden:

```bat
python scripts\download_models.py
python scripts\verify_models.py
python scripts\test_local_model.py
```

La descarga usa Hugging Face solo para obtener el archivo exacto. La
verificación comprueba contención de ruta, nombre, extensión, tamaño mínimo,
firma GGUF y SHA-256 cuando el manifiesto incluya una suma confiable. El hash
oficial no se ha fijado sin una fuente previamente verificada.

El script de prueba carga el modelo bajo demanda con contexto 4096,
`n_gpu_layers=0`, CPU y un número conservador de hilos; ejecuta un prompt
controlado y libera la memoria al terminar. Los archivos de modelos están
ignorados y no deben subirse a Git.

## Modelo local de embeddings

El modelo de embeddings se descarga y verifica solo por decisión explícita del
propietario. Desde la raíz del proyecto, con las dependencias de embeddings
instaladas:

```bat
python scripts\download_models.py --model multilingual-e5-small
python scripts\verify_models.py --model multilingual-e5-small
python scripts\test_embedding_model.py
```

La prueba usa entradas sintéticas y comprueba carga local, dimensión,
normalización, orden de resultados y liberación. La validación final confirmó
74 pruebas aprobadas, Ruff y mypy sin errores. No procesa documentos ni guarda
vectores.

## Inicio del frontend

En otra ventana de CMD, desde la raíz:

```bat
cd frontend
npm run dev
```

La interfaz estará en `http://localhost:5173`. Vite lee el `.env` de la raíz,
incluida la variable `VITE_API_BASE_URL`.

## Pruebas y comprobaciones

Desde `backend` y con dependencias de desarrollo instaladas:

```bat
python -m pytest
python -m ruff check app tests
python -m mypy app
```

## Búsqueda textual local

La Fase 5 incorpora recuperación textual de chunks mediante
SQLite FTS5. El índice es derivado y reconstruible; SQLite y `document_chunks`
siguen siendo la fuente de verdad. La migración no se ejecuta al iniciar el
backend.

```json
{
  "query": "consulta sintética",
  "match_mode": "all_terms",
  "document_types": ["jurisprudencia"],
  "page": 1,
  "page_size": 20
}
```

`POST /api/search/text` admite los modos `all_terms`, `any_term` y `phrase`,
además de filtros opcionales por documento, tipo y rango de páginas. Devuelve
resultados trazables con ranking BM25 —menor valor es mejor— y snippets seguros;
no devuelve la consulta, texto completo, rutas, hashes ni vectores. La búsqueda
híbrida, el reranking y RAG siguen sin estar implementados.

El rango de páginas usa contención completa: `min_page` exige que el chunk
comience en esa página o después, y `max_page` que termine en esa página o
antes. Un chunk que solo se solapa parcialmente con el rango queda excluido.

La validación manual, tras respaldar la base local, utiliza:

```bat
cd backend
python -m alembic upgrade head
python -m alembic current
```

## Búsqueda semántica local

La Fase 6 implementa un índice ChromaDB local, persistente, derivado y
reconstruible. SQLite continúa como fuente de verdad. Chroma almacena embeddings
y metadatos mínimos, pero no el texto completo de los chunks. La distancia
coseno se interpreta como “menor es más similar”; no es probabilidad, porcentaje
ni certeza jurídica.

La secuencia manual prevista es:

1. `POST /api/models/embeddings/load`.
2. `GET /api/search/semantic/status`.
3. `POST /api/search/semantic/rebuild`.
4. `POST /api/search/semantic`.
5. `POST /api/models/embeddings/unload`.

Solicitud sintética:

```json
{
  "query": "consulta semántica sintética",
  "top_k": 10,
  "document_types": ["jurisprudencia"],
  "min_page": 1,
  "max_page": 5
}
```

Respuesta sintética:

```json
{
  "items": [
    {
      "chunk_id": "00000000-0000-0000-0000-000000000001",
      "document_id": "00000000-0000-0000-0000-000000000002",
      "document_type": "jurisprudencia",
      "chunk_index": 1,
      "start_page": 1,
      "end_page": 2,
      "snippet": "Fragmento sintético limitado.",
      "distance_cosine": 0.2
    }
  ],
  "returned": 1,
  "top_k": 10
}
```

Los filtros de páginas exigen contención completa. Los resultados se validan
contra SQLite y pueden ser menos que `top_k` cuando el índice esté desactualizado.
El almacenamiento bajo `storage/vector/` está ignorado. La búsqueda híbrida,
el reranking y RAG permanecen fuera de alcance.

El estado detecta obsolescencia mediante un fingerprint SHA-256 determinista
de los chunks activos y sus metadatos relevantes; el archivo guarda únicamente
el hash, nunca textos ni ids individuales. Si no existen chunks activos, un
rebuild explícito activa un índice vacío válido. Una colección antigua que no
pueda eliminarse después de activar la nueva queda como huérfana segura para
revisión manual y no se buscan ni borran colecciones desconocidas.

Para comprobar el frontend:

```bat
cd frontend
npm run lint
npm run build
```

## Logging

El logger central se llama `asistente_juridico_backend` y se importa siempre
desde `app.core.Log`. Admite consola y archivo rotativo UTF-8, evita handlers
duplicados y añade fecha, nivel, logger, archivo y línea. El archivo se ubica,
por defecto, en `storage/logs/asistente_juridico_backend.log`.

Además de los niveles estándar incorpora:

- `DOC` (15): configuración y documentación operativa.
- `SUCCESS` (25): finalización correcta de operaciones relevantes.

La política es estricta: nunca se deben registrar textos completos de
expedientes o chunks, prompts o respuestas completas, cuerpos de solicitudes,
datos personales sensibles, binarios, contraseñas, tokens, cookies, claves de
API ni otros secretos. Solo se permiten identificadores y metadatos técnicos
necesarios para diagnóstico. Consulta [logging](docs/logging.md).

## Estructura

```text
.
├── backend/              # API, configuración, logging y pruebas
│   ├── app/
│   │   ├── api/          # Router y endpoint de salud
│   │   ├── core/         # Rutas, settings, middleware y Log.py
│   │   ├── ai/           # Gestor de modelos y adaptador LLM local
│   │   ├── database/     # Modelos, sesiones y repositorios asíncronos
│   │   ├── ingestion/    # Estructura futura, sin procesamiento
│   │   ├── retrieval/    # Estructura futura, sin búsquedas
│   │   ├── legal/        # Estructura futura, sin análisis
│   │   ├── graph/        # Estructura futura, sin grafo
│   │   └── vector_store/ # Adaptador local y estado del índice ChromaDB
│   └── tests/
├── frontend/             # React + TypeScript + Vite
├── models/               # Manifiesto y destino local ignorado de artefactos
├── storage/              # Carpetas locales vacías y protegidas
├── scripts/              # Descarga, verificación y prueba manual del LLM
├── docs/                 # Documentación técnica
└── notebooks/legacy/     # Reserva para material legado
```

## Estado actual y próximas fases

Las fases completadas incluyen el esqueleto, configuración central, logging
seguro, salud del backend, frontend inicial, gestión del LLM Qwen3 y la Fase 2
de persistencia y carga controlada de documentos. La
inferencia solo está disponible mediante el script manual después de instalar
dependencias y descargar el modelo; no existe todavía un endpoint de prompts.

La recuperación textual SQLite FTS5 de la Fase 5 está completada y validada.
La Fase 6 está en validación: el índice persistente y la búsqueda semántica
local mediante ChromaDB están implementados, pero la dependencia y el índice
real todavía no se han instalado ni construido como parte de esta tarea.

El proyecto sigue sin búsqueda híbrida, reranking, RAG, inferencia jurídica
basada en recuperación, OCR, autenticación, streaming, Docker ni despliegue.
La Fase 7 permanece pendiente.
### Cierre de la Fase 6

La Fase 6 está **Completada** y validada: ChromaDB opera localmente y offline
como índice derivado persistente y reconstruible; la telemetría anonimizada está
deshabilitada; `multilingual-e5-small` se cargó en CPU con dimensión dinámica
384; se reconstruyeron 44 chunks activos con distancia cosine, fingerprint
SHA-256 y activación atómica. SQLite continúa siendo la fuente de verdad,
ChromaDB conserva metadatos mínimos sin texto completo y los candidatos y
snippets se validan u obtienen desde SQLite.

La persistencia después del reinicio, la búsqueda sin reconstrucción posterior,
los filtros y el estado final `unloaded` fueron comprobados. Los conteos SQLite
iniciales y finales fueron iguales: 1 documento, 28 páginas, 44 chunks y 44
registros FTS5. El validador integral terminó aprobado con código 0; hubo 146
pruebas aprobadas, Ruff sin errores y mypy sin errores en 70 archivos.

La Fase 7 permanece pendiente: recuperación híbrida combinando FTS5 y búsqueda
semántica. También siguen pendientes fusión de rankings, reranking, RAG,
generación con contexto recuperado, citas finales e inferencia jurídica basada
en recuperación.
