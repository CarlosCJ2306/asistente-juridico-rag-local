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
RAG ya están implementados. La interfaz de Chat y sus fuentes visibles siguen
pendientes.

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
- 12C-1 quedó completada después de 12B-4; 12C-2 es el siguiente bloque
  autorizado.
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

### 12C-2 — Interfaz del Chat jurídico RAG — Siguiente bloque

Interfaz stateless para pregunta, filtros de corpus, respuesta y fuentes
verificables, sin historial persistente.

### 12D — Incorporación web controlada y verificable

Fuentes externas bajo procedencia, fecha, permisos, conservación y revisión explícitas.

### 12E — Generación asistida de propuestas HPN

Borradores asistidos a partir de evidencia seleccionada; no sustituyen la edición y revisión humanas.

### 12F — Revisión, aprobación y trazabilidad hacia Red jurídica

Flujo de revisión de matrices y relación controlada con la proyección de Red jurídica.

## Dependencias

12A-0A establece el modelo persistente, 12A-0B centraliza sus políticas,
12A-0C las integra con recuperación y Chat RAG, 12A-0D valida ese flujo y
12A-0E incorpora fuentes administradas de forma explícita. 12A-1 expone la
biblioteca y 12A-2 incorpora la carga PDF explícita. 12B habilitó el núcleo
Chat RAG completado en 12C-1; 12C-2 es el próximo bloque autorizado. La
biblioteca y la carga habilitan el procesamiento; el procesamiento e índices
habilitan el Chat RAG; el Chat con fuentes y la
gobernanza de evidencia preceden a propuestas HPN; la revisión de esas
propuestas precede su trazabilidad hacia la Red jurídica.

## Criterios generales de finalización

Cada bloque requiere contratos tipados, pruebas con datos sintéticos o temporales, privacidad de logs y respuestas, validaciones de calidad configuradas y documentación actualizada. Ningún bloque se marca completado sin validación funcional proporcional a su riesgo.
