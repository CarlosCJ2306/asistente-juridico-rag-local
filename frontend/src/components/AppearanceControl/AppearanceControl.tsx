import { usePreferences } from "../../hooks/usePreferences";
import type { ThemePreference } from "../../types/preferences";
import { Button, Inline, VisuallyHidden } from "../../design-system";

const OPTIONS: ReadonlyArray<{ readonly value: ThemePreference; readonly label: string }> = [
  { value: "light", label: "Claro" },
  { value: "dark", label: "Oscuro" },
  { value: "system", label: "Sistema" },
];

export function AppearanceControl() {
  const { theme, setTheme } = usePreferences();
  return (
    <Inline gap="xs" role="group" aria-label="Apariencia">
      <VisuallyHidden>Seleccionar apariencia</VisuallyHidden>
      {OPTIONS.map((option) => (
        <Button key={option.value} size="sm" variant={theme === option.value ? "primary" : "ghost"} aria-pressed={theme === option.value} onClick={() => setTheme(option.value)}>{option.label}</Button>
      ))}
    </Inline>
  );
}
