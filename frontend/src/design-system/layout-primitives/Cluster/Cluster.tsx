import type { HTMLAttributes } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../layout-primitives.module.css";
import { gapClasses, justifyClasses, type LayoutGap, type LayoutJustification } from "../shared";

export interface ClusterProps extends HTMLAttributes<HTMLDivElement> {
  gap?: LayoutGap;
  justify?: LayoutJustification;
}

export function Cluster({ gap = "sm", justify = "start", className, ...props }: ClusterProps) {
  return <div {...props} className={classNames(styles.cluster, gapClasses[gap], justifyClasses[justify], className)} />;
}
