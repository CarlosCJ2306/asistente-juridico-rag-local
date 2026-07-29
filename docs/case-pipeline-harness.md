# CasePipelineHarness

## Estado y decisión

**Diseño planificado y no ejecutable.** 12D-1 preparó únicamente ports y
adaptadores de transición; no implementó el orquestador, stages, runs,
checkpoints, locks o lifecycle. Se recomienda un orquestador propio, pequeño y
determinista, compatible con FastAPI, SQLAlchemy asíncrono y SQLite.

12E-1 y 12E-2 añaden el núcleo persistente `Case` y asociaciones documentales;
no activan el harness, pipeline, locks de etapas, ejecuciones, extracción
estructurada ni recuperación multi-documento del caso.

## Etapas

`ingest -> extract -> entities -> facts -> evidence -> norms -> hpn -> hpn_audit -> network -> metrics -> scenarios -> dashboard`

Cada etapa declara entradas tipadas, salidas tipadas, versión de esquema, dependencias, timeout, política de reintento y si exige revisión humana. Una etapa no puede leer estado implícito de otra.

## Modelo de ejecución

- `PipelineDefinition`: grafo acíclico y versionado de etapas.
- `PipelineRun`: ejecución de un caso con estado global.
- `StageRun`: intento individual, tiempos, estado y códigos seguros.
- `Checkpoint`: referencia al artefacto persistido y fingerprint; nunca contiene el payload en logs.
- `HumanReviewGate`: bloquea la siguiente etapa hasta una decisión explícita.
- `AuditEvent`: transición estructurada y sanitizada.

Estados sugeridos: `pending`, `running`, `waiting_review`, `succeeded`, `failed`, `cancel_requested`, `cancelled`, `stale` y `superseded`.

Transiciones permitidas:

| Desde | Hacia | Condición |
| --- | --- | --- |
| `pending` | `running` | Dependencias satisfechas y lock adquirido. |
| `running` | `succeeded` | Salida validada y checkpoint confirmado. |
| `running` | `waiting_review` | La etapa exige promoción humana. |
| `running` | `failed` | Error clasificado o timeout. |
| `running` | `cancel_requested` | Solicitud explícita de cancelación. |
| `cancel_requested` | `cancelled` | Adaptador detenido y recursos cerrados. |
| `failed` | `pending` | Reintento autorizado y dentro del límite. |
| `succeeded` | `stale` | Cambió una entrada, política o fuente. |
| `succeeded` | `superseded` | Una nueva versión fue aceptada. |

No se salta de `waiting_review` a aceptado por temporizador, retry o salida de
un modelo; requiere una decisión humana auditable.

## Garantías

### Idempotencia

La clave combina caso, etapa, versión, fingerprint de entradas y parámetros públicos normalizados. Repetir una etapa exitosa devuelve su checkpoint; `force` crea una nueva versión explícita, no sobrescribe.

### Reintentos y timeout

Solo errores clasificados como transitorios son reintentables, con límite y backoff. Errores de validación, gobernanza o revisión requieren intervención. Un timeout marca el intento; no declara que un proceso externo terminó si no pudo confirmarse.

### Cancelación

Cooperativa entre lotes. `cancel_requested` no equivale a `cancelled`. Los adaptadores verifican la señal, cierran recursos y persisten un checkpoint consistente.

### Locks y concurrencia

Un lock persistente por `case_id + stage` evita ejecuciones duplicadas. La adquisición usa una transacción corta; no se mantiene una sesión SQLite durante inferencia o render bloqueante. Locks vencidos se recuperan mediante lease y auditoría, no por borrado silencioso.

### Reinicio

Al iniciar, un reconciliador marca ejecuciones sin lease como recuperables, verifica checkpoints y reanuda desde la última etapa confirmada. Nunca repite automáticamente una decisión humana ni promueve artefactos draft.

## Ejecución individual y completa

- Individual: ejecuta una etapa cuando sus dependencias y revisiones están satisfechas.
- Completa: avanza en orden hasta terminar, fallar, cancelarse o llegar a revisión humana.
- Reanudación: continúa el mismo `PipelineRun` desde un checkpoint válido.
- Dry-run futuro: valida dependencias y alcance sin ejecutar productores.

## Adaptadores

El harness coordina interfaces; no duplica servicios. Ingesta/extracción reutilizan el pipeline documental, evidencia usa recuperación y SQLite, HPN usa el dominio revisable, Red usa NetworkX y dashboard consume artefactos aceptados. Operaciones CPU/GPU o librerías síncronas se ejecutan fuera del event loop.

## Privacidad y observabilidad

Se permiten `run_id` abreviado, etapa, estado, duración, conteos, intento y código de error. Se prohíben títulos, documentos, texto, prompts, respuestas, UUID completos, vectores, rutas, SQL y checkpoints serializados. Los errores públicos son códigos estables; el detalle técnico queda sanitizado.

## Límites iniciales

- una ejecución activa por caso;
- timeout configurable por etapa;
- máximo de reintentos acotado;
- máximo de artefactos y tamaño por etapa;
- presupuesto de memoria para lotes;
- retención configurable de runs y auditoría;
- un worker recomendado hasta implementar coordinación multiproceso comprobada.

## Criterio para no usar una librería externa

El flujo es local, conocido, con revisiones humanas y pocos workers. SQLite, contratos tipados y adaptadores existentes cubren la necesidad con menor superficie de ataque. Una librería se reconsiderará solo si demuestra recuperación, cancelación y persistencia superiores sin introducir servicios remotos ni estado opaco.
