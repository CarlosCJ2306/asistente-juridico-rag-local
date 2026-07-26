import styles from "./SkipLink.module.css";

export interface SkipLinkProps {
  targetId: string;
}

export function SkipLink({ targetId }: SkipLinkProps) {
  return <a className={styles.skipLink} href={`#${targetId}`}>Saltar al contenido principal</a>;
}
