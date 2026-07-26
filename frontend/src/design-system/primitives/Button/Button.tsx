import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

import { classNames } from "../../internal/classNames";
import { Spinner } from "../Spinner/Spinner";
import styles from "../primitives.module.css";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  fullWidth?: boolean;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: styles.buttonPrimary,
  secondary: styles.buttonSecondary,
  ghost: styles.buttonGhost,
  danger: styles.buttonDanger,
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: styles.buttonSm,
  md: styles.buttonMd,
  lg: styles.buttonLg,
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "md",
    loading = false,
    fullWidth = false,
    leadingIcon,
    trailingIcon,
    disabled,
    className,
    children,
    type = "button",
    ...props
  },
  ref,
) {
  return (
    <button
      {...props}
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={classNames(
        styles.button,
        variantClasses[variant],
        sizeClasses[size],
        fullWidth && styles.buttonFull,
        className,
      )}
    >
      {loading ? (
        <span className={styles.buttonIcon} aria-hidden="true"><Spinner decorative /></span>
      ) : leadingIcon ? (
        <span className={styles.buttonIcon} aria-hidden="true">{leadingIcon}</span>
      ) : null}
      <span>{children}</span>
      {!loading && trailingIcon ? (
        <span className={styles.buttonIcon} aria-hidden="true">{trailingIcon}</span>
      ) : null}
    </button>
  );
});
