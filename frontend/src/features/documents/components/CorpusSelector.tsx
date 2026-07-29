import { FormField, Select } from "../../../design-system";
import type { KnowledgeLayer, PublicDocument } from "../types";

interface CorpusSelectorProps {
  readonly documents: readonly PublicDocument[];
  readonly documentId: string;
  readonly documentType: string;
  readonly knowledgeLayer: string;
  readonly onDocumentIdChange: (value: string) => void;
  readonly onDocumentTypeChange: (value: string) => void;
  readonly onKnowledgeLayerChange: (value: string) => void;
  readonly allowedKnowledgeLayers?: readonly KnowledgeLayer[];
}

const DEFAULT_LAYERS: readonly KnowledgeLayer[] = [
  "managed_corpus",
  "private_library",
  "temporary",
  "web_verified",
];

const LAYER_LABELS: Record<Exclude<KnowledgeLayer, "global_candidate">, string> = {
  managed_corpus: "Corpus administrado",
  private_library: "Biblioteca privada",
  temporary: "Temporal",
  web_verified: "Fuente web verificada",
};

export function CorpusSelector({
  documents,
  documentId,
  documentType,
  knowledgeLayer,
  onDocumentIdChange,
  onDocumentTypeChange,
  onKnowledgeLayerChange,
  allowedKnowledgeLayers = DEFAULT_LAYERS,
}: CorpusSelectorProps) {
  const eligibleDocuments = documents.filter((document) => document.ragEligible);
  const layers = allowedKnowledgeLayers.filter(
    (layer): layer is Exclude<KnowledgeLayer, "global_candidate"> => layer !== "global_candidate",
  );

  return (
    <>
      <FormField label="Documento específico">
        {(props) => (
          <Select {...props} value={documentId} onChange={(event) => onDocumentIdChange(event.target.value)}>
            <option value="">Todos los documentos elegibles</option>
            {eligibleDocuments.map((document) => (
              <option key={document.id} value={document.id}>
                {document.displayName} · {LAYER_LABELS[document.knowledgeLayer as Exclude<KnowledgeLayer, "global_candidate">] ?? document.knowledgeLayer}
              </option>
            ))}
          </Select>
        )}
      </FormField>
      <FormField label="Tipo documental">
        {(props) => (
          <Select {...props} value={documentType} onChange={(event) => onDocumentTypeChange(event.target.value)}>
            <option value="">Todos los tipos</option>
            <option value="expediente">Expediente</option>
            <option value="normativa">Normativa</option>
            <option value="jurisprudencia">Jurisprudencia</option>
            <option value="otro">Otro</option>
          </Select>
        )}
      </FormField>
      <FormField label="Capa documental">
        {(props) => (
          <Select {...props} value={knowledgeLayer} onChange={(event) => onKnowledgeLayerChange(event.target.value)}>
            <option value="">Todas las capas elegibles</option>
            {layers.map((layer) => <option key={layer} value={layer}>{LAYER_LABELS[layer]}</option>)}
          </Select>
        )}
      </FormField>
    </>
  );
}
