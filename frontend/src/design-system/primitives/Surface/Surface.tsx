import type { HTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../primitives.module.css";

export interface SurfaceProps extends HTMLAttributes<HTMLElement> {
  as?: "div" | "section" | "article";
  tone?: "default" | "subtle" | "elevated";
  padding?: "none" | "sm" | "md" | "lg";
  bordered?: boolean;
}

const toneClasses = { default: undefined, subtle: styles.surfaceSubtle, elevated: styles.surfaceElevated } as const;
const paddingClasses = { none: undefined, sm: styles.surfaceSm, md: styles.surfaceMd, lg: styles.surfaceLg } as const;

export function Surface({ as: Element = "div", tone = "default", padding = "none", bordered = false, className, ...props }: SurfaceProps) {
  return <Element {...props} className={classNames(styles.surface, toneClasses[tone], paddingClasses[padding], bordered && styles.surfaceBordered, className)} />;
}
