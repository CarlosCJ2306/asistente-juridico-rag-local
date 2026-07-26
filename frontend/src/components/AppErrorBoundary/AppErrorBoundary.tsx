import { Component, type ReactNode } from "react";

import { Button, ErrorState } from "../../design-system";
import styles from "./AppErrorBoundary.module.css";

interface AppErrorBoundaryProps {
  readonly children: ReactNode;
}

interface AppErrorBoundaryState {
  readonly hasError: boolean;
}

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true };
  }

  private reload = () => window.location.reload();

  render() {
    if (this.state.hasError) {
      return (
        <main className={styles.fallback}>
          <ErrorState
            centered
            title="La interfaz no pudo continuar"
            message="Ocurrió un error inesperado. Puedes recargar la aplicación de forma segura."
            retryAction={<Button onClick={this.reload}>Recargar aplicación</Button>}
          />
        </main>
      );
    }
    return this.props.children;
  }
}
