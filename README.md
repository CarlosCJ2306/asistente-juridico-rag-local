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
  No hay persistencia ni índice vectorial.
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
no devuelve la consulta, texto completo, rutas, hashes ni vectores. FTS5,
persistencia de embeddings, ChromaDB, búsqueda semántica y RAG siguen sin estar
implementados.

El rango de páginas usa contención completa: `min_page` exige que el chunk
comience en esa página o después, y `max_page` que termine en esa página o
antes. Un chunk que solo se solapa parcialmente con el rango queda excluido.

La validación manual, tras respaldar la base local, utiliza:

```bat
cd backend
python -m alembic upgrade head
python -m alembic current
```

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
│   │   └── vector_store/ # Estructura futura, sin ChromaDB
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

El proyecto sigue sin OCR, persistencia de embeddings, indexación lexical o
semántica, SQLite FTS5, ChromaDB, búsqueda vectorial o híbrida, reranking, RAG
ni inferencia jurídica basada en recuperación,
autenticación, CUDA, streaming, Docker ni despliegue.

La próxima fase autorizada es la búsqueda semántica local mediante ChromaDB.
Persistencia e indexación semántica, búsqueda vectorial, búsqueda híbrida,
reranking, RAG e inferencia jurídica basada en recuperación siguen pendientes.
La recuperación textual SQLite FTS5 de la Fase 5 está completada y validada.
La próxima fase autorizada es búsqueda semántica local mediante ChromaDB;
persistencia e indexación semántica, búsqueda vectorial o híbrida, reranking,
RAG e inferencia jurídica basada en recuperación siguen pendientes.
