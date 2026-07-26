import type { DensityPreference, ThemePreference, VisualPreferences } from "../types/preferences";

const STORAGE_KEY = "ajrl.visual-preferences.v1";
const STORAGE_VERSION = 1;

export const DEFAULT_VISUAL_PREFERENCES: VisualPreferences = Object.freeze({
  theme: "system",
  density: "comfortable",
});

function isTheme(value: unknown): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark";
}

function isDensity(value: unknown): value is DensityPreference {
  return value === "comfortable" || value === "compact";
}

export function readVisualPreferences(): VisualPreferences {
  if (typeof window === "undefined") return DEFAULT_VISUAL_PREFERENCES;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) return DEFAULT_VISUAL_PREFERENCES;
    const parsed: unknown = JSON.parse(stored);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return DEFAULT_VISUAL_PREFERENCES;
    const keys = Object.keys(parsed).sort();
    if (keys.join(",") !== "density,theme,version") return DEFAULT_VISUAL_PREFERENCES;
    if (!("version" in parsed) || parsed.version !== STORAGE_VERSION) return DEFAULT_VISUAL_PREFERENCES;
    if (!("theme" in parsed) || !isTheme(parsed.theme)) return DEFAULT_VISUAL_PREFERENCES;
    if (!("density" in parsed) || !isDensity(parsed.density)) return DEFAULT_VISUAL_PREFERENCES;
    return { theme: parsed.theme, density: parsed.density };
  } catch {
    return DEFAULT_VISUAL_PREFERENCES;
  }
}

export function writeVisualPreferences(preferences: VisualPreferences): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
      version: STORAGE_VERSION,
      theme: preferences.theme,
      density: preferences.density,
    }));
  } catch {
    // El almacenamiento visual es opcional; la aplicación continúa con estado en memoria.
  }
}

export function clearVisualPreferences(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Un almacenamiento inaccesible no impide restablecer el estado en memoria.
  }
}
