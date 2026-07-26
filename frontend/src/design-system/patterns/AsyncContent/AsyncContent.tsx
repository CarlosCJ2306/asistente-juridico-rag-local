import type { ReactNode } from "react";

import { EmptyState } from "../../composites/EmptyState/EmptyState";
import { ErrorState } from "../../composites/ErrorState/ErrorState";
import { Spinner } from "../../primitives/Spinner/Spinner";
import { classNames } from "../../internal/classNames";
import styles from "../patterns.module.css";

export type AsyncStatus = "idle" | "loading" | "success" | "empty" | "error" | "unauthorized" | "forbidden" | "offline";
type NonSuccessStatus = Exclude<AsyncStatus, "success">;

interface AsyncContentSharedProps {
  presentations?: Partial<Record<NonSuccessStatus, ReactNode>>;
  className?: string;
}

export type AsyncContentProps = AsyncContentSharedProps & (
  | { status: "success"; children: ReactNode }
  | { status: NonSuccessStatus; children?: never }
);

function defaultPresentation(status: NonSuccessStatus): ReactNode {
  switch (status) {
    case "idle": return null;
    case "loading": return <div className={styles.asyncLoading} role="status"><Spinner label="Cargando contenido" /><span>Cargando…</span></div>;
    case "empty": return <EmptyState title="Sin contenido" description="No hay elementos para mostrar." />;
    case "error": return <ErrorState title="No fue posible cargar" message="Ocurrió un error controlado. Inténtalo de nuevo cuando corresponda." />;
    case "unauthorized": return <ErrorState title="Sesión requerida" message="La operación requiere una sesión autorizada." />;
    case "forbidden": return <ErrorState title="Acceso no permitido" message="La sesión actual no tiene acceso a esta operación." />;
    case "offline": return <ErrorState title="Servicio local no disponible" message="Comprueba que el servicio local esté disponible antes de reintentar." />;
  }
}

export function AsyncContent({ status, children, presentations = {}, className }: AsyncContentProps) {
  const content = status === "success" ? children : (presentations[status] ?? defaultPresentation(status));
  return <div className={classNames(styles.async, className)} data-async-status={status}>{content}</div>;
}
