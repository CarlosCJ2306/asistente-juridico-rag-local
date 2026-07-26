import { createContext, useContext } from "react";

import type { PreferencesContextValue } from "../types/preferences";

export const PreferencesContext = createContext<PreferencesContextValue | undefined>(undefined);

export function usePreferences(): PreferencesContextValue {
  const preferences = useContext(PreferencesContext);
  if (!preferences) throw new Error("PREFERENCES_PROVIDER_MISSING");
  return preferences;
}
