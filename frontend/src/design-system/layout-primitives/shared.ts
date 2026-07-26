import styles from "./layout-primitives.module.css";

export type LayoutGap = "none" | "xs" | "sm" | "md" | "lg" | "xl";
export type LayoutAlignment = "start" | "center" | "end" | "stretch";
export type LayoutJustification = "start" | "center" | "end" | "between";

export const gapClasses: Record<LayoutGap, string> = {
  none: styles.gapNone,
  xs: styles.gapXs,
  sm: styles.gapSm,
  md: styles.gapMd,
  lg: styles.gapLg,
  xl: styles.gapXl,
};

export const alignClasses: Record<LayoutAlignment, string> = {
  start: styles.alignStart,
  center: styles.alignCenter,
  end: styles.alignEnd,
  stretch: styles.alignStretch,
};

export const justifyClasses: Record<LayoutJustification, string> = {
  start: styles.justifyStart,
  center: styles.justifyCenter,
  end: styles.justifyEnd,
  between: styles.justifyBetween,
};
