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
No hay OCR ni reranking. La búsqueda híbrida y Chat RAG están completados;
la siguiente fase autorizada corresponde a citas y trazabilidad.

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
ChromaDB y búsqueda vectorial, validado localmente y offline como índice derivado persistente y reconstruible.

Qwen3-1.7B GGUF y `multilingual-e5-small` conservan sus ciclos de vida
explícitos e independientes. La búsqueda híbrida RRF está implementada y en
validación; el reranking, RAG y la inferencia jurídica basada en recuperación
siguen pendientes.
## Cierre de Fase 6

La validación real confirmó ChromaDB local y offline, telemetría anonimizada
deshabilitada, dimensión dinámica 384, 44 chunks activos, distancia cosine,
fingerprint SHA-256 y activación atómica. SQLite sigue siendo la fuente de
verdad; ChromaDB es un índice derivado reconstruible con metadatos mínimos, y
los candidatos y snippets se validan u obtienen desde SQLite. La persistencia
tras reinicio funcionó sin rebuild posterior y el modelo terminó `unloaded`.

La Fase 7 está completada con recuperación híbrida RRF mediante FTS5 y
búsqueda semántica; no incluye reranking, RAG, generación con contexto
recuperado, citas finales ni inferencia jurídica basada en recuperación.
## Recuperación híbrida RRF

```text
consulta
   ├── FTS5 → ranking textual
   └── ChromaDB → ranking semántico
               ↓
        Reciprocal Rank Fusion
               ↓
      validación final SQLite
               ↓
      resultados híbridos trazables
```

SQLite continúa como fuente de verdad; FTS5 y ChromaDB son índices derivados.
Las fuentes se ejecutan secuencialmente porque comparten el contexto de sesión
del request. RRF combina posiciones, no valores BM25 y cosine, y no es un
modelo ni una probabilidad. No existe reranking ni generación en esta fase.
## Cierre de la Fase 7

La Fase 7 está completada. RRF utiliza únicamente ranks iniciados en 1 con los pesos configurados; BM25 y cosine distance no se suman ni se normalizan dentro del score. Los resultados se deduplican, se filtran con contención completa por página y se validan contra SQLite antes de generar snippets. FTS5 y ChromaDB permanecen como índices derivados persistentes; SQLite sigue siendo la fuente de verdad. La Fase 8 está completada con Chat RAG local y contexto controlado.
## Flujo de Chat RAG local

```text
pregunta
    ↓
recuperación híbrida
    ↓
texto vigente desde SQLite
    ↓
selección por presupuesto de tokens
    ↓
prompt con evidencia no confiable
    ↓
Qwen local
    ↓
salida controlada
```

SQLite continúa como fuente de verdad. Los documentos son datos, nunca
instrucciones: se neutralizan delimitadores y tokens de roles antes de crear un
único mensaje de usuario bajo un system prompt fijo. RAG no implica certeza y
toda respuesta requiere revisión profesional. La Fase 8 no incluye citas
finales, historial persistente ni reranking.

El presupuesto cuenta el prompt renderizado con la plantilla del GGUF cuando
llama.cpp la expone. En versiones que no permiten renderizarla, se aplica un
overhead conservador por mensaje además de reservar salida y margen de
seguridad. La truncación del primer chunk utiliza tokens y detokenización del
mismo GGUF; nunca usa el tokenizer de embeddings ni aproximaciones por
caracteres en producción. Si un chunk posterior no cabe, se descarta y se
continúa en el orden híbrido. Solo el primer candidato puede truncarse cuando
ningún chunk completo cabe.

## Cierre de la Fase 8

La validación integral real confirmó Chat RAG stateless mediante `POST
/api/chat/rag`, una recuperación híbrida única por petición, contexto
determinista y texto vigente revalidado desde SQLite. Se comprobaron la
plantilla GGUF, `/no_think`, la neutralización de evidencia no confiable y el
presupuesto con context_size 4096, max_new_tokens 512, safety_margin 128 y
context_tokens 1728; el prompt quedó dentro de 3456 tokens.

Se validaron `answered` e `insufficient_context`, la persistencia de FTS5 y
ChromaDB tras reinicio sin rebuild, los conteos SQLite 1 / 28 / 44 / 44, el
estado final `unloaded`, la liberación del puerto y la ausencia de procesos
propios pendientes. El validador terminó con código 0, con 281 pruebas, Ruff
limpio y mypy sin errores en 76 archivos. La Fase 9 está completada; la Matriz
HPN de la Fase 10 está implementada y completada. Permanecen pendientes el
reranking, el historial persistente y la red jurídica de la Fase 11.

## Citas y trazabilidad estructural — Fase 9 completada

```text
chunks seleccionados
       ↓
registro interno [F1]..[Fn]
       ↓
prompt con evidencia marcada
       ↓
Qwen produce únicamente markers
       ↓
parser cerrado y cobertura por elemento
       ↓
revalidación en una sesión SQLite nueva
       ↓
answer + citations estructuradas
```

El registro de fuentes se construye en el servidor, conserva el orden final
del contexto y existe solo durante la petición. Los markers forman parte del
presupuesto de tokens. Los markers que aparezcan dentro de documentos o de la
pregunta se neutralizan sin alterar las referencias jurídicas ordinarias.
Tras seleccionar definitivamente los chunks, el prompt enumera únicamente los
markers del registro interno, añade un ejemplo estructural breve y coloca un
recordatorio obligatorio después del último bloque de evidencia. Todo este
overhead se cuenta con la plantilla GGUF antes de generar, lo que puede reducir
determinísticamente la evidencia seleccionada sin reducir el margen de seguridad.

Qwen no produce metadata pública: documento, nombre de presentación, tipo,
chunk y páginas proceden de SQLite después de una revalidación posterior a la
generación. La sesión de recuperación se cierra antes de invocar el modelo y
la comprobación final usa una operación nueva. Si una fuente cambia, la
respuesta no se entrega.

La política de obsolescencia es estricta: cambios en documento, tipo, índice
de chunk, páginas, texto u `original_filename`, así como cualquier eliminación,
producen `RAG_CITATION_SOURCE_STALE`. No se sustituye una fuente ni se devuelve
una respuesta parcial. El nombre público usa `original_filename`, reducido a
basename, con controles y NUL eliminados, markers neutralizados, HTML escapado
y longitud limitada; `stored_filename` nunca se utiliza.

SQLite continúa como fuente de verdad y las citas no se persisten. La
trazabilidad estructural demuestra que un marker corresponde a una fuente
incluida en el contexto, pero no evalúa automáticamente entailment, veracidad
jurídica ni suficiencia semántica. No existe reranking, historial persistente
ni una segunda generación para reparar citas.
Una salida sin markers sigue siendo inválida: no existe reparación automática,
inyección posterior de citas ni reintento de generación.

## Matriz HPN manual — Fase 10 completada

```text
matriz
  ├── hechos
  ├── pruebas
  │     └── fuentes documentales
  ├── normas
  │     └── fuentes documentales
  └── relaciones dirigidas
```

SQLite sigue siendo la fuente de verdad. Las snapshots HPN guardan únicamente
metadata mínima y un fingerprint SHA-256 para detectar cambios; no reemplazan
documentos o chunks y no almacenan su texto. La resolución vigente clasifica
las fuentes como `valid`, `stale` o `unavailable` sin modificarlas.

Las claves foráneas y triggers propios de la migración HPN impiden que una
snapshot nueva asocie un chunk con un documento distinto de su propietario.

HPN es estrictamente manual: los nodos y relaciones son afirmaciones
revisables del profesional, no conclusiones del sistema. La validación comprueba
estructura, estados y disponibilidad de fuentes, pero no corrección jurídica,
verdad, suficiencia probatoria o probabilidad. El dominio NetworkX de solo
lectura está implementado en 11A; PyVis, la API y la red visual permanecen para
los bloques posteriores de la Fase 11.

`archived` representa una matriz activa de solo lectura, incluida en listados;
el borrado lógico usa `deleted_at` y es independiente. Los cambios de título o
descripción y toda modificación estructural de una matriz `reviewed` la
devuelven a `in_review` dentro de la misma transacción. Un nodo `reviewed` no
cambia automáticamente si su fuente queda obsoleta: el estado de fuente y
`valid_for_review=false` exponen el problema para revisión humana.
## Red jurídica — Fase 11A

```text
SQLite / HPN vigente
        ↓ lectura agrupada
HpnService.detail()
        ↓ DTOs seguros
NetworkX MultiDiGraph temporal
        ↓
proyección estructural determinista
```

La proyección se construye bajo demanda, no se persiste y no modifica la
matriz, sus fuentes ni SQLite. Antes de delegar el cálculo al hilo, el detalle
HPN se reduce a DTOs inmutables que excluyen `statement`, `rationale` y toda
referencia documental; el hilo no recibe ORM, sesiones, engines ni conexiones.
Incluye solo nodos HPN y relaciones activas; las fuentes se resumen por estado.
`structural_warning_count` cuenta exclusivamente grafo vacío, componentes
desconectados y ciclos dirigidos; no mezcla avisos de revisión o fuentes. El
total de componentes nunca se trunca por el límite reservado para metadata
detallada futura. PyVis, API y frontend quedan fuera de 11A.
