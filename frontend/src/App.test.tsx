import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import App from "@/App";

describe("App", () => {
  it("renders the GlowDesk home page", () => {
    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>,
    );

    expect(screen.getByText("GlowDesk")).toBeInTheDocument();
  });
});
