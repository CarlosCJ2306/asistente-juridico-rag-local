import { ChatIcon, DocumentIcon, HomeIcon, MatrixIcon, ModelIcon, NetworkIcon, SearchIcon, SettingsIcon } from "../../design-system";

import type { NavigationSection } from "./navigation.types";

export const navigationSections: ReadonlyArray<NavigationSection> = [
  {
    id: "work",
    label: "Trabajo",
    items: [
      { id: "home", label: "Inicio", route: "/", icon: HomeIcon, availability: "active", matchStrategy: "exact" },
      { id: "documents", label: "Documentos", route: "/documents", icon: DocumentIcon, availability: "active", matchStrategy: "prefix", detailLabel: "Detalle" },
      { id: "search", label: "Búsqueda", route: "/search", icon: SearchIcon, availability: "hidden", matchStrategy: "prefix" },
      { id: "chat", label: "Chat jurídico", route: "/chat", icon: ChatIcon, availability: "hidden", matchStrategy: "prefix" },
    ],
  },
  {
    id: "analysis",
    label: "Análisis",
    items: [
      { id: "hpn", label: "Matrices HPN", route: "/matrices-hpn", icon: MatrixIcon, availability: "active", matchStrategy: "prefix", detailLabel: "Detalle" },
      { id: "legal-network", label: "Red jurídica", route: "/legal-network", icon: NetworkIcon, availability: "active", matchStrategy: "prefix", detailLabel: "Red" },
    ],
  },
  {
    id: "system",
    label: "Sistema",
    items: [
      { id: "models", label: "Modelos locales", route: "/models", icon: ModelIcon, availability: "active", matchStrategy: "exact" },
      { id: "notifications", label: "Notificaciones", route: "/notifications", icon: SettingsIcon, availability: "hidden", matchStrategy: "prefix" },
      { id: "system-status", label: "Estado del sistema", route: "/system/status", icon: SettingsIcon, availability: "hidden", matchStrategy: "prefix" },
      { id: "settings", label: "Configuración", route: "/settings", icon: SettingsIcon, availability: "hidden", matchStrategy: "prefix" },
    ],
  },
];
