import { useEffect } from "react";

import { branding } from "../config/branding";

export function BrandMetadata() {
  useEffect(() => {
    document.title = branding.applicationName;
    const description = document.querySelector('meta[name="description"]') ?? document.head.appendChild(document.createElement("meta"));
    description.setAttribute("name", "description");
    description.setAttribute("content", branding.description);
    const icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]') ?? document.head.appendChild(document.createElement("link"));
    icon.rel = "icon";
    icon.type = "image/svg+xml";
    icon.href = branding.favicon;
  }, []);
  return null;
}
