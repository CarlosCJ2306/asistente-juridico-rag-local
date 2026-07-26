import type { ReactNode } from "react";

export interface PageLayoutProps {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  metadata?: ReactNode;
  children: ReactNode;
  className?: string;
}
