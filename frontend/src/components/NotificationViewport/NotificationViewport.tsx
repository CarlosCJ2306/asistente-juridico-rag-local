import { useNotifications } from "../../hooks";
import { NotificationToast } from "../NotificationToast/NotificationToast";
import styles from "./NotificationViewport.module.css";

const MAX_VISIBLE_NOTIFICATIONS = 3;

export function NotificationViewport() {
  const { notifications, dismiss } = useNotifications();
  const visible = notifications.slice(-MAX_VISIBLE_NOTIFICATIONS);
  if (visible.length === 0) return null;

  return (
    <aside className={styles.viewport} aria-label="Notificaciones" aria-live="polite" aria-relevant="additions removals">
      {visible.map((notification) => (
        <div className={styles.item} key={notification.id}>
          <NotificationToast notification={notification} onDismiss={dismiss} />
        </div>
      ))}
    </aside>
  );
}
