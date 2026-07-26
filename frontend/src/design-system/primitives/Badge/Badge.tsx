import type { HTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../primitives.module.css";

export type BadgeVariant = "neutral" | "info" | "success" | "warning" | "danger";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  neutral: styles.badgeNeutral,
  info: styles.badgeInfo,
  success: styles.badgeSuccess,
  warning: styles.badgeWarning,
  danger: styles.badgeDanger,
};

export function Badge({ variant = "neutral", className, children, ...props }: BadgeProps) {
  return <span {...props} className={classNames(styles.badge, variantClasses[variant], className)}>{children}</span>;
}
