import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import Login from "../src/pages/Login";

const login = vi.fn().mockResolvedValue(undefined);
vi.mock("../src/contexts/AuthContext", () => ({ useAuth: () => ({ user: null, login }) }));

describe("Login page", () => {
  it("validates required fields and submits credentials", async () => {
    render(<MemoryRouter><Login /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText("Enter your username or email")).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText(/username or email/i), "admin");
    await userEvent.type(screen.getByLabelText(/password/i), "secret-pass");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(login).toHaveBeenCalledWith("admin", "secret-pass");
  });
});
