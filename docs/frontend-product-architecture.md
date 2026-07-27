# Arquitectura de producto frontend

## Estado implementado

El frontend usa React, TypeScript, Vite, React Router y TanStack Query. App Shell, sidebar, topbar, Drawer móvil, Design System, cliente HTTP compartido, providers de sesión local, preferencias y notificaciones están implementados.

Las rutas activas son Inicio, Documentos, detalle documental, Matrices HPN,
detalle de matriz y Red jurídica. La biblioteca consume los contratos públicos
de listado paginado y detalle mediante el cliente HTTP compartido; las matrices
consumen contratos HPN tipados y la Red jurídica consume JSON sanitizado,
muestra alternativa textual y usa iframe PyVis relativo con sandbox restringido.

## Límites actuales

No existen todavía carga PDF, procesamiento, selección de corpus, búsqueda,
Chat jurídico, citas o fuentes visibles. La biblioteca documental actual es de
solo lectura: no permite cambiar estados, importar, procesar, indexar, eliminar
ni visualizar contenido de PDF. Los destinos futuros permanecen fuera de la
navegación hasta que tengan contratos y flujos completos.

## Decisiones vigentes

- Features por dominio sobre un cliente HTTP común; no usar `fetch` directo dentro de features.
- `features/documents` mantiene tipos cerrados, guards de respuesta, query keys,
  hooks, rutas y componentes de metadatos; no persiste respuestas documentales
  en almacenamiento web.
- Estados loading, empty, error y offline mediante patrones compartidos.
- Renderizar contenido de dominio como texto; no usar `dangerouslySetInnerHTML` ni `srcDoc`.
- Mantener preguntas, respuestas, snippets, vectores y datos documentales fuera de almacenamiento web y notificaciones.
- Usar rutas relativas para recursos locales y no exponer configuraciones, rutas o identificadores restringidos.
- La accesibilidad incluye foco visible, targets táctiles, navegación por teclado y alternativa textual para el grafo.

## Próximas áreas

La evolución frontend sigue el plan activo: carga y procesamiento documental,
selección de corpus, chat, citas/fuentes y propuestas HPN asistidas. Cada área
debe reutilizar contratos backend existentes, evitar exponer identificadores
técnicos innecesarios y conservar revisión profesional obligatoria.

## Relación con el Design System

El contrato visual y de interacción está en [frontend-design-system.md](frontend-design-system.md). Este documento define producto, rutas y límites de datos; el Design System no contiene lógica de dominio.
