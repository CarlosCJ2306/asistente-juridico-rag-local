import type { NavigationSection } from "../../app/navigation/navigation.types";
import { AppBrand, NavigationGroup } from "../../components";
import { Button, CollapseIcon, ExpandIcon, IconButton } from "../../design-system";
import styles from "../layouts.module.css";

export interface AppSidebarProps {
  sections: ReadonlyArray<NavigationSection>;
  compact: boolean;
  onCompactChange: (compact: boolean) => void;
}

export function AppSidebar({ sections, compact, onCompactChange }: AppSidebarProps) {
  const toggleLabel = compact ? "Expandir navegación" : "Compactar navegación";
  const navigationId = "desktop-navigation";

  return (
    <aside className={styles.sidebarRegion} aria-label="Navegación de escritorio">
      <div className={styles.sidebar}>
        <div className={styles.sidebarBrand}><AppBrand compact={compact} /></div>
        <nav id={navigationId} className={styles.sidebarNavigation} aria-label="Navegación principal">
          {sections.map((section) => <NavigationGroup key={section.id} section={section} compact={compact} />)}
        </nav>
        <div className={styles.sidebarFooter}>
          {compact ? (
            <IconButton title={toggleLabel} aria-label={toggleLabel} aria-expanded={false} aria-controls={navigationId} onClick={() => onCompactChange(false)}><ExpandIcon /></IconButton>
          ) : (
            <Button variant="ghost" fullWidth leadingIcon={<CollapseIcon />} aria-expanded={true} aria-controls={navigationId} onClick={() => onCompactChange(true)}>{toggleLabel}</Button>
          )}
        </div>
      </div>
    </aside>
  );
}
