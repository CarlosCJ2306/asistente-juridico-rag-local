import { forwardRef, type TextareaHTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../primitives.module.css";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea({ invalid = false, "aria-invalid": ariaInvalid, className, ...props }, ref) {
    return (
      <textarea
        {...props}
        ref={ref}
        aria-invalid={invalid ? true : ariaInvalid}
        className={classNames(
          styles.control,
          styles.textarea,
          invalid && styles.controlInvalid,
          className,
        )}
      />
    );
  },
);
