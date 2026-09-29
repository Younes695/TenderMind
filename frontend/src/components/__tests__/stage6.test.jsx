import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

function json(status, data) {
  return { ok: status < 300, status, headers: { get: () => "application/json" },
           json: async () => data, text: async () => JSON.stringify(data) };
}

describe("Stage 6 - eligibility, bid tools, score, settings", () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it("eligibility banner shows reasons and sends 'continue anyway' with a reason", async () => {
    const sent = [];
    vi.stubGlobal("fetch", vi.fn(async (url, opts = {}) => {
      if (url.includes("/override")) { sent.push(JSON.parse(opts.body)); return json(200, { job_id: "J2" }); }
      return json(200, { status: "INELIGIBLE", checks: [
        { key: "voltage", label: "Voltage", result: "FAIL", detail: "Tender: 380 kV. Company works up to 132 kV.",
          detail_key: "Tender: {kv} kV. Company works up to {max} kV.", detail_vars: { kv: 380, max: "132" },
          evidence: { file: "SOW.pdf", page: 12, quote: "380 kV GIS" } }] });
    }));
    const onContinue = vi.fn();
    const { EligibilityBanner } = await import("../BidTools.jsx");
    render(<EligibilityBanner tenderId="T1" onContinue={onContinue} />);
    expect(await screen.findByText(/Company works up to 132 kV/)).toBeTruthy();
    expect(screen.getByText(/SOW.pdf/)).toBeTruthy();
    fireEvent.click(screen.getByTestId("continue-anyway"));
    expect(await screen.findByText("Write why the team continues")).toBeTruthy();  // reason required
    fireEvent.change(screen.getByPlaceholderText("Why continue anyway?"), { target: { value: "strategic client" } });
    fireEvent.click(screen.getByTestId("continue-anyway"));
    await waitFor(() => expect(onContinue).toHaveBeenCalled());
    expect(sent[0].reason).toBe("strategic client");
  });

  it("bid tools load on demand and show vote percentages", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn(async (url, opts = {}) => {
      calls.push(url);
      if (url.includes("/team")) return json(200, [{ id: "M1", name: "Sara", department: "Finance" }]);
      if (url.includes("/sections")) return json(200, { sections: [{ document: "SOW.pdf", title: "APPENDIX VI", page_from: 3, page_to: 9, discipline: "HVAC" }],
        disciplines: [{ discipline: "HVAC", pages: 7, suppliers: [{ contractor: "Cool Air Co", selected: 2, avg_fit: 80 }] }] });
      if (url.includes("/votes")) return json(200, { votes: [{ member_name: "Sara", department: "Finance", vote: "APPROVE" }],
        summary: { overall: { approve: 1, reject: 1, abstain: 0, total: 2, approve_pct: 50 }, by_department: [] } });
      if (url.includes("/tasks")) return json(200, []);
      return json(200, { status: null, checks: [] });
    }));
    const { default: BidTools } = await import("../BidTools.jsx");
    render(<MemoryRouter><BidTools tenderId="T1" /></MemoryRouter>);
    expect(calls.length).toBe(0);  // nothing fetched until opened
    fireEvent.click(screen.getByTestId("open-bid-tools"));
    expect(await screen.findByText(/Cool Air Co/)).toBeTruthy();
    expect(screen.getByText("APPENDIX VI")).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId("votes-overall").textContent).toContain("50%"));
  });

  it("score block shows factors, what is not counted, and a hard No-Go", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(200, {
      decision: "REVIEW", headline: "Recommendation: bid only if the conditions below are met.", notes: [], sections: [],
      match_percent: null, mandatory_total: 0, mandatory_met: 0,
      score: { score: 82, band: "NO_GO", hard_fail: "1 mandatory requirement(s) contradicted by your documents.", not_counted: ["Past partners"],
        factors: [{ key: "fit", label: "Company fit", value: 80, counted: true, effective_weight: 47, reason: "r", reason_key: "Mandatory requirements met with evidence.", reason_vars: {} },
                  { key: "partners", label: "Past partners", value: null, counted: false, effective_weight: 0, reason: "No past quotations recorded yet.", reason_key: "No past quotations recorded yet.", reason_vars: {} }] },
    })));
    const { default: RecommendationPanel } = await import("../RecommendationPanel.jsx");
    render(<RecommendationPanel tenderId="T1" />);
    fireEvent.click(screen.getByTestId("load-recommendation"));
    expect((await screen.findByTestId("go-score-value")).textContent).toBe("82");
    expect(screen.getByText(/No-Go regardless of the score/)).toBeTruthy();
    expect(screen.getByText("not counted")).toBeTruthy();
    expect(screen.getByText("No past quotations recorded yet.")).toBeTruthy();
  });

  it("capabilities card saves toggled work types and certifications", async () => {
    let saved = null;
    vi.stubGlobal("fetch", vi.fn(async (url, opts = {}) => {
      if (opts.method === "PUT") { saved = JSON.parse(opts.body); return json(200, saved); }
      return json(200, { work_types: [], countries: [], registrations: [], certifications: [], max_kv: null });
    }));
    const { CapabilityCard } = await import("../SettingsStage6.jsx");
    render(<CapabilityCard />);
    fireEvent.click(await screen.findByLabelText("Types of work: substation"));
    fireEvent.change(screen.getByPlaceholderText("ISO 9001"), { target: { value: "ISO 9001\n\nISO 45001 " } });
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => expect(saved).not.toBeNull());
    expect(saved.work_types).toEqual(["substation"]);
    expect(saved.certifications).toEqual(["ISO 9001", "ISO 45001"]);
  });
});
