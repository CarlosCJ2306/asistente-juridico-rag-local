import type { ReactNode } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../composites.module.css";

export interface EmptyStateProps { title: ReactNode; description: ReactNode; action?: ReactNode; icon?: ReactNode; centered?: boolean; className?: string; }

export function EmptyState({ title, description, action, icon, centered = false, className }: EmptyStateProps) {
  return <section className={classNames(styles.state, centered && styles.stateCentered, className)}>{icon ? <span className={styles.stateIcon} aria-hidden="true">{icon}</span> : null}<h2 className={styles.stateTitle}>{title}</h2><p className={styles.stateDescription}>{description}</p>{action}</section>;
}
