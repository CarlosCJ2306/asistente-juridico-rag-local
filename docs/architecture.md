# Arquitectura

## Visión general

El sistema es local. FastAPI expone servicios documentales, recuperación, Chat RAG, Matrices HPN y Red jurídica. React/Vite consume esos contratos mediante un cliente HTTP compartido. SQLite es la fuente de verdad; FTS5 y ChromaDB son índices derivados y reconstruibles.

Desde 12D la arquitectura objetivo distingue tres límites:

1. **Asistente jurídico general:** Chat RAG y conversaciones no asociadas a un expediente.
2. **Workspace de inteligencia de casos:** núcleo persistente `Case`
   implementado; expediente documental, artefactos versionados, HPN, Red,
   métricas, escenarios y frontend conectado pendientes.
3. **Plataforma local compartida:** biblioteca, procesamiento, recuperación,
   modelos, persistencia, seguridad y observabilidad.

El segundo límite está **parcialmente implementado** desde 12E-1. Los módulos
existentes se clasifican en [modules.md](modules.md).

## Backend y persistencia

- `documents`, `document_pages` y `document_chunks` almacenan metadatos, páginas y fragmentos trazables.
- `documents` distingue capa de conocimiento, procedencia, revisión editorial,
  vigencia jurídica y estado de indexación, y permite enlazar una versión con
  el documento que sustituye. Estos ejes no se mezclan con el estado técnico
  de extracción.
- El servicio documental valida PDF, escribe temporalmente, evita traversal y registra metadatos de forma controlada.
- PyMuPDF reconstruye texto por palabras y líneas; el limpiador y el chunker conservan orden y rangos de página.
- Alembic mantiene el esquema explícitamente. FastAPI no crea tablas ni ejecuta migraciones al iniciar.
- La revisión `20260728_09` añade `cases` y `case_audit_events`. `Case` usa un
  identificador público UUID, estados cerrados, retención temporal o local,
  locking optimista y auditoría transaccional; no contiene documentos ni
  referencias HPN/Red.
- La revisión `20260729_10` añade `case_documents`. Cada fila referencia un
  `Document` existente, guarda únicamente snapshot mínima y puede retirarse
  lógicamente. Un índice único parcial impide dos asociaciones activas para la
  misma pareja sin sobrescribir asociaciones retiradas.

`DocumentGovernanceService` centraliza las matrices de transición de revisión,
vigencia e indexación, las reglas de capa y versionado, y la elegibilidad RAG
calculada. Cada flujo de recuperación obtiene candidatos desde el índice,
carga chunks y gobernanza vigente desde SQLite y aplica esa política antes de
exponer resultados. La evaluación usa campos ya cargados, no persiste la
elegibilidad y evita consultas N+1.

## Corpus administrado

El manifiesto versionable declara metadatos y nombres relativos, mientras que
los PDF permanecen en un staging local ignorado. La CLI valida sin escribir y,
solo ante una orden de importación, reutiliza `DocumentService`, el
almacenamiento oficial y `DocumentGovernanceService`. El registro
`managed_corpus_entries` vincula cada `source_key` con un documento sin
duplicar metadatos. Importar no aprueba, extrae ni indexa; las versiones nuevas
se conservan por separado y pueden enlazar el documento sustituido.

## Recuperación e IA local

El manifiesto versionado bajo `models/` funciona como catálogo permitido. La
selección activa se conserva en configuración operacional local mediante
reemplazo atómico: activo indica qué modelo usará la próxima carga, mientras
que cargado indica exclusivamente la presencia actual en memoria. Ninguna
selección acepta rutas o repositorios suministrados por la API.

- FTS5 indexa texto de chunks y se sincroniza con triggers SQLite.
- `multilingual-e5-small` genera embeddings locales bajo demanda.
- ChromaDB persiste solo embeddings y metadatos mínimos, incluida la capa; no reemplaza los chunks SQLite.

## Automatización documental 12B-4

`storage/inbox/private_library` y `storage/inbox/temporary` son las únicas
bandejas observadas. El ciclo de vida de FastAPI inicia un escáner periódico
de biblioteca estándar que espera estabilidad, valida un sidecar opcional o
requerido según la capa y crea un trabajo SQLite. La carga HTTP crea el mismo
tipo de trabajo sin aceptar rutas.

Los trabajos reutilizan `DocumentService` y `DocumentExtractionService`. Los
documentos listos se agrupan durante una ventana de debounce y una sola
reconstrucción copy-on-write actualiza ChromaDB para todo el lote. Esta
estrategia se eligió porque el adaptador vigente no ofrece un upsert por
documento con rollback atómico; el índice activo anterior permanece intacto
hasta validar y activar la colección temporal.

La política de embeddings puede ser `manual` u `on_demand`. Bajo demanda, un
coordinador impide cargas concurrentes, protege búsquedas e indexaciones
activas y descarga el modelo tras un periodo configurable sin actividad.
- El fingerprint semántico incluye los cambios de gobernanza que alteran la
  fuente y la versión del esquema de metadata. Una incompatibilidad exige
  rebuild explícito mediante colección temporal y activación atómica.
- La búsqueda híbrida combina únicamente candidatos elegibles de FTS5 y
  semántica mediante RRF, con filtros de capa y revalidación contra SQLite.
- La pantalla de búsqueda documental consume ese contrato sin cargar modelos ni
  reconstruir índices; muestra sólo fragmentos, procedencia resumida y rangos
  de página que el backend ya revalidó.
- Qwen3 GGUF se ejecuta mediante `llama-cpp-python`, con plantilla
  conversacional del GGUF. Su política puede ser `manual` u `on_demand`; esta
  última es la predeterminada y nunca carga pesos durante imports o startup.

## RAG y citas

`RagChatService` valida la solicitud, recupera una vez, obtiene texto vigente
desde SQLite y vuelve a comprobar elegibilidad y filtros antes de seleccionar
contexto. Solo si queda evidencia suficiente solicita al coordinador que cargue
Qwen; por ello `insufficient_context` no inicializa el LLM. La evidencia se
delimita como contenido no confiable y no puede modificar el mensaje de sistema.

El coordinador del LLM serializa la carga, reutiliza la instancia cargada,
protege generaciones activas, aplica timeouts y programa descarga por
inactividad. `RagCitationService` valida markers, cobertura y nuevamente la
fuente gobernada antes de construir citas con nombre visible, capa, documento,
chunk y páginas. El endpoint individual permanece stateless y exige revisión
profesional.

## Conversaciones persistentes

La revisión `20260728_08` añade conversaciones, mensajes, snapshots de citas,
claims y relaciones claim-cita. Una sesión invitada se identifica mediante una
cookie aleatoria HttpOnly; SQLite conserva solo SHA-256 del token. El hilo se
limita al hash propietario y expira siete días después de la última actividad.
Una tarea del lifecycle ejecuta limpieza al iniciar y periódicamente.

En cada turno, el servicio carga solo una ventana limitada de mensajes. Ese
contexto se rotula como no probatorio y sirve para interpretar la pregunta; la
evidencia jurídica procede exclusivamente de una recuperación híbrida nueva y
de chunks revalidados en SQLite. Las citas guardan metadata pública, rango de
páginas y un extracto literal limitado. No se persisten prompts ensamblados,
chain-of-thought, embeddings, rutas ni índices derivados.

El modelo admite `owner_type=account` y `user_id`, pero no existe autenticación
real. No se crea principal ficticio ni endpoint de transferencia.

## Matrices HPN y Red jurídica

Las matrices almacenan nodos fact, evidence y norm, sus fuentes y relaciones dirigidas revisables. NetworkX construye una proyección de solo lectura; la API JSON ofrece DTOs sanitizados y PyVis exporta una visualización local restringida. Las métricas y relaciones son estructurales, no conclusiones jurídicas.

HPN y Red carecen actualmente de `case_id`; son legado operativo respecto del
workspace objetivo. Su migración será aditiva y conservará matrices globales
sin asignación. Consulte [hpn-and-legal-network.md](hpn-and-legal-network.md).

## Núcleo Case y orquestación futura

`app.cases` contiene el dominio independiente del ORM, repositorio asíncrono y
servicio autoritativo. `/api/cases` expone CRUD limitado y acciones explícitas
de estado. Los casos `temporary` reutilizan la identidad invitada y renuevan
siete días de retención con actividad autorizada; `local_persistent` pertenece
a la instalación. `account` no se acepta por HTTP. El borrado es lógico y no
hay purga física en 12E-1.

`CaseDocumentService` permite asociar únicamente documentos privados o
temporales activos. Resuelve cada página documental en un lote, aplica la
gobernanza pública vigente y compara la snapshot en memoria. Las mutaciones
incrementan `Case.version` y `CaseDocument.version` y agregan el evento de
auditoría dentro de la misma transacción. No inicia extracción, indexación,
recuperación ni modelos.

El [CasePipelineHarness](case-pipeline-harness.md) planificado coordinará etapas
tipadas, checkpoints, revisión humana, reintentos y recuperación sin duplicar
servicios. El [CaseEvaluationHarness](evaluation-harness.md) usará casos
sintéticos y golden fixtures aislados. Ninguno está implementado en 12E-1.

## Contratos de transición 12D-1

Los contratos de transición de `app.cases` definen DTO inmutables y ports de documentos,
extracción, recuperación acotada, HPN legacy y Red legacy. Adaptadores pequeños
delegan en fachadas públicas existentes y mapean únicamente referencias y
resúmenes seguros. 12E-1 añadió por separado ORM, repositorio, servicio y router
del agregado `Case`, sin activar esos adaptadores ni asociar documentos.

La dirección comprobada es `Casos planificados -> fachadas compartidas` y
`Asistente general -> plataforma compartida`. La plataforma, el Asistente, HPN
y Red no importan Casos. La importación de `app.cases` no abre SQLite o Chroma,
ni carga embeddings o Qwen.

## Navegación y shell de Casos 12D-2

`/cases` es una ruta frontend estática sin acceso a backend, SQLite, índices ni
persistencia. Su estado vacío no representa expedientes ni crea datos. La
feature `features/cases` expone un `CaseWorkspaceShell` puramente
presentacional para una futura entidad Case: recibe títulos, etiquetas visibles,
secciones, advertencias y contenido desde props, sin conocer objetos de dominio.
Las rutas HPN y Red jurídica siguen siendo globales y no se redirigen.

## Compatibilidad legacy 12D-3

`app.cases` conserva un manifiesto estático versionado, clasificación interna,
referencias inmutables y políticas puras para HPN y Red globales. Estas piezas
no importan ORM ni servicios, no consultan SQLite y no aparecen en OpenAPI.
La asociación, deprecación y retiro permanecen desactivados: no existe
`case_id` en HPN/Red, redirect ni asociación documental durante esta fase.

## Frontend y proxy

React, TypeScript y Vite implementan App Shell, Design System, cliente HTTP
compartido, Inicio, Biblioteca documental con carga PDF explícita, Matrices HPN
y Red jurídica. En desarrollo, `frontend/.env` define la base local y Vite
redirige `/api` al backend. El iframe PyVis usa ruta relativa y sandbox
restringido; React no interpreta HTML HPN.

El mapa canónico de rutas frontend y endpoints asociados está en
[routes.md](routes.md).

## Estado de conexión

| Área | Estado |
| --- | --- |
| Flujo documental y Chat RAG backend | Implementado y conectado |
| Biblioteca y carga PDF frontend | Implementadas; validación manual de carga pendiente |
| Procesamiento, corpus, chat y fuentes frontend | Implementados con validaciones manuales pendientes según el plan |
| Matrices HPN frontend | Implementado |
| Red jurídica frontend | Implementada; validación integrada pendiente |
| Dominio y workspace de casos | Núcleo, pertenencia documental y API implementados; frontend pendiente |
| Fuentes web | Futuro de baja prioridad |

## Seguridad y logging

Los módulos usan `app.core.Log` y registran solo metadatos operativos. No se registran prompts, respuestas ni texto documental. La política de privacidad está en [security-privacy.md](security-privacy.md) y el detalle técnico de logging en [logging.md](logging.md).
