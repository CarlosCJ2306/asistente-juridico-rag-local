import { useId, type ReactNode } from "react";

import { CloseIcon } from "../../icons/Icon";
import { IconButton } from "../../primitives/IconButton/IconButton";
import { VisuallyHidden } from "../../primitives/VisuallyHidden/VisuallyHidden";
import { classNames } from "../../internal/classNames";
import { useDialog } from "../../internal/useDialog";
import styles from "../composites.module.css";

export type DrawerPosition = "start" | "end" | "bottom";
interface DrawerBaseProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  position?: DrawerPosition;
  closeLabel?: string;
  className?: string;
}

type DrawerDismissPolicy =
  | { preventClose?: false; preventCloseReason?: never }
  | { preventClose: true; preventCloseReason: string };

export type DrawerProps = DrawerBaseProps & DrawerDismissPolicy;

const positionClasses: Record<DrawerPosition, string> = { start: styles.drawerStart, end: styles.drawerEnd, bottom: styles.drawerBottom };

export function Drawer({ open, onOpenChange, title, description, children, footer, position = "end", preventClose = false, preventCloseReason, closeLabel = "Cerrar panel", className }: DrawerProps) {
  const titleId = useId();
  const descriptionId = useId();
  const preventCloseReasonId = useId();
  const describedBy = [description ? descriptionId : null, preventCloseReason ? preventCloseReasonId : null].filter(Boolean).join(" ") || undefined;
  const { dialogRef, requestClose, handleCancel, handleBackdropClick, handleClose } = useDialog({ open, preventClose, onOpenChange });
  return (
    <dialog ref={dialogRef} aria-labelledby={titleId} aria-describedby={describedBy} onCancel={handleCancel} onClose={handleClose} onClick={handleBackdropClick} className={classNames(styles.dialog, styles.drawer, positionClasses[position], className)}>
      <div className={styles.dialogPanel}>
        {preventCloseReason ? <VisuallyHidden id={preventCloseReasonId}>{preventCloseReason}</VisuallyHidden> : null}
        <header className={styles.dialogHeader}>
          <div className={styles.dialogHeading}>
            <h2 id={titleId} className={styles.dialogTitle}>{title}</h2>
            {description ? <p id={descriptionId} className={styles.dialogDescription}>{description}</p> : null}
          </div>
          <IconButton aria-label={closeLabel} onClick={requestClose} disabled={preventClose}><CloseIcon /></IconButton>
        </header>
        <div className={styles.dialogBody}>{children}</div>
        {footer ? <footer className={styles.dialogFooter}>{footer}</footer> : null}
      </div>
    </dialog>
  );
}
