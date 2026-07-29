import { Link } from "react-router-dom";

import { Card, EmptyState, Heading, Inline, Stack, Text } from "../../../design-system";
import { ContentLayout } from "../../../layouts";

export function CasesPage() {
  return (
    <ContentLayout title="Casos" description="Espacio futuro para reunir expediente, revisión y análisis de un caso sin duplicar las herramientas actuales.">
      <Stack gap="lg">
        <Card as="section" aria-labelledby="case-intelligence-title">
          <Stack gap="md">
            <Heading as="h2" size="sm" id="case-intelligence-title">Inteligencia de casos</Heading>
            <Text variant="secondary">Cuando el dominio de casos esté disponible, reunirá expediente, Matriz HPN, Red jurídica, métricas, simulaciones y asistencia de caso bajo revisiones y retención explícitas.</Text>
            <ol><li>Expediente y evidencia elegible.</li><li>Revisión humana y artefactos trazables.</li><li>Análisis técnico sin decisiones jurídicas automáticas.</li></ol>
          </Stack>
        </Card>
        <EmptyState title="Aún no hay casos disponibles" description="La creación y gestión de expedientes se habilitarán con el dominio Case. Esta pantalla no crea ni simula datos." action={<Inline gap="md" wrap><Link to="/chat">Ir al Asistente jurídico</Link><Link to="/documents">Abrir Biblioteca jurídica</Link><Link to="/matrices-hpn">Ver Matrices HPN globales</Link></Inline>} />
      </Stack>
    </ContentLayout>
  );
}
