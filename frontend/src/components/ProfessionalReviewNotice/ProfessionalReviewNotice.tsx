import type { ReactNode } from "react";

import { InfoIcon } from "../../design-system";
import styles from "./ProfessionalReviewNotice.module.css";

export interface ProfessionalReviewNoticeProps {
  variant?: "compact" | "full";
  children?: ReactNode;
  className?: string;
}

export function ProfessionalReviewNotice({ variant = "full", children, className }: ProfessionalReviewNoticeProps) {
  const noticeClassName = [
    styles.review,
    variant === "compact" ? styles.reviewCompact : styles.reviewFull,
    className,
  ].filter(Boolean).join(" ");

  return (
    <aside className={noticeClassName} aria-label="Revisión profesional obligatoria">
      <InfoIcon className={styles.reviewIcon} />
      <div className={styles.reviewContent}>
        <p className={styles.reviewTitle}>Contenido asistido</p>
        <p className={styles.reviewMessage}>No constituye una decisión jurídica y requiere revisión de un profesional competente.</p>
        {children ? <div className={styles.reviewAdditional}>{children}</div> : null}
      </div>
    </aside>
  );
}
