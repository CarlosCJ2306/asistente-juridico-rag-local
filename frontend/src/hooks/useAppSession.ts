import { createContext, useContext } from "react";

import type { AppSession } from "../types/session";

export const SessionContext = createContext<AppSession | undefined>(undefined);

export function useAppSession(): AppSession {
  const session = useContext(SessionContext);
  if (!session) throw new Error("SESSION_PROVIDER_MISSING");
  return session;
}
