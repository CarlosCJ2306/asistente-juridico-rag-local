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
| `/documents/:documentId` | `features/documents` | Consultar un documento público registrado. | `:documentId`. | Desde listado o carga exitosa. | Implementada y conectada. | `GET /api/documents/{document_id}`. |
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
| `GET /api/models/embeddings/status` | Estado de embeddings. | Ninguno. | Solo backend. | No importa pesos. |
| `POST /api/models/embeddings/load` | Cargar embeddings locales. | Ninguno. | Solo backend. | Operación explícita. |
| `POST /api/models/embeddings/unload` | Liberar embeddings. | Ninguno. | Solo backend. | Operación idempotente. |
| `GET /api/models/llm/status` | Estado de Qwen. | Ninguno. | Solo backend. | No carga el GGUF. |
| `POST /api/models/llm/load` | Cargar Qwen local. | Ninguno. | Solo backend. | Operación explícita. |
| `POST /api/models/llm/unload` | Liberar Qwen. | Ninguno. | Solo backend. | Operación idempotente. |

### Búsqueda textual, semántica e híbrida

| Método y ruta | Propósito | Consumidor actual | Conexión | Nota |
| --- | --- | --- | --- | --- |
| `POST /api/search/text` | Recuperación textual FTS5. | Ninguno. | Solo backend. | Consulta controlada y resultados trazables. |
| `GET /api/search/semantic/status` | Estado del índice semántico. | Ninguno. | Solo backend. | No crea ni reconstruye el índice. |
| `POST /api/search/semantic/rebuild` | Reconstrucción semántica explícita. | Ninguno. | Solo backend. | Requiere modelo e índice locales. |
| `POST /api/search/semantic` | Recuperación semántica. | Ninguno. | Solo backend. | Revalida candidatos contra SQLite. |
| `POST /api/search/hybrid` | Recuperación híbrida RRF. | Ninguno. | Solo backend. | No presenta resultados en frontend aún. |

### Chat RAG

| Método y ruta | Propósito | Consumidor actual | Conexión | Nota |
| --- | --- | --- | --- | --- |
| `POST /api/chat/rag` | Recuperar evidencia y generar una respuesta local con citas estructuradas. | Ninguno. | Solo backend. | Stateless; requiere evidencia elegible y revisión profesional. |

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
| Cargar PDF | `/documents` | `/api/documents` | `POST` | Conectada; no procesa ni indexa. |
| Detalle documental | `/documents/:documentId` | `/api/documents/{document_id}` | `GET` | Conectada. |
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
