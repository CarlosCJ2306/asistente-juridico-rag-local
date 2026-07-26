import { useCallback, useEffect, useMemo, useRef, useState, type PropsWithChildren } from "react";

import { PreferencesContext } from "../../hooks/usePreferences";
import type { DensityPreference, PreferencesContextValue, ThemePreference, VisualPreferences } from "../../types/preferences";
import {
  DEFAULT_VISUAL_PREFERENCES,
  clearVisualPreferences,
  readVisualPreferences,
  writeVisualPreferences,
} from "../../utils/safeStorage";

export function PreferencesProvider({ children }: PropsWithChildren) {
  const [preferences, setPreferences] = useState<VisualPreferences>(readVisualPreferences);
  const preferencesRef = useRef(preferences);

  const update = useCallback((next: VisualPreferences) => {
    preferencesRef.current = next;
    setPreferences(next);
    writeVisualPreferences(next);
  }, []);
  const setTheme = useCallback((theme: ThemePreference) => update({ ...preferencesRef.current, theme }), [update]);
  const setDensity = useCallback((density: DensityPreference) => update({ ...preferencesRef.current, density }), [update]);
  const resetPreferences = useCallback(() => {
    preferencesRef.current = DEFAULT_VISUAL_PREFERENCES;
    setPreferences(DEFAULT_VISUAL_PREFERENCES);
    clearVisualPreferences();
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") return undefined;
    const root = document.documentElement;
    const previousTheme = root.getAttribute("data-theme");
    const previousDensity = root.getAttribute("data-density");
    if (preferences.theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", preferences.theme);
    root.setAttribute("data-density", preferences.density);
    return () => {
      if (previousTheme === null) root.removeAttribute("data-theme");
      else root.setAttribute("data-theme", previousTheme);
      if (previousDensity === null) root.removeAttribute("data-density");
      else root.setAttribute("data-density", previousDensity);
    };
  }, [preferences]);

  const value = useMemo<PreferencesContextValue>(() => ({
    ...preferences,
    setTheme,
    setDensity,
    resetPreferences,
  }), [preferences, resetPreferences, setDensity, setTheme]);

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}
