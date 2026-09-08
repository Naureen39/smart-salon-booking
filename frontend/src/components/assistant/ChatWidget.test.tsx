import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatWidget from "@/components/assistant/ChatWidget";

describe("ChatWidget", () => {
  it("shows a sign-in prompt when there is no access token", () => {
    render(<ChatWidget accessToken={null} />);

    fireEvent.click(screen.getByLabelText("Open chat assistant"));

    expect(screen.getByText(/please sign in to chat/i)).toBeInTheDocument();
  });

  it("toggles the panel open and closed", () => {
    render(<ChatWidget accessToken={null} />);

    const launcher = screen.getByLabelText("Open chat assistant");
    fireEvent.click(launcher);
    expect(screen.getByText("GlowDesk Assistant")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Close chat"));
    expect(screen.queryByText("GlowDesk Assistant")).not.toBeInTheDocument();
  });
});

describe("ChatWidget voice input", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "session-1", channel: "chat", state: {} }),
    });
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: vi.fn().mockRejectedValue(new Error("denied")) },
    });
  });

  it("shows a clear error when microphone access is denied", async () => {
    render(<ChatWidget accessToken="fake-token" />);
    fireEvent.click(screen.getByLabelText("Open chat assistant"));

    fireEvent.click(screen.getByLabelText("Start voice input"));

    await waitFor(() => expect(screen.getByText(/microphone access was denied/i)).toBeInTheDocument());
  });
});
