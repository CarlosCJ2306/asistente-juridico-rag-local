import type { HTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import { VisuallyHidden } from "../VisuallyHidden/VisuallyHidden";
import styles from "../primitives.module.css";

type SpinnerAccessibility =
  | { decorative: true; label?: never }
  | { decorative?: false; label: string };

export type SpinnerProps = Omit<HTMLAttributes<HTMLSpanElement>, "children"> & SpinnerAccessibility;

export function Spinner({ decorative = false, label, className, ...props }: SpinnerProps) {
  return (
    <span {...props} className={classNames(styles.spinner, className)} aria-hidden={decorative || undefined}>
      {!decorative && label ? <VisuallyHidden>{label}</VisuallyHidden> : null}
    </span>
  );
}
