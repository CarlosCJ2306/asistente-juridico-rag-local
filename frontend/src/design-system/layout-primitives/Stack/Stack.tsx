import type { HTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../layout-primitives.module.css";
import { alignClasses, gapClasses, type LayoutAlignment, type LayoutGap } from "../shared";

export interface StackProps extends HTMLAttributes<HTMLElement> {
  as?: "div" | "section" | "article" | "ul";
  gap?: LayoutGap;
  align?: LayoutAlignment;
}

export function Stack({ as: Element = "div", gap = "md", align = "stretch", className, ...props }: StackProps) {
  return <Element {...props} className={classNames(styles.stack, gapClasses[gap], alignClasses[align], className)} />;
}
