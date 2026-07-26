export interface ProductConfig {
  readonly applicationName: string;
  readonly shortName: string;
  readonly description: string;
  readonly environmentLabel: string;
}

export const productConfig = {
  applicationName: "Asistente Jurídico RAG Local",
  shortName: "Asistente Jurídico",
  description: "Herramienta local de apoyo para trabajo jurídico profesional.",
  environmentLabel: "Entorno local",
} as const satisfies ProductConfig;
