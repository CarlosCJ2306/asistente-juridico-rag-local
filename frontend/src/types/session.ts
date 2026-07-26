export type SessionMode = "local" | "authenticated";

export type AppCapability =
  | "documents.read"
  | "documents.manage"
  | "search.use"
  | "chat.use"
  | "hpn.read"
  | "hpn.manage"
  | "graph.read"
  | "settings.manage";

export interface AppUser {
  readonly id: string;
  readonly displayName: string;
}

export interface LocalSession {
  readonly mode: "local";
  readonly user: null;
  readonly capabilities: readonly AppCapability[];
  readonly isSecurityBoundary: false;
}

export interface AuthenticatedSession {
  readonly mode: "authenticated";
  readonly user: AppUser;
  readonly capabilities: readonly AppCapability[];
  readonly isSecurityBoundary: false;
}

export type AppSession = LocalSession | AuthenticatedSession;
