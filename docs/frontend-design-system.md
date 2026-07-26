# Design System frontend — Fase 11D-1

**Estado:** implementación estática completada; validación interactiva y visual
diferida a 11D-5.

Este documento describe la API estable del núcleo visual. Las decisiones de
producto, arquitectura de información y secuencia completa de frontend se
mantienen en
[`frontend-product-architecture.md`](frontend-product-architecture.md).

## Filosofía

El sistema de diseño ofrece una base local, reutilizable, responsive y
accesible sin incorporar lógica jurídica. Sus componentes renderizan texto
React normal, trabajan con variantes cerradas y no acceden a API,
almacenamiento, modelos, variables de backend ni estado global.

Principios:

- semántica HTML antes que ARIA;
- contratos visuales expresados mediante tokens semánticos;
- mobile-first y adaptación por contenedor;
- interacción completa por teclado y objetivos táctiles de al menos 44 px;
- estados comprensibles sin depender solo del color;
- composición explícita en lugar de numerosas propiedades booleanas;
- operación offline, sin telemetría ni recursos remotos.

## Capas

```text
tokens
  ↓
primitives + icons
  ↓
layout-primitives + composites
  ↓
patterns
  ↓
features futuras
```

`design-system` no importa páginas, features ni componentes de producto. Las
features futuras podrán consumir su API pública desde `src/design-system/index.ts`;
no deben importar archivos CSS internos ni `design-system/internal`.

La organización interna es:

- `primitives/`: controles y elementos visuales básicos;
- `composites/`: Card, Alert, Modal, Drawer, Tabs, Tooltip, Skeleton,
  EmptyState, ErrorState y FormField;
- `layout-primitives/`: Container, Stack, Inline, ResponsiveGrid y Cluster;
- `patterns/`: únicamente AsyncContent y PageHeader;
- `icons/` y `tokens/`: recursos visuales reutilizables;
- `internal/`: utilidades privadas, no exportadas desde la API pública.

## Tokens

Los tokens se cargan una sola vez desde `tokens/index.css` en el punto de
entrada. Están separados por responsabilidad:

- `colors.css`: paleta interna y colores semánticos;
- `typography.css`: familias, tamaños adaptables, alturas y pesos;
- `spacing.css`: escala espacial y densidad de controles;
- `sizing.css`: controles, iconos, objetivos táctiles y anchos de contenido;
- `radii.css`, `shadows.css`, `motion.css` y `layers.css`;
- `breakpoints.css`: contrato documental de viewport y contenedores;
- `themes.css`: light, dark y preferencia del sistema.

Los componentes consumen nombres como `--color-surface`,
`--color-text-primary`, `--color-border`, `--color-action-primary` y
`--color-status-danger`. La paleta física no forma parte de la API de los
componentes.

## Temas y densidad

El tema explícito se aplica al elemento raíz:

```html
<html data-theme="light">
<html data-theme="dark">
```

Sin atributo, `prefers-color-scheme` selecciona el tema del sistema. No existe
todavía persistencia ni pantalla de preferencias.

La densidad se controla con `data-density="comfortable"` o
`data-density="compact"`. El modo compacto reduce el padding, pero conserva en
todo caso la altura mínima y los objetivos interactivos de 44 × 44 px. No
persiste preferencias ni cambia según el tipo de puntero.

## Responsividad

Los rangos documentales son 360–479 px, 480–767 px, 768–1023 px,
1024–1439 px y desde 1440 px. Los layouts son mobile-first. `ResponsiveGrid` y
`PageHeader` emplean container queries porque su composición depende del ancho
local. Las preferencias globales, como reducción de movimiento y tema, usan
media queries.

Los textos rompen línea, los grupos de acciones envuelven, los modales se
adaptan a pantalla completa en móvil y ninguna primitiva requiere hover.

## API pública disponible

### Primitivas

- `Button`, `IconButton`;
- `TextInput`, `Textarea`, `Select`;
- `Checkbox`, `Radio`, `Switch`;
- `Badge`, `Spinner`, `Divider`, `VisuallyHidden`;
- `Text`, `Heading`, `Surface`;
- iconos mínimos `CloseIcon`, `InfoIcon` y `ChevronDownIcon`.

### Layout

- `Container`: anchos reading, standard, wide y fluid;
- `Stack`: flujo vertical y gaps cerrados;
- `Inline`: flujo horizontal, wrap y colapso móvil optativo;
- `ResponsiveGrid`: columnas automáticas por ancho del contenedor;
- `Cluster`: grupos adaptables de acciones o badges.

### Componentes

- `Card`, `Alert`;
- `Modal`, `Drawer`;
- `Tabs`, `Tooltip`;
- `Skeleton`, `EmptyState`, `ErrorState`;
- `FormField`.

### Patrones

- `AsyncContent`;
- `PageHeader`.

`ProfessionalReviewNotice` no pertenece al Design System: es un componente
compartido del producto jurídico y se exporta desde `src/components`.

## Composición

Ejemplo de campo accesible:

```tsx
<FormField label="Título" required error={errorMessage}>
  {(fieldProps) => <TextInput {...fieldProps} />}
</FormField>
```

Ejemplo de estado asíncrono:

```tsx
<AsyncContent status={status} presentations={{ offline: offlineNotice }}>
  {content}
</AsyncContent>
```

Ejemplo de acciones responsive:

```tsx
<Inline gap="sm" collapseOnSmall>
  <Button>Continuar</Button>
  <Button variant="secondary">Cancelar</Button>
</Inline>
```

Las presentaciones inyectables reciben nodos React, nunca HTML. El reintento
pertenece a la feature: `AsyncContent` no reintenta automáticamente.

## Contratos de interacción

- `Button` se deshabilita durante `loading` y conserva texto accesible.
- `IconButton` exige `aria-label` en su tipo público.
- controles de formulario reenvían ref y aceptan atributos ARIA nativos;
- `FormField` genera IDs neutrales con `useId()`, compone descripción, error,
  éxito y contador, conserva `aria-invalid` aportado por el consumidor e
  impide combinar error y éxito en su contrato tipado;
- `Modal` y `Drawer` usan `<dialog>`, Escape y devolución de foco; el cierre
  exterior solo puede bloquearse con una razón accesible obligatoria;
- solo se admite una superficie modal activa por flujo; el consumidor debe
  cerrar la actual antes de abrir otra y no puede apilar diálogos;
- `Tabs` implementa tablist, tab, tabpanel, roving tabindex, flechas, Home, End
  y activación automática o manual; sus asociaciones conservan identificadores
  internos estables cuando los elementos cambian de orden;
- `Tooltip` funciona con foco y hover, cierra con Escape y admite solo texto.

## Accesibilidad

El objetivo es WCAG 2.2 AA. La implementación incluye foco visible, controles
nativos, labels clicables, mensajes asociados, contenido no dependiente de
color, targets táctiles, reduced motion, retorno de foco y layouts compatibles
con crecimiento de texto y zoom.

La auditoría estática calculó contraste sRGB de combinaciones principales. En
tema claro se obtuvieron 18.20:1 y 7.64:1 para texto primario y secundario sobre
superficie, 3.74:1 para el borde de control, 4.90:1 para foco y entre 5.89:1 y
7.26:1 para estados. En tema oscuro se obtuvieron 15.13:1 y 9.88:1 para texto,
3.41:1 para borde, 7.74:1 para foco, 4.92:1 para el botón primario y entre
6.75:1 y 7.62:1 para estados. Estos cálculos verifican los pares declarados en
tokens; no sustituyen una comprobación del resultado renderizado.

La validación interactiva automatizada permanece pendiente porque el proyecto
no declara Vitest ni React Testing Library. No se instalaron dependencias. En
11D-5 se deben comprobar en navegador teclado, foco, Escape, retorno de foco,
lector de pantalla, responsive desde 360 px, zoom al 200 %, contraste final
renderizado, posicionamiento de Tooltip y compatibilidad real de `<dialog>`.

## Cierre de la auditoría estática

La auditoría corrigió los contratos incompatibles de `FormField`, `Alert`,
`AsyncContent`, `Modal` y `Drawer`; estabilizó la asociación ARIA y el foco de
`Tabs`; aseguró la semántica de iconos; corrigió la adaptación por contenedor
de `PageHeader`; y ajustó tamaños de diálogo, densidad y tokens que no cumplían
los contrastes objetivo. Los barridos estáticos no encontraron llamadas de
red, almacenamiento del navegador, HTML interpretado, telemetría, colores
fuera de tokens, rutas antiguas, clases CSS inexistentes ni ciclos evidentes.

11D-1 queda completada en implementación estática. Esto no equivale a una
validación interactiva o visual. 11D-2 y 11D-3 están completadas en alcance
estático; 11D-4 es el siguiente bloque autorizado y la Fase 11 continúa en
desarrollo.

## Consumo desde el App Shell

11D-2 consume la API pública sin incorporar contratos de aplicación al núcleo.
El shell reutiliza `Button`, `IconButton`, `Drawer`, `Container`,
`Stack`, `PageHeader`, `Card`, estados, textos e iconos centralizados. Los
componentes de navegación, marca y breadcrumbs permanecen en `src/components`;
los layouts de aplicación permanecen en `src/layouts`.

El Design System no importa navegación, producto, router, páginas ni layouts
de aplicación. El estado responsive del shell tampoco modifica los tokens ni
persiste tema, densidad o dimensiones.

## Seguridad y privacidad

El núcleo no utiliza `dangerouslySetInnerHTML`, `eval`, `new Function`,
`document.write`, URLs externas, telemetría, API, `localStorage` ni contenido
jurídico. Alertas, tooltips, diálogos y estados renderizan sus props como nodos
React, no como HTML interpretado. `ErrorState` está diseñado para mensajes
curados y no para tracebacks o payloads crudos.

## Política de `className`

La API acepta `className` como punto de composición controlado. No sustituye
variantes, tamaños, semántica ni estados ARIA. Una feature no debe usarlo para
redefinir targets táctiles, ocultar foco o alterar el significado de estados.

## Límites de alcance

Permanecen fuera de 11D-1:

- App Shell, sidebar, topbar y navegación principal, implementados después en
  11D-2 sin incorporarse al núcleo visual;
- cliente API compartido y notificaciones globales, implementados después en
  11D-3 sin incorporarse al núcleo visual;
- componentes de documentos, recuperación, chat, citas, HPN y red jurídica;
- iframe PyVis y alternativa textual del grafo;
- autenticación, cuentas, permisos y persistencia de sesión;
- pantalla de preferencias; 11D-3 solo incorpora persistencia allowlisted de
  tema y densidad.

Los elementos todavía pendientes requieren 11D-4, 11D-5 o una autorización
futura.

## Límites con componentes de producto y features

`src/components` contiene componentes compartidos entre dos o más features o
por el shell que conocen el producto y se construyen sobre el Design System.
11D-1 incorporó `ProfessionalReviewNotice`; 11D-2 añadió marca, navegación,
breadcrumbs y skip link. El núcleo visual no los importa ni los reexporta.

Los componentes específicos permanecen en
`src/features/<feature>/components`. Una feature puede importar el Design
System, componentes compartidos del producto, hooks, API, tipos y utilidades
compartidas, pero no internals de otra feature ni de `design-system/internal`.

`src/layouts` queda reservado para distribuciones futuras de aplicación y
página; no contiene primitivas visuales del Design System. `src/utils` queda
reservado para funciones neutrales compartidas por la aplicación.

## Extensibilidad

Un componente nuevo debe demostrar al menos dos usos compatibles o un contrato
transversal claro. Debe consumir tokens semánticos, ofrecer variantes cerradas,
evitar dependencias de features y documentar teclado, ARIA, responsive,
privacidad y estados. Los componentes de dominio se ubican en su feature y no
se incorporan al núcleo hasta demostrar reutilización neutral.

## Cambios incompatibles

Se considera breaking change eliminar o renombrar exports, variantes, tokens
semánticos o comportamientos de teclado; cambiar el significado de un estado;
reducir accesibilidad; o alterar la estructura requerida por consumidores. Un
cambio incompatible exige entrada en `CAMBIOS.md`, migración de consumidores,
validación de build y revisión de accesibilidad. Añadir una variante optativa y
compatible no es breaking si conserva el contrato existente.
