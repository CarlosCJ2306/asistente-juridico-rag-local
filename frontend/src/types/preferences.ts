export type ThemePreference = "system" | "light" | "dark";
export type DensityPreference = "comfortable" | "compact";

export interface VisualPreferences {
  readonly theme: ThemePreference;
  readonly density: DensityPreference;
}

export interface PreferencesContextValue extends VisualPreferences {
  readonly setTheme: (theme: ThemePreference) => void;
  readonly setDensity: (density: DensityPreference) => void;
  readonly resetPreferences: () => void;
}
