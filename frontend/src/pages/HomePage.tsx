import { useQuery } from "@tanstack/react-query";

import { getHealth } from "../api/health";

export function HomePage() {
  const healthQuery = useQuery({
    queryKey: ["backend-health"],
    queryFn: getHealth,
    retry: 1,
  });

  let connectionStatus = "Conectando…";
  let statusClass = "status status--loading";

  if (healthQuery.isSuccess) {
    connectionStatus = "Backend disponible";
    statusClass = "status status--available";
  } else if (healthQuery.isError) {
    connectionStatus = "Backend no disponible";
    statusClass = "status status--unavailable";
  }

  return (
    <main className="home">
      <section className="card" aria-labelledby="page-title">
        <p className="eyebrow">Entorno local</p>
        <h1 id="page-title">Asistente Jurídico RAG Local</h1>
        <p className="notice">
          Herramienta de apoyo. No sustituye el criterio de un profesional
          competente.
        </p>
        <p className={statusClass} role="status" aria-live="polite">
          <span className="status__indicator" aria-hidden="true" />
          {connectionStatus}
        </p>
      </section>
    </main>
  );
}
