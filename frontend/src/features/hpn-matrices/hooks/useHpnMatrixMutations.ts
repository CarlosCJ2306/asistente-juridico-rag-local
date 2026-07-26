import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useNotifications } from "../../../hooks";
import {
  createHpnMatrix,
  createHpnNode,
  createHpnRelation,
  deleteHpnMatrix,
  deleteHpnNode,
  deleteHpnRelation,
  deleteHpnSource,
  hpnMatrixKeys,
  updateHpnMatrix,
  updateHpnNode,
  updateHpnRelation,
} from "../api";
import type {
  HpnId,
  HpnMatrixCreateInput,
  HpnMatrixUpdateInput,
  HpnNodeCreateInput,
  HpnNodeUpdateInput,
  HpnRelationCreateInput,
  HpnRelationUpdateInput,
} from "../types";

function useRefreshMatrix() {
  const queryClient = useQueryClient();
  return async (matrixId: HpnId) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: hpnMatrixKeys.lists() }),
      queryClient.invalidateQueries({ queryKey: hpnMatrixKeys.detail(matrixId) }),
    ]);
  };
}

export function useCreateHpnMatrix() {
  const queryClient = useQueryClient();
  const { notify } = useNotifications();
  return useMutation({
    mutationFn: (payload: HpnMatrixCreateInput) => createHpnMatrix(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: hpnMatrixKeys.lists() });
      notify({ kind: "success", title: "Matriz creada", deduplicationKey: "hpn-matrix-created" });
    },
  });
}

export function useUpdateHpnMatrix() {
  const refresh = useRefreshMatrix();
  const { notify } = useNotifications();
  return useMutation({
    mutationFn: ({ matrixId, payload }: { readonly matrixId: HpnId; readonly payload: HpnMatrixUpdateInput }) => updateHpnMatrix(matrixId, payload),
    onSuccess: async (_, variables) => {
      await refresh(variables.matrixId);
      notify({ kind: "success", title: "Matriz actualizada", deduplicationKey: "hpn-matrix-updated" });
    },
  });
}

export function useDeleteHpnMatrix() {
  const queryClient = useQueryClient();
  const { notify } = useNotifications();
  return useMutation({
    mutationFn: (matrixId: HpnId) => deleteHpnMatrix(matrixId),
    onSuccess: async (_, matrixId) => {
      queryClient.removeQueries({ queryKey: hpnMatrixKeys.detail(matrixId) });
      await queryClient.invalidateQueries({ queryKey: hpnMatrixKeys.lists() });
      notify({ kind: "success", title: "Matriz eliminada", deduplicationKey: "hpn-matrix-deleted" });
    },
  });
}

export function useCreateHpnNode() {
  const refresh = useRefreshMatrix();
  const { notify } = useNotifications();
  return useMutation({
    mutationFn: ({ matrixId, payload }: { readonly matrixId: HpnId; readonly payload: HpnNodeCreateInput }) => createHpnNode(matrixId, payload),
    onSuccess: async (_, variables) => {
      await refresh(variables.matrixId);
      notify({ kind: "success", title: "Elemento creado", deduplicationKey: "hpn-node-created" });
    },
  });
}

export function useUpdateHpnNode() {
  const refresh = useRefreshMatrix();
  const { notify } = useNotifications();
  return useMutation({
    mutationFn: ({ matrixId, nodeId, payload }: { readonly matrixId: HpnId; readonly nodeId: HpnId; readonly payload: HpnNodeUpdateInput }) => updateHpnNode(matrixId, nodeId, payload),
    onSuccess: async (_, variables) => {
      await refresh(variables.matrixId);
      notify({ kind: "success", title: "Elemento actualizado", deduplicationKey: "hpn-node-updated" });
    },
  });
}

export function useDeleteHpnNode() {
  const refresh = useRefreshMatrix();
  const { notify } = useNotifications();
  return useMutation({
    mutationFn: ({ matrixId, nodeId }: { readonly matrixId: HpnId; readonly nodeId: HpnId }) => deleteHpnNode(matrixId, nodeId),
    onSuccess: async (_, variables) => {
      await refresh(variables.matrixId);
      notify({ kind: "success", title: "Elemento eliminado", deduplicationKey: "hpn-node-deleted" });
    },
  });
}

export function useDeleteHpnSource() {
  const refresh = useRefreshMatrix();
  const { notify } = useNotifications();
  return useMutation({
    mutationFn: ({ matrixId, nodeId, sourceId }: { readonly matrixId: HpnId; readonly nodeId: HpnId; readonly sourceId: HpnId }) => deleteHpnSource(matrixId, nodeId, sourceId),
    onSuccess: async (_, variables) => {
      await refresh(variables.matrixId);
      notify({ kind: "success", title: "Fuente desvinculada", deduplicationKey: "hpn-source-deleted" });
    },
  });
}

export function useCreateHpnRelation() {
  const refresh = useRefreshMatrix();
  const { notify } = useNotifications();
  return useMutation({
    mutationFn: ({ matrixId, payload }: { readonly matrixId: HpnId; readonly payload: HpnRelationCreateInput }) => createHpnRelation(matrixId, payload),
    onSuccess: async (_, variables) => {
      await refresh(variables.matrixId);
      notify({ kind: "success", title: "Relación creada", deduplicationKey: "hpn-relation-created" });
    },
  });
}

export function useUpdateHpnRelation() {
  const refresh = useRefreshMatrix();
  const { notify } = useNotifications();
  return useMutation({
    mutationFn: ({ matrixId, relationId, payload }: { readonly matrixId: HpnId; readonly relationId: HpnId; readonly payload: HpnRelationUpdateInput }) => updateHpnRelation(matrixId, relationId, payload),
    onSuccess: async (_, variables) => {
      await refresh(variables.matrixId);
      notify({ kind: "success", title: "Relación actualizada", deduplicationKey: "hpn-relation-updated" });
    },
  });
}

export function useDeleteHpnRelation() {
  const refresh = useRefreshMatrix();
  const { notify } = useNotifications();
  return useMutation({
    mutationFn: ({ matrixId, relationId }: { readonly matrixId: HpnId; readonly relationId: HpnId }) => deleteHpnRelation(matrixId, relationId),
    onSuccess: async (_, variables) => {
      await refresh(variables.matrixId);
      notify({ kind: "success", title: "Relación eliminada", deduplicationKey: "hpn-relation-deleted" });
    },
  });
}
