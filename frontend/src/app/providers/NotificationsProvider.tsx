import { useCallback, useEffect, useMemo, useRef, useState, type PropsWithChildren } from "react";

import { NotificationsContext } from "../../hooks/useNotifications";
import type { AppNotification, NotificationInput, NotificationsContextValue } from "../../types/notifications";

const MAX_NOTIFICATIONS = 10;
const DEFAULT_DURATION_MS = 6_000;

function cleanText(value: string, maximumLength: number): string {
  const withoutControls = Array.from(value, (character) => {
    const code = character.codePointAt(0) ?? 0;
    return code < 32 || code === 127 ? " " : character;
  }).join("");
  return withoutControls.replace(/\s+/gu, " ").trim().slice(0, maximumLength);
}

function createEntropy(): string {
  if (typeof crypto !== "undefined" && "getRandomValues" in crypto) {
    return crypto.getRandomValues(new Uint32Array(1))[0].toString(36);
  }
  return "local";
}

export function NotificationsProvider({ children }: PropsWithChildren) {
  const [notifications, setNotifications] = useState<readonly AppNotification[]>([]);
  const notificationsRef = useRef(notifications);
  const sequenceRef = useRef(0);
  const timersRef = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const replaceNotifications = useCallback((next: readonly AppNotification[]) => {
    notificationsRef.current = next;
    setNotifications(next);
  }, []);

  const clearTimer = useCallback((id: string) => {
    const timer = timersRef.current.get(id);
    if (timer !== undefined) globalThis.clearTimeout(timer);
    timersRef.current.delete(id);
  }, []);

  const dismiss = useCallback((id: string) => {
    clearTimer(id);
    replaceNotifications(notificationsRef.current.filter((item) => item.id !== id));
  }, [clearTimer, replaceNotifications]);

  const clear = useCallback(() => {
    for (const timer of timersRef.current.values()) globalThis.clearTimeout(timer);
    timersRef.current.clear();
    replaceNotifications([]);
  }, [replaceNotifications]);

  useEffect(() => () => {
    for (const timer of timersRef.current.values()) globalThis.clearTimeout(timer);
    timersRef.current.clear();
  }, []);

  const notify = useCallback((input: NotificationInput): string => {
    const deduplicationKey = input.deduplicationKey?.slice(0, 80);
    if (deduplicationKey) {
      const existing = notificationsRef.current.find((item) => item.deduplicationKey === deduplicationKey);
      if (existing) return existing.id;
    }
    sequenceRef.current += 1;
    const id = `notice-${sequenceRef.current}-${createEntropy()}`;
    const persistent = input.reviewable === true || input.kind === "error";
    const notification: AppNotification = {
      id,
      kind: input.kind,
      title: cleanText(input.title, 120) || "Aviso",
      message: input.message ? cleanText(input.message, 360) : undefined,
      dismissible: input.dismissible ?? true,
      deduplicationKey,
      reviewable: input.reviewable === true,
      durationMs: persistent ? undefined : Math.min(Math.max(input.durationMs ?? DEFAULT_DURATION_MS, 2_000), 30_000),
    };
    const next = [...notificationsRef.current, notification].slice(-MAX_NOTIFICATIONS);
    const retainedIds = new Set(next.map((item) => item.id));
    for (const current of notificationsRef.current) {
      if (!retainedIds.has(current.id)) clearTimer(current.id);
    }
    replaceNotifications(next);
    if (notification.durationMs !== undefined) {
      const timer = globalThis.setTimeout(() => dismiss(id), notification.durationMs);
      timersRef.current.set(id, timer);
    }
    return id;
  }, [clearTimer, dismiss, replaceNotifications]);
  const value = useMemo<NotificationsContextValue>(() => ({ notifications, notify, dismiss, clear }), [clear, dismiss, notifications, notify]);

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>;
}
