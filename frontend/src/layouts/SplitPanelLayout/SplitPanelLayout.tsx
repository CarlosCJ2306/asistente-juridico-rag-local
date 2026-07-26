import type { ReactNode } from "react";

import { Stack } from "../../design-system";
import styles from "../layouts.module.css";

export type SplitPanelRatio = "balanced" | "primary-wide" | "secondary-wide";

export interface SplitPanelLayoutProps {
  primary: ReactNode;
  secondary: ReactNode;
  ratio?: SplitPanelRatio;
  className?: string;
}

const ratioClasses: Record<SplitPanelRatio, string> = {
  balanced: styles.splitBalanced,
  "primary-wide": styles.splitPrimaryWide,
  "secondary-wide": styles.splitSecondaryWide,
};

export function SplitPanelLayout({ primary, secondary, ratio = "primary-wide", className }: SplitPanelLayoutProps) {
  return (
    <div className={[styles.splitPanel, className].filter(Boolean).join(" ")}>
      <Stack gap="lg" className={[styles.splitContent, ratioClasses[ratio]].join(" ")}>
        <div className={styles.splitPrimary}>{primary}</div>
        <div className={styles.splitSecondary}>{secondary}</div>
      </Stack>
    </div>
  );
}
