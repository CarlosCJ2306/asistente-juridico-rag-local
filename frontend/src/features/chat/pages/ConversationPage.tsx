import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { isRequestCancelledError } from "../../../api";
import { Button, Drawer, ErrorState, Heading, IconButton, InfoIcon, MenuIcon, Modal, Stack, Text, Tooltip } from "../../../design-system";
import { ConversationComposer } from "../components/ConversationComposer";
import { ConversationEvidence } from "../components/ConversationEvidence";
import { ConversationRail } from "../components/ConversationRail";
import { ConversationThread } from "../components/ConversationThread";
import { useConversation, useConversationActions, useConversationList, useConversationMessage } from "../hooks";
import type { ConversationCitation, ConversationInput, ConversationMessage } from "../types";
import styles from "../chat.module.css";

function copyMessage(message: ConversationMessage): string {
  const claims = message.claims.map((claim, index) => `${index + 1}. ${claim.statement}`).join("\n");
  const sources = message.citations.map((citation) => `${citation.marker} ${citation.displayName} · Página ${citation.startPage}`).join("\n");
  return [message.content, claims, sources].filter(Boolean).join("\n\n");
}

export function ConversationPage() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const list = useConversationList();
  const detail = useConversation(conversationId);
  const actions = useConversationActions();
  const send = useConversationMessage();
  const [draft, setDraft] = useState("");
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [sessionOpen, setSessionOpen] = useState(false);
  const [evidence, setEvidence] = useState<{ message: ConversationMessage; citation?: string; trigger: HTMLElement }>();
  const messages = detail.data?.messages ?? [];
  const pending = send.isPending || actions.create.isPending;
  const accessFailure = detail.isError && !isRequestCancelledError(detail.error);
  const title = detail.data?.title ?? "Nueva conversación";

  async function submit(input: ConversationInput) {
    let id = conversationId;
    if (!id) {
      try { id = (await actions.create.mutateAsync()).id; navigate(`/chat/${id}`); } catch { return; }
    }
    send.mutate({ id, input, idempotencyKey: send.newKey() }, { onSuccess: () => { setDraft(""); setEvidence(undefined); } });
  }
  function openEvidence(message: ConversationMessage, trigger: HTMLElement, citation?: ConversationCitation) { setEvidence({ message, citation: citation?.id, trigger }); }
  function closeEvidence(open: boolean) { if (open) return; const trigger = evidence?.trigger; setEvidence(undefined); globalThis.setTimeout(() => trigger?.focus(), 0); }
  function onNew() { setDraft(""); navigate("/chat"); }

  const actionPending = actions.rename.isPending || actions.archive.isPending || actions.remove.isPending;
  const rail = <ConversationRail items={list.data?.items ?? []} currentId={conversationId} pending={actionPending} collapsed={railCollapsed} onCollapsedChange={setRailCollapsed} onNew={onNew} onSelect={() => setRailOpen(false)} onRename={(id, titleValue) => actions.rename.mutate({ id, title: titleValue })} onArchive={(id, status) => actions.archive.mutate({ id, status })} onDelete={(id) => { actions.remove.mutate(id); onNew(); }} />;
  const drawerRail = <ConversationRail items={list.data?.items ?? []} currentId={conversationId} pending={actionPending} onNew={onNew} onSelect={() => setRailOpen(false)} onRename={(id, titleValue) => actions.rename.mutate({ id, title: titleValue })} onArchive={(id, status) => actions.archive.mutate({ id, status })} onDelete={(id) => { actions.remove.mutate(id); onNew(); }} />;
  const workspaceClass = [styles.chatWorkspace, railCollapsed ? styles.chatWorkspaceCollapsed : null].filter(Boolean).join(" ");

  return <>
    <div className={workspaceClass}>
      {rail}
      <main className={styles.chatMain}>
        <header className={styles.chatHeader}>
          <div className={styles.mobileConversationControl}><Button variant="secondary" leadingIcon={<MenuIcon />} onClick={() => setRailOpen(true)}>Conversaciones</Button></div>
          <Tooltip content={title}><div className={styles.conversationTitle}><Heading as="h1" size="sm">{title}</Heading></div></Tooltip>
          <div className={styles.chatHeaderActions}>
            {detail.data?.status ? <Text variant="secondary" className={styles.conversationStatus}>{detail.data.status === "archived" ? "Archivada" : "Activa"}</Text> : null}
            <Tooltip content="Información de sesión invitada"><IconButton aria-label="Información de sesión invitada" onClick={() => setSessionOpen(true)}><InfoIcon /></IconButton></Tooltip>
          </div>
        </header>
        <div className={styles.threadScroller}>
          <ConversationThread messages={messages} pending={pending} onCitation={(message, citation, trigger) => openEvidence(message, trigger, citation)} onEvidence={(message, trigger) => openEvidence(message, trigger)} onCopy={(message) => void navigator.clipboard.writeText(copyMessage(message))} onExample={setDraft} />
          {accessFailure ? <ErrorState title="No fue posible acceder a esta conversación." message="Vuelve al historial para iniciar o abrir una conversación disponible." retryAction={<Link to="/chat">Ir a conversaciones</Link>} /> : null}
        </div>
        <footer className={styles.composer}>
          <ConversationComposer value={draft} pending={pending} onChange={setDraft} onSubmit={(input) => void submit(input)} onCancel={() => send.cancel()} />
          <Text variant="secondary" className={styles.reviewNote}>Las respuestas son contenido asistido y requieren revisión de un profesional competente.</Text>
        </footer>
      </main>
    </div>
    <Drawer open={railOpen} onOpenChange={setRailOpen} title="Conversaciones" position="start">{drawerRail}</Drawer>
    <Drawer open={Boolean(evidence)} onOpenChange={closeEvidence} title="Evidencia de esta respuesta" position="end"><ConversationEvidence message={evidence?.message} selected={evidence?.citation} /></Drawer>
    <Modal open={sessionOpen} onOpenChange={setSessionOpen} title="Sesión invitada"><Stack gap="sm"><Text>Tus conversaciones se guardan localmente durante siete días desde la última actividad. Otro navegador utiliza una sesión diferente y no existe sincronización entre equipos.</Text><Text>Eliminar una conversación la retira antes. No está asociada a una cuenta; las cuentas persistentes son una capacidad futura, no disponible actualmente.</Text></Stack></Modal>
  </>;
}
