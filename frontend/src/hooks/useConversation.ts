import { useCallback, useState } from "react";

import { sendConversationMessage, startConversation } from "@/lib/conversation-api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  quickReplies?: string[] | null;
}

export function useConversation(accessToken: string | null) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ensureSession = useCallback(async (): Promise<string> => {
    if (sessionId) return sessionId;
    if (!accessToken) throw new Error("Not signed in");
    const session = await startConversation(accessToken);
    setSessionId(session.id);
    return session.id;
  }, [sessionId, accessToken]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !accessToken) return;

      setError(null);
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", text: trimmed }]);
      setIsSending(true);

      try {
        const activeSessionId = await ensureSession();
        const response = await sendConversationMessage(activeSessionId, trimmed, accessToken);
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            text: response.reply_text,
            quickReplies: response.quick_replies,
          },
        ]);
      } catch {
        setError("Sorry, something went wrong. Please try again.");
      } finally {
        setIsSending(false);
      }
    },
    [accessToken, ensureSession],
  );

  const addAssistantMessage = useCallback((text: string, quickReplies?: string[] | null) => {
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "assistant", text, quickReplies }]);
  }, []);

  return { messages, sendMessage, isSending, error, sessionId, ensureSession, addAssistantMessage };
}
