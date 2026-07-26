import { forwardRef } from "react";

import { IconButton, MenuIcon } from "../../design-system";

export interface MobileNavigationTriggerProps {
  onOpen: () => void;
  open: boolean;
  controls: string;
  className?: string;
}

export const MobileNavigationTrigger = forwardRef<HTMLButtonElement, MobileNavigationTriggerProps>(
  function MobileNavigationTrigger({ onOpen, open, controls, className }, ref) {
    return (
      <IconButton
        ref={ref}
        aria-label="Abrir navegación principal"
        aria-expanded={open}
        aria-controls={controls}
        aria-haspopup="dialog"
        onClick={onOpen}
        className={className}
      >
        <MenuIcon />
      </IconButton>
    );
  },
);
