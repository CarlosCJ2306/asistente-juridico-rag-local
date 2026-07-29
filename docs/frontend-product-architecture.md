# Arquitectura de producto frontend

## Estado implementado

El frontend usa React, TypeScript, Vite, React Router y TanStack Query. App Shell, sidebar, topbar, Drawer móvil, Design System, cliente HTTP compartido, providers de sesión local, preferencias y notificaciones están implementados.

Las rutas activas son Inicio, Asistente jurídico, Documentos, detalle documental, Matrices HPN,
detalle de matriz y Red jurídica. La biblioteca consume los contratos públicos
de listado paginado, detalle y carga PDF mediante el cliente HTTP compartido;
las matrices
consumen contratos HPN tipados y la Red jurídica consume JSON sanitizado,
muestra alternativa textual y usa iframe PyVis relativo con sandbox restringido.
El [mapa canónico de rutas e integración](routes.md) mantiene la relación
actualizada entre cada pantalla y sus endpoints reales.

[La configuración de marca y apariencia](frontend-branding-theming.md) detalla tokens, presets, iconografía y preferencias visuales locales.

## Límites actuales

El feature `features/chat` admite el contrato individual de `POST /api/chat/rag`
y conversaciones invitadas persistidas por el backend. React no accede a la
cookie HttpOnly ni guarda preguntas, respuestas o citas en almacenamiento web.
Cada turno vuelve a recuperar evidencia; el historial no es fuente jurídica.

La biblioteca permite una carga PDF explícita para biblioteca privada o
consulta temporal con expiración futura, pero no permite cambiar estados,
procesar, indexar, eliminar ni visualizar contenido de PDF. Los destinos
futuros permanecen fuera de la navegación hasta que tengan contratos y flujos
completos.

El detalle documental permite iniciar la extracción local y consultar solo los
totales de páginas y fragmentos; no muestra texto ni inicia indexación.

## Decisiones vigentes

- Features por dominio sobre un cliente HTTP común; no usar `fetch` directo dentro de features.
- `features/documents` mantiene tipos cerrados, guards de respuesta, query keys,
  hooks, rutas y componentes de metadatos; no persiste respuestas documentales
  en almacenamiento web.
- `features/models` consume el catálogo permitido, la selección persistida por
  el backend y los estados de embeddings, LLM e índice semántico. Comparte las
  query keys semánticas con Documentos y Búsqueda: activo determina la próxima
  carga y cargado representa exclusivamente la memoria actual.
- `features/chat` no consulta ni controla estados de modelos o índices. Permite
  una pregunta individual, filtros de corpus autorizados, estado de espera
  único, respuesta plain-text segura y citas que abren `/documents/:documentId`.
- Estados loading, empty, error y offline mediante patrones compartidos.
- Renderizar contenido de dominio como texto; no usar `dangerouslySetInnerHTML` ni `srcDoc`.
- Mantener preguntas, respuestas, snippets, vectores y datos documentales fuera de almacenamiento web y notificaciones.
- Usar rutas relativas para recursos locales y no exponer configuraciones, rutas o identificadores restringidos.
- La accesibilidad incluye foco visible, targets táctiles, navegación por teclado y alternativa textual para el grafo.
- En escritorio, el sidebar se limita al viewport: marca y control de
  compactación no se desplazan, mientras solo la navegación central puede
  desplazarse. El Drawer móvil conserva su propio ciclo de foco y cierre.

## Chat conversacional persistente

`/chat` usa un workspace full-bleed que ocupa toda la fila disponible del App
Shell bajo el topbar, sin `Container` de lectura, breadcrumb exterior ni
padding de página. Usa dos regiones: un rail plegable que lista solo el historial devuelto
por el backend y un área principal de hilo, composer y advertencia discreta.
El rail conserva su estado exclusivamente en memoria; en tamaños reducidos se
abre como Drawer. La evidencia se abre bajo demanda en un Drawer derecho desde
la respuesta concreta, sin reservar una tercera columna ni cambiar el scroll
del hilo.
La conversación se crea al primer envío, no al entrar a la ruta. TanStack
Query conserva únicamente respuestas de API en memoria y las query keys no
contienen preguntas, respuestas ni citas.

La cookie HttpOnly se maneja exclusivamente por el navegador en peticiones
same-origin. No existe almacenamiento web, autenticación simulada ni
sincronización entre dispositivos.

## Deuda de validación heredada

El backend ofrece CRUD bajo `/api/conversations` y creación de turnos bajo
`/{conversation_id}/messages`. La interfaz representa historial lateral, hilo
ordenado, estados `answered`, `partial`, `insufficient_context` y `failed`,
claims, cobertura y citas directas. La cookie invitada es HttpOnly: React no
debe leerla, copiarla ni persistirla. La transferencia a cuenta no debe
mostrarse hasta que exista autenticación real y consentimiento.

Esta validación pendiente no cambia los contratos ni convierte conversaciones
generales en conversaciones de caso.

## Navegación objetivo desde 12D

La navegación visible es Inicio, Asistente jurídico, Casos, Biblioteca
jurídica, Matrices HPN, Red jurídica y Modelos locales. Procesamiento no se
incorpora al App Shell porque no tiene una pantalla funcional independiente.

`Casos` será un workspace con Resumen, Expediente, Matriz HPN, Red, Métricas,
Simulaciones, Asistente y Auditoría. Todo ese workspace está **planificado**;
no existen todavía sus rutas ni contratos. Las rutas actuales de Matrices HPN
y Red permanecen como legado operativo hasta lograr paridad, asociación humana
y deprecación documentada. Consulte [case-workspace.md](case-workspace.md).

12D-2 incorporó `/cases` como único destino estático, con estado vacío honesto
y enlaces a capacidades existentes. La navegación visible se organiza en
Trabajo (Inicio, Asistente jurídico, Casos), Conocimiento (Biblioteca jurídica),
Herramientas actuales (Matrices HPN y Red jurídica) y Sistema (Modelos locales).
No se añadió Procesamiento porque no tiene una pantalla funcional, ni rutas
dinámicas, API o datos de casos.

12D-3 no cambia la interfaz visual ni la navegación: registra solamente
metadata interna de compatibilidad. La experiencia se prioriza para PC; la
validación móvil y el refinamiento visual definitivo permanecen diferidos.

12D-1 consolidó los `index.ts` de features como
fachadas públicas, eliminó imports profundos Chat→Documentos, Red→HPN y
Modelos→Documentos, y movió una utilidad modal genérica fuera de HPN. ESLint
impide volver a importar internals de otra feature o de
`design-system/internal`.

## Relación con el Design System

El contrato visual y de interacción está en [frontend-design-system.md](frontend-design-system.md). Este documento define producto, rutas y límites de datos; el Design System no contiene lógica de dominio.
