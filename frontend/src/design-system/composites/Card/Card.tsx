import type { HTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../composites.module.css";

export interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: "div" | "section" | "article";
  padding?: "sm" | "md" | "lg";
  elevated?: boolean;
  interactive?: boolean;
}

const paddingClasses = { sm: styles.cardSm, md: styles.cardMd, lg: styles.cardLg } as const;

export function Card({ as: Element = "article", padding = "md", elevated = false, interactive = false, className, ...props }: CardProps) {
  return <Element {...props} className={classNames(styles.card, paddingClasses[padding], elevated && styles.cardElevated, interactive && styles.cardInteractive, className)} />;
}
