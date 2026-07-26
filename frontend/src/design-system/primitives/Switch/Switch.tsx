import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../primitives.module.css";

export interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "role"> {
  label: ReactNode;
}

export const Switch = forwardRef<HTMLInputElement, SwitchProps>(function Switch(
  { label, disabled, className, ...props },
  ref,
) {
  return (
    <label className={classNames(styles.switchLabel, disabled && styles.choiceLabelDisabled, className)}>
      <input {...props} ref={ref} type="checkbox" role="switch" disabled={disabled} className={styles.switchInput} />
      <span className={styles.switchTrack} aria-hidden="true" />
      <span className={styles.choiceText}>{label}</span>
    </label>
  );
});
