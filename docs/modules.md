# Inventario y decisión de módulos

## Convención de estado

- **Existente:** implementado y conectado.
- **Parcial:** útil, pero su contrato no cubre todavía el producto orientado a casos.
- **Legado operativo:** se conserva durante la transición; no es el destino arquitectónico.
- **Preparado:** hay estructuras deliberadamente inactivas para una capacidad futura.
- **Planificado:** diseño aprobado documentalmente, aún sin implementación.
- **Futuro:** fuera de la hoja de ruta inmediata.

## Matriz de decisión

| Área actual | Estado | Decisión | Motivo y destino |
| --- | --- | --- | --- |
| FastAPI, configuración, errores y `app.core.Log` | Existente | Preservar | Plataforma transversal local; debe seguir sin contenido jurídico en logs. |
| SQLite y sesiones SQLAlchemy asíncronas | Existente | Preservar | Fuente de verdad. `Case` usa la misma unidad de persistencia y una migración aditiva. |
| Núcleo `Case` y `/api/cases` | Existente | Extender por bloques | 12E-1 implementa propiedad, retención, estados, locking, auditoría y borrado lógico; no incluye documentos ni workspace. |
| `CaseDocument` y API del expediente | Existente | Extender por bloques | 12E-2 referencia documentos privados/temporales, compara snapshots y no duplica archivos, contenido ni índices. |
| Documentos, páginas y chunks | Existente | Preservar y extender | La biblioteca general no debe duplicarse. Un caso referenciará documentos mediante una asociación gobernada. |
| Gobernanza documental y corpus administrado | Existente | Preservar | Elegibilidad, procedencia, vigencia y revisión siguen siendo autoritativas. La pertenencia a un caso no las omite. |
| Extracción PyMuPDF y chunking | Existente | Reutilizar | Será una etapa del pipeline de casos, sin crear una segunda implementación. |
| Trabajos de procesamiento documental | Existente | Refactorizar hacia adaptador | Su cola recuperable sirve para ingesta/extracción, pero no sustituye el estado integral de un pipeline de caso. |
| FTS5 | Existente | Preservar como índice derivado | Búsqueda textual compartida; deberá aceptar alcance de caso sin clonar índices. |
| ChromaDB y embeddings | Existente | Preservar como índice derivado | Búsqueda semántica compartida; los candidatos se revalidan contra SQLite y la membresía del caso. |
| Recuperación híbrida RRF | Existente | Reutilizar con alcance | Servicio transversal; necesita un filtro de caso explícito antes de usarse en un workspace. |
| Chat RAG stateless y conversaciones invitadas | Existente | Separar y migrar | El asistente general permanece. Las conversaciones de caso necesitarán `case_id`, retención y permisos propios; no se reinterpretan las actuales. |
| Citas, claims y snapshots conversacionales | Existente | Reutilizar y versionar | Son una base de trazabilidad, pero los artefactos de caso necesitan revisión y versión explícitas. |
| Matrices HPN | Parcial / legado operativo | Migrar de forma aditiva | Son globales y manuales. Deben vincularse a un caso sin alterar las matrices históricas ni simular que ya lo están. |
| Red jurídica NetworkX | Parcial / legado operativo | Reutilizar como proyección | El servicio determinista es válido; la entrada futura será una versión HPN de caso. |
| Exportación PyVis | Existente | Preservar con límites | Visualización derivada, local y sanitizada; no será fuente de verdad ni archivo del expediente. |
| API HPN y Red global | Legado operativo | Mantener, deprecar y redirigir después | Continúa operativa hasta existir equivalencia funcional dentro de Casos. |
| Frontend Chat | Existente | Preservar como Asistente jurídico | Flujo general independiente del análisis de un expediente. |
| Frontend Documentos y Búsqueda | Existente | Reagrupar | Se presentará como Biblioteca jurídica y Procesamiento sin cambiar inicialmente sus contratos. |
| Frontend Matrices HPN y Red | Legado operativo | Migrar al workspace | Destino: pestañas Matriz HPN y Red de `/cases/:caseId`; no se eliminan rutas actuales antes del backfill. |
| Centro de modelos | Existente | Preservar | Administración local transversal; no pertenece a un caso. |
| Scripts de descarga y verificación de modelos | Existente | Preservar | Operaciones explícitas y offline; no forman parte del pipeline de caso. |
| Validadores integrales por fase | Existente | Reemplazar progresivamente | Mantener como historial reproducible; el `CaseEvaluationHarness` asumirá regresiones nuevas de casos sintéticos. |
| Scripts diagnósticos puntuales | Legado operativo | Archivar documentalmente | No deben convertirse en runtime ni en una segunda plataforma de observabilidad. |
| Autenticación por cuenta | Preparado | Mantener inactivo | Los esquemas admiten `account`, pero no existe autenticación real. No se expondrá propiedad ficticia. |
| Importación web | Futuro | Posponer | Baja prioridad hasta cerrar casos, evaluación y trazabilidad. |

## Inventario por capa

### Persistencia y migraciones

- **Conservar:** `Document`, `DocumentPage`, `DocumentChunk`,
  `DocumentProcessingJob`, `ManagedCorpusEntry`, conversaciones, mensajes,
  citas y claims; revisiones Alembic `20260723_01` a `20260729_10`.
- **Migrar:** `HpnMatrix`, `HpnNode`, `HpnNodeSource` y `HpnRelation` mediante
  asociación/versionado de caso futuro; la revisión histórica
  `20260725_04` no se modifica.
- **Creado en 12E-1/12E-2:** `Case`, `CaseDocument` y auditoría estructurada de
  sus mutaciones.
- **Crear en fases futuras:** artefactos, ejecuciones, etapas y checkpoints.
- **No persistir:** grafos NetworkX, HTML PyVis, resultados de búsqueda o
  payloads completos del pipeline como una segunda fuente de verdad.

### Repositorios

- **Conservar:** repositorios de documentos, páginas, chunks, corpus,
  recuperación textual/semántica, procesamiento y conversaciones.
- **Refactorizar mediante interfaces:** `HpnRepository` y las consultas de
  fuentes para aceptar una versión de caso sin hacer que HPN importe `Case`.
- **Creado en 12E-1:** repositorio asíncrono de casos con paginación estable,
  ownership, optimistic locking y auditoría en la misma transacción.
- **Creado en 12E-2:** repositorio de asociaciones con resolución documental
  batch y sin N+1.
- **Crear después:** repositorios de membresía y runs, con cargas por lote.

### Servicios

- **Reutilizar:** documental, extracción, gobernanza, embeddings, índice,
  búsquedas textual/semántica/híbrida, RAG/citas, HPN y grafo.
- **Separar:** runtime de modelos y selección siguen en Plataforma; Chat
  general no asumirá contexto de caso.
- **Adaptar:** automatización documental será una etapa invocable; no será el
  orquestador integral.
- **Creado en 12E-1:** servicio autoritativo de casos.
- **Creado en 12E-2:** servicio autoritativo de membresía documental.
- **Crear después:** artefactos, pipeline y evaluación.

### API y schemas

- **Conservar:** salud, documentos/procesamiento, modelos, búsquedas, Chat,
  conversaciones y contratos HPN/Red actuales.
- **Deprecar después:** HPN/Red globales, únicamente cuando las rutas de caso
  tengan paridad y backfill validado.
- **Versionar:** respuestas nuevas de artefactos y runs mediante
  `schema_version`; evitar ampliar silenciosamente schemas existentes con
  semántica de caso.
- **Creado en 12E-1:** namespace tipado `/api/cases`, sin documentos, HPN, Red
  ni pipeline.
- **Creado en 12E-2:** subrutas tipadas `/api/cases/{case_id}/documents`, sin
  upload, procesamiento, búsqueda, HPN o Red.

### Frontend

- **Conservar:** App Shell, Design System, cliente HTTP, providers, Inicio,
  Chat, Documentos/Búsqueda, Modelos y estados compartidos.
- **Reagrupar:** Documentos pasa conceptualmente a Biblioteca jurídica y la
  cola/índices a Procesamiento; inicialmente pueden reutilizar rutas.
- **Migrar:** `features/hpn-matrices` y `features/legal-network` a secciones del
  workspace, manteniendo páginas legacy durante la transición.
- **Crear después:** `features/cases` y secciones del expediente.

### Scripts, pruebas y documentación

- **Conservar:** descarga/verificación explícita de modelos, corpus administrado
  y validación semántica; suites backend/frontend existentes.
- **Retirar gradualmente:** validadores y diagnósticos numerados de fases una
  vez cubiertos por evaluación reproducible y conservada su evidencia.
- **Extender:** pruebas unitarias, repositorio, servicio, API, frontend,
  migración temporal, seguridad, concurrencia y recuperación para cada bloque.
- **Corregido en 12D-0:** documentación que omitía el Chat conversacional ya
  existente o presentaba el siguiente paso como incorporación web.

## Contratos HPN auditados

Los enums actuales son matrices `draft/in_review/reviewed/archived`, nodos
`fact/evidence/norm`, revisión `draft/reviewed/rejected` y cuatro relaciones
dirigidas. Hay borrado lógico, restricciones de rango y una relación activa
única por origen, destino y tipo. `HpnService` centraliza escritura, invalida
la revisión ante cambios y resuelve fuentes contra chunks activos; el grafo
consume una proyección de solo lectura.

Los campos públicos seguros son títulos/estados HPN, statements revisables,
relaciones y referencias documentales saneadas. Fingerprints, IDs internos de
chunks, rutas, nombres almacenados y SQL permanecen internos. Para casos,
statements y rationales son contenido sensible y no pueden llegar a logs.

`sources(node_ids)` y `active_chunks_by_ids(chunk_ids)` ya permiten cargas por
lote. Deben reutilizarse para evitar N+1; resolver cada nodo, fuente o documento
por separado dentro del workspace sería una regresión.

## Inconsistencias y riesgos encontrados

1. HPN, Red y conversaciones son recursos globales: carecen de `case_id` y no pueden atribuirse de forma segura a un expediente.
2. La biblioteca general, los documentos temporales y la evidencia de un caso comparten `documents`, pero no existe una asociación que exprese propósito, retención o inclusión en el expediente.
3. La cola documental cubre operaciones técnicas; no modela dependencias entre extracción, HPN, auditoría, red, métricas y escenarios.
4. El estado de revisión HPN es suficiente para edición manual básica, pero no ofrece versiones de artefactos, checkpoints ni auditoría de una ejecución integral.
5. Las rutas globales `/matrices-hpn` y `/legal-network` mezclan una herramienta técnica con el futuro flujo centrado en casos.
6. Algunos documentos describen el Chat como stateless aunque ya existen conversaciones persistentes; la distinción correcta es endpoint individual stateless frente a conversación temporal persistente.
7. Validadores por fase duplican patrones de procesos, cleanup e informes. Deben converger en un harness reutilizable, sin eliminar todavía evidencia histórica.
8. La API de casos expone `version` para locking optimista; las extensiones
   futuras deben preservar ese contrato sin mutar respuestas anteriores de
   manera incompatible.
9. Una implementación ingenua puede producir N+1 al resolver fuentes HPN, membresía documental y artefactos. Los repositorios de caso deberán cargar lotes y proyecciones completas.
10. Persistir proyecciones NetworkX, HTML o resultados intermedios como verdad crearía duplicación y problemas de invalidación.
11. No se confirmó un ciclo de imports en las capas auditadas; el riesgo aparece
    si Documentos/HPN importan el dominio `Case`. La dependencia debe
    mantenerse desde Casos hacia puertos compartidos, nunca a la inversa.
12. No se encontró una colisión de método+ruta en los routers actuales. La
    duplicación es de experiencia y alcance: Matrices HPN y Red aparecen como
    destinos globales separados de donde deberán vivir dentro de Casos.

## Dependencias que deben permanecer unidireccionales

`api -> services -> repositories -> models/database`

El dominio de casos podrá invocar adaptadores de documentos, recuperación, HPN y Red. Esos módulos compartidos no deberán importar el workspace ni el pipeline de casos. Frontend consume contratos públicos; nunca importa reglas del backend ni reproduce la gobernanza autoritativa.

## Versionado de contratos

- Conservar sin cambios incompatibles los endpoints existentes.
- Extender recursos de caso bajo `/api/cases` sin cambiar contratos existentes;
  las rutas de workspace descritas en 12D siguen planificadas.
- Incluir `schema_version` en artefactos persistidos y reportes del harness.
- Deprecar con cabeceras, documentación y telemetría segura antes de retirar una ruta global.
- No reutilizar un identificador global como si ya fuera un identificador de caso.

## Shell frontend preparatorio 12D-2

`features/cases` es una feature pública aislada con una página vacía y un shell
presentacional tipado. No contiene API, hooks, queries, datos mock, persistencia
ni imports profundos de otras features. 12E-1 y 12E-2 añadieron el modelo, la
pertenencia documental y las APIs solo en backend; esta feature todavía no los
consume.

## Compatibilidad legacy 12D-3

HPN y Red conservan su condición `current_global` y sus rutas operativas. Un
manifiesto y políticas internas describen su migración futura sin asignación
automática, `case_id`, deprecación, redirect ni cambio de APIs. La Red sigue
siendo derivada y reconstruible; SQLite conserva la fuente de verdad.

## Límites implementados en 12D-1

- `app.documents`, `app.retrieval`, `app.ai`, `app.assistant`, `app.legal` y
  `app.graph` son fachadas públicas pequeñas sobre implementaciones existentes.
- `app.cases` conserva contratos, ports y adaptadores de transición inactivos y
  añade el dominio, repositorio y servicio de `Case`; su `__init__` sigue sin
  importar infraestructura ni producir efectos laterales.
- Plataforma y Asistente no importan `app.cases`; los adaptadores de casos
  consumen solo las fachadas públicas de Plataforma y los recursos legacy.
- Las features frontend consumen otra feature únicamente desde su `index.ts`.
  Utilidades genéricas, como la política de cierre de modal, viven fuera de una
  feature jurídica.
- HPN y Red conservan rutas, schemas y comportamiento; los adaptadores solo
  devuelven resúmenes sanitizados y no les atribuyen `case_id`.

La recuperación híbrida existente carece de batch por conjunto de documentos.
El port ya representa un alcance explícito, pero el adaptador 12D-1 admite un
solo documento y devuelve `TRANSITION_RETRIEVAL_SCOPE_UNSUPPORTED` para más de
uno. No hace búsquedas en loop ni filtra tardíamente resultados globales.
