import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getHealth, toAppError } from "../api";
import { productConfig } from "../app/product.config";
import { ProfessionalReviewNotice } from "../components";
import { AsyncContent, Badge, Button, Card, ErrorState, Heading, Inline, ResponsiveGrid, Stack, Text } from "../design-system";
import { ContentLayout } from "../layouts";

export function HomePage() {
  const navigate = useNavigate();
  const healthQuery = useQuery({
    queryKey: ["backend-health"],
    queryFn: ({ signal }) => getHealth(signal),
  });

  let serviceStatus: ReactNode = <AsyncContent status="loading" />;
  if (healthQuery.isSuccess) {
    serviceStatus = <AsyncContent status="success"><Badge variant="success" role="status">Backend disponible</Badge></AsyncContent>;
  } else if (healthQuery.isError) {
    const error = toAppError(healthQuery.error);
    serviceStatus = error.category === "offline" ? (
      <AsyncContent status="offline" presentations={{ offline: <Badge variant="danger" role="status">Backend no disponible</Badge> }} />
    ) : (
      <AsyncContent status="error" presentations={{ error: <ErrorState title="Backend no disponible" message={error.userMessage} retryAction={<Button variant="secondary" onClick={() => void healthQuery.refetch()}>Reintentar</Button>} /> }} />
    );
  }

  return (
    <ContentLayout title="Inicio" description={productConfig.description}>
      <ResponsiveGrid minimum="standard">
        <Card as="section" aria-labelledby="assistant-flow-title">
          <Stack gap="md" align="start">
            <Heading as="h2" size="sm" id="assistant-flow-title">Asistente jurídico</Heading>
            <Text variant="secondary">Consulta evidencia local y revisa las fuentes documentales utilizadas en cada respuesta.</Text>
            <Button onClick={() => navigate("/chat")}>Ir al asistente</Button>
          </Stack>
        </Card>
        <Card as="section" aria-labelledby="case-intelligence-title">
          <Stack gap="md" align="start">
            <Heading as="h2" size="sm" id="case-intelligence-title">Inteligencia de casos</Heading>
            <Text variant="secondary">Conoce el espacio que organizará expediente, revisión y análisis cuando el dominio de casos esté disponible.</Text>
            <Button variant="secondary" onClick={() => navigate("/cases")}>Explorar Casos</Button>
          </Stack>
        </Card>
      </ResponsiveGrid>
      <Card as="section" aria-labelledby="shared-tools-title">
        <Stack gap="sm">
          <Heading as="h2" size="sm" id="shared-tools-title">Herramientas compartidas</Heading>
          <Inline gap="md" wrap>
            <Link to="/documents">Biblioteca jurídica</Link>
            <Link to="/documents/search">Búsqueda documental</Link>
            <Link to="/matrices-hpn">Matrices HPN</Link>
            <Link to="/legal-network">Red jurídica</Link>
          </Inline>
        </Stack>
      </Card>
      <Card as="section" aria-labelledby="service-status-title">
        <Stack gap="md" align="start">
          <Heading as="h2" size="sm" id="service-status-title">Estado del servicio local</Heading>
          <Text variant="secondary">Disponibilidad del backend configurado para esta instalación.</Text>
          {serviceStatus}
        </Stack>
      </Card>
      <ProfessionalReviewNotice variant="compact" />
    </ContentLayout>
  );
}
