# Asistente Jurídico RAG Local

Aplicación local que, en fases posteriores, permitirá consultar documentos
jurídicos mediante recuperación aumentada por generación (RAG). El estado
actual incorpora la gestión y carga diferida del modelo generativo local y la
carga controlada de PDF, pero todavía no incluye extracción, embeddings ni RAG.

> **Advertencia profesional:** esta aplicación será una herramienta de apoyo.
> No toma decisiones jurídicas definitivas ni sustituye el análisis, la
> responsabilidad o el criterio de un abogado u otro profesional competente.

## Arquitectura

- **Backend:** Python 3.12, FastAPI, Pydantic y `pydantic-settings`. Expone
  `GET /api/health` y el estado seguro `GET /api/models/status`.
- **Frontend:** React, TypeScript y Vite, con React Router y TanStack Query.
  La página inicial muestra el estado real de conexión con el backend.
- **Persistencia documental (Fase 2 completada):** SQLite registra metadatos y los PDF
  validados se almacenan localmente por categoría. La base no se crea durante
  imports ni al iniciar FastAPI; no hay extracción de texto, páginas o chunks.
- **LLM local:** Qwen3-1.7B Q4_K_M en formato GGUF, ejecutado directamente con
  `llama-cpp-python` sobre CPU. La carga es diferida y nunca ocurre al importar
  módulos ni al iniciar FastAPI.
- **Embeddings futuros:** `multilingual-e5-small` continúa declarado pero no se
  descarga, instala ni utiliza en esta fase.
- **RAG futuro:** ingestión, segmentación jurídica, recuperación híbrida,
  construcción de contexto y presentación de fuentes. Todos estos módulos son
  únicamente estructura documental en el estado actual.

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

`requirements-embeddings.txt` queda reservado para una fase posterior y no es
necesario para el estado actual.

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
- `POST http://localhost:8000/api/documents`
- `GET http://localhost:8000/api/documents`

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

El proyecto sigue sin extracción o procesamiento de contenido PDF, OCR,
embeddings, SQLite FTS5, ChromaDB,
autenticación, CUDA, streaming, Docker ni despliegue.

Las próximas fases previstas son persistencia, ingestión controlada,
recuperación textual, embeddings e índice semántico, RAG con citas, relaciones
entre hechos-pruebas-normas y análisis preliminar, cada una con sus propias
pruebas y controles de privacidad.
