# Mapa canónico de rutas e integración

## Propósito

Este documento describe las rutas implementadas y su relación entre interfaz y
backend local. No sustituye los schemas Pydantic ni OpenAPI: esos contratos son
la referencia de detalle de payloads y respuestas. Debe actualizarse cuando una
ruta se añada, retire o cambie. Distingue la implementación frontend, la API
backend y las conexiones que ya están activas.

## Convenciones

- La API local usa el prefijo `/api`.
- La interfaz expresa parámetros dinámicos como `:documentId`; la API los
  expresa como `{document_id}`.
- La paginación parte de `page=1` cuando el endpoint la admite.
- En desarrollo, Vite recibe `/api` en el origen del frontend y lo reenvía al
  backend local mediante su proxy.
- No hay autenticación, cuentas ni rutas de sesión de usuario implementadas.
- El tratamiento es local y privado. Los contratos públicos no exponen rutas de
  almacenamiento, hashes ni metadatos internos restringidos.
- La relación entre navegación, iconos y apariencia está documentada en
  [frontend-branding-theming.md](frontend-branding-theming.md).

## Mapa de rutas frontend

| Ruta | Página o feature | Propósito | Parámetros | Entrada de navegación | Estado | Endpoints principales |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | `HomePage` | Inicio y orientación local. | Ninguno. | Inicio. | Implementada y conectada. | `GET /api/health`. |
| `/documents` | `features/documents` | Listar documentos públicos y abrir la carga PDF explícita. | Ninguno. | Documentos. | Implementada y conectada. | `GET`, `POST /api/documents`. |
| `/documents/search` | `features/documents` | Buscar evidencia documental mediante recuperación híbrida gobernada. | Ninguno. | Desde Biblioteca documental. | Implementada; validación manual pendiente. | `POST /api/search/hybrid`. |
| `/documents/:documentId` | `features/documents` | Consultar un documento público registrado. | `:documentId`. | Desde listado o carga exitosa. | Implementada y conectada. | `GET /api/documents/{document_id}`. |
| `/models` | `features/models` | Consultar catálogo, selección y ciclo de vida de modelos locales. | Ninguno. | Modelos locales. | Implementada; validación visual pendiente. | Catálogo, selección, estado, carga y descarga bajo `/api/models`. |
| `/matrices-hpn` | `features/hpn-matrices` | Listar y crear matrices HPN. | Ninguno. | Matrices HPN. | Implementada y conectada. | `GET`, `POST /api/hpn/matrices`. |
| `/matrices-hpn/:matrixId` | `features/hpn-matrices` | Editar una matriz y sus nodos o relaciones revisables. | `:matrixId`. | Desde matrices HPN. | Implementada y conectada. | Rutas de matrices, nodos y relaciones HPN. |
| `/legal-network` | `features/legal-network` | Estado vacío de la red y acceso a matrices. | Ninguno. | Red jurídica. | Solo frontend. | Ninguno. |
| `/legal-network/:matrixId` | `features/legal-network` | Mostrar la proyección estructural y la exportación PyVis restringida. | `:matrixId`. | Desde el detalle HPN. | Implementada y conectada. | `GET /api/hpn/matrices/{matrix_id}/graph` y `/graph/export`. |
| `*` | `NotFoundPage` | Ruta no encontrada. | Ninguno. | No aplica. | Solo frontend. | Ninguno. |

La ruta de Chat jurídico no existe todavía en el router. Es una ruta futura por
definir; el endpoint Chat RAG backend no implica una pantalla activa.

## Mapa de endpoints backend

### Salud

| Método y ruta | Propósito | Consumidor actual | Conexión | Nota |
| --- | --- | --- | --- | --- |
| `GET /api/health` | Disponibilidad del proceso local. | Cliente de salud del frontend. | Conectada. | No expone estado documental. |

### Documentos, extracción, páginas y chunks

| Método y ruta | Propósito | Consumidor actual | Conexión | Nota |
| --- | --- | --- | --- | --- |
| `POST /api/documents` | Registrar un PDF validado. | Biblioteca, modal de carga. | Conectada. | Validación autoritativa de PDF y gobernanza. |
| `GET /api/documents/processing/summary` | Resumen seguro de la cola automática. | Biblioteca. | Conectada. | Sin rutas ni contenido documental. |
| `GET /api/documents/processing/jobs?limit=` | Trabajos recientes sanitizados. | Ninguno. | Solo backend. | No devuelve la ruta interna de bandeja. |
| `GET /api/documents/processing/jobs/{job_id}` | Estado de un trabajo. | Ninguno. | Solo backend. | Metadatos operativos mínimos. |
| `POST /api/documents/processing/jobs/{job_id}/retry` | Reintentar un fallo permitido. | Ninguno. | Solo backend. | No acepta rutas ni reintenta cuarentena. |
| `GET /api/documents?page=&page_size=&document_type=&status=` | Listar documentos públicos. | Biblioteca. | Conectada. | Paginación base 1; filtros opcionales. |
| `GET /api/documents/{document_id}` | Detalle público. | Detalle documental. | Conectada. | Sin rutas ni hashes. |
| `DELETE /api/documents/{document_id}` | Borrado lógico. | Ninguno. | Solo backend. | Conserva el archivo según la política vigente. |
| `POST /api/documents/{document_id}/extract` | Ejecutar extracción local explícita. | Ninguno. | Solo backend. | No se inicia desde la carga frontend. |
| `GET /api/documents/{document_id}/pages?page=&page_size=` | Páginas extraídas. | Ninguno. | Solo backend. | Requiere extracción previa; paginación base 1. |
| `GET /api/documents/{document_id}/chunks?page=&page_size=` | Chunks extraídos. | Ninguno. | Solo backend. | Requiere extracción previa; paginación base 1. |

### Modelos locales

| Método y ruta | Propósito | Consumidor actual | Conexión | Nota |
| --- | --- | --- | --- | --- |
| `GET /api/models/status` | Estado seguro de modelos declarados. | Ninguno. | Solo backend. | No carga el modelo. |
| `GET /api/models/embeddings/status` | Estado de embeddings. | Modelos locales y búsqueda documental. | Conectada. | Indica carga automática sin importar pesos. |
| `POST /api/models/embeddings/load` | Cargar embeddings locales. | Modelos locales e índice semántico. | Conectada. | Operación explícita. |
| `POST /api/models/embeddings/unload` | Liberar embeddings. | Modelos locales e índice semántico. | Conectada. | Operación idempotente. |
| `GET /api/models/catalog` | Catálogo sanitizado de modelos locales permitidos. | Modelos locales. | Conectada. | No expone rutas ni descarga artefactos. |
| `GET /api/models/selection` | Selección activa persistente. | Modelos locales. | Conectada. | Distingue modelo activo de modelo cargado. |
| `PUT /api/models/selection/embeddings` | Seleccionar embeddings instalados. | Modelos locales. | Conectada. | Requiere el modelo actual descargado; no reconstruye el índice. |
| `PUT /api/models/selection/llm` | Seleccionar LLM instalado. | Modelos locales. | Conectada. | Requiere el modelo actual descargado; no carga el nuevo. |
| `GET /api/models/llm/status` | Estado de Qwen. | Modelos locales. | Conectada. | No carga el GGUF; informa estado, operación y origen de carga seguros. |
| `POST /api/models/llm/load` | Cargar Qwen local. | Modelos locales. | Conectada. | Control manual conservado junto a la política bajo demanda. |
| `POST /api/models/llm/unload` | Liberar Qwen. | Modelos locales. | Conectada. | Idempotente y bloqueada durante actividad protegida. |

### Búsqueda textual, semántica e híbrida

| Método y ruta | Propósito | Consumidor actual | Conexión | Nota |
| --- | --- | --- | --- | --- |
| `POST /api/search/text` | Recuperación textual FTS5. | Ninguno. | Solo backend. | Consulta controlada y resultados trazables. |
| `GET /api/search/semantic/status` | Estado del índice semántico. | Ninguno. | Solo backend. | No crea ni reconstruye el índice. |
| `POST /api/search/semantic/rebuild` | Reconstrucción semántica explícita. | Ninguno. | Solo backend. | Requiere modelo e índice locales. |
| `POST /api/search/semantic` | Recuperación semántica. | Ninguno. | Solo backend. | Revalida candidatos contra SQLite. |
| `POST /api/search/hybrid` | Recuperación híbrida RRF. | Búsqueda documental. | Conectada. | Filtros gobernados y resultados trazables; no inicia Chat. |

### Chat RAG

| Método y ruta | Propósito | Consumidor actual | Conexión | Nota |
| --- | --- | --- | --- | --- |
| `POST /api/chat/rag` | Recuperar evidencia y generar una respuesta local con citas estructuradas. | Ninguno. | Solo backend. | Recibe una pregunta y filtros, no mensajes ni historial; recupera antes de cargar Qwen. |

La respuesta pública distingue `answered` e `insufficient_context`, conserva
conteos técnicos seguros y solo incluye citas revalidadas con documento
público, capa, tipo, chunk y páginas. No devuelve prompt, contexto, scores,
vectores, rutas ni contenido completo. Los fallos de índice, modelos,
generación o citas usan códigos estables sin traceback.

### Matrices HPN, nodos y relaciones

| Método y ruta | Propósito | Consumidor actual | Conexión | Nota |
| --- | --- | --- | --- | --- |
| `GET /api/hpn/matrices?page=&page_size=` | Listar matrices. | Matrices HPN. | Conectada. | Paginación base 1. |
| `POST /api/hpn/matrices` | Crear una matriz. | Matrices HPN. | Conectada. | Registro manual revisable. |
| `GET`, `PATCH`, `DELETE /api/hpn/matrices/{matrix_id}` | Consultar, actualizar o borrar lógicamente una matriz. | Detalle HPN. | Conectada. | Estados y revisión son controlados. |
| `GET /api/hpn/matrices/{matrix_id}/validation` | Resumen de validación HPN. | Ninguno. | Solo backend. | No constituye conclusión jurídica. |
| `POST /api/hpn/matrices/{matrix_id}/nodes` | Crear nodo HPN. | Detalle HPN. | Conectada. | Nodo fact, evidence o norm revisable. |
| `PATCH`, `DELETE /api/hpn/matrices/{matrix_id}/nodes/{node_id}` | Actualizar o borrar nodo. | Detalle HPN. | Conectada. | Sin automatizar decisiones. |
| `POST /api/hpn/matrices/{matrix_id}/nodes/{node_id}/sources` | Asociar fuente a nodo. | Ninguno. | Solo backend. | Mantiene trazabilidad de fuente. |
| `DELETE /api/hpn/matrices/{matrix_id}/nodes/{node_id}/sources/{source_id}` | Retirar una fuente asociada. | Detalle HPN. | Conectada. | No elimina el documento de origen. |
| `POST /api/hpn/matrices/{matrix_id}/relations` | Crear relación dirigida. | Detalle HPN. | Conectada. | No prueba causalidad ni aplicabilidad. |
| `PATCH`, `DELETE /api/hpn/matrices/{matrix_id}/relations/{relation_id}` | Actualizar o retirar relación. | Detalle HPN. | Conectada. | Conserva revisión humana. |

### Red jurídica y exportación PyVis

| Método y ruta | Propósito | Consumidor actual | Conexión | Nota |
| --- | --- | --- | --- | --- |
| `GET /api/hpn/matrices/{matrix_id}/graph` | Proyección JSON estructural de solo lectura. | Red jurídica. | Conectada. | No expresa conclusiones jurídicas automáticas. |
| `GET /api/hpn/matrices/{matrix_id}/graph/export` | HTML PyVis local y restringido. | Iframe de Red jurídica. | Conectada. | Sin rutas locales ni HTML aportado por usuario. |

## Matriz pantalla → endpoint

| Pantalla o acción | Ruta frontend | Endpoint | Método | Estado |
| --- | --- | --- | --- | --- |
| Salud local | `/` | `/api/health` | `GET` | Conectada. |
| Listar documentos | `/documents` | `/api/documents` | `GET` | Conectada. |
| Cargar PDF | `/documents` | `/api/documents` | `POST` | Conectada; encola procesamiento automático. |
| Detalle documental | `/documents/:documentId` | `/api/documents/{document_id}` | `GET` | Conectada. |
| Búsqueda documental gobernada | `/documents/search` | `/api/search/hybrid` | `POST` | Conectada; prepara embeddings bajo demanda si el índice es compatible. |
| Administrar modelos locales | `/models` | `/api/models/catalog`, `/selection`, estados, load y unload | `GET`, `PUT`, `POST` | Conectada; no descarga artefactos ni ejecuta inferencia. |
| Extraer contenido y resumen técnico | `/documents/:documentId` | `/api/documents/{document_id}/extract`, `/pages`, `/chunks` | `POST`, `GET` | Conectada; totales paginados sin mostrar texto. |
| Listar o crear matrices | `/matrices-hpn` | `/api/hpn/matrices` | `GET`, `POST` | Conectada. |
| Editar matriz, nodos o relaciones | `/matrices-hpn/:matrixId` | Rutas HPN correspondientes | Varios | Conectada. |
| Proyección de red | `/legal-network/:matrixId` | `/api/hpn/matrices/{matrix_id}/graph` | `GET` | Conectada. |
| Visualización PyVis | `/legal-network/:matrixId` | `/api/hpn/matrices/{matrix_id}/graph/export` | `GET` | Conectada. |

## Capacidades backend sin pantalla

Ya están implementadas, pero no tienen una pantalla frontend activa: extracción
documental, consulta de páginas y chunks, estado y ciclo de vida de modelos,
búsqueda textual, semántica e híbrida, Chat RAG, procesamiento e indexación
explícitos y corpus administrado mediante CLI. Estas capacidades no deben
interpretarse como flujos de interfaz ya disponibles.

## Rutas futuras

- Procesamiento documental desde frontend — ruta por definir.
- Chat jurídico — ruta por definir.
- Selección de corpus — ruta por definir.
- Fuentes y citas visibles — ruta por definir.
- Propuestas HPN asistidas — ruta por definir.
