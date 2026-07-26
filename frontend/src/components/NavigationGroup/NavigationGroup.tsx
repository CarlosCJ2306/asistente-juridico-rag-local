import type { NavigationSection } from "../../app/navigation/navigation.types";
import { NavigationItem } from "../NavigationItem/NavigationItem";
import styles from "./NavigationGroup.module.css";

export interface NavigationGroupProps {
  section: NavigationSection;
  compact?: boolean;
  onNavigate?: () => void;
}

export function NavigationGroup({ section, compact = false, onNavigate }: NavigationGroupProps) {
  return (
    <section className={styles.group} aria-label={section.label}>
      {compact ? null : <p className={styles.label}>{section.label}</p>}
      <ul className={styles.list}>
        {section.items.map((item) => (
          <li key={item.id}><NavigationItem item={item} compact={compact} onNavigate={onNavigate} /></li>
        ))}
      </ul>
    </section>
  );
}
