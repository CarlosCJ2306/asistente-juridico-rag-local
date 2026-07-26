import { NavLink } from "react-router-dom";

import type { NavigationItemConfig } from "../../app/navigation/navigation.types";
import { VisuallyHidden } from "../../design-system";
import styles from "./NavigationItem.module.css";

export interface NavigationItemProps {
  item: NavigationItemConfig;
  compact?: boolean;
  onNavigate?: () => void;
}

export function NavigationItem({ item, compact = false, onNavigate }: NavigationItemProps) {
  const Icon = item.icon;

  if (item.availability === "hidden") return null;

  if (item.availability === "planned") {
    const plannedItem = (
      <span className={styles.planned} aria-disabled="true" title={compact ? `${item.label}, próximamente` : undefined}>
        <Icon className={styles.icon} />
        {compact ? <VisuallyHidden>{item.label}</VisuallyHidden> : <span>{item.label} (próximamente)</span>}
      </span>
    );
    return plannedItem;
  }

  const link = (
    <NavLink
      to={item.route}
      end={item.matchStrategy === "exact"}
      onClick={onNavigate}
      aria-label={compact ? item.label : undefined}
      title={compact ? item.label : undefined}
      className={({ isActive }) => [styles.link, isActive ? styles.active : null, compact ? styles.compact : null].filter(Boolean).join(" ")}
    >
      <Icon className={styles.icon} />
      {compact ? null : <span className={styles.label}>{item.label}</span>}
    </NavLink>
  );

  return link;
}
