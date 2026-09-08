import { apiFetch } from "@/lib/api-client";

export interface ConversationSession {
  id: string;
  channel: string | null;
  state: Record<string, unknown>;
}

export interface ConversationTurnResponse {
  reply_text: string;
  quick_replies: string[] | null;
  appointment_id: string | null;
  state: Record<string, unknown>;
}

export function startConversation(accessToken: string): Promise<ConversationSession> {
  return apiFetch<ConversationSession>(
    "/api/v1/conversation/start",
    { method: "POST", body: JSON.stringify({ channel: "chat" }) },
    accessToken,
  );
}

export function sendConversationMessage(
  sessionId: string,
  message: string,
  accessToken: string,
): Promise<ConversationTurnResponse> {
  return apiFetch<ConversationTurnResponse>(
    `/api/v1/conversation/${sessionId}/message`,
    { method: "POST", body: JSON.stringify({ message }) },
    accessToken,
  );
}
