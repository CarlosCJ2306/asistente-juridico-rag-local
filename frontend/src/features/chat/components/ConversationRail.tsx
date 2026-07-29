import { useState } from "react";
import { Link } from "react-router-dom";

import { Button, ChatIcon, CollapseIcon, IconButton, MenuIcon, Modal, Text, TextInput, Tooltip } from "../../../design-system";
import type { ConversationSummary } from "../types";
import styles from "../chat.module.css";

interface ConversationRailProps {
  readonly items: readonly ConversationSummary[];
  readonly currentId: string | undefined;
  readonly pending: boolean;
  readonly collapsed?: boolean;
  readonly onCollapsedChange?: (value: boolean) => void;
  readonly onNew: () => void;
  readonly onSelect?: () => void;
  readonly onRename: (id: string, title: string) => void;
  readonly onArchive: (id: string, status: "active" | "archived") => void;
  readonly onDelete: (id: string) => void;
}

function activity(value: string): string { return new Date(value).toLocaleDateString([], { day: "2-digit", month: "short" }); }

export function ConversationRail({ items, currentId, pending, collapsed = false, onCollapsedChange, onNew, onSelect, onRename, onArchive, onDelete }: ConversationRailProps) {
  const [actionsFor, setActionsFor] = useState<ConversationSummary>();
  const [rename, setRename] = useState<ConversationSummary>();
  const [remove, setRemove] = useState<ConversationSummary>();
  const [title, setTitle] = useState("");
  function startRename(item: ConversationSummary) { setActionsFor(undefined); setRename(item); setTitle(item.title); }

  if (collapsed) return <aside className={`${styles.rail} ${styles.railCollapsed}`} aria-label="Conversaciones"><div className={styles.collapsedRailActions}><Tooltip content="Nueva conversación"><IconButton aria-label="Nueva conversación" onClick={onNew}><ChatIcon /></IconButton></Tooltip>{onCollapsedChange ? <Tooltip content="Mostrar conversaciones"><IconButton aria-label="Mostrar conversaciones" onClick={() => onCollapsedChange(false)}><MenuIcon /></IconButton></Tooltip> : null}</div></aside>;

  return <aside className={styles.rail} aria-label="Conversaciones"><header className={styles.railHeader}><h2 className={styles.railTitle}>Conversaciones</h2>{onCollapsedChange ? <Tooltip content="Ocultar conversaciones"><IconButton aria-label="Ocultar conversaciones" onClick={() => onCollapsedChange(true)}><CollapseIcon /></IconButton></Tooltip> : null}</header><Button className={styles.railNewButton} leadingIcon={<ChatIcon />} fullWidth onClick={onNew}>Nueva conversación</Button><Text variant="secondary" className={styles.railNotice}>Sesión invitada · historial local temporal</Text><nav aria-label="Historial de conversaciones" className={styles.railScroll}><ul className={styles.conversationList}>{items.map((item) => <li key={item.id} className={item.id === currentId ? styles.currentConversation : undefined}><div className={styles.conversationRow}><Link className={styles.conversationLink} to={`/chat/${item.id}`} onClick={onSelect}><span>{item.title}</span><small>{item.id === currentId ? "Activa" : activity(item.lastActivityAt)}</small></Link><IconButton aria-label={`Acciones de ${item.title}`} onClick={() => setActionsFor(item)}><span className={styles.actionMenuGlyph} aria-hidden="true">⋮</span></IconButton></div></li>)}</ul>{items.length === 0 ? <Text variant="secondary">Aún no tienes conversaciones activas.</Text> : null}</nav><Modal open={Boolean(actionsFor)} onOpenChange={(open) => { if (!open) setActionsFor(undefined); }} title="Acciones de conversación" size="sm"><div className={styles.conversationMenu}><Button variant="ghost" fullWidth onClick={() => { if (actionsFor) startRename(actionsFor); }} disabled={pending}>Renombrar</Button><Button variant="ghost" fullWidth onClick={() => { if (actionsFor) onArchive(actionsFor.id, actionsFor.status === "active" ? "archived" : "active"); setActionsFor(undefined); }} disabled={pending}>{actionsFor?.status === "active" ? "Archivar" : "Restaurar"}</Button><Button variant="danger" fullWidth onClick={() => { setRemove(actionsFor); setActionsFor(undefined); }} disabled={pending}>Eliminar</Button></div></Modal><Modal open={Boolean(rename)} onOpenChange={(open) => { if (!open) setRename(undefined); }} title="Renombrar conversación" footer={<><Button variant="secondary" onClick={() => setRename(undefined)}>Cancelar</Button><Button onClick={() => { if (rename && title.trim()) onRename(rename.id, title.trim()); setRename(undefined); }} disabled={!title.trim() || title.length > 200}>Guardar</Button></>}><TextInput aria-label="Título de la conversación" value={title} maxLength={200} onChange={(event) => setTitle(event.target.value)} /></Modal><Modal open={Boolean(remove)} onOpenChange={(open) => { if (!open) setRemove(undefined); }} title="Eliminar conversación" description="Esta acción elimina sus mensajes, respuestas y snapshots de citas." footer={<><Button variant="secondary" onClick={() => setRemove(undefined)}>Cancelar</Button><Button variant="danger" onClick={() => { if (remove) onDelete(remove.id); setRemove(undefined); }}>Eliminar</Button></>}><Text>La eliminación no puede deshacerse.</Text></Modal></aside>;
}
