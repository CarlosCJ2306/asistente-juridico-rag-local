import { Link } from "react-router-dom";

import { ArrowBackIcon, ErrorState } from "../design-system";
import { ContentLayout } from "../layouts";
import styles from "./NotFoundPage.module.css";

export function NotFoundPage() {
  const homeLink = (
    <Link to="/" className={styles.homeLink}>
      <ArrowBackIcon />
      <span>Volver al inicio</span>
    </Link>
  );

  return (
    <ContentLayout title="Página no encontrada">
      <ErrorState
        title="La página solicitada no existe"
        message="Comprueba la navegación disponible o vuelve al inicio de la aplicación."
        retryAction={homeLink}
      />
    </ContentLayout>
  );
}
