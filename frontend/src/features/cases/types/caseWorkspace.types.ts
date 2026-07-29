import type { ReactNode } from "react";

export interface CaseWorkspaceSection {
  readonly id: string;
  readonly label: string;
}

export interface CaseWorkspaceShellProps {
  readonly title: string;
  readonly statusLabel: string;
  readonly retentionLabel: string;
  readonly reviewLabel: string;
  readonly activeSection: string;
  readonly sections: ReadonlyArray<CaseWorkspaceSection>;
  readonly children: ReactNode;
  readonly actions?: ReactNode;
  readonly readOnly?: boolean;
  readonly warnings?: ReadonlyArray<string>;
  readonly onActiveSectionChange?: (sectionId: string) => void;
}
