import type { HpnId } from "../../hpn-matrices";

export const legalGraphKeys = {
  all: ["legal-network"] as const,
  detail: (matrixId: HpnId) => [...legalGraphKeys.all, matrixId] as const,
};
