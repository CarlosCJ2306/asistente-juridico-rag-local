import { useId, type ReactNode } from "react";

import styles from "../composites.module.css";

export interface FormFieldControlProps {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
  required?: boolean;
}

interface FormFieldBaseProps {
  label: ReactNode;
  children: (controlProps: FormFieldControlProps) => ReactNode;
  description?: ReactNode;
  required?: boolean;
  counter?: ReactNode;
  id?: string;
}

type FormFieldFeedback =
  | { error: ReactNode; success?: never }
  | { error?: never; success?: ReactNode };

export type FormFieldProps = FormFieldBaseProps & FormFieldFeedback;

export function FormField({ label, children, description, required = false, error, success, counter, id }: FormFieldProps) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  const descriptionId = `${controlId}-description`;
  const messageId = `${controlId}-message`;
  const describedBy = [description ? descriptionId : null, error || success || counter ? messageId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={styles.field}>
      <label htmlFor={controlId} className={styles.fieldLabel}>{label}{required ? <span className={styles.fieldRequired}> (obligatorio)</span> : null}</label>
      {description ? <p id={descriptionId} className={styles.fieldDescription}>{description}</p> : null}
      {children({ id: controlId, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined, required: required || undefined })}
      {error || success || counter ? (
        <div id={messageId} className={styles.fieldMessage}>
          <span className={error ? styles.fieldError : styles.fieldSuccess}>{error ?? success}</span>
          {counter ? <span className={styles.fieldCounter}>{counter}</span> : null}
        </div>
      ) : null}
    </div>
  );
}
