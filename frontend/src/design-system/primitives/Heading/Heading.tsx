import type { HTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../primitives.module.css";

export type HeadingSize = "sm" | "md" | "lg" | "xl";
export interface HeadingProps extends HTMLAttributes<HTMLHeadingElement> {
  as?: "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
  size?: HeadingSize;
}

const sizeClasses: Record<HeadingSize, string> = {
  sm: styles.headingSm,
  md: styles.headingMd,
  lg: styles.headingLg,
  xl: styles.headingXl,
};

export function Heading({ as: Element = "h2", size = "md", className, ...props }: HeadingProps) {
  return <Element {...props} className={classNames(styles.heading, sizeClasses[size], className)} />;
}
