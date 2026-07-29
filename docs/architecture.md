# Arquitectura

## Visión general

El sistema es local. FastAPI expone servicios documentales, recuperación, Chat RAG, Matrices HPN y Red jurídica. React/Vite consume esos contratos mediante un cliente HTTP compartido. SQLite es la fuente de verdad; FTS5 y ChromaDB son índices derivados y reconstruibles.

## Backend y persistencia

- `documents`, `document_pages` y `document_chunks` almacenan metadatos, páginas y fragmentos trazables.
- `documents` distingue capa de conocimiento, procedencia, revisión editorial,
  vigencia jurídica y estado de indexación, y permite enlazar una versión con
  el documento que sustituye. Estos ejes no se mezclan con el estado técnico
  de extracción.
- El servicio documental valida PDF, escribe temporalmente, evita traversal y registra metadatos de forma controlada.
- PyMuPDF reconstruye texto por palabras y líneas; el limpiador y el chunker conservan orden y rangos de página.
- Alembic mantiene el esquema explícitamente. FastAPI no crea tablas ni ejecuta migraciones al iniciar.

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
| Procesamiento, corpus, chat y fuentes frontend | Pendiente |
| Matrices HPN frontend | Implementado |
| Red jurídica frontend | Implementada; validación integrada pendiente |
| Fuentes web y propuestas HPN asistidas | Futuro |

## Seguridad y logging

Los módulos usan `app.core.Log` y registran solo metadatos operativos. No se registran prompts, respuestas ni texto documental. La política de privacidad está en [security-privacy.md](security-privacy.md) y el detalle técnico de logging en [logging.md](logging.md).
