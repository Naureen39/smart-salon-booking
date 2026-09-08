import { useEffect, useRef, useState } from "react";

import { useConversation } from "@/hooks/useConversation";

interface ChatWidgetProps {
  /** Null when the visitor isn't signed in — the widget shows a sign-in
   * prompt instead of a chat panel (auth pages/state land in a later phase;
   * this prop is the wiring point for them). */
  accessToken: string | null;
}

export default function ChatWidget({ accessToken }: ChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const { messages, sendMessage, isSending, error } = useConversation(accessToken);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isSending]);

  const handleSend = (text: string) => {
    if (isSending) return;
    void sendMessage(text);
    setDraft("");
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 font-sans">
      {isOpen && (
        <div className="mb-4 flex h-[32rem] w-80 flex-col overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-2xl sm:w-96">
          <div className="flex items-center justify-between bg-brand px-4 py-3 text-white">
            <span className="font-display text-lg">GlowDesk Assistant</span>
            <button
              type="button"
              aria-label="Close chat"
              onClick={() => setIsOpen(false)}
              className="text-white/80 hover:text-white"
            >
              ✕
            </button>
          </div>

          {!accessToken ? (
            <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-neutral-600">
              Please sign in to chat with our booking assistant.
            </div>
          ) : (
            <>
              <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
                {messages.length === 0 && (
                  <p className="text-sm text-neutral-500">
                    Hi! I can help you book an appointment or answer questions — try "book a haircut" or "what are
                    your hours?"
                  </p>
                )}
                {messages.map((message) => (
                  <div key={message.id} className={message.role === "user" ? "flex justify-end" : "flex justify-start"}>
                    <div
                      className={
                        message.role === "user"
                          ? "max-w-[85%] whitespace-pre-line rounded-2xl rounded-br-sm bg-brand px-3 py-2 text-sm text-white"
                          : "max-w-[85%] whitespace-pre-line rounded-2xl rounded-bl-sm bg-neutral-100 px-3 py-2 text-sm text-neutral-900"
                      }
                    >
                      {message.text}
                      {message.quickReplies && message.quickReplies.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {message.quickReplies.map((reply) => (
                            <button
                              key={reply}
                              type="button"
                              onClick={() => handleSend(reply)}
                              className="rounded-full border border-brand px-3 py-1 text-xs font-medium text-brand hover:bg-brand hover:text-white"
                            >
                              {reply}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {isSending && <p className="text-xs italic text-neutral-400">Thinking…</p>}
                {error && <p className="text-xs text-red-600">{error}</p>}
              </div>

              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  handleSend(draft);
                }}
                className="flex items-center gap-2 border-t border-neutral-200 p-3"
              >
                <input
                  type="text"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder="Type a message…"
                  className="flex-1 rounded-full border border-neutral-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={isSending || !draft.trim()}
                  className="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
                >
                  Send
                </button>
              </form>
            </>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-label="Open chat assistant"
        className="flex h-14 w-14 items-center justify-center rounded-full bg-brand text-white shadow-lg hover:bg-brand-light"
      >
        {isOpen ? "✕" : "💬"}
      </button>
    </div>
  );
}
