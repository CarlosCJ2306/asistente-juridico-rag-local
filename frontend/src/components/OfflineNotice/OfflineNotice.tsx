import { Alert } from "../../design-system";
import { useOnlineStatus } from "../../hooks";
import styles from "./OfflineNotice.module.css";

export function OfflineNotice() {
  const isOnline = useOnlineStatus();
  if (isOnline) return null;
  return (
    <aside className={styles.notice} role="status" aria-live="polite">
      <Alert variant="warning" title="Navegador sin conexión">
        Este indicador refleja la conectividad del navegador; no sustituye el estado del backend local.
      </Alert>
    </aside>
  );
}
