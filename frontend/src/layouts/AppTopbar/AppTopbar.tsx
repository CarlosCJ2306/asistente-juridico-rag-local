import type { ReactNode } from "react";

import { AppearanceControl, MobileNavigationTrigger } from "../../components";
import styles from "../layouts.module.css";

export interface AppTopbarProps {
  sectionTitle: string;
  onOpenNavigation: () => void;
  navigationOpen: boolean;
  navigationId: string;
  actions?: ReactNode;
}

export function AppTopbar({ sectionTitle, onOpenNavigation, navigationOpen, navigationId, actions }: AppTopbarProps) {
  return (
    <header className={styles.topbar}>
      <div className={styles.topbarPrimary}>
        <MobileNavigationTrigger className={styles.mobileTrigger} onOpen={onOpenNavigation} open={navigationOpen} controls={navigationId} />
        <p className={styles.topbarTitle}>{sectionTitle}</p>
      </div>
      <div className={styles.topbarActions}><AppearanceControl />{actions}</div>
    </header>
  );
}
