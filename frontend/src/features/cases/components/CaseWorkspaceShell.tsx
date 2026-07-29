import { Alert, Badge, Inline, Select, Stack, Text } from "../../../design-system";

import type { CaseWorkspaceShellProps } from "../types/caseWorkspace.types";
import styles from "./CaseWorkspaceShell.module.css";

export function CaseWorkspaceShell({ title, statusLabel, retentionLabel, reviewLabel, activeSection, sections, children, actions, readOnly = false, warnings = [], onActiveSectionChange }: CaseWorkspaceShellProps) {
  const activeLabel = sections.find((section) => section.id === activeSection)?.label ?? activeSection;
  return (
    <section className={styles.shell} aria-label="Espacio de trabajo del caso">
      <header className={styles.header}>
        <Stack gap="sm">
          <Text as="p" variant="caption">Caso</Text>
          <h1 className={styles.title}>{title}</h1>
          <Inline gap="sm" wrap>
            <Badge variant="neutral">{statusLabel}</Badge><Badge variant="neutral">{retentionLabel}</Badge><Badge variant="neutral">{reviewLabel}</Badge>
            {readOnly ? <Badge variant="warning">Solo lectura</Badge> : null}
          </Inline>
        </Stack>
        {actions ? <div className={styles.actions}>{actions}</div> : null}
      </header>
      {warnings.map((warning) => <Alert key={warning} variant="warning">{warning}</Alert>)}
      <nav className={styles.sections} aria-label="Secciones del caso">
        <div className={styles.desktopSections}>
          {sections.map((section) => <button key={section.id} type="button" className={section.id === activeSection ? styles.activeSection : styles.sectionButton} aria-current={section.id === activeSection ? "page" : undefined} onClick={onActiveSectionChange ? () => onActiveSectionChange(section.id) : undefined} disabled={!onActiveSectionChange}>{section.label}</button>)}
        </div>
        <div className={styles.mobileSections}>
          <label className={styles.selectorLabel} htmlFor="case-workspace-section">Sección activa</label>
          <Select id="case-workspace-section" value={activeSection} aria-label={`Sección activa: ${activeLabel}`} disabled={!onActiveSectionChange} onChange={onActiveSectionChange ? (event) => onActiveSectionChange(event.target.value) : undefined}>
            {sections.map((section) => <option key={section.id} value={section.id}>{section.label}</option>)}
          </Select>
        </div>
      </nav>
      <div className={styles.content}>{children}</div>
    </section>
  );
}
