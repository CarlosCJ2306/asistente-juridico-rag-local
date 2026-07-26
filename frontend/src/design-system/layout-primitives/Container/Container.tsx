import type { HTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../layout-primitives.module.css";

export type ContainerWidth = "reading" | "standard" | "wide" | "fluid";
export interface ContainerProps extends HTMLAttributes<HTMLDivElement> { width?: ContainerWidth; }

const widthClasses: Record<ContainerWidth, string> = {
  reading: styles.containerReading,
  standard: styles.containerStandard,
  wide: styles.containerWide,
  fluid: styles.containerFluid,
};

export function Container({ width = "standard", className, ...props }: ContainerProps) {
  return <div {...props} className={classNames(styles.container, widthClasses[width], className)} />;
}
