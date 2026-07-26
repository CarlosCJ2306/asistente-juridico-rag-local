import { Container, PageHeader, Stack } from "../../design-system";
import type { PageLayoutProps } from "../layout.types";
import styles from "../layouts.module.css";

export function FullWidthLayout({ title, description, actions, metadata, children, className }: PageLayoutProps) {
  return (
    <Container width="fluid" className={[styles.fullWidthLayout, className].filter(Boolean).join(" ")}>
      <Stack gap="lg">
        {title ? <PageHeader title={title} description={description} actions={actions} metadata={metadata} /> : null}
        {children}
      </Stack>
    </Container>
  );
}
