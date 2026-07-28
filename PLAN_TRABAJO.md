# Plan de trabajo — Asistente Jurídico Local

## Propósito

Este es el plan activo y la única hoja de ruta vigente. Ordena la evolución del producto local, trazable y sujeto a revisión profesional. El historial de trabajo ya realizado se conserva en [CAMBIOS.md](CAMBIOS.md).

## Restricciones técnicas vigentes

- SQLite es la fuente de verdad documental; FTS5 y ChromaDB son índices derivados y reconstruibles.
- El procesamiento de contenido jurídico, embeddings y generación ocurre localmente; no se usan servicios externos de inferencia.
- Los modelos se cargan explícitamente y no durante imports o el inicio de FastAPI.
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

Las Matrices HPN manuales, la Red jurídica y la biblioteca documental con carga PDF explícita ya están implementadas. El procesamiento, la selección de corpus, el Chat RAG y las fuentes visibles en frontend siguen pendientes.

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

### 12B-2 — Procesamiento, clasificación e indexación — Siguiente bloque

Estado visible de extracción, páginas, chunks e índices, sin ocultar operaciones costosas o errores.

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

### 12C — Chat jurídico RAG con selección de corpus y citas

Interfaz stateless para recuperación, respuesta, filtros de corpus y fuentes verificables.

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
biblioteca y 12A-2 incorpora la carga PDF explícita. 12B es el próximo bloque
autorizado. La biblioteca y la carga habilitan el procesamiento; el
procesamiento e índices habilitan el Chat RAG; el Chat con fuentes y la
gobernanza de evidencia preceden a propuestas HPN; la revisión de esas
propuestas precede su trazabilidad hacia la Red jurídica.

## Criterios generales de finalización

Cada bloque requiere contratos tipados, pruebas con datos sintéticos o temporales, privacidad de logs y respuestas, validaciones de calidad configuradas y documentación actualizada. Ningún bloque se marca completado sin validación funcional proporcional a su riesgo.
