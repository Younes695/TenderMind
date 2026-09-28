import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { PreferencesProvider } from "../../i18n";

function json(status, data) {
  return { ok: status < 300, status, headers: { get: () => "application/json" },
           json: async () => data, text: async () => JSON.stringify(data) };
}

describe("Stage 5I - settings and subcontractors", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.documentElement.classList.remove("dark");
    document.documentElement.dir = "ltr";
    try { window.localStorage.clear(); } catch { /* ignore */ }
  });

  it("switching to Arabic flips the page to RTL and translates; dark mode toggles the class", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => url.includes("/feedback") ? json(200, { items: [] })
      : json(200, { authenticated: true, email: "me@x.test", name: "Me" })));
    const { default: Settings } = await import("../Settings.jsx");
    render(<PreferencesProvider><MemoryRouter><Settings /></MemoryRouter></PreferencesProvider>);
    fireEvent.click(await screen.findByTestId("lang-ar"));
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(screen.getByText("الإعدادات")).toBeTruthy();
    fireEvent.click(screen.getByTestId("theme-dark"));
    await waitFor(() => expect(document.documentElement.classList.contains("dark")).toBe(true));
    fireEvent.click(screen.getByTestId("lang-en"));
    await waitFor(() => expect(document.documentElement.dir).toBe("ltr"));
  });

  it("upgrade request and problem report are sent to the server", async () => {
    const bodies = [];
    vi.stubGlobal("fetch", vi.fn(async (url, opts = {}) => {
      if (opts.method === "POST") { bodies.push(JSON.parse(opts.body)); return json(200, { id: "FB-1", status: "NEW" }); }
      if (url.includes("/feedback")) return json(200, { items: [] });
      return json(200, { authenticated: true, email: "me@x.test", name: "Me" });
    }));
    const { default: Settings } = await import("../Settings.jsx");
    render(<MemoryRouter><Settings /></MemoryRouter>);
    fireEvent.click(await screen.findByTestId("upgrade-Professional"));
    fireEvent.change(screen.getByTestId("problem-text"), { target: { value: "Page 7 unreadable" } });
    fireEvent.click(screen.getByText("Send"));
    await waitFor(() => expect(bodies).toEqual([{ kind: "upgrade", plan: "Professional" },
      { kind: "problem", message: "Page 7 unreadable", page: expect.any(String) }]));
  });

  it("Subcontractors shows quotations with the BEST badge from the server's scoring", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (url.includes("/api/rfqs")) return json(200, { rfqs: [{ id: "RFQ-1", tender_id: "T1", reference: "RFQ-MECH-04",
        package_name: "Mechanical Work Package", discipline: "HVAC", currency: "SAR", status: "OPEN", invited_count: 6,
        closes_at: null, quoted_count: 2, quotations: [
          { id: "Q1", contractor: "DesertCool", price: 1940000, duration_weeks: 11, technical_fit: 94, payment_terms_days: 60,
            score: 88.1, is_best: true, eligible: true, best_reason: "Best overall score: highest technical fit" },
          { id: "Q2", contractor: "GulfAir", price: 1870000, duration_weeks: 14, technical_fit: 55, payment_terms_days: 90,
            score: 70, is_best: false, eligible: false, note: "Technical fit below 60% - not eligible for best" }] }] });
      return json(200, [{ id: "T1" }]);
    }));
    const { default: Subcontractors } = await import("../Subcontractors.jsx");
    render(<MemoryRouter><Subcontractors /></MemoryRouter>);
    expect(await screen.findByText("DesertCool")).toBeTruthy();
    expect(screen.getAllByTestId("quote-row")).toHaveLength(2);
    expect(screen.getAllByTestId("best-badge")).toHaveLength(1);
    expect(screen.getByText("1.94M")).toBeTruthy();
    expect(screen.getByText(/sent to 6 contractors/)).toBeTruthy();
  });
});
