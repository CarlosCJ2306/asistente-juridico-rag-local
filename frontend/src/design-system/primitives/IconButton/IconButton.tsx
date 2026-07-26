import { forwardRef, type ButtonHTMLAttributes, type ReactElement } from "react";

import { classNames } from "../../internal/classNames";
import styles from "../primitives.module.css";

export interface IconButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label"> {
  "aria-label": string;
  children: ReactElement;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  function IconButton({ className, children, type = "button", ...props }, ref) {
    return (
      <button
        {...props}
        ref={ref}
        type={type}
        className={classNames(styles.iconButton, className)}
      >
        {children}
      </button>
    );
  },
);
