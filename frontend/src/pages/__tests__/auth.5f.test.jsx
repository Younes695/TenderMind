import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

function json(data, ok = true, status = 200) {
  return { ok, status, headers: { get: () => "application/json" }, json: async () => data, text: async () => JSON.stringify(data) };
}

function renderAt(path, element) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={element} />
        <Route path="/signup" element={element} />
        <Route path="/dashboard" element={<div>dashboard page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Stage 5F — sign up / log in", () => {
  let fetchMock;
  let providers;
  beforeEach(() => {
    providers = { password: true, signup: true, google: false, microsoft: false };
    fetchMock = vi.fn(async (url, opts = {}) => {
      const u = String(url);
      if (u.includes("/auth/providers")) return json(providers);
      if (u.includes("/auth/signup")) {
        const body = JSON.parse(opts.body);
        if (body.email === "taken@company.com") return json({ detail: "An account with this email already exists — log in instead" }, false, 409);
        return json({ authenticated: true, email: body.email });
      }
      return json({});
    });
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.restoreAllMocks());

  it("sign-up shows password rules live and blocks a mismatch without calling the server", async () => {
    const { default: Signup } = await import("../Signup.jsx");
    renderAt("/signup", <Signup />);
    fireEvent.change(screen.getByLabelText("Work Email"), { target: { value: "a@company.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Tender2026" } });
    expect(screen.getByTestId("rule-len").className).toMatch(/2E7D5B/);
    expect(screen.getByTestId("rule-digit").className).toMatch(/2E7D5B/);
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "Tender2027" } });
    fireEvent.click(screen.getByText("Create account"));
    expect(await screen.findByTestId("signup-error")).toHaveTextContent("Passwords do not match");
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/auth/signup"))).toBe(false);
  });

  it("successful sign-up goes to the dashboard", async () => {
    const { default: Signup } = await import("../Signup.jsx");
    renderAt("/signup", <Signup />);
    fireEvent.change(screen.getByLabelText(/Full name/), { target: { value: "Sara" } });
    fireEvent.change(screen.getByLabelText("Work Email"), { target: { value: "sara@company.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Tender2026" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "Tender2026" } });
    fireEvent.click(screen.getByText("Create account"));
    expect(await screen.findByText("dashboard page")).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([u]) => String(u).includes("/auth/signup"));
    expect(JSON.parse(call[1].body)).toEqual({ name: "Sara", email: "sara@company.com", password: "Tender2026", account_type: "company" });  // company is the default
  });

  it("existing email shows the server's message", async () => {
    const { default: Signup } = await import("../Signup.jsx");
    renderAt("/signup", <Signup />);
    fireEvent.change(screen.getByLabelText("Work Email"), { target: { value: "taken@company.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Tender2026" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "Tender2026" } });
    fireEvent.click(screen.getByText("Create account"));
    expect(await screen.findByTestId("signup-error")).toHaveTextContent("already exists");
  });

  it("Google / Microsoft buttons are disabled until configured, then link to the server OAuth start", async () => {
    const { default: Login } = await import("../Login.jsx");
    const { unmount } = renderAt("/login", <Login />);
    await waitFor(() => expect(screen.getByTestId("oauth-google")).toBeDisabled());
    expect(screen.getByTestId("oauth-microsoft")).toBeDisabled();
    unmount();
    providers = { password: true, signup: true, google: true, microsoft: true };
    renderAt("/login", <Login />);
    await waitFor(() => expect(screen.getByTestId("oauth-google").tagName).toBe("A"));
    expect(screen.getByTestId("oauth-google").getAttribute("href")).toBe("/api/auth/oauth/google/start?next=%2Fdashboard");
    expect(screen.getByTestId("oauth-microsoft").getAttribute("href")).toContain("/api/auth/oauth/microsoft/start");
  });

  it("login links to sign-up and explains OAuth errors from the server", async () => {
    const { default: Login } = await import("../Login.jsx");
    renderAt("/login?auth_error=invalid_state", <Login />);
    expect(screen.getByTestId("login-error")).toHaveTextContent("sign-in session expired");
    expect(screen.getByText("Sign up").getAttribute("href")).toBe("/signup");
  });
});
