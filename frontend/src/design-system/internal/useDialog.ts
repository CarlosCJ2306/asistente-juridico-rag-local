import { useCallback, useEffect, useRef, type MouseEvent, type SyntheticEvent } from "react";

export interface UseDialogOptions {
  open: boolean;
  preventClose?: boolean;
  onOpenChange: (open: boolean) => void;
}

export function useDialog({
  open,
  preventClose = false,
  onOpenChange,
}: UseDialogOptions) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const suppressProgrammaticCloseRef = useRef(false);

  const restoreFocus = useCallback(() => {
    const previousFocus = previousFocusRef.current;
    previousFocusRef.current = null;
    if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (open && !dialog.open && dialog.isConnected) {
      previousFocusRef.current =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      dialog.showModal();
    } else if (!open && dialog.open) {
      suppressProgrammaticCloseRef.current = true;
      dialog.close();
    }
  }, [open]);

  useEffect(
    () => () => {
      if (dialogRef.current?.open) {
        suppressProgrammaticCloseRef.current = true;
        dialogRef.current.close();
      }
      restoreFocus();
    },
    [restoreFocus],
  );

  const requestClose = () => {
    if (!preventClose) onOpenChange(false);
  };

  const handleCancel = (event: SyntheticEvent<HTMLDialogElement>) => {
    event.preventDefault();
    requestClose();
  };

  const handleBackdropClick = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === event.currentTarget) requestClose();
  };

  const handleClose = () => {
    restoreFocus();
    if (suppressProgrammaticCloseRef.current) {
      suppressProgrammaticCloseRef.current = false;
      return;
    }
    if (open) onOpenChange(false);
  };

  return { dialogRef, requestClose, handleCancel, handleBackdropClick, handleClose };
}
