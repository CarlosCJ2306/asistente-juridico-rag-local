import { toAppError } from "../../../api";

const messages: Readonly<Record<string, string>> = {
  MODEL_NOT_FOUND: "El modelo seleccionado no pertenece al catálogo local.",
  MODEL_NOT_INSTALLED: "El modelo seleccionado no está instalado localmente.",
  MODEL_TYPE_MISMATCH: "El modelo seleccionado no corresponde al tipo requerido.",
  MODEL_DISABLED: "El modelo seleccionado no está habilitado.",
  MODEL_CURRENTLY_LOADED: "Descarga el modelo actual antes de cambiar la selección.",
  MODEL_SELECTION_INVALID: "La selección del modelo local no es válida.",
  MODEL_CATALOG_INVALID: "El catálogo local de modelos no pudo validarse.",
  MODEL_SELECTION_STORAGE_ERROR: "No fue posible guardar la selección del modelo.",
};

export function modelErrorMessage(error: unknown): string { const appError = toAppError(error); return messages[appError.code] ?? (appError.category === "network" || appError.category === "offline" ? appError.userMessage : "No fue posible completar la operación sobre el modelo local."); }
