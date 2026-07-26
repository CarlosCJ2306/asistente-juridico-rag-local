import type { HTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../primitives.module.css";

export interface DividerProps extends HTMLAttributes<HTMLDivElement> {
  orientation?: "horizontal" | "vertical";
}

export function Divider({ orientation = "horizontal", className, ...props }: DividerProps) {
  return (
    <div
      {...props}
      role="separator"
      aria-orientation={orientation}
      className={classNames(styles.divider, orientation === "horizontal" ? styles.dividerHorizontal : styles.dividerVertical, className)}
    />
  );
}
