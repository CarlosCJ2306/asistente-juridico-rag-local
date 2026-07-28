import { useCallback, useEffect, useMemo, useRef, useState, type PropsWithChildren } from "react";

import { branding, getBrandPalette, type ResolvedTheme } from "../../config/branding";
import { PreferencesContext } from "../../hooks/usePreferences";
import type { DensityPreference, PreferencesContextValue, ThemePreference, VisualPreferences } from "../../types/preferences";
import { DEFAULT_VISUAL_PREFERENCES, clearVisualPreferences, readVisualPreferences, writeVisualPreferences } from "../../utils/safeStorage";

function resolvedTheme(preference: ThemePreference, media: MediaQueryList): ResolvedTheme {
  return preference === "system" ? (media.matches ? "dark" : "light") : preference;
}

function applyVisualPreferences(preferences: VisualPreferences, media: MediaQueryList): void {
  const root = document.documentElement;
  const theme = resolvedTheme(preferences.theme, media);
  const palette = getBrandPalette(theme);
  root.dataset.theme = theme;
  root.dataset.themePreference = preferences.theme;
  root.dataset.brand = branding.themePreset;
  root.dataset.density = preferences.density;
  root.style.setProperty("--brand-primary", palette.primary);
  root.style.setProperty("--brand-primary-hover", palette.primaryHover);
  root.style.setProperty("--brand-secondary", palette.secondary);
  root.style.setProperty("--brand-accent", palette.accent);
}

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
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const updateSystemTheme = () => applyVisualPreferences(preferences, media);
    updateSystemTheme();
    if (preferences.theme === "system") media.addEventListener("change", updateSystemTheme);
    return () => media.removeEventListener("change", updateSystemTheme);
  }, [preferences]);

  const value = useMemo<PreferencesContextValue>(() => ({ ...preferences, setTheme, setDensity, resetPreferences }), [preferences, resetPreferences, setDensity, setTheme]);
  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}
