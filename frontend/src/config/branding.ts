export type ResolvedTheme = "light" | "dark";
export type BrandPresetId = "local-green";

export interface BrandPalette {
  readonly primary: string;
  readonly primaryHover: string;
  readonly secondary: string;
  readonly accent: string;
}

export interface BrandPreset {
  readonly id: BrandPresetId;
  readonly light: BrandPalette;
  readonly dark: BrandPalette;
}

export interface BrandingConfig {
  readonly applicationName: string;
  readonly shortName: string;
  readonly organizationName?: string;
  readonly description: string;
  readonly environmentLabel: string;
  readonly logo?: { readonly light: string; readonly dark?: string; readonly alt: string };
  readonly compactLogo?: { readonly light: string; readonly dark?: string; readonly alt: string };
  readonly favicon: string;
  readonly themePreset: BrandPresetId;
}

export const brandPresets: Readonly<Record<BrandPresetId, BrandPreset>> = {
  "local-green": {
    id: "local-green",
    light: { primary: "#1e6847", primaryHover: "#164c34", secondary: "#285e94", accent: "#2f74b5" },
    dark: { primary: "#337e58", primaryHover: "#2f7652", secondary: "#9cc9f2", accent: "#7db7eb" },
  },
};

export const branding: BrandingConfig = {
  applicationName: "Asistente Jurídico RAG Local",
  shortName: "Asistente Jurídico",
  description: "Herramienta local de apoyo para trabajo jurídico profesional.",
  environmentLabel: "Entorno local",
  favicon: "/favicon.svg",
  themePreset: "local-green",
};

export function getBrandPalette(theme: ResolvedTheme): BrandPalette {
  return brandPresets[branding.themePreset][theme];
}
