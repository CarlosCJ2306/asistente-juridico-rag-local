import type { HTMLAttributes, ReactNode } from "react";

import { InfoIcon, CloseIcon } from "../../icons/Icon";
import { IconButton } from "../../primitives/IconButton/IconButton";
import { classNames } from "../../internal/classNames";
import styles from "../composites.module.css";

export type AlertVariant = "info" | "success" | "warning" | "error";
interface AlertBaseProps extends Omit<HTMLAttributes<HTMLDivElement>, "title" | "role"> {
  variant?: AlertVariant;
  title?: ReactNode;
}

type AlertAction =
  | { action?: ReactNode; onDismiss?: never; dismissLabel?: never }
  | { action?: never; onDismiss: () => void; dismissLabel?: string };

export type AlertProps = AlertBaseProps & AlertAction;

const variantClasses: Record<AlertVariant, string> = {
  info: styles.alertInfo,
  success: styles.alertSuccess,
  warning: styles.alertWarning,
  error: styles.alertError,
};

const variantLabels: Record<AlertVariant, string> = {
  info: "Información",
  success: "Correcto",
  warning: "Advertencia",
  error: "Error",
};

export function Alert({ variant = "info", title, action, dismissLabel = "Cerrar aviso", onDismiss, className, children, ...props }: AlertProps) {
  const role = variant === "error" ? "alert" : variant === "success" ? "status" : undefined;
  return (
    <div {...props} role={role} className={classNames(styles.alert, variantClasses[variant], className)}>
      <InfoIcon className={styles.alertIcon} />
      <div className={styles.alertContent}>
        <p className={styles.alertVariantLabel}>{variantLabels[variant]}</p>
        {title ? <p className={styles.alertTitle}>{title}</p> : null}
        <div className={styles.alertBody}>{children}</div>
      </div>
      {onDismiss ? (
        <IconButton aria-label={dismissLabel} onClick={onDismiss} className={styles.alertAction}><CloseIcon /></IconButton>
      ) : action ? <div className={styles.alertAction}>{action}</div> : null}
    </div>
  );
}
