import { useMutation } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";

import { askRagChat } from "../api";
import type { RagChatInput } from "../types";

export function useRagChat() {
  const controllerRef = useRef<AbortController | null>(null);
  const [canCancel, setCanCancel] = useState(false);
  const mutation = useMutation({
    mutationFn: async (input: RagChatInput) => {
      const controller = new AbortController();
      controllerRef.current = controller;
      setCanCancel(true);
      try {
        return await askRagChat(input, controller.signal);
      } finally {
        if (controllerRef.current === controller) {
          controllerRef.current = null;
          setCanCancel(false);
        }
      }
    },
  });

  const cancel = useCallback(() => controllerRef.current?.abort(), []);

  return { ...mutation, cancel, canCancel };
}
