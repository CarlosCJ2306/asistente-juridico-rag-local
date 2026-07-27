# Instalación y operación local

## Requisitos

Python 3.12, Node.js y acceso local a los modelos necesarios para las capacidades de IA. No se descargan modelos ni dependencias automáticamente.

## Backend

Desde la raíz, cree y active un entorno Python y use los manifiestos de dependencias requeridos por la instalación:

```bat
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\activate
python -m pip install -r backend\requirements.txt
python -m pip install -r backend\requirements-dev.txt
```

Instale los componentes opcionales locales solo cuando correspondan:

```bat
python -m pip install -r backend\requirements-llm.txt
python -m pip install -r backend\requirements-embeddings.txt
python -m pip install -r backend\requirements-vector.txt
```

Configure las variables del backend según el archivo de ejemplo aplicable. No versionar secretos, bases SQLite, modelos, documentos jurídicos ni índices.

## Migraciones y backend

Ejecute las migraciones de forma explícita desde `backend` sobre la base autorizada:

```bat
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Compruebe `GET /api/health` antes de usar otros flujos. No ejecute migraciones, resets o seeds sin autorización para la base objetivo.

## Corpus administrado local

Configure `MANAGED_CORPUS_STAGING_PATH` con una ruta relativa bajo
`storage/staging`; el valor predeterminado es
`storage/staging/managed_corpus`. Los PDF de staging no se versionan y el
manifiesto vive en `managed_corpus/manifest.json`. Copiar un PDF no dispara
ninguna operación.

Desde la raíz, con el entorno backend activo y después de aplicar las
migraciones autorizadas, use comandos explícitos:

```bat
python scripts\manage_corpus.py --json validate
python scripts\manage_corpus.py --json import
python scripts\manage_corpus.py --json status
python scripts\manage_corpus.py --json review --source-key FUENTE --decision approve --legal-validity current --confirm
python scripts\manage_corpus.py --json promote --source-key FUENTE --document-id UUID --confirm
```

`import` se detiene en el primer error salvo que se indique
`--continue-on-error`. Aprobar no extrae ni indexa. El procesamiento posterior
continúa mediante los servicios oficiales: revisión humana, vigencia,
extracción, chunks, indexación confirmada y, finalmente, elegibilidad RAG.

## Frontend

Desde `frontend`:

```bat
npm install
npm run dev
```

Vite lee `frontend/.env`; la variable `VITE_API_BASE_URL` debe referirse al origen local del frontend para que las solicitudes `/api` usen el proxy de desarrollo. El proxy reenvía `/api` al backend local. El backend usa su propia configuración; sus variables no sustituyen el archivo `.env` del frontend.

## Modelos locales

Los directorios de modelos se resuelven desde la configuración local. Qwen GGUF y el modelo de embeddings deben estar disponibles localmente antes de cargarlos. La carga y descarga se solicitan explícitamente mediante las rutas de modelos; no hay fallback a Internet durante inferencia.

## Validaciones básicas

```bat
cd backend
python -m pytest
python -m ruff check app tests
python -m mypy app

cd ..\frontend
npm run lint
npx tsc -b
npm run build
```

## Problemas comunes

- Si `/api` falla en desarrollo, confirme que backend y Vite estén activos y que `frontend/.env` use el origen local esperado.
- Si una ruta de modelo o almacenamiento es rechazada, corrija la configuración dentro de los directorios autorizados; no use rutas absolutas externas ni traversal.
- Si un índice derivado no está listo, siga el flujo explícito de carga y reconstrucción autorizado; no modifique SQLite directamente.
