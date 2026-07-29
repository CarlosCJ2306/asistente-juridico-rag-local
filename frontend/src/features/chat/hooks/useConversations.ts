import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef } from "react";

import { createConversation, deleteConversation, getConversation, listConversations, sendConversationMessage, updateConversation } from "../api";
import { conversationKeys } from "../api/conversations.queries";
import type { ConversationInput, ConversationStatus } from "../types";

function key(): string { return crypto.randomUUID(); }
export function useConversationList(status: ConversationStatus = "active") { return useQuery({queryKey:conversationKeys.list(status),queryFn:({signal})=>listConversations(1,20,status,signal)}); }
export function useConversation(id: string | undefined) { return useQuery({queryKey:conversationKeys.detail(id ?? "draft"),queryFn:({signal})=>getConversation(id ?? "",signal),enabled:Boolean(id),retry:false}); }
export function useConversationActions() {
  const client=useQueryClient(); const invalidate=useCallback(()=>client.invalidateQueries({queryKey:conversationKeys.all}),[client]);
  const create=useMutation({mutationFn:()=>createConversation(),onSuccess:invalidate});
  const rename=useMutation({mutationFn:({id,title}:{id:string;title:string})=>updateConversation(id,{title}),onSuccess:invalidate});
  const archive=useMutation({mutationFn:({id,status}:{id:string;status:ConversationStatus})=>updateConversation(id,{status}),onSuccess:invalidate});
  const remove=useMutation({mutationFn:deleteConversation,onSuccess:invalidate});
  return {create,rename,archive,remove};
}
export function useConversationMessage() {
  const client=useQueryClient(); const controller=useRef<AbortController|null>(null);
  const mutation=useMutation({mutationFn:async({id,input,idempotencyKey}:{id:string;input:ConversationInput;idempotencyKey:string})=>{const next=new AbortController();controller.current=next;try{return await sendConversationMessage(id,input,idempotencyKey,next.signal);}finally{if(controller.current===next)controller.current=null;}},onSuccess:(turn)=>{client.setQueryData(conversationKeys.detail(turn.conversation.id),(previous: unknown)=>{if(!previous||typeof previous!=="object")return previous;const detail=previous as {messages: unknown[]};return {...detail,messages:[...detail.messages,turn.userMessage,turn.assistantMessage]};});void client.invalidateQueries({queryKey:conversationKeys.all});}});
  return {...mutation,cancel:()=>controller.current?.abort(),newKey:key};
}
