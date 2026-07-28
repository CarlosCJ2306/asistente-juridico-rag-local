# Asistente Jurídico Local

Aplicación local para administrar documentos PDF, recuperar evidencia documental y apoyar la revisión jurídica profesional. No toma decisiones jurídicas ni sustituye el criterio de un profesional competente.

## Enfoque

El sistema procesa los documentos localmente: registra y extrae PDF con PyMuPDF, conserva páginas y fragmentos en SQLite, usa FTS5 y ChromaDB como índices derivados y genera respuestas RAG con Qwen local. Las respuestas del backend incluyen citas estructuradas verificables.

Los documentos no reentrenan el modelo. Se utilizan como evidencia mediante recuperación aumentada por generación (RAG).

## Capacidades actuales

- Backend: carga segura de PDF, extracción, páginas, chunks, embeddings locales, recuperación textual, semántica e híbrida, Chat RAG y citas estructuradas.
- Análisis estructural: CRUD manual de Matrices HPN, API de grafo y exportación PyVis local.
- Frontend: Inicio, Biblioteca documental con carga PDF explícita, Matrices HPN
  y Red jurídica.

El procesamiento documental desde frontend, la selección visual de corpus, el
Chat jurídico y la presentación de fuentes en frontend siguen pendientes.

## Arquitectura resumida

- Backend: FastAPI y SQLite como fuente de verdad.
- Índices derivados: SQLite FTS5 y ChromaDB local.
- IA local: `multilingual-e5-small` y Qwen3 mediante `llama-cpp-python`.
- Frontend: React, TypeScript y Vite; en desarrollo, `/api` se enruta mediante proxy local.

## Requisitos básicos y arranque

Se requiere Python 3.12, Node.js y los modelos locales correspondientes para las capacidades de IA. Las instrucciones reproducibles de entorno, migraciones, modelos, backend y frontend están en la guía de instalación.

## Documentación canónica

- [Producto y alcance](docs/product.md)
- [Plan de trabajo vigente](PLAN_TRABAJO.md)
- [Arquitectura](docs/architecture.md)
- [Instalación y operación local](docs/installation.md)
- [Seguridad y privacidad](docs/security-privacy.md)
- [Calidad](docs/quality.md)
- [Arquitectura de producto frontend](docs/frontend-product-architecture.md)
- [Marca y apariencia frontend](docs/frontend-branding-theming.md)
- [Mapa canónico de rutas e integración](docs/routes.md)
- [Design System frontend](docs/frontend-design-system.md)
- [Historial técnico](CAMBIOS.md)
