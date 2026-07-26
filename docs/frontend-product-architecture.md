# Arquitectura de producto frontend — Fase 11D-0

**Estado:** 11D-0 a 11D-4 completadas en su alcance estático; 11D-5 pendiente.

**Alcance vigente:** definir la arquitectura de producto, experiencia de uso,
sistema de diseño y responsividad antes de iniciar cambios en React. Los bloques
11A y 11B están completados. El bloque 11C está completado en su alcance de
backend y seguridad; su integración real en navegador se verificará en 11D-5.
La Fase 11 continúa en desarrollo. La validación interactiva y visual acumulada
se mantiene diferida a 11D-5.

## 1. Principios de producto

- La aplicación es una herramienta profesional local de apoyo: no decide,
  califica ni sustituye el criterio jurídico humano.
- SQLite continúa como fuente de verdad. FTS5, ChromaDB y cualquier
  visualización son proyecciones derivadas.
- La interfaz debe privilegiar trazabilidad, revisión y estados explícitos por
  encima de automatismos o apariencia de certeza.
- La ausencia, obsolescencia o indisponibilidad de una fuente nunca se oculta
  ni se repara silenciosamente.
- La experiencia debe funcionar sin servicios externos, telemetría, CDN ni
  dependencias de red.
- Esta planificación no autoriza historial persistente, autenticación, nuevas
  decisiones automáticas ni cambios en contratos del backend.

## 2. Realidad actual y límites

El frontend usa React, TypeScript, Vite, React Router y TanStack Query. 11D-1
incorpora tokens, temas, densidad, primitivas, layouts, componentes y patrones
base sin añadir bibliotecas. No existe todavía App Shell, panel jurídico, chat
integrado ni visualización de la red.

11D-0 fue exclusivamente documental. 11D-1 no incorpora autenticación,
persistencia de sesiones, ejecución del HTML PyVis, cambios de API ni páginas
de producto.

## 3. Arquitectura de información

La navegación propuesta se organiza por tareas profesionales, no por detalles
de infraestructura:

| Grupo | Destinos previstos | Propósito |
| --- | --- | --- |
| Inicio | Resumen operativo | Estado general y accesos a tareas, sin contenido sensible en tarjetas globales. |
| Documentos | Registro, detalle, extracción | Gestionar la fuente documental y sus estados. |
| Recuperación | Búsqueda textual, semántica e híbrida | Explorar resultados trazables sin equiparar ranking con certeza jurídica. |
| Análisis asistido | Chat RAG, citas | Consultar con revisión profesional obligatoria y fuentes visibles. |
| Estructuración jurídica | Matrices HPN, red jurídica | Revisar hechos, pruebas, normas, relaciones y advertencias estructurales. |
| Sistema | Salud y modelos locales | Ver disponibilidad y ciclo de vida sin exponer rutas ni configuración sensible. |

La navegación principal debe mostrar únicamente destinos implementados. Los
destinos futuros pueden aparecer en documentación, pero no como controles
activos que sugieran funcionalidad disponible.

### Flujos prioritarios

1. Localizar un documento, revisar su estado y pasar a recuperación.
2. Ejecutar una búsqueda y abrir su trazabilidad documental.
3. Formular una consulta RAG, revisar respuesta y citas sin persistir la
   conversación.
4. Seleccionar una matriz HPN y alternar entre detalle estructurado, red visual
   y alternativa textual accesible.
5. Consultar salud y modelos sin provocar cargas ni efectos secundarios.

## 4. Shell de aplicación y responsividad

El shell propuesto contiene encabezado, navegación, área principal, región de
notificaciones y un panel contextual opcional. Mantiene visible el estado
local/offline y la exigencia de revisión profesional cuando corresponda.

| Entorno | Comportamiento esperado |
| --- | --- |
| Móvil pequeño, 360–479 px | Una columna; navegación futura en panel modal; acciones primarias visibles; tablas transformadas en listas o tarjetas; panel contextual debajo del contenido. |
| Móvil, 480–767 px | Una columna flexible; acciones con wrap; espacio adicional sin activar todavía la navegación de tableta. |
| Tableta, 768–1023 px | Navegación futura compacta; una o dos columnas según espacio real; panel contextual superpuesto o colapsable. |
| Escritorio, 1024–1439 px | Navegación lateral persistente; contenido y panel contextual; densidad cómoda por defecto. |
| Pantalla amplia, desde 1440 px | Ancho de lectura limitado; espacio adicional para comparación o contexto, nunca líneas de texto indefinidamente largas. |

Estos valores son puntos de partida de diseño, no detección de dispositivo. Los
componentes reutilizables deben responder primero al ancho de su contenedor
mediante container queries cuando su composición dependa del espacio local;
los media queries quedan para cambios del shell y capacidades globales.

Reglas transversales:

- ningún flujo esencial depende de hover;
- los controles táctiles conservan un objetivo mínimo de 44 × 44 px;
- las tablas deben preservar encabezados y significado al reordenarse;
- el grafo nunca será la única representación de información;
- zoom del navegador y tamaño de fuente no deben provocar pérdida de acciones;
- movimiento y animación respetan `prefers-reduced-motion`.

## 5. Sistema de diseño propuesto

El sistema se organiza en capas con dependencias descendentes:

1. **Fundamentos:** color semántico, tipografía, escala espacial, radios,
   elevación, movimiento, densidad y breakpoints.
2. **Primitivas:** texto, icono, botón, enlace, campo, selección, checkbox,
   badge, separador y superficie.
3. **Patrones:** formulario, toolbar, tabla/lista adaptable, diálogo, drawer,
   tabs, breadcrumb, paginación, empty state, skeleton y aviso.
4. **Componentes de dominio:** estado documental, referencia de fuente,
   resultado recuperado, respuesta RAG, nodo HPN, advertencia de fuente y
   leyenda del grafo.
5. **Composiciones de página:** documentos, búsqueda, chat, matriz, red y
   sistema.

Los tokens deben usar nombres semánticos —por ejemplo, superficie, texto,
advertencia, crítico, foco y estado de fuente— en lugar de colores ligados a
una pantalla. Los estados no se comunican solo con color.

### Reutilización y personalización

- Las primitivas exponen variantes y tamaños cerrados, estados ARIA y un punto
  de composición documentado.
- `className` puede admitirse en primitivas de layout para composición local,
  pero no debe permitir que una feature redefina contratos de accesibilidad o
  estados semánticos.
- Los componentes de dominio consumen primitivas y tokens; no duplican botones,
  diálogos, manejo asíncrono ni avisos.
- No se crean abstracciones universales antes de existir al menos dos usos
  compatibles y verificables.
- Una biblioteca externa de componentes solo podrá proponerse tras auditar
  accesibilidad, operación offline, peso, mantenimiento y compatibilidad con
  esta jerarquía. 11D-0 no elige una.

## 6. Estructura React propuesta

```text
src/
  api/                 # contratos HTTP compartidos
  components/          # componentes compartidos propios del producto jurídico
  design-system/
    tokens/
    primitives/
    composites/
    layout-primitives/
    patterns/           # patrones genéricos
    icons/
    internal/           # privado; no se importa fuera del Design System
  features/
    <feature>/components/
  hooks/               # hooks neutrales compartidos
  layouts/             # composición futura de aplicación y páginas
  pages/
  router/
  types/
  utils/               # funciones neutrales compartidas
  test/
```

Reglas de dependencia:

- `components` contiene elementos compartidos del producto jurídico que pueden
  depender de `design-system`; no contiene componentes genéricos del núcleo.
- `features` pueden depender de `design-system`, `components`, `api`, `hooks`,
  `types` y `utils`, nunca de otra feature de forma directa.
- `design-system` no depende de `components`, features, páginas ni contratos
  jurídicos. `internal` es privado y no se importa desde fuera del núcleo.
- `layouts` compone distribuciones de aplicación o página, sin convertirse en
  un segundo sistema de componentes. `utils` mantiene funciones neutrales.
- las llamadas HTTP viven junto al contrato de la feature o en el cliente
  compartido, no dentro de componentes puramente visuales;
- no se importan internals de otra feature ni se crean ciclos.

React Router seguirá siendo el límite de navegación. TanStack Query es la
opción ya disponible para estado remoto y caché de servidor, sujeto a una
revisión de claves, invalidación y privacidad en el bloque que lo utilice.
El estado visual y de formulario permanece local mientras no haya una necesidad
demostrada de compartirlo.

## 7. Estado, carga y errores

Cada pantalla separa cuatro categorías:

- **estado remoto:** datos obtenidos del backend, actualización e invalidación;
- **estado de formulario:** valores, validación y envío;
- **estado de interfaz:** paneles, selección visual y foco;
- **preferencias:** tema, densidad y accesibilidad visual permitida.

El patrón `AsyncContent` será un contrato conceptual común con estados
`idle`, `loading`, `success-empty`, `success-data`, `error-retryable` y
`error-terminal`. Debe impedir que una pantalla confunda “sin resultados” con
un fallo o conserve datos obsoletos sin indicarlo. 11D-1 implementa el patrón
genérico `AsyncContent`; las features decidirán sus presentaciones y reintentos.

Los errores del backend se traducen desde un contrato cerrado con código
estable, estado HTTP y `request_id` seguro. La interfaz muestra mensajes
curados por código; nunca presenta traceback, SQL, body crudo, rutas, prompts,
texto generado rechazado ni mensajes libres del servidor. Los códigos
desconocidos producen una explicación genérica y conservan solo el request ID
cuando sea seguro.

## 8. Sesión local y futura autenticación

La primera versión usa una abstracción de sesión local, no una cuenta real:

- `mode: local_anonymous`;
- capacidades derivadas de la disponibilidad local, no de roles simulados;
- sin token, contraseña, cookie de autenticación ni perfil personal;
- una interfaz interna estable permitirá incorporar una sesión autenticada en
  una fase autorizada sin acoplar cada feature al mecanismo futuro.

No deben aparecer pantallas ficticias de inicio de sesión, selector de usuario,
permisos simulados ni afirmaciones de seguridad multiusuario. Si en el futuro
se implementan cuentas, requerirán modelo de amenazas, backend, expiración,
revocación y migración de preferencias expresamente autorizados.

## 9. Chat temporal en memoria

El Chat RAG continúa stateless en el backend. El frontend podrá conservar
durante una pestaña una secuencia temporal de turnos para presentación, con
estas reglas:

- no se envían turnos anteriores como contexto salvo contrato futuro explícito;
- recargar o cerrar la pestaña elimina la conversación;
- no se guarda en `localStorage`, `sessionStorage`, IndexedDB, URL ni logs;
- la interfaz identifica claramente que no hay historial persistente;
- copiar o exportar requiere una acción explícita del usuario y queda fuera de
  11D-0.

## 10. Notificaciones

Se distinguen dos canales:

| Canal | Uso | Ejemplos |
| --- | --- | --- |
| Inmediato y transitorio | Confirmar una acción reciente o un error recuperable | operación completada, reintento disponible |
| Revisable y persistente en pantalla | Mantener advertencias que afectan interpretación o flujo | fuente stale/unavailable, revisión profesional, índice no disponible |

Las notificaciones se deduplican por código y contexto no sensible, tienen
prioridad cerrada, no incluyen contenido documental y no desaparecen
automáticamente cuando requieren una decisión. Las regiones transitorias usan
`aria-live` con moderación; los errores de formulario se asocian directamente
al campo y reciben foco controlado.

## 11. Tema, preferencias y almacenamiento del navegador

Se prevén tema claro, oscuro y sistema, además de densidad, tamaño de texto,
reducción de movimiento y estado de navegación lateral. Solo estas preferencias
de presentación pueden persistirse localmente mediante claves versionadas y
una allowlist estricta.

Nunca se almacenarán en el navegador:

- preguntas, respuestas, prompts, snippets o texto documental;
- UUID, rutas, hashes, fingerprints o nombres internos de colecciones;
- embeddings, vectores, SQL o metadatos de fuentes;
- tokens de autenticación futuros en almacenamiento accesible a JavaScript;
- matrices, nodos o relaciones HPN completas;
- errores crudos o payloads HTTP.

Las preferencias inválidas se descartan de forma conservadora. Ningún dato de
preferencia se sincroniza externamente.

## 12. Accesibilidad

El objetivo mínimo es WCAG 2.2 nivel AA en los flujos implementados:

- HTML semántico, orden de encabezados y landmarks;
- teclado completo, foco visible y devolución de foco tras modales;
- nombres accesibles y descripciones de error;
- contraste suficiente y estados redundantes a color;
- zoom al 200 %, reflow y tamaños táctiles adecuados;
- tablas con encabezados y alternativas compactas comprensibles;
- anuncios no intrusivos de carga, resultados y errores;
- animación reducible;
- pruebas con teclado, lector de pantalla y herramientas automáticas.

La red jurídica tendrá una alternativa textual equivalente con listado de
nodos, relaciones y advertencias. Las métricas se etiquetan como estructurales
y nunca como relevancia o certeza jurídica.

## 13. Seguridad y privacidad frontend

- No se usa `dangerouslySetInnerHTML` con datos dinámicos.
- El HTML PyVis se integrará únicamente en un `iframe` con `sandbox` mínimo,
  origen no confiable y sin `allow-same-origin`; no se habilita navegación,
  formularios, popups ni acceso al documento padre.
- No se usa `postMessage` en la primera integración. Si fuera imprescindible en
  el futuro, requerirá esquema cerrado, origen verificado y datos no sensibles.
- La UI no carga fuentes, scripts, estilos, iconos o telemetría desde Internet.
- Los UUID técnicos pueden viajar en contratos existentes cuando sean
  necesarios para operar, pero no deben convertirse en etiquetas visibles ni
  copiarse a notificaciones, URL o logs.
- La consola no registra payloads, consultas, respuestas, snippets, HTML,
  identificadores, rutas o errores crudos.
- Toda salida textual se renderiza como texto; las citas y referencias usan
  campos tipados y sanitizados.

## 14. Módulo futuro de red jurídica

La feature `legal-graph` consumirá los contratos seguros ya completados en 11B
y 11C. La vista propuesta incluye selector de matriz, resumen estructural,
leyendas, advertencias, visualización aislada y alternativa textual.

- En escritorio, grafo y panel accesible pueden coexistir.
- En tableta, el panel es colapsable y conserva controles fuera del iframe.
- En móvil, la alternativa textual es primaria y el grafo es una vista
  secundaria optativa.
- Una matriz `archived` se muestra en modo de solo lectura.
- Estados `stale` y `unavailable` permanecen visibles como advertencias.
- No se interpreta grado, centralidad, caminos o componentes como conclusiones
  jurídicas.

La integración real del HTML PyVis, CSP, sandbox, operación offline y
accesibilidad en navegador pertenece a 11D-5.

## 15. División de la Fase 11D

### 11D-0 — Arquitectura de producto y sistema de diseño

- **Objetivo:** acordar la arquitectura de información, UX/UI, responsividad,
  capas de componentes, estado, privacidad y secuencia de implementación.
- **Alcance:** este documento rector y referencias coherentes en la
  documentación general.
- **Fuera de alcance:** código, dependencias, prototipos ejecutables y cambios
  de API.
- **Entregables:** decisiones documentadas, inventario de capas, reglas de
  dependencias, límites de almacenamiento y desglose 11D-1 a 11D-5.
- **Dependencias:** 11A y 11B completadas; 11C completada en backend y
  seguridad.
- **Riesgos:** documentar una interfaz inexistente como implementada o fijar
  prematuramente una biblioteca.
- **Pruebas:** revisión documental de coherencia, privacidad, accesibilidad y
  ausencia de afirmaciones de implementación.
- **Cierre:** criterios de la sección 16 aprobados antes de autorizar 11D-1.

### 11D-1 — Design System y componentes base

- **Objetivo:** implementar tokens, primitivas esenciales, layouts y patrones
  asíncronos accesibles y responsive.
- **Alcance:** temas, densidad, foco, errores públicos y componentes base.
- **Fuera de alcance:** flujos jurídicos completos, grafo PyVis y persistencia
  de chat.
- **Entregables:** fundamentos, API pública y catálogo verificable de
  componentes.
- **Dependencias:** cierre explícito de 11D-0 y auditoría de dependencias ya
  instaladas.
- **Riesgos:** componentes inaccesibles, exceso de abstracción y estilos
  divergentes.
- **Pruebas:** unitarias, accesibilidad automática, teclado, responsividad y
  build estático.
- **Cierre:** tokens, componentes y estados asíncronos validados en los rangos
  documentales, sin duplicación ni dependencias de dominio.

### 11D-2 — App Shell, navegación y layouts responsive

- **Objetivo:** construir el armazón profesional que alojará los flujos
  funcionales sin implementarlos todavía.
- **Alcance:** marca local, configuración central de navegación, skip link,
  sidebar, topbar, Drawer móvil, breadcrumbs, layouts de página y 404.
- **Fuera de alcance:** páginas funcionales de documentos, búsqueda, chat,
  HPN, red, notificaciones, sesión, autenticación y cambios de backend.
- **Entregables:** shell mobile-first, navegación basada en disponibilidad
  cerrada, ruta existente preservada y layouts reutilizables.
- **Dependencias:** 11D-1 y React Router vigente.
- **Riesgos:** enlaces a módulos inexistentes, divergencia entre navegación
  móvil y escritorio, pathname sensible, overflow y pérdida de foco.
- **Pruebas:** TypeScript, ESLint, build, imports, rutas y barridos estáticos;
  interacción real diferida a 11D-5 por ausencia de runner de navegador.
- **Cierre:** shell implementado sin rutas ficticias, datos simulados,
  almacenamiento web ni lógica de dominio.

### 11D-3 — Servicios compartidos del frontend

- **Objetivo:** establecer cliente API, errores seguros, composición de
  providers, sesión local, preferencias visuales, conectividad y notificaciones
  efímeras sin implementar flujos jurídicos.
- **Alcance:** health sobre el cliente común, QueryClient único, contratos
  cerrados, tema y densidad, allowlist de almacenamiento y límites globales de
  error y conectividad.
- **Fuera de alcance:** cuentas, autenticación, documentos, búsqueda, chat,
  HPN, red jurídica, historial y nuevas rutas.
- **Entregables:** infraestructura tipada y neutral reutilizable por los
  siguientes bloques.
- **Dependencias:** 11D-1 y 11D-2.
- **Riesgos:** tratar capacidades de UI como autorización, persistir datos
  sensibles o exponer respuestas técnicas.
- **Pruebas:** ESLint, TypeScript, build y barridos estáticos; interacción,
  timers, storage y navegador se difieren a 11D-5.
- **Cierre:** cliente y providers únicos, errores sanitizados y almacenamiento
  limitado exclusivamente a tema, densidad y versión de esquema.

### 11D-4 — Matriz HPN

- **Objetivo:** ofrecer edición y revisión manual de matrices, nodos, fuentes y
  relaciones conforme a la Fase 10.
- **Alcance:** estados, formularios, relaciones compatibles, borrado lógico,
  warnings de fuentes y modo archived.
- **Fuera de alcance:** inferencia jurídica, reparación automática y red
  visual.
- **Entregables:** flujos HPN accesibles y adaptables, con confirmaciones y
  errores seguros.
- **Dependencias:** 11D-1 y API HPN vigente.
- **Riesgos:** perder cambios, ocultar stale/unavailable o confundir revisión
  humana con validación automática.
- **Pruebas:** reglas de estado, formularios, concurrencia observable,
  accesibilidad, privacidad y solo lectura.
- **Cierre:** los contratos HPN se respetan y ninguna etiqueta atribuye valor
  jurídico automático.

### 11D-5 — Red jurídica, PyVis y validación integral

- **Objetivo:** integrar la API JSON y exportación PyVis en una experiencia
  local, segura y accesible.
- **Alcance:** selector de matriz, iframe restringido, alternativa textual,
  leyendas, advertencias y validación real en navegador.
- **Fuera de alcance:** edición dentro del grafo, persistencia gráfica,
  simulación y conclusiones automáticas.
- **Entregables:** módulo responsive, validación offline de 11C, pruebas de CSP
  y sandbox, validador integral y cierre documental.
- **Dependencias:** 11D-1, 11D-4 y contratos 11A–11C.
- **Riesgos:** XSS, pérdida de accesibilidad, recursos remotos, aislamiento
  insuficiente o fuga de identificadores.
- **Pruebas:** navegador real local, seguridad HTML, teclado, lector de
  pantalla, responsividad, privacidad, cleanup y ausencia de red.
- **Cierre:** representación visual y textual equivalentes, PyVis offline
  aislado, 11C verificada en navegador y Fase 11 validada integralmente.

## 16. Criterios de aceptación de 11D-0

11D-0 quedó completada al verificarse que:

- exista una sola arquitectura de información y una sola secuencia 11D vigente;
- se documenten desktop, tableta, móvil y pantalla amplia, junto con container
  queries para componentes;
- la jerarquía de tokens, primitivas, patrones, dominio y páginas sea explícita;
- las reglas de dependencias React impidan acoplamiento entre features;
- estado remoto, formularios, UI, preferencias, sesión y notificaciones estén
  separados conceptualmente;
- la sesión local no simule autenticación ni permisos inexistentes;
- el chat temporal no persista ni reutilice historial como contexto;
- exista una allowlist de preferencias y una prohibición explícita de datos
  sensibles en almacenamiento del navegador;
- errores, accesibilidad, privacidad, iframe PyVis y operación offline tengan
  reglas verificables;
- cada bloque 11D-1 a 11D-5 tenga objetivo, alcance, exclusiones, entregables,
  dependencias, riesgos, pruebas y criterio de cierre;
- la documentación no afirme que el frontend profesional ya está implementado;
- 11D-1 requiriera una aprobación separada antes de iniciar su implementación.

## 17. Estado de implementación de 11D-1

11D-1 está completada en implementación estática. Su API y reglas de extensión se
documentan en [`frontend-design-system.md`](frontend-design-system.md). La
integración se limita a cargar tokens globales y adaptar los estilos de la
pantalla inicial existente; no incorpora App Shell, rutas o páginas nuevas.
La corrección estructural separa `composites`, `layout-primitives` e `internal`
dentro del núcleo, y traslada `ProfessionalReviewNotice` a `src/components`.

La auditoría estática confirmó dependencias, API pública, tokens, contrastes
declarados, responsividad estructural, accesibilidad tipada y ausencia de APIs
inseguras. La interacción real, teclado, foco, Escape, lectores de pantalla,
contraste renderizado, reflow, zoom y `<dialog>` se validarán en 11D-5. 11D-2
fue implementada y auditada posteriormente en su alcance estático.

## 18. Estado de implementación de 11D-2

11D-2 implementa el armazón profesional sin añadir funciones jurídicas: un
`AppLayout` con skip link, sidebar persistente desde escritorio, topbar,
Drawer móvil, un único `<main>` y `Outlet` de React Router. La configuración
tipada de navegación es la única fuente para sidebar, navegación móvil, título
de sección y breadcrumbs seguros.

Durante 11D-2 la única ruta funcional activa era `/`, cuya consulta de salud se
preservó. Documentos, Búsqueda, Chat jurídico, Matrices HPN, Red jurídica,
Notificaciones, Estado del sistema y Configuración están declarados como
reservas ocultas en ese bloque: no se renderizaban ni generaban enlaces. 11D-4
activó posteriormente Matrices HPN; las demás reservas continúan ocultas. No
hay rutas planeadas visibles. La ruta comodín presenta un 404 seguro sin
repetir el pathname.

`ContentLayout`, `FullWidthLayout` y `SplitPanelLayout` construyen sobre las
primitivas del Design System. El último se apila por defecto y cambia a una de
tres proporciones cerradas mediante container query. El estado del shell se
limita al colapso local del sidebar y la apertura del Drawer; no usa Context,
almacenamiento ni persistencia.

La auditoría estática corrigió el cierre del Drawer al cruzar a escritorio, el
reflow global con zoom, la semántica de breadcrumbs y paneles, la ayuda visual
compacta, el wrap de topbar y la inmutabilidad de configuración. Teclado real,
retorno de foco, Drawer, responsive desde 360 px, orientación, zoom al 200 %,
lector de pantalla y navegadores se comprobarán en 11D-5. 11D-2 queda
completada en implementación estática; 11D-3 fue autorizada, implementada y
auditada posteriormente en el mismo alcance.

## 19. Estado de implementación de 11D-3

11D-3 está completada en implementación estática. `AppProviders` compone el límite de
errores, preferencias, sesión local, TanStack Query y notificaciones en memoria.
La sesión `local` no contiene usuario, credenciales ni tokens; el modo
`authenticated` queda reservado como contrato futuro. Las capacidades sirven
solo para adaptación futura de la interfaz y nunca sustituyen autorización del
backend.

El cliente API nativo valida la base configurada, construye URLs y queries de
forma cerrada, soporta JSON, `FormData`, cancelación y timeout, y normaliza
errores sin mostrar cuerpos libres. `/api/health` conserva una única
implementación sobre este cliente. Las preferencias permiten únicamente tema y
densidad en una clave versionada de `localStorage`; sesión, capacidades,
notificaciones y contenido jurídico permanecen fuera del almacenamiento.

Las notificaciones tienen IDs efímeros, deduplicación, límites y timers con
cleanup, sin persistencia. El indicador offline distingue conectividad del
navegador de salud del backend. No se añadieron rutas ni funciones de dominio.
La interacción real, timers, bloqueo de storage, foco, lector de pantalla y
responsive visual continúan diferidos a 11D-5. 11D-4 fue implementada después
de este bloque.

## 20. Estado de implementación de 11D-4

11D-4 está completada en implementación estática. La ruta `/matrices-hpn` ofrece listado
paginado y creación; `/matrices-hpn/:matrixId` ofrece detalle, actualización y
borrado. Dentro del detalle se administran nodos y relaciones conforme a los
cuatro tipos dirigidos del backend, se presentan estados de revisión y fuentes
vinculadas, y se permite su desvinculación. `archived` bloquea la modificación
del contenido, nodos, relaciones y fuentes; la eliminación de la matriz completa
sigue disponible conforme al contrato backend.

La feature mantiene tipos y guards propios, API sobre el cliente compartido,
keys y hooks de TanStack Query, componentes y páginas. Las respuestas se
rechazan íntegramente cuando no cumplen el contrato mínimo. No hay optimistic
updates, estado remoto duplicado, almacenamiento del navegador, datos simulados
ni contenido HPN en notificaciones.

La creación de vínculos de fuente se omite deliberadamente: aunque existe el
endpoint backend, requiere `document_id` y `chunk_index`; no existe todavía un
selector documental frontend autorizado y mostrar o pedir un UUID violaría la
arquitectura de privacidad. La consulta de validación separada tampoco se
duplica porque el detalle devuelve `validation_summary`.

Matrices HPN permanece en navegación activa. Red jurídica permanece oculta y no se
registran rutas de grafo, exportación o PyVis. ESLint, TypeScript y build Vite
son las garantías estáticas de este bloque; interacción, teclado, foco,
responsive real, zoom, lector de pantalla y comunicación con backend se
validarán en 11D-5. La auditoría estática comprobó además códigos HTTP exactos,
el enum documental completo, paginación estable, mutations controladas y los
once contadores backend sin agregación superpuesta. Los identificadores HPN
solo permanecen en href, keys y requests técnicos; no se muestran como
contenido o nombre accesible.
