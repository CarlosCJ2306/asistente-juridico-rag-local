import type { AppErrorCategory } from "../types/errors";

export const ERROR_MESSAGES: Readonly<Record<AppErrorCategory, string>> = {
  validation: "Revisa los datos e inténtalo de nuevo.",
  unauthorized: "La operación requiere una sesión autorizada.",
  forbidden: "La sesión actual no permite esta operación.",
  not_found: "El recurso solicitado no está disponible.",
  conflict: "La operación entra en conflicto con el estado actual.",
  too_large: "La solicitud supera el tamaño permitido.",
  unavailable: "El servicio local no está disponible en este momento.",
  server: "El servicio local no pudo completar la operación.",
  network: "No fue posible conectar con el servicio local.",
  offline: "El navegador informa que no hay conexión disponible.",
  timeout: "El servicio local tardó demasiado en responder.",
  unknown: "Ocurrió un error controlado. Inténtalo de nuevo cuando corresponda.",
};
