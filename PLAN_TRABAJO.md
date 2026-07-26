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

Las Matrices HPN manuales y la Red jurídica ya están implementadas. La biblioteca documental, la carga PDF, el procesamiento, la selección de corpus, el Chat RAG y las fuentes visibles en frontend siguen pendientes.

## Hoja de ruta activa

### 12A-0A — Fundamentos de gobernanza documental — Implementada

- Modelo y migración aditiva para capas de conocimiento, procedencia, revisión,
  vigencia, indexación y versiones documentales.
- Contrato público de documentos saneado, sin rutas, nombres almacenados ni
  hashes.

### 12A-0B — Políticas y ciclo de vida documental — Siguiente bloque

- Definir transiciones controladas, elegibilidad, aprobación, archivo y
  expiración sin mezclar estados técnicos, editoriales y jurídicos.

### 12A-0C — Integración de gobernanza con recuperación — Pendiente

- Aplicar las políticas aprobadas a FTS5, ChromaDB, selección de corpus y Chat
  RAG; no forma parte de 12A-0A.

### 12A-1 — Biblioteca documental frontend

Interfaz para listar y consultar el estado de documentos ya administrados por el backend.

### 12A-2 — Carga segura de PDF desde frontend

Flujo de carga que reutilice la validación, límites y contratos documentales existentes.

### 12B — Procesamiento, clasificación e indexación

Estado visible de extracción, páginas, chunks e índices, sin ocultar operaciones costosas o errores.

### 12C — Chat jurídico RAG con selección de corpus y citas

Interfaz stateless para recuperación, respuesta, filtros de corpus y fuentes verificables.

### 12D — Incorporación web controlada y verificable

Fuentes externas bajo procedencia, fecha, permisos, conservación y revisión explícitas.

### 12E — Generación asistida de propuestas HPN

Borradores asistidos a partir de evidencia seleccionada; no sustituyen la edición y revisión humanas.

### 12F — Revisión, aprobación y trazabilidad hacia Red jurídica

Flujo de revisión de matrices y relación controlada con la proyección de Red jurídica.

## Dependencias

12A-0A establece el modelo persistente; 12A-0B es el próximo bloque autorizado
y precede la integración 12A-0C. La biblioteca y la carga habilitan el
procesamiento; el procesamiento e índices habilitan el Chat RAG; el Chat con
fuentes y la gobernanza de evidencia preceden a propuestas HPN; la revisión de
esas propuestas precede su trazabilidad hacia la Red jurídica.

## Criterios generales de finalización

Cada bloque requiere contratos tipados, pruebas con datos sintéticos o temporales, privacidad de logs y respuestas, validaciones de calidad configuradas y documentación actualizada. Ningún bloque se marca completado sin validación funcional proporcional a su riesgo.
