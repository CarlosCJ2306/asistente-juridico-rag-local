# Plan de trabajo — Asistente Jurídico Local

## Propósito

Este es el plan activo y la única hoja de ruta vigente. Ordena la evolución del producto local, trazable y sujeto a revisión profesional. El historial de trabajo ya realizado se conserva en [CAMBIOS.md](CAMBIOS.md).

## Restricciones técnicas vigentes

- SQLite es la fuente de verdad documental; FTS5 y ChromaDB son índices derivados y reconstruibles.
- El procesamiento de contenido jurídico, embeddings y generación ocurre localmente; no se usan servicios externos de inferencia.
- Los modelos no se cargan durante imports o el inicio de FastAPI; embeddings
  y Qwen admiten política manual o bajo demanda, con `on_demand` como valor
  predeterminado del producto.
- No se registran prompts, respuestas, chunks ni documentos completos.
- No se versionan modelos, documentos, bases SQLite, índices, secretos, logs o informes locales de validación.
- Toda salida asistida requiere revisión profesional; no constituye una decisión jurídica.

## Estado resumido: Fases 0 a 11

| Fase | Estado | Resultado vigente |
| --- | --- | --- |
| 0 | Completada | Base FastAPI/React, salud, configuración y observabilidad. |
| 1 | Completada | Qwen local bajo demanda con plantilla conversacional GGUF. |
| 2 | Completada | Persistencia documental y carga segura de PDF en backend. |
| 3 | Completada | Extracción PyMuPDF, páginas y chunks trazables. |
| 4 | Completada | Embeddings locales con `multilingual-e5-small`. |
| 5 | Completada | Recuperación textual SQLite FTS5. |
| 6 | Completada | Índice y búsqueda semántica local con ChromaDB. |
| 7 | Completada | Recuperación híbrida mediante RRF. |
| 8 | Completada | Contexto controlado y Chat RAG local. |
| 9 | Completada | Citas estructuradas revalidadas contra SQLite. |
| 10 | Completada | Matrices HPN manuales, revisables y trazables. |
| 11 | Implementada; validación integrada pendiente | Red jurídica con NetworkX, API, PyVis y frontend de red. |

Las Matrices HPN manuales, la Red jurídica, la biblioteca documental, el
procesamiento, la selección gobernada de corpus y el núcleo backend del Chat
RAG ya están implementados. La interfaz single-turn de Chat existe; la
experiencia frontend de historial multi-turn y evidencia persistente está
implementada; su validación manual integrada corresponde al cierre del bloque.

## Hoja de ruta activa

### 12A-0A — Fundamentos de gobernanza documental — Implementada

- Modelo y migración aditiva para capas de conocimiento, procedencia, revisión,
  vigencia, indexación y versiones documentales.
- Contrato público de documentos saneado, sin rutas, nombres almacenados ni
  hashes.

### 12A-0B — Políticas y ciclo de vida documental — Completada

- Política central implementada para transiciones controladas, elegibilidad
  RAG calculada, aprobación, vigencia, archivo y expiración, sin mezclar
  estados técnicos, editoriales y jurídicos.
- El contrato público informa elegibilidad, motivos técnicos seguros y
  expiración sin persistir un indicador derivado.

### 12A-0C — Integración de gobernanza con recuperación — Completada

- FTS5, búsqueda semántica, recuperación híbrida, contexto RAG y citas
  revalidan en SQLite la elegibilidad calculada y los filtros de capa.
- El índice semántico incorpora gobernanza a su fingerprint, metadatos mínimos
  y ciclo de `IndexStatus`; una proyección anterior requiere reconstrucción
  explícita y nunca se actualiza automáticamente.

### 12A-0D — Validación operativa de recuperación gobernada — Completada

- La reconstrucción explícita, recuperación gobernada, filtros de capa y Chat
  RAG se validaron sobre persistencias locales respaldadas, sin modificar la
  biblioteca ni los índices derivados fuera de su proyección técnica.
- El caso sin evidencia devuelve `insufficient_context` sin requerir Qwen; el
  caso con evidencia exige el modelo y conserva citas revalidadas en SQLite.

### 12A-0E — Importación controlada del corpus administrado — Completada

- Manifiesto JSON versionable, staging local ignorado y CLI explícita para
  validar, importar, consultar estado, revisar y promover fuentes.
- La importación reutiliza el almacenamiento documental oficial y deja cada
  fuente en revisión pendiente, vigencia desconocida y sin indexar.
- Los duplicados no se promueven automáticamente; las versiones posteriores
  son documentos independientes enlazados con su versión anterior.

### 12A-1 — Biblioteca documental frontend — Completada

- Rutas de solo lectura para listado paginado y detalle documental, conectadas a
  los contratos públicos existentes.
- La interfaz presenta procedencia, gobernanza y elegibilidad RAG sin exponer
  rutas, hashes, nombres almacenados, errores internos ni contenido documental.

### 12A-2 — Carga segura de PDF desde frontend — Implementada; validación manual pendiente

- Modal explícito de carga que reutiliza el contrato `POST /api/documents` y el
  cliente HTTP compartido con `FormData`.
- Propósitos públicos limitados a biblioteca privada y consulta temporal con
  expiración futura; el backend conserva la validación autoritativa de archivo,
  gobernanza y tamaño.
- La carga registra el documento sin iniciar extracción, indexación ni cambios
  de elegibilidad desde el frontend.
- La validación manual de carga sigue siendo independiente de los ajustes
  transversales de rutas y App Shell.

### 12B-2 — Procesamiento, clasificación e indexación — Completada

Estado visible de extracción, páginas, chunks e índices, sin ocultar operaciones costosas o errores.

### 12B-3 — Recuperación documental gobernada — Implementada; validación manual pendiente

- Ruta `/documents/search` conectada de forma tipada a la recuperación híbrida
  local, con filtros de documento, tipo, capa, páginas y modo textual.
- La interfaz no carga modelos, no reconstruye índices y no abre Chat; el
  backend mantiene la elegibilidad, revalidación y trazabilidad.

### 12B-4 — Ingesta, procesamiento e indexación automáticos — Completada

- Bandejas locales controladas para biblioteca privada y documentos temporales,
  sidecars JSON estrictos, cuarentena y cola SQLite recuperable tras reinicios.
- La carga manual y la bandeja convergen en el mismo pipeline de registro,
  extracción PyMuPDF e indexación semántica coordinada por lotes.
- Embeddings se preparan bajo demanda y se descargan tras inactividad; Qwen no
  participa. La validación operativa confirmó detección, extracción, indexación,
  búsqueda híbrida y cuarentena con datos sintéticos y backups previos.

### Ajuste transversal — Catálogo y selección segura de modelos locales

- Catálogo permitido, selección persistente y ciclo de vida independiente para
  embeddings y LLM, sin descargas ni rutas arbitrarias desde la API.
- Cambiar embeddings invalida la compatibilidad semántica y exige rebuild
  explícito; cambiar el LLM no modifica los índices.
- 12C-1 y 12C-2 están implementadas; 12C-3A completó el backend conversacional
  y 12C-3B implementó el flujo frontend persistente con cookie HttpOnly.
- Centro frontend `/models` completado con catálogo, selección, load/unload y
  estado semántico compartido; su validación visual manual permanece pendiente.

### 12B-1 — Procesamiento y extracción documental frontend — Completada

- Acción local de extracción, confirmación y resumen seguro de páginas y chunks.
- 12B-2 queda como siguiente bloque de procesamiento e indexación.

### Ajuste transversal — Alineación de rutas y App Shell

- Mapa canónico de rutas frontend y endpoints backend relacionados en
  `docs/routes.md`.
- Sidebar de escritorio limitado al viewport, con navegación interna desplazable
  y control de compactación independiente del contenido principal.
- Este ajuste no modifica el orden de fases ni cierra la validación manual de
  12A-2.

### Ajuste transversal — Marca, apariencia e iconografía

- Preferencias claro, oscuro y sistema; preset local y tokens semánticos
  centralizados sin cambiar capacidades de producto.
- La validación manual de carga 12A-2 y el orden de fases permanecen sin cambios.

### 12C-1 — Núcleo del Chat jurídico RAG — Completada

- `POST /api/chat/rag` conserva una consulta stateless: primero recupera y
  revalida evidencia gobernada, y solo después carga Qwen bajo demanda cuando
  existe contexto suficiente.
- El caso sin evidencia devuelve `insufficient_context` sin cargar Qwen. Con
  evidencia, la respuesta se limita al contexto, valida citas contra SQLite y
  exige revisión profesional.
- El runtime evita cargas duplicadas, protege la generación, aplica timeouts y
  descarga Qwen tras inactividad sin interferir con los controles manuales.

### 12C-2 — Interfaz del Chat jurídico RAG — Implementada; validación visual y operativa pendiente

Interfaz stateless para pregunta, filtros de corpus, respuesta y fuentes
verificables, sin historial persistente.

### 12C-3A — Conversaciones persistentes y evidencia verificable — Completada

- Conversaciones invitadas aisladas por cookie HttpOnly, persistidas siete días
  desde la última actividad y eliminables manual o automáticamente al expirar.
- Cada turno ejecuta recuperación nueva. El historial reciente ayuda a resolver
  referencias conversacionales, pero nunca sustituye la evidencia documental.
- Mensajes, estados, claims y snapshots literales de citas se conservan en
  SQLite sin prompts, chain-of-thought, embeddings, rutas ni contexto ensamblado.
- El esquema admite ownership `account`, pero no existe autenticación real ni
  transferencia: ambas capacidades quedan condicionadas a un principal real y
  consentimiento explícito.

### 12C-3B — Experiencia frontend de conversaciones — Implementada; validación manual pendiente

Incluye historial lateral, hilo multi-turn, creación diferida, cobertura,
claims y evidencia verificable con los endpoints de 12C-3A. El navegador usa
la cookie HttpOnly same-origin sin acceder a su valor ni persistir datos en
almacenamiento web. La validación integrada de cookie, aislamiento, responsive
y flujo real de modelos permanece pendiente.

El refinamiento visual consolidó un layout de dos regiones, rail plegable y
evidencia bajo demanda; la validación manual integrada pendiente se mantiene
sin avanzar a 12C-3C.

La corrección full-bleed elimina el contenedor de lectura y el breadcrumb para
Chat, pero 12C-3B conserva pendiente su validación visual real antes de 12C-3C.

### 12C-3C — Validación integrada de conversaciones — Pendiente heredada

Validar el flujo invitado completo en entorno local aislado: persistencia,
aislamiento, multi-turn, citas, accesibilidad y responsive, sin simular
autenticación.

Esta validación conserva su alcance y se gestionará como deuda de cierre de
12C; no redefine el producto objetivo ni autoriza nuevas capacidades dentro
del Chat general.

### 12D — Reestructuración integral del producto — Completada

- **12D-0 — Arquitectura, inventario y hoja de ruta — Completada
  documentalmente:** define los límites Asistente jurídico general, Workspace
  de inteligencia de casos y Plataforma local compartida; clasifica los
  módulos actuales y diseña los harnesses de pipeline y evaluación. No crea
  tablas, endpoints, rutas ni comportamiento funcional.
- **12D-1 — Límites modulares y contratos de transición — Completada:** fachadas
  públicas pequeñas, DTO inmutables, ports y adaptadores legacy inactivos;
  comprobaciones AST/ESLint y paridad de rutas protegen la dirección de
  dependencias sin tablas, endpoints o UI de casos.
- **12D-2 — Navegación objetivo y shell de Casos — Completada:** incorpora la
  única ruta estática `/cases`, un estado vacío honesto y un shell presentacional
  reutilizable, sin dominio, datos ni APIs de casos.
- **12D-3 — Compatibilidad, legado y preparación de deprecación — Completada:**
  clasificación interna, manifiesto versionado, referencias inmutables y
  políticas puras sin asociar recursos a Case ni cambiar rutas públicas.

### 12E — Casos y expediente — En curso

- **12E-1 — Núcleo persistente de Case y API local — Completada:** agregado de
  dominio separado del ORM, tablas `cases` y `case_audit_events`, propiedad
  `temporary` aislada por sesión invitada y `local_persistent` de instalación,
  retención rodante, transiciones explícitas, locking optimista, auditoría
  transaccional y borrado lógico bajo `/api/cases`.
- **12E-2 — Pertenencia documental explícita del expediente — Completada:**
  `CaseDocument` vincula un caso con documentos existentes de
  `private_library` o `temporary`, conserva snapshot mínima, calcula
  disponibilidad vigente, usa locking en ambas versiones y audita cada
  mutación sin copiar PDF, páginas, chunks o índices.
- El frontend `/cases` permanece estático. No existen todavía carga directa al
  caso, pipeline, conversaciones de caso ni `case_id` en HPN o Red. La
  propiedad `account` permanece futura y no se simula.
- **12E-3 — Siguiente bloque:** conexión frontend del expediente a los contratos
  backend ya implementados.

### 12F — Extracción estructurada de caso — Pendiente

Entidades y artefactos versionados sobre la extracción documental existente,
con checkpoints, idempotencia y revisión.

### 12G — HPN de caso — Pendiente

Matrices versionadas y revisables vinculadas al expediente, conservando las
matrices globales como legado operativo hasta una migración explícita.

### 12H — Red jurídica de caso — Pendiente

Proyección NetworkX y PyVis desde una versión HPN seleccionada, con métricas
exclusivamente estructurales y trazabilidad a SQLite.

### 12I — Métricas y simulaciones — Pendiente

Indicadores técnicos y escenarios comparables, sin convertir centralidad,
conectividad o resultados en conclusiones jurídicas.

### 12J — Dashboard de caso — Pendiente

Resumen de estado, evidencia, advertencias, revisiones y artefactos aceptados.

### 12K — Asistente de caso — Pendiente

Conversaciones ligadas al expediente y recuperación limitada a sus documentos
elegibles. El Asistente jurídico general permanece separado.

### 12L — Harness de evaluación y cierre — Pendiente

Casos sintéticos dorados, regresión de schemas y artefactos, privacidad,
recuperación ante fallos y validación integral reproducible.

La incorporación web controlada se traslada a una capacidad futura de baja
prioridad; no forma parte de 12D–12L.

## Dependencias

12A estableció gobernanza y biblioteca; 12B consolidó procesamiento,
recuperación y modelos; 12C incorporó Chat RAG y conversaciones persistentes.
12D reorganizó esas capacidades, 12E-1 creó el agregado persistente `Case` y
12E-2 incorporó la pertenencia documental explícita. 12E-3 conectará el
frontend sin habilitar aún artefactos; solo entonces 12F–12K podrán producir artefactos de
caso, HPN, Red, métricas, dashboard y asistencia contextual. 12L cerrará con
evaluación integral. La validación heredada de 12C-3C no se confunde con una
capacidad nueva y debe completarse antes de declarar cerrado su flujo visual.

## Próximo bloque autorizado

**12E-3 — Conexión frontend del expediente.** No está autorizado implementar
extracción estructurada, pipeline, recuperación multi-documento de caso ni
atribuir HPN/Red globales a un caso.

## Criterios generales de finalización

Cada bloque requiere contratos tipados, pruebas con datos sintéticos o temporales, privacidad de logs y respuestas, validaciones de calidad configuradas y documentación actualizada. Ningún bloque se marca completado sin validación funcional proporcional a su riesgo.
