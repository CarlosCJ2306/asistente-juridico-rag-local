import { ChatIcon, DocumentIcon, HomeIcon, MatrixIcon, ModelIcon, NavigationIcon, NetworkIcon } from "../../design-system";

import type { NavigationSection } from "./navigation.types";

export const navigationSections: ReadonlyArray<NavigationSection> = [
  {
    id: "work",
    label: "Trabajo",
    items: [
      { id: "home", label: "Inicio", route: "/", icon: HomeIcon, availability: "active", matchStrategy: "exact" },
      { id: "chat", label: "Asistente jurídico", route: "/chat", icon: ChatIcon, availability: "active", matchStrategy: "prefix" },
      { id: "cases", label: "Casos", route: "/cases", icon: NavigationIcon, availability: "active", matchStrategy: "exact" },
    ],
  },
  {
    id: "knowledge",
    label: "Conocimiento",
    items: [
      { id: "documents", label: "Biblioteca jurídica", route: "/documents", icon: DocumentIcon, availability: "active", matchStrategy: "prefix", detailLabel: "Detalle" },
    ],
  },
  {
    id: "tools",
    label: "Herramientas actuales",
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
    ],
  },
];
