import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { getHealth, toAppError } from "../api";
import { productConfig } from "../app/product.config";
import { ProfessionalReviewNotice } from "../components";
import { AsyncContent, Badge, Button, Card, ErrorState, Heading, Stack, Text } from "../design-system";
import { ContentLayout } from "../layouts";

export function HomePage() {
  const healthQuery = useQuery({
    queryKey: ["backend-health"],
    queryFn: ({ signal }) => getHealth(signal),
  });

  let serviceStatus: ReactNode = <AsyncContent status="loading" />;
  if (healthQuery.isSuccess) {
    serviceStatus = (
      <AsyncContent status="success">
        <Badge variant="success" role="status">Backend disponible</Badge>
      </AsyncContent>
    );
  } else if (healthQuery.isError) {
    const error = toAppError(healthQuery.error);
    serviceStatus = error.category === "offline" ? (
      <AsyncContent
        status="offline"
        presentations={{ offline: <Badge variant="danger" role="status">Backend no disponible</Badge> }}
      />
    ) : (
      <AsyncContent
        status="error"
        presentations={{
          error: (
            <ErrorState
              title="Backend no disponible"
              message={error.userMessage}
              retryAction={<Button variant="secondary" onClick={() => void healthQuery.refetch()}>Reintentar</Button>}
            />
          ),
        }}
      />
    );
  }

  return (
    <ContentLayout title="Inicio" description={productConfig.description}>
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
