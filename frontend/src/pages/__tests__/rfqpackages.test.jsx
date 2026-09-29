import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

function json(status, data) {
  return { ok: status < 300, status, headers: { get: () => "application/json" },
           json: async () => data, text: async () => JSON.stringify(data) };
}

const PKG = (key, name, label, rfq_id = null) => ({
  key, name, label, rfq_id, discipline: "Primary electrical (GIS / transformers)", pages: 12, specs: ["32-TMSS-02"], suppliers: [{ contractor: "Hyosung" }],
  parts: { scope: [{ document: "SOW.pdf", ranges: [[2, 3]], pages: 2 }], design: [], drawings: [], schedules: [{ document: "SOW.pdf", ranges: [[9, 18]], pages: 10 }] },
});

describe("RFQ packages", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("lists equipment packages, downloads the chosen ones and registers them as RFQs", async () => {
    const gis = PKG("hv_switchgear", "132kV GIS / circuit breakers", { key: "{kv} GIS / circuit breakers", vars: { kv: "132kV" } });
    const tr = PKG("power_transformer", "Power transformers", { key: "Power transformers", vars: {} });
    const fetch = vi.fn(async (url, opts) => (opts?.method === "POST"
      ? json(200, { created: 2, packages: [{ ...gis, rfq_id: "R1" }, { ...tr, rfq_id: "R2" }] })
      : json(200, { packages: [gis, tr] })));
    vi.stubGlobal("fetch", fetch);
    const { default: RfqPackages } = await import("../../components/RfqPackages.jsx");
    render(<RfqPackages tenderId="T1" />);
    expect(await screen.findByText("132kV GIS / circuit breakers")).toBeTruthy();
    expect(screen.getByTestId("rfq-package-hv_switchgear").textContent).toContain("Data schedules to fill: 10");
    fireEvent.click(screen.getByLabelText("Power transformers"));
    expect(screen.getByTestId("rfq-zip").getAttribute("href")).toContain("keys=hv_switchgear");
    expect(screen.getByTestId("rfq-zip").getAttribute("href")).not.toContain("power_transformer");
    fireEvent.click(screen.getByLabelText("Power transformers"));
    fireEvent.click(screen.getByTestId("rfq-register"));
    expect(await screen.findByText("2 RFQ(s) added to Subcontractors")).toBeTruthy();
    expect(screen.getAllByText("RFQ added").length).toBe(2);
  });
});
