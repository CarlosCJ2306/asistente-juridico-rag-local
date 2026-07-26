import { useEffect, useState } from "react";

import { Button, Card, ErrorState, Heading, Spinner, Stack, Text } from "../../../design-system";
import styles from "../legalNetwork.module.css";

export function LegalGraphFrame({ src }: { readonly src: string }) {
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => { setState("loading"); }, [src, attempt]);

  return <Card as="section" padding="lg" className={styles.sectionCard}><Stack gap="md"><div><Heading as="h2">Vista visual de la red</Heading><Text id="legal-graph-frame-description" variant="secondary">Visualización PyVis local, aislada y de solo lectura. La alternativa textual permanece disponible debajo.</Text></div>{state === "loading" ? <div className={styles.frameStatus}><Spinner label="Cargando visualización local" /><Text variant="secondary">Cargando visualización local…</Text></div> : null}{state === "error" ? <ErrorState title="No fue posible cargar la visualización" message="La alternativa textual de la red continúa disponible." retryAction={<Button variant="secondary" onClick={() => setAttempt((value) => value + 1)}>Reintentar</Button>} /> : <iframe key={`${src}-${attempt}`} className={styles.frame} src={src} title="Visualización local de la red jurídica" sandbox="allow-scripts" referrerPolicy="no-referrer" loading="lazy" aria-describedby="legal-graph-frame-description" onLoad={() => setState("ready")} onError={() => setState("error")} />}</Stack></Card>;
}
