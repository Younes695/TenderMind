import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

function json(status, data) {
  return { ok: status < 300, status, headers: { get: () => "application/json" },
           json: async () => data, text: async () => JSON.stringify(data) };
}

// Website leads belong to whoever runs the server, not to customer accounts.
function serve(me, calls) {
  return vi.fn(async (url) => {
    calls.push(url);
    if (url.includes("/api/auth/me")) return json(200, me);
    if (url.includes("/api/demo-requests")) return json(200, [
      { id: "DR-1", name: "Sara Ali", email: "sara@delta.test", topic: "plan:growth", created_at: "2026-09-30T10:00:00" }]);
    if (url.includes("/feedback")) return json(200, { items: [] });
    return json(200, {});
  });
}

describe("Settings - website demo requests", () => {
  afterEach(() => vi.restoreAllMocks());

  it("are neither shown nor fetched for a customer account", async () => {
    const calls = [];
    vi.stubGlobal("fetch", serve({ authenticated: true, email: "c@x.test", is_admin: false, auth_disabled: false }, calls));
    const { default: Settings } = await import("../Settings.jsx");
    render(<MemoryRouter><Settings /></MemoryRouter>);
    await waitFor(() => expect(calls.some((u) => u.includes("/api/auth/me"))).toBe(true));
    await screen.findAllByText("Change password");   // the page has rendered past the cards
    expect(screen.queryByText("Demo requests from the website")).toBeNull();
    expect(calls.some((u) => u.includes("/api/demo-requests"))).toBe(false);
  });

  it("are listed for the server admin", async () => {
    const calls = [];
    vi.stubGlobal("fetch", serve({ authenticated: true, email: "admin@x.test", is_admin: true, auth_disabled: false }, calls));
    const { default: Settings } = await import("../Settings.jsx");
    render(<MemoryRouter><Settings /></MemoryRouter>);
    expect(await screen.findByText("Demo requests from the website")).toBeTruthy();
    expect(await screen.findByText("sara@delta.test")).toBeTruthy();
  });
});
