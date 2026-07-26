export type NotificationKind = "info" | "success" | "warning" | "error";

interface NotificationInputBase {
  readonly kind: NotificationKind;
  readonly title: string;
  readonly message?: string;
  readonly dismissible?: boolean;
  readonly deduplicationKey?: string;
}

export type NotificationInput =
  | (NotificationInputBase & { readonly reviewable: true; readonly durationMs?: never })
  | (NotificationInputBase & { readonly reviewable?: false; readonly durationMs?: number });

export interface AppNotification {
  readonly id: string;
  readonly kind: NotificationKind;
  readonly title: string;
  readonly message?: string;
  readonly dismissible: boolean;
  readonly deduplicationKey?: string;
  readonly reviewable: boolean;
  readonly durationMs?: number;
}

export interface NotificationsContextValue {
  readonly notifications: readonly AppNotification[];
  readonly notify: (input: NotificationInput) => string;
  readonly dismiss: (id: string) => void;
  readonly clear: () => void;
}
