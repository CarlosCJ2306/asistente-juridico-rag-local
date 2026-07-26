import { Link } from "react-router-dom";

import type { BreadcrumbItem } from "../../app/navigation/navigation.types";
import styles from "./Breadcrumbs.module.css";

export interface BreadcrumbsProps {
  items: ReadonlyArray<BreadcrumbItem>;
}

export function Breadcrumbs({ items }: BreadcrumbsProps) {
  if (items.length === 0) return null;

  return (
    <nav aria-label="Ruta de navegación" className={styles.breadcrumbs}>
      <ol className={styles.list}>
        {items.map((item, index) => (
          <li key={item.id} className={styles.item}>
            {index > 0 ? <span className={styles.separator} aria-hidden="true">/</span> : null}
            {item.route && !item.current ? <Link to={item.route}>{item.label}</Link> : <span aria-current={item.current ? "page" : undefined}>{item.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}
