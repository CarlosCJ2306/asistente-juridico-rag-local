import { navigationSections } from "./navigation.config";
import type { BreadcrumbItem, NavigationItemConfig, NavigationSection } from "./navigation.types";

function withoutQueryOrHash(locationValue: string): string {
  const suffixIndex = locationValue.search(/[?#]/);
  return suffixIndex === -1 ? locationValue : locationValue.slice(0, suffixIndex);
}

export function matchesNavigationPath(item: NavigationItemConfig, locationValue: string): boolean {
  const pathname = withoutQueryOrHash(locationValue);
  if (item.matchStrategy === "exact") return pathname === item.route;
  return pathname === item.route || pathname.startsWith(`${item.route}/`);
}

export function getVisibleNavigationSections(): ReadonlyArray<NavigationSection> {
  return navigationSections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => item.availability !== "hidden"),
    }))
    .filter((section) => section.items.length > 0);
}

export function getActiveNavigationItem(pathname: string): NavigationItemConfig | undefined {
  return navigationSections
    .flatMap((section) => section.items)
    .filter((item) => item.availability === "active")
    .find((item) => matchesNavigationPath(item, pathname));
}

export function getSectionTitle(pathname: string): string {
  return getActiveNavigationItem(pathname)?.label ?? "Página no encontrada";
}

export function getBreadcrumbs(pathname: string): ReadonlyArray<BreadcrumbItem> {
  const activeItem = getActiveNavigationItem(pathname);
  if (!activeItem) return [];
  const currentItem = { id: activeItem.id, label: activeItem.label, current: true };
  if (activeItem.route === "/") return [currentItem];
  if (withoutQueryOrHash(pathname) === "/documents/search") {
    return [
      { id: "home", label: "Inicio", route: "/", current: false },
      { id: "documents", label: "Documentos", route: "/documents", current: false },
      { id: "documents-search", label: "Búsqueda", current: true },
    ];
  }
  const isDetail = activeItem.matchStrategy === "prefix" && withoutQueryOrHash(pathname) !== activeItem.route;
  return [
    { id: "home", label: "Inicio", route: "/", current: false },
    ...(isDetail ? [
      { id: activeItem.id, label: activeItem.label, route: activeItem.route, current: false },
      { id: `${activeItem.id}-detail`, label: activeItem.detailLabel ?? "Detalle", current: true },
    ] : [currentItem]),
  ];
}
