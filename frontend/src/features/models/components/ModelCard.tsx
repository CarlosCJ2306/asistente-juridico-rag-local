import { Badge, Button, Card, Heading, Inline, Stack, Text } from "../../../design-system";
import type { CatalogModel } from "../types";
import styles from "../models.module.css";

function bytes(value: number | null): string { if (value === null) return "No informado"; return new Intl.NumberFormat("es-CO", { style: "unit", unit: value >= 1_000_000_000 ? "gigabyte" : "megabyte", unitDisplay: "short", maximumFractionDigits: 1 }).format(value / (value >= 1_000_000_000 ? 1_000_000_000 : 1_000_000)); }

interface ModelCardProps {
  readonly title: string;
  readonly model: CatalogModel;
  readonly runtimeState: "unloaded" | "loading" | "loaded" | "error";
  readonly busy: boolean;
  readonly selectionDisabled: boolean;
  readonly unloadDisabled?: boolean;
  readonly onSelect: () => void;
  readonly onLoad: () => void;
  readonly onUnload: () => void;
}

export function ModelCard({ title, model, runtimeState, busy, selectionDisabled, unloadDisabled = false, onSelect, onLoad, onUnload }: ModelCardProps) {
  const loaded = runtimeState === "loaded";
  return <Card as="section" className={styles.modelCard}><Stack gap="md"><div><Heading as="h2" size="sm">{title}</Heading><Text as="p" variant="secondary">{model.description}</Text></div><Inline gap="sm"><Badge variant={model.installed ? "success" : "warning"}>{model.installed ? "Instalado" : "No instalado"}</Badge><Badge variant={loaded ? "success" : "neutral"}>{loaded ? "Cargado" : "Descargado"}</Badge><Badge variant={model.compatibilityStatus === "compatible" ? "success" : model.compatibilityStatus === "not_installed" || model.compatibilityStatus === "disabled" ? "warning" : "info"}>{model.compatibilityStatus}</Badge></Inline><dl className={styles.metadata}><div><dt>Modelo activo</dt><dd>{model.displayName}</dd></div><div><dt>Familia</dt><dd>{model.family}</dd></div><div><dt>Formato</dt><dd>{model.format}</dd></div>{model.quantization ? <div><dt>Cuantización</dt><dd>{model.quantization}</dd></div> : null}<div><dt>Tamaño local</dt><dd>{bytes(model.sizeBytes)}</dd></div>{model.embeddingDimension ? <div><dt>Dimensión</dt><dd>{model.embeddingDimension}</dd></div> : null}{model.contextLength ? <div><dt>Contexto</dt><dd>{model.contextLength} tokens</dd></div> : null}<div><dt>Capacidades</dt><dd>{model.capabilities.join(", ") || "No informadas"}</dd></div></dl><Inline gap="sm" collapseOnSmall><Button variant="secondary" disabled={busy || selectionDisabled} onClick={onSelect}>Seleccionar</Button><Button loading={busy && !loaded} disabled={busy || loaded || !model.installed} onClick={onLoad}>Cargar</Button><Button variant="ghost" loading={busy && loaded} disabled={busy || !loaded || unloadDisabled} onClick={onUnload}>Descargar</Button></Inline></Stack></Card>;
}
