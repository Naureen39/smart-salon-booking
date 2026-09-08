import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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
