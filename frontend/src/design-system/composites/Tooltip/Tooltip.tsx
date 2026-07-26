import { cloneElement, useId, useState, type KeyboardEvent, type ReactElement } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../composites.module.css";

interface DescribedElementProps { "aria-describedby"?: string; }
export interface TooltipProps {
  content: string;
  children: ReactElement<DescribedElementProps>;
  position?: "top" | "bottom" | "start" | "end";
  className?: string;
}

const positionClasses = { top: styles.tooltipTop, bottom: styles.tooltipBottom, start: styles.tooltipStart, end: styles.tooltipEnd } as const;

export function Tooltip({ content, children, position = "top", className }: TooltipProps) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const describedBy = [children.props["aria-describedby"], id].filter(Boolean).join(" ");
  const handleKeyDown = (event: KeyboardEvent<HTMLSpanElement>) => {
    if (event.key === "Escape") setVisible(false);
  };
  return (
    <span className={classNames(styles.tooltipAnchor, className)} onMouseEnter={() => setVisible(true)} onMouseLeave={() => setVisible(false)} onFocusCapture={() => setVisible(true)} onBlurCapture={() => setVisible(false)} onKeyDown={handleKeyDown}>
      {cloneElement(children, { "aria-describedby": describedBy })}
      {visible ? <span id={id} role="tooltip" className={classNames(styles.tooltip, positionClasses[position])}>{content}</span> : null}
    </span>
  );
}
