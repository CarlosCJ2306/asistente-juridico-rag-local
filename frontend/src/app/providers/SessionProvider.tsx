import type { PropsWithChildren } from "react";

import { SessionContext } from "../../hooks/useAppSession";
import type { AppCapability, AppSession } from "../../types/session";

const LOCAL_CAPABILITIES = [
  "documents.read",
  "documents.manage",
  "search.use",
  "chat.use",
  "hpn.read",
  "hpn.manage",
  "graph.read",
  "settings.manage",
] as const satisfies readonly AppCapability[];

const LOCAL_SESSION: AppSession = Object.freeze({
  mode: "local",
  user: null,
  capabilities: Object.freeze(LOCAL_CAPABILITIES),
  isSecurityBoundary: false,
});

export function SessionProvider({ children }: PropsWithChildren) {
  return <SessionContext.Provider value={LOCAL_SESSION}>{children}</SessionContext.Provider>;
}
