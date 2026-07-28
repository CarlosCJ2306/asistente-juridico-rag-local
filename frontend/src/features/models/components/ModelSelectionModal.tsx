import { useState } from "react";

import { Alert, Button, Inline, Modal, Radio, Stack, Text } from "../../../design-system";
import type { CatalogModel, ModelType } from "../types";

interface ModelSelectionModalProps {
  readonly open: boolean;
  readonly modelType: ModelType;
  readonly models: readonly CatalogModel[];
  readonly activeModelId: string;
  readonly pending: boolean;
  readonly errorMessage?: string;
  readonly onOpenChange: (open: boolean) => void;
  readonly onConfirm: (modelId: string) => void;
}

export function ModelSelectionModal({ open, modelType, models, activeModelId, pending, errorMessage, onOpenChange, onConfirm }: ModelSelectionModalProps) {
  const [selectedId, setSelectedId] = useState(activeModelId);
  const selected = models.find((model) => model.modelId === selectedId);
  const warning = modelType === "embedding" ? "El índice actual puede quedar incompatible y requerir una reconstrucción explícita. No se borrarán PDF, páginas ni chunks y el nuevo modelo no se cargará automáticamente." : "La selección afectará las próximas respuestas generadas. No modifica el índice documental y el nuevo modelo no se cargará automáticamente.";
  const dismissPolicy = pending ? { preventClose: true as const, preventCloseReason: "La selección está en curso." } : { preventClose: false as const };
  return <Modal open={open} onOpenChange={onOpenChange} title={modelType === "embedding" ? "Seleccionar modelo de embeddings" : "Seleccionar modelo generativo"} description="Solo se muestran modelos permitidos por el catálogo local." {...dismissPolicy}><Stack gap="md"><Alert variant="warning" title="Confirma el cambio">{warning}</Alert><fieldset><legend>Modelos disponibles</legend><Stack gap="sm">{models.map((model) => <Radio key={model.modelId} name={`model-${modelType}`} value={model.modelId} checked={selectedId === model.modelId} disabled={pending || !model.installed || model.compatibilityStatus === "disabled"} onChange={() => setSelectedId(model.modelId)} label={`${model.displayName} · ${model.installed ? "instalado" : "no instalado"}${model.active ? " · activo" : ""}`} />)}</Stack></fieldset>{errorMessage ? <Alert variant="error">{errorMessage}</Alert> : null}<Text variant="caption" aria-live="polite">{pending ? "Guardando selección…" : "La selección se conserva en el backend local."}</Text><Inline gap="sm" justify="end" collapseOnSmall><Button variant="ghost" disabled={pending} onClick={() => onOpenChange(false)}>Cancelar</Button><Button loading={pending} disabled={pending || !selected || !selected.installed || selectedId === activeModelId} onClick={() => onConfirm(selectedId)}>Confirmar selección</Button></Inline></Stack></Modal>;
}
