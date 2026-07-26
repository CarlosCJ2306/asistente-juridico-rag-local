import { forwardRef, type SelectHTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../primitives.module.css";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { invalid = false, "aria-invalid": ariaInvalid, className, children, ...props },
  ref,
) {
  return (
    <select
      {...props}
      ref={ref}
      aria-invalid={invalid ? true : ariaInvalid}
      className={classNames(
        styles.control,
        styles.select,
        invalid && styles.controlInvalid,
        className,
      )}
    >
      {children}
    </select>
  );
});
