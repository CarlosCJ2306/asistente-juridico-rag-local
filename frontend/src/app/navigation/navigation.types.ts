import type { ComponentType } from "react";

import type { IconProps } from "../../design-system";

export type NavigationAvailability = "active" | "planned" | "hidden";
export type NavigationMatchStrategy = "exact" | "prefix";
export type NavigationIcon = ComponentType<IconProps>;

export interface NavigationItemConfig {
  readonly id: string;
  readonly label: string;
  readonly route: `/${string}`;
  readonly icon: NavigationIcon;
  readonly availability: NavigationAvailability;
  readonly matchStrategy: NavigationMatchStrategy;
  readonly description?: string;
}

export interface NavigationSection {
  readonly id: string;
  readonly label: string;
  readonly items: ReadonlyArray<NavigationItemConfig>;
}

export interface BreadcrumbItem {
  readonly id: string;
  readonly label: string;
  readonly route?: string;
  readonly current: boolean;
}
