import { Alert } from "../../design-system";
import type { AppNotification } from "../../types/notifications";

export interface NotificationToastProps {
  readonly notification: AppNotification;
  readonly onDismiss: (id: string) => void;
}

export function NotificationToast({ notification, onDismiss }: NotificationToastProps) {
  const dismissProps = notification.dismissible
    ? { onDismiss: () => onDismiss(notification.id), dismissLabel: "Cerrar notificación" }
    : {};

  return (
    <Alert variant={notification.kind} title={notification.title} {...dismissProps}>
      {notification.message}
    </Alert>
  );
}
