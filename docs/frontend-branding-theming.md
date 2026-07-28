# Marca y apariencia frontend

La apariencia (`light`, `dark` o `system`) es una preferencia local de la
persona usuaria. La marca es una configuración de instalación; no existe un
selector de marca ni una configuración remota.

`frontend/src/config/branding.ts` centraliza nombre, descripción, etiqueta de
entorno, logos opcionales, favicon y preset. `product.config.ts` solo conserva
compatibilidad de importación. Si no hay recurso de logo, `AppBrand` usa el SVG
del sistema como fallback; los recursos declarados deben ser locales y seguros.

Los tokens base de marca son `--brand-primary`, `--brand-primary-hover`,
`--brand-secondary` y `--brand-accent`. Componentes y features usan tokens
semánticos (`--color-canvas`, superficies, textos, bordes, acciones, foco y
estados), no colores corporativos directos. El preset `local-green` declara
valores light y dark; un nuevo preset se registra en esa configuración sin
cambiar componentes.

El provider existente guarda únicamente apariencia y densidad. En sistema
escucha `prefers-color-scheme`; la elección explícita prevalece. La topbar
incluye un control accesible Claro, Oscuro y Sistema. No se almacenan datos
documentales. El script inicial resuelve la apariencia antes de React.

Ruta, etiqueta e icono viven juntos en
`app/navigation/navigation.config.ts`; sidebar y Drawer usan la misma fuente.
Los iconos SVG son decorativos y los enlaces mantienen nombre accesible.

No están implementados panel administrativo, carga de marca remota ni
multiempresa. Una evolución futura deberá conservar presets locales tipados,
assets verificados y separación entre apariencia de usuario y marca.
