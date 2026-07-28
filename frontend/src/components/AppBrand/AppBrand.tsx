import { Link } from "react-router-dom";

import { productConfig } from "../../app/product.config";
import { usePreferences } from "../../hooks/usePreferences";
import { BrandIcon } from "../../design-system";
import styles from "./AppBrand.module.css";

export interface AppBrandProps {
  compact?: boolean;
}

export function AppBrand({ compact = false }: AppBrandProps) {
  const { theme } = usePreferences();
  const accessibleName = compact ? productConfig.shortName : productConfig.applicationName;
  const asset = compact ? productConfig.compactLogo : productConfig.logo;
  const logoSource = asset ? (theme === "dark" ? asset.dark ?? asset.light : asset.light) : undefined;
  return (
    <Link to="/" title={compact ? productConfig.applicationName : undefined} className={[styles.brand, compact ? styles.brandCompact : null].filter(Boolean).join(" ")} aria-label={`${accessibleName}, ir al inicio`}>
      {logoSource ? <img className={styles.logo} src={logoSource} alt={asset?.alt ?? ""} /> : <BrandIcon className={styles.icon} />}
      {compact ? null : (
        <span className={styles.names}>
          <span className={styles.name}>{productConfig.applicationName}</span>
          <span className={styles.environment}>{productConfig.environmentLabel}</span>
        </span>
      )}
    </Link>
  );
}
