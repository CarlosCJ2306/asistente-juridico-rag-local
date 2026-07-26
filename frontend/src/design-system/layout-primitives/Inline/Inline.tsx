import type { HTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../layout-primitives.module.css";
import { alignClasses, gapClasses, justifyClasses, type LayoutAlignment, type LayoutGap, type LayoutJustification } from "../shared";

export interface InlineProps extends HTMLAttributes<HTMLElement> {
  as?: "div" | "nav" | "ul";
  gap?: LayoutGap;
  align?: LayoutAlignment;
  justify?: LayoutJustification;
  wrap?: boolean;
  collapseOnSmall?: boolean;
}

export function Inline({ as: Element = "div", gap = "md", align = "center", justify = "start", wrap = true, collapseOnSmall = false, className, ...props }: InlineProps) {
  return <Element {...props} className={classNames(styles.inline, gapClasses[gap], alignClasses[align], justifyClasses[justify], !wrap && styles.inlineNoWrap, collapseOnSmall && styles.inlineCollapse, className)} />;
}
