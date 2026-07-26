import type { HTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../primitives.module.css";

export type TextVariant = "body" | "secondary" | "label" | "caption";
export interface TextProps extends HTMLAttributes<HTMLElement> {
  as?: "p" | "span" | "small";
  variant?: TextVariant;
}

const variantClasses: Record<TextVariant, string> = {
  body: styles.textBody,
  secondary: styles.textSecondary,
  label: styles.textLabel,
  caption: styles.textCaption,
};

export function Text({ as: Element = "p", variant = "body", className, ...props }: TextProps) {
  return <Element {...props} className={classNames(styles.text, variantClasses[variant], className)} />;
}
