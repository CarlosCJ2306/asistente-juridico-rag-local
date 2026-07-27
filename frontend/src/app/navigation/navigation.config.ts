import { HomeIcon, NavigationIcon } from "../../design-system";

import type { NavigationSection } from "./navigation.types";

export const navigationSections: ReadonlyArray<NavigationSection> = [
  {
    id: "work",
    label: "Trabajo",
    items: [
      { id: "home", label: "Inicio", route: "/", icon: HomeIcon, availability: "active", matchStrategy: "exact" },
      { id: "documents", label: "Documentos", route: "/documents", icon: NavigationIcon, availability: "active", matchStrategy: "prefix", detailLabel: "Detalle" },
      { id: "search", label: "Búsqueda", route: "/search", icon: NavigationIcon, availability: "hidden", matchStrategy: "prefix" },
      { id: "chat", label: "Chat jurídico", route: "/chat", icon: NavigationIcon, availability: "hidden", matchStrategy: "prefix" },
    ],
  },
  {
    id: "analysis",
    label: "Análisis",
    items: [
      { id: "hpn", label: "Matrices HPN", route: "/matrices-hpn", icon: NavigationIcon, availability: "active", matchStrategy: "prefix", detailLabel: "Detalle" },
      { id: "legal-network", label: "Red jurídica", route: "/legal-network", icon: NavigationIcon, availability: "active", matchStrategy: "prefix", detailLabel: "Red" },
    ],
  },
  {
    id: "system",
    label: "Sistema",
    items: [
      { id: "notifications", label: "Notificaciones", route: "/notifications", icon: NavigationIcon, availability: "hidden", matchStrategy: "prefix" },
      { id: "system-status", label: "Estado del sistema", route: "/system/status", icon: NavigationIcon, availability: "hidden", matchStrategy: "prefix" },
      { id: "settings", label: "Configuración", route: "/settings", icon: NavigationIcon, availability: "hidden", matchStrategy: "prefix" },
    ],
  },
];
