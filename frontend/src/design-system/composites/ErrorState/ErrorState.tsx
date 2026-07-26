import type { ReactNode } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../composites.module.css";

export interface ErrorStateProps { title: ReactNode; message: ReactNode; retryAction?: ReactNode; centered?: boolean; className?: string; }

export function ErrorState({ title, message, retryAction, centered = false, className }: ErrorStateProps) {
  return <section role="alert" className={classNames(styles.state, centered && styles.stateCentered, className)}><h2 className={styles.stateTitle}>{title}</h2><p className={styles.stateDescription}>{message}</p>{retryAction}</section>;
}
