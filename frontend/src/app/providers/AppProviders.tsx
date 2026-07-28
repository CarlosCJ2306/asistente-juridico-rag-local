import type { PropsWithChildren } from "react";

import { AppErrorBoundary, NotificationViewport, OfflineNotice } from "../../components";
import { BrandMetadata } from "../BrandMetadata";
import { NotificationsProvider } from "./NotificationsProvider";
import { PreferencesProvider } from "./PreferencesProvider";
import { QueryProvider } from "./QueryProvider";
import { SessionProvider } from "./SessionProvider";

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <AppErrorBoundary>
      <PreferencesProvider>
        <BrandMetadata />
        <SessionProvider>
          <QueryProvider>
            <NotificationsProvider>
              {children}
              <OfflineNotice />
              <NotificationViewport />
            </NotificationsProvider>
          </QueryProvider>
        </SessionProvider>
      </PreferencesProvider>
    </AppErrorBoundary>
  );
}
