# Workspace de inteligencia de casos

## Estado

**Preparación visual limitada.** El backend dispone de entidades, API de casos
y pertenencia documental, pero el frontend ofrece `/cases` únicamente como
estado vacío honesto; no hay listado, creación, selección, datos ni rutas
dinámicas conectadas.

## Navegación principal objetivo

1. Inicio.
2. Asistente jurídico.
3. Casos.
4. Biblioteca jurídica.
5. Matrices HPN y Red jurídica como herramientas globales actuales.
6. Modelos locales.

El Asistente jurídico conserva el Chat general. Casos reúne el análisis de un expediente. Biblioteca jurídica conserva documentos y búsqueda. Procesamiento concentra cola, extracción e índices. Modelos mantiene el runtime local.

## Ruta y secciones de un caso

Ruta futura conceptual: `/cases/:caseId`. No está implementada.

| Sección | Propósito | Estado tras 12E-2 |
| --- | --- | --- |
| Resumen | Estado, alertas, revisiones y últimos artefactos. | Planificada |
| Expediente | Documentos asociados, retención y elegibilidad. | Backend implementado; frontend pendiente |
| Matriz HPN | Versiones HPN y revisión humana. | Migración planificada desde HPN global |
| Red | Proyección NetworkX/PyVis de la versión HPN seleccionada. | Migración planificada desde Red global |
| Métricas | Indicadores técnicos y cobertura, sin interpretación jurídica automática. | Planificada |
| Simulaciones | Escenarios explícitos y comparables, no predicciones ni decisiones. | Planificada |
| Asistente | Conversación limitada al caso y a evidencia elegible. | Planificada |
| Auditoría | Ejecuciones, checkpoints, versiones y decisiones humanas. | Planificada |

## Transición de rutas actuales

- `/matrices-hpn` y `/matrices-hpn/:matrixId` permanecen como **legado operativo**.
- `/legal-network` y `/legal-network/:matrixId` permanecen como **legado operativo**.
- Cuando exista la asociación HPN de caso, las nuevas matrices podrán nacer
  dentro de un caso; el mero núcleo `Case` no las vincula.
- Las matrices históricas se vincularán solo mediante migración explícita o asignación humana.
- Tras lograr equivalencia funcional, las rutas globales podrán mostrar aviso y redirigir a la ruta de caso correspondiente; las matrices no vinculadas conservarán una vista de legado.
- No hay redirecciones ni retiros en 12E-2.

## Reglas de experiencia

- El encabezado muestra caso, estado, retención y revisión, no identificadores internos.
- Cada pestaña mantiene estados loading, empty, error, stale y read-only.
- `archived` permite lectura y exportación segura, no edición.
- Las advertencias de fuentes stale/unavailable no se ocultan.
- La alternativa textual es obligatoria para grafos y métricas visuales.
- Acciones costosas declaran alcance, progreso real, cancelación y consecuencias.
- No se usa `dangerouslySetInnerHTML` con contenido de dominio.

## PC y accesibilidad

La validación futura se concentra en PC y ventanas redimensionables de 1024px
a 2560px. Zoom, teclado, foco y scroll controlado siguen siendo requisitos; la
adaptación móvil y el Drawer móvil no son criterios de cierre. El párrafo de
diseño histórico siguiente no habilita una validación móvil obligatoria.

En escritorio, navegación del caso secundaria y contenido principal. En móvil, selector de sección accesible sin perder contexto. Foco visible, navegación por teclado, regiones con nombre, anuncios de estados asíncronos y targets táctiles se mantienen como requisitos de cierre.
