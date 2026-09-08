import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AdminDashboard from "@/pages/AdminDashboard";

describe("AdminDashboard", () => {
  it("shows a sign-in prompt when there is no access token", () => {
    render(<AdminDashboard accessToken={null} />);

    expect(screen.getByText(/please sign in as an admin or staff member/i)).toBeInTheDocument();
  });
});
