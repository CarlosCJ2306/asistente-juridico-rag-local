import { forwardRef, type InputHTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../primitives.module.css";

export interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
  function TextInput({ invalid = false, "aria-invalid": ariaInvalid, className, ...props }, ref) {
    return (
      <input
        {...props}
        ref={ref}
        aria-invalid={invalid ? true : ariaInvalid}
        className={classNames(styles.control, invalid && styles.controlInvalid, className)}
      />
    );
  },
);
