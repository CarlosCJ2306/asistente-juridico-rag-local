import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../primitives.module.css";

export interface RadioProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: ReactNode;
  invalid?: boolean;
}

export const Radio = forwardRef<HTMLInputElement, RadioProps>(function Radio(
  { label, invalid = false, disabled, "aria-invalid": ariaInvalid, className, ...props },
  ref,
) {
  return (
    <label className={classNames(styles.choiceLabel, disabled && styles.choiceLabelDisabled, invalid && styles.choiceError, className)}>
      <input {...props} ref={ref} type="radio" disabled={disabled} aria-invalid={invalid ? true : ariaInvalid} className={styles.choiceInput} />
      <span className={styles.choiceText}>{label}</span>
    </label>
  );
});
