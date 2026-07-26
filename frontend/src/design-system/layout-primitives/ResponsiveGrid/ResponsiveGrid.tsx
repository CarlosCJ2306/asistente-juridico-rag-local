import type { HTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../layout-primitives.module.css";

export type GridMinimum = "compact" | "standard" | "wide";
export interface ResponsiveGridProps extends HTMLAttributes<HTMLDivElement> { minimum?: GridMinimum; }

const minimumClasses: Record<GridMinimum, string> = {
  compact: styles.gridCompact,
  standard: styles.gridStandard,
  wide: styles.gridWide,
};

export function ResponsiveGrid({ minimum = "standard", className, ...props }: ResponsiveGridProps) {
  return (
    <div className={styles.gridContainer}>
      <div {...props} className={classNames(styles.grid, minimumClasses[minimum], className)} />
    </div>
  );
}
