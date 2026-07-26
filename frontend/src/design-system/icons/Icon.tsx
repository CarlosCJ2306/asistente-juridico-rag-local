import type { SVGProps } from "react";

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, "children" | "aria-label" | "aria-hidden" | "focusable" | "role"> {
  title?: string;
}

function accessibilityProps(title: string | undefined) {
  return title
    ? { role: "img" as const, "aria-label": title }
    : { "aria-hidden": true as const };
}

export function CloseIcon({ title, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}>
      <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function InfoIcon({ title, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" />
      <path d="M12 11v6M12 7.5v.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function ChevronDownIcon({ title, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}>
      <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function MenuIcon({ title, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}>
      <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function CollapseIcon({ title, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}>
      <path d="M14 6l-6 6 6 6M20 4v16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ExpandIcon({ title, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}>
      <path d="M10 6l6 6-6 6M4 4v16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function HomeIcon({ title, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}>
      <path d="M3.5 10.5L12 3l8.5 7.5M5.5 9v11h13V9M9.5 20v-6h5v6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function NavigationIcon({ title, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}>
      <circle cx="6" cy="6" r="2" stroke="currentColor" strokeWidth="2" />
      <circle cx="18" cy="12" r="2" stroke="currentColor" strokeWidth="2" />
      <circle cx="6" cy="18" r="2" stroke="currentColor" strokeWidth="2" />
      <path d="M8 6h3a3 3 0 013 3v0a3 3 0 003 3M8 18h3a3 3 0 003-3v0a3 3 0 013-3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function ArrowBackIcon({ title, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}>
      <path d="M19 12H5M11 6l-6 6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function BrandIcon({ title, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}>
      <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
      <path d="M8 9.5h8M8 14.5h8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
