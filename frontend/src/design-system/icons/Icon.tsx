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

export function DocumentIcon({ title, ...props }: IconProps) {
  return <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}><path d="M6 3.5h8l4 4V20.5H6zM14 3.5v4h4M9 12h6M9 16h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export function MatrixIcon({ title, ...props }: IconProps) {
  return <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}><rect x="4" y="4" width="16" height="16" rx="1" stroke="currentColor" strokeWidth="2" /><path d="M4 10h16M4 15h16M10 4v16" stroke="currentColor" strokeWidth="2" /></svg>;
}

export function NetworkIcon({ title, ...props }: IconProps) {
  return <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}><circle cx="6" cy="12" r="2" stroke="currentColor" strokeWidth="2"/><circle cx="18" cy="6" r="2" stroke="currentColor" strokeWidth="2"/><circle cx="18" cy="18" r="2" stroke="currentColor" strokeWidth="2"/><path d="M8 11l8-4M8 13l8 4" stroke="currentColor" strokeWidth="2"/></svg>;
}

export function ChatIcon({ title, ...props }: IconProps) {
  return <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}><path d="M5 5h14v10H9l-4 4z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

export function SearchIcon({ title, ...props }: IconProps) {
  return <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}><circle cx="10.5" cy="10.5" r="5.5" stroke="currentColor" strokeWidth="2"/><path d="M15 15l4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>;
}

export function SettingsIcon({ title, ...props }: IconProps) {
  return <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}><circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2"/><path d="M12 3v2M12 19v2M21 12h-2M5 12H3M18.4 5.6L17 7M7 17l-1.4 1.4M18.4 18.4L17 17M7 7L5.6 5.6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>;
}

export function ModelIcon({ title, ...props }: IconProps) {
  return <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}><path d="M5 7.5h14v9H5zM8 4v3.5M12 4v3.5M16 4v3.5M8 16.5V20M12 16.5V20M16 16.5V20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/><circle cx="9" cy="12" r="1" fill="currentColor"/><circle cx="15" cy="12" r="1" fill="currentColor"/></svg>;
}

export function BrandIcon({ title, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" {...props} focusable="false" {...accessibilityProps(title)}>
      <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
      <path d="M8 9.5h8M8 14.5h8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
