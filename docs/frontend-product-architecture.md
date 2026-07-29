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

El feature `features/chat` consume `POST /api/chat/rag` mediante el cliente
HTTP compartido y una mutation. Reutiliza `CorpusSelector`, contratos cerrados
y guards de respuesta para mostrar texto plano, citas públicas y enlaces al
detalle documental. La pregunta, la respuesta y las citas viven únicamente en
estado React: no hay multi-turn, persistencia, query keys con contenido ni
almacenamiento web.
Al recargar o navegar fuera de `/chat`, esa sesión visual se descarta; volver
con el navegador inicia una nueva consulta sin restaurar preguntas o respuestas.

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

## Próximas áreas

### Contrato de 12C-3B

El backend ofrece CRUD bajo `/api/conversations` y creación de turnos bajo
`/{conversation_id}/messages`. El futuro frontend deberá representar historial
lateral, hilo ordenado, estados `answered`, `partial`, `insufficient_context` y
`failed`, claims, cobertura y panel de citas directas. La cookie invitada es
HttpOnly: React no debe leerla, copiarla ni persistirla. La transferencia a
cuenta no debe mostrarse hasta que exista autenticación real y consentimiento.

La evolución frontend sigue el plan activo: validación manual de recuperación,
mejoras futuras de Chat, citas/fuentes y propuestas HPN asistidas. Cada área
debe reutilizar contratos backend existentes, evitar exponer identificadores
técnicos innecesarios y conservar revisión profesional obligatoria.

## Relación con el Design System

El contrato visual y de interacción está en [frontend-design-system.md](frontend-design-system.md). Este documento define producto, rutas y límites de datos; el Design System no contiene lógica de dominio.
