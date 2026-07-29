import type { ReactNode } from "react";

import type { BreadcrumbItem } from "../../app/navigation/navigation.types";
import { Breadcrumbs } from "../../components";
import { Container } from "../../design-system";
import styles from "../layouts.module.css";

export interface MainContentProps {
  id: string;
  breadcrumbs?: ReadonlyArray<BreadcrumbItem>;
  children: ReactNode;
  fullBleed?: boolean;
}

export function MainContent({ id, breadcrumbs = [], children, fullBleed = false }: MainContentProps) {
  return (
    <main id={id} tabIndex={-1} className={[styles.mainContent, fullBleed ? styles.mainContentFullBleed : null].filter(Boolean).join(" ")}>
      {!fullBleed && breadcrumbs.length > 1 ? (
        <Container width="wide" className={styles.breadcrumbRegion}><Breadcrumbs items={breadcrumbs} /></Container>
      ) : null}
      {children}
    </main>
  );
}
