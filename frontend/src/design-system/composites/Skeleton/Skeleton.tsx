import type { HTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../composites.module.css";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return <span {...props} aria-hidden="true" className={classNames(styles.skeleton, className)} />;
}
