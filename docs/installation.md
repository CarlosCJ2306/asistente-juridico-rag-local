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
python -m pip install -r backend\requirements-embeddings.txt
python -m pip install -r backend\requirements-vector.txt
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

PyMuPDF se instala con `backend\requirements.txt`; no se requiere OCR.

### Validación manual de FTS5

La validación final de la Fase 5 confirmó la migración, la tabla FTS5, sus
triggers, el backfill completo y las búsquedas con filtros en un entorno local
controlado. Para repetirla posteriormente, use una base respaldada; el
backend no crea el índice durante imports ni inicio.

Para repetir la validación, use una base local respaldada y aplique la
migración explícitamente; el backend no crea el índice durante imports ni
inicio. Confirme primero que SQLite dispone de FTS5 en un entorno controlado:

```bat
python -m alembic upgrade head
python -m alembic current
```

El endpoint `POST /api/search/text` devuelve 503 controlado mientras el índice
no exista. Tras la migración, valide conteos de chunks e índice, búsqueda sin
tilde, filtros y páginas.

## 6. Carga documental manual

Con el backend iniciado, puede cargar un PDF de prueba mediante `curl`:

```bat
curl -X POST http://localhost:8000/api/documents -F "document_type=expediente" -F "file=@C:\ruta\archivo.pdf;type=application/pdf"
```

La carga valida extensión `.pdf`, MIME exacto, firma `%PDF-`, tamaño máximo y
duplicados SHA-256. El archivo se conserva localmente bajo `storage/documents/`.

## 7. Extracción manual

Después de aplicar la nueva migración, solicite la extracción explícitamente:

```bat
curl -X POST http://localhost:8000/api/documents/{document_id}/extract
```

El flujo usa PyMuPDF para PDFs con capa de texto, persiste páginas y chunks en
SQLite y no realiza OCR. Un PDF escaneado sin texto extraíble falla de forma
controlada.

## 8. Modelos

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

### Embeddings locales

El adaptador de embeddings no descarga, carga ni prueba pesos al importar la
aplicación. Tras instalar `backend\requirements-embeddings.txt`, ejecute
manualmente:

```bat
python scripts\download_models.py --model multilingual-e5-small
python scripts\verify_models.py --model multilingual-e5-small
python scripts\test_embedding_model.py
```

El directorio local esperado es `models/embeddings/multilingual-e5-small/`.
La validación final confirmó carga offline en CPU, dimensión 384, prefijos
`query:` y `passage:`, normalización L2, estado final `unloaded` y archivos
locales disponibles después de liberar el modelo. No crea índices, no guarda
vectores y no ejecuta RAG.

Los artefactos de modelos están ignorados y no deben subirse a Git.

### Índice semántico local

ChromaDB se instala manualmente desde la raíz y no forma parte de las
dependencias base:

```bat
python -m pip install -r backend\requirements-vector.txt
```

Las variables principales son `CHROMA_PERSIST_PATH`,
`SEMANTIC_INDEX_STATE_FILE`, `SEMANTIC_COLLECTION_PREFIX`,
`SEMANTIC_INDEX_BATCH_SIZE`, los límites `SEMANTIC_SEARCH_TOP_K_*` y
`SEMANTIC_SNIPPET_MAX_LENGTH`. Las rutas se limitan a `storage/vector/`, que
permanece ignorado. El cliente usa persistencia local y telemetría anonimizada
deshabilitada.

La validación futura debe ejecutarse con un único worker durante la
reconstrucción. La secuencia manual, después de respaldar los datos, es:

```bat
curl -X POST http://localhost:8000/api/models/embeddings/load
curl http://localhost:8000/api/search/semantic/status
curl -X POST http://localhost:8000/api/search/semantic/rebuild
python scripts\validate_semantic_index.py --status
python scripts\validate_semantic_index.py --validate-active
curl -X POST http://localhost:8000/api/models/embeddings/unload
```

Los comandos de validación no reconstruyen por sí solos. La búsqueda se prueba
mediante `POST /api/search/semantic` con una consulta sintética o autorizada.
No use múltiples workers durante el rebuild: la exclusión concurrente actual
protege un único proceso y no implementa un lock multiproceso.
### Cierre de la Fase 6

La validación integral real fue aprobada: ChromaDB funcionó offline con
telemetría anonimizada deshabilitada, el modelo se cargó en CPU con dimensión
384, se reconstruyeron 44 chunks activos y la persistencia tras reinicio fue
confirmada sin una reconstrucción posterior. El modelo terminó `unloaded` y
SQLite mantuvo sin cambios sus conteos documentales.
## Registro de validación de la Fase 7

La validación real confirmó FTS5 disponible, índice semántico `ready`, ChromaDB y
Sentence Transformers instalados, modelo de embeddings local y un único worker
del backend. Debe cargarse embeddings antes de invocar
`POST /api/search/hybrid` y descargarse al terminar. El validador preparado no
reconstruye índices ni modifica SQLite.
## Cierre de la Fase 7

La validación integral real fue aprobada con 206 pruebas, Ruff sin errores y mypy sin errores en 72 archivos. Se confirmaron la búsqueda híbrida, RRF, filtros, persistencia de FTS5 y ChromaDB tras reinicio y el estado final `unloaded`, sin cambios en SQLite.
## Validación final de la Fase 8

La validación real requiere FTS5 disponible, índice ChromaDB `ready`, modelos
de embeddings y Qwen instalados localmente, operación offline y un solo worker
de Uvicorn. Los modelos iniciaron `unloaded`, se cargaron explícitamente y se
descargaron al finalizar. La validación integral real confirmó Chat RAG HTTP
200, persistencia de FTS5 y ChromaDB tras reinicio, y ausencia de cambios en
SQLite. Se obtuvieron 281 pruebas aprobadas, Ruff sin errores y mypy sin
errores en 76 archivos; el validador terminó con código 0.

El presupuesto validado fue context_size 4096, max_new_tokens 512,
safety_margin 128, context_tokens 1728 y prompt_tokens dentro de 3456.
No se incluyen citas finales, reranking ni historial persistente; el próximo
paso autorizado es la Fase 9 de citas y trazabilidad.

## Cierre de validación de la Fase 9

La validación integral real requirió FTS5 disponible, ChromaDB en estado
`ready`, modelos locales instalados y inicialmente `unloaded`, operación
offline y un solo worker de Uvicorn. No debe ejecutar migraciones ni rebuilds.

El script preparado es:

```bat
python scripts\validate_phase9_end_to_end.py
```

El validador comprobará Chat RAG `answered`, markers, correspondencia exacta
con `citations`, metadata vigente desde SQLite, páginas, chunk, cobertura por
elemento sustantivo, `insufficient_context`, privacidad y persistencia tras
reinicio. También comparará los conteos SQLite y liberará ambos modelos y los
puertos al finalizar.

Los informes locales se escribirán atómicamente bajo
`local_validation_reports/` y permanecerán ignorados. No almacenarán pregunta,
respuesta, marker concreto, identificadores, nombres documentales, páginas,
prompt, contexto, texto, vectores ni rutas. El validador está preparado, pero
no se ejecuta durante la implementación de la Fase 9. La validación integral
fue aprobada con código 0 y dio paso a la Fase 10 — Matriz HPN, actualmente
implementada y completada. La instrumentación del centinela de disposición es
diagnóstica y no bloqueante.

## Migración y validación de la Fase 10

La revisión `20260725_04` crea exclusivamente las tablas de Matriz HPN. Su
aplicación sobre la base local requiere respaldo y autorización explícita:

```bat
cd backend
python -m alembic upgrade head
python -m alembic current
```

Durante la implementación no se ejecutó esa migración sobre la base real. El
validador futuro se ejecuta desde la raíz:

```bat
python scripts\validate_phase10_end_to_end.py
```

El validador usa una copia temporal y aislada de SQLite, aplica la migración
solo a esa copia, valida CRUD, fuentes, fingerprint, estados, relaciones,
revisión, borrado lógico y persistencia tras reinicio, y comprueba que la base
original conserva sus conteos. No carga Qwen o embeddings ni reconstruye FTS5
o ChromaDB.
## Dependencias de red jurídica — Fase 11A

NetworkX se utiliza bajo demanda para construir una proyección estructural HPN
en memoria. La aplicación no debe importar ni requerir la dependencia hasta
invocar el servicio. PyVis, HTML y exportación no forman parte de este bloque.

La proyección no crea archivos ni modifica SQLite, FTS5 o ChromaDB.
