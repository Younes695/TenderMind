import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

function json(status, data) {
  return { ok: status < 300, status, headers: { get: () => "application/json" },
           json: async () => data, text: async () => JSON.stringify(data) };
}

const PRICE = { price: 150, currency: "EGP", unit: "m", supplier: "Nile Cables", price_date: "2026-09-01", stale: false };

describe("Materials, prices and the Tender Radar", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("shows bulk material with listed price, estimate label and a real price-break scenario", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => (url.includes("/price-lists")
      ? json(200, { lists: [{ id: "L1", supplier: "Nile Cables", currency: "EGP", price_date: "2026-09-01", items: 2, filename: "nile.xlsx" }] })
      : json(200, { active_tenders: 3, tenders_with_boq: 2, review: [], bulk: [{
          key: "cable|size=4x16", name: "Cable 4x16 mm² 1 kV CU XLPE", unit: "m", total_quantity: 20000,
          tenders: [{ tender_id: "A", title: "Obour", quantity: 12000 }, { tender_id: "B", title: "Badr", quantity: 8000 }],
          price: PRICE, estimated_cost: 3000000,
          bulk_scenario: { price: { ...PRICE, price: 140, min_qty: 15000 }, estimated_cost: 2800000, difference: 200000 } }] }))));
    const { default: Materials } = await import("../Materials.jsx");
    render(<MemoryRouter><Materials /></MemoryRouter>);
    expect(await screen.findByText("Cable 4x16 mm² 1 kV CU XLPE")).toBeTruthy();
    const row = screen.getByTestId("bulk-row").textContent;
    expect(row).toContain("20,000");
    expect(row).toContain("EGP 3,000,000");
    expect(row).toContain("EGP 2,800,000");
    expect(row).toContain("Nile Cables");
    expect(await screen.findByText(/nile\.xlsx/)).toBeTruthy();
  });

  it("radar shows match % with every reason, and insufficient data without a percentage", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(200, {
      count: 2, countries: ["Saudi Arabia"], sources: [], capabilities_set: true, summary: { closing_this_week: 1 },
      items: [
        { id: "N1", title: "132 kV substation", country: "Saudi Arabia", deadline_at: "2099-01-01T00:00:00",
          fit: { match: 100, status: "STRONG", factors: [{ factor: "voltage", status: "MET", key: "{kv} kV is within your {max} kV", vars: { kv: 132, max: 220 } }] } },
        { id: "N2", title: "Consulting services", country: "Saudi Arabia", deadline_at: "2099-01-01T00:00:00",
          fit: { match: null, status: "INSUFFICIENT_DATA", factors: [] } }] })));
    const { default: News } = await import("../News.jsx");
    render(<MemoryRouter><News /></MemoryRouter>);
    expect(await screen.findByText("Match 100%")).toBeTruthy();
    expect(screen.getByText("132 kV is within your 220 kV")).toBeTruthy();
    expect(screen.getByText("Match: insufficient data")).toBeTruthy();
    expect(screen.getByTestId("radar-summary").textContent).toContain("1 strong matches");
    expect(screen.getAllByTestId("analyze-notice")[0].getAttribute("href")).toContain("title=132+kV+substation");
  });
});
