import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

function json(status, data) {
  return { ok: status < 300, status, headers: { get: () => "application/json" },
           json: async () => data, text: async () => JSON.stringify(data) };
}

describe("Individual accounts", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("sign-up sends the chosen account type", async () => {
    const fetch = vi.fn(async () => json(200, { authenticated: true, email: "a@b.test" }));
    vi.stubGlobal("fetch", fetch);
    const { default: Signup } = await import("../Signup.jsx");
    render(<MemoryRouter><Signup /></MemoryRouter>);
    fireEvent.click(screen.getByLabelText(/Individual professional/));
    fireEvent.change(screen.getByLabelText(/Work Email/), { target: { value: "a@b.test" } });
    fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: "Tender2026" } });
    fireEvent.change(screen.getByLabelText(/Confirm password/), { target: { value: "Tender2026" } });
    fireEvent.submit(screen.getByTestId("account-type").closest("form"));
    await vi.waitFor(() => expect(fetch.mock.calls.some(([u]) => String(u).includes("/api/auth/signup"))).toBe(true));
    const body = JSON.parse(fetch.mock.calls.find(([u]) => String(u).includes("/api/auth/signup"))[1].body);
    expect(body.account_type).toBe("individual");
  });

  it("an individual account hides approvals and department votes", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => json(200, String(url).includes("/api/account") ? { account_type: "individual" } : [])));
    const { resetAccountCache } = await import("../../account.js");
    resetAccountCache();
    const { default: DashboardSidebar } = await import("../../components/DashboardSidebare.jsx");
    render(<MemoryRouter><DashboardSidebar user={{ email: "a@b.test" }} onSignOut={() => {}} /></MemoryRouter>);
    expect(await screen.findByText("Tender Radar")).toBeTruthy();
    await vi.waitFor(() => expect(screen.queryByText("Approvals")).toBeNull());
  });
});
