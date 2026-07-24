# Instalación y ejecución manual

Los siguientes comandos están escritos para CMD en Windows. El proyecto no
instala nada automáticamente.

## 1. Configuración local

Desde la raíz:

```bat
copy .env.example .env
```

El archivo `.env` queda ignorado por Git. No agregue secretos a
`.env.example`.

## 2. Backend

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
python -m pip install -r backend\requirements-dev.txt
python -m pip install -r backend\requirements-llm.txt
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Verificación manual en otra ventana:

```bat
curl http://localhost:8000/api/health
```

Respuesta esperada:

```json
{"status":"ok","service":"asistente-juridico-backend"}
```

## 3. Frontend

Desde la raíz, en otra ventana de CMD:

```bat
cd frontend
npm install
npm run dev
```

Abra `http://localhost:5173`. La aplicación consulta el backend definido en
`VITE_API_BASE_URL`.

## 4. Pruebas

```bat
cd backend
python -m pytest
python -m ruff check app tests
python -m mypy app
```

Las pruebas fuerzan `LOG_TO_FILE=false` y `LOG_CONSOLE=false` antes de importar
la aplicación, de modo que no escriben en el directorio real de logs.

## 5. Migraciones de base de datos

Desde `backend`, con el entorno virtual activo, ejecute las migraciones de
forma explícita:

```bat
python -m alembic upgrade head
python -m alembic current
python -m alembic history
```

La base local se crea en `storage/database/asistente_juridico.db` solo al
ejecutar la migración. Importar módulos o iniciar FastAPI no crea la base ni
tablas.

## 6. Carga documental manual

Con el backend iniciado, puede cargar un PDF de prueba mediante `curl`:

```bat
curl -X POST http://localhost:8000/api/documents -F "document_type=expediente" -F "file=@C:\ruta\archivo.pdf;type=application/pdf"
```

La carga valida extensión `.pdf`, MIME exacto, firma `%PDF-`, tamaño máximo y
duplicados SHA-256. El archivo se conserva localmente bajo `storage/documents/`;
no se extrae texto ni se crean páginas o chunks.

## 7. Modelos

Los comandos de esta sección se ejecutan desde la **raíz del proyecto**, no
desde `backend` ni `scripts`. Si estaba dentro de `backend`, ejecute primero:

```bat
cd ..
```

Descarga explícita del único artefacto GGUF declarado:

```bat
python scripts\download_models.py
```

El script no se ejecuta al importarlo, evita repetir una descarga ya verificada
y usa `local_dir` para dejar el archivo en:

```text
models/llm/qwen3-1.7b/Qwen3-1.7B-Q4_K_M.gguf
```

Verificación independiente:

```bat
python scripts\verify_models.py
```

Prueba manual de inferencia por CPU:

```bat
python scripts\test_local_model.py
```

La prueba no descarga automáticamente. Primero verifica el modelo, lo carga de
forma diferida, solicita una frase controlada y ejecuta `unload()` al finalizar.
No ejecute la prueba si todavía no descargó el archivo.

Los artefactos `.gguf` están ignorados y no deben subirse a Git. No instale
`requirements-embeddings.txt`: Sentence Transformers y ChromaDB pertenecen a
una fase futura.
