# Asistente Jurídico Local

Aplicación local para administrar documentos PDF, recuperar evidencia documental y apoyar la revisión jurídica profesional. No toma decisiones jurídicas ni sustituye el criterio de un profesional competente.

## Enfoque

El sistema procesa los documentos localmente: registra y extrae PDF con PyMuPDF, conserva páginas y fragmentos en SQLite, usa FTS5 y ChromaDB como índices derivados y genera respuestas RAG con Qwen local. Las respuestas del backend incluyen citas estructuradas verificables.

Los documentos no reentrenan el modelo. Se utilizan como evidencia mediante recuperación aumentada por generación (RAG).

## Capacidades actuales

- Backend: carga segura de PDF, extracción, páginas, chunks, embeddings locales, recuperación textual, semántica e híbrida, Chat RAG, conversaciones invitadas, citas estructuradas y núcleo persistente de casos.
- Análisis estructural: CRUD manual de Matrices HPN, API de grafo y exportación PyVis local.
- Frontend: Inicio, Asistente jurídico conversacional, Casos como estado vacío
  preparatorio, Biblioteca documental, búsqueda, procesamiento, Modelos
  locales, Matrices HPN y Red jurídica.

El backend implementa el agregado `Case`, la API local `/api/cases` y la
pertenencia documental explícita mediante `CaseDocument`, con
retención temporal por sesión invitada, persistencia de instalación, estados,
locking optimista, auditoría y borrado lógico. El frontend `/cases` continúa
siendo únicamente un estado vacío preparatorio y no consume esa API. No existe
todavía carga directa al caso, pipeline, conversación de caso ni vínculo de
HPN/Red con un caso. Tampoco existen
cuentas, transferencia entre dispositivos o autenticación. HPN y Red continúan
como recursos globales hasta su futura asociación aditiva con `Case`.

## Conversaciones RAG

`POST /api/chat/rag` conserva el contrato individual sin persistencia. Los
endpoints bajo `/api/conversations` crean y administran hilos invitados y
añaden mensajes multi-turn. Una cookie HttpOnly identifica al invitado; el
backend guarda solo su hash y aplica siete días de retención desde la última
actividad. Cada respuesta vuelve a recuperar y revalidar evidencia, persiste
claims y snapshots de citas, y nunca trata respuestas anteriores como fuente.

## Arquitectura resumida

- Backend: FastAPI y SQLite como fuente de verdad.
- Índices derivados: SQLite FTS5 y ChromaDB local.
- IA local: `multilingual-e5-small` y Qwen3 mediante `llama-cpp-python`.
- Frontend: React, TypeScript y Vite; en desarrollo, `/api` se enruta mediante proxy local.

La experiencia de producto se orienta a PC y ventanas redimensionables de
1024px a 2560px. Se conservan zoom, teclado, foco y scroll controlado; la
armonización visual definitiva se realizará después de las capacidades
funcionales principales.

La arquitectura objetivo desde 12D separa tres límites: Asistente jurídico
general, Workspace de inteligencia de casos y Plataforma local compartida.
12E-1 implementó el núcleo backend de `Case` y 12E-2 añadió asociaciones
documentales explícitas sin duplicar archivos ni índices. El workspace
frontend sigue pendiente. Consulte el [inventario de módulos](docs/modules.md), el
[dominio de casos](docs/case-domain.md) y la
[estrategia de migración](docs/migration-strategy.md).

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
- [Inventario y decisión de módulos](docs/modules.md)
- [Dominio de casos](docs/case-domain.md)
- [Workspace de casos](docs/case-workspace.md)
- [CasePipelineHarness](docs/case-pipeline-harness.md)
- [CaseEvaluationHarness](docs/evaluation-harness.md)
- [HPN y Red jurídica en casos](docs/hpn-and-legal-network.md)
- [Arquitectura multiagente futura](docs/multiagent-architecture.md)
- [Estrategia de migración](docs/migration-strategy.md)
- [Design System frontend](docs/frontend-design-system.md)
- [Historial técnico](CAMBIOS.md)
