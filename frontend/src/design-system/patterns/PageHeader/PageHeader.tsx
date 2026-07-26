import type { ReactNode } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../patterns.module.css";

export interface PageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  breadcrumbs?: ReactNode;
  actions?: ReactNode;
  metadata?: ReactNode;
  headingLevel?: "h1" | "h2";
  className?: string;
}

export function PageHeader({ title, description, breadcrumbs, actions, metadata, headingLevel: Heading = "h1", className }: PageHeaderProps) {
  return (
    <header className={classNames(styles.pageHeader, className)}>
      <div className={styles.pageHeaderContent}>
        <div className={styles.pageHeaderMain}>
          {breadcrumbs ? <div className={styles.pageHeaderBreadcrumbs}>{breadcrumbs}</div> : null}
          <Heading className={styles.pageHeaderTitle}>{title}</Heading>
          {description ? <p className={styles.pageHeaderDescription}>{description}</p> : null}
          {metadata ? <div className={styles.pageHeaderMetadata}>{metadata}</div> : null}
        </div>
        {actions ? <div className={styles.pageHeaderActions}>{actions}</div> : null}
      </div>
    </header>
  );
}
