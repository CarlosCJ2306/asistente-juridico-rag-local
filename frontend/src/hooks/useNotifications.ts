import { createContext, useContext } from "react";

import type { NotificationsContextValue } from "../types/notifications";

export const NotificationsContext = createContext<NotificationsContextValue | undefined>(undefined);

export function useNotifications(): NotificationsContextValue {
  const notifications = useContext(NotificationsContext);
  if (!notifications) throw new Error("NOTIFICATIONS_PROVIDER_MISSING");
  return notifications;
}
