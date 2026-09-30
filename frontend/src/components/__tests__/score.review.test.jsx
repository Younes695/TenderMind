import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

function json(status, data) {
  return { ok: status < 300, status, headers: { get: () => "application/json" },
           json: async () => data, text: async () => JSON.stringify(data) };
}

function recommendation(score) {
  return {
    decision: "REVIEW", headline: "Recommendation: review first.", notes: [], sections: [],
    match_percent: 75, mandatory_total: 4, mandatory_met: 3,
    score: { not_counted: [], factors: [
      { key: "fit", label: "Company fit", value: 75, counted: true, effective_weight: 100, reason: "r",
        reason_key: "Mandatory requirements met with evidence.", reason_vars: {} }], ...score },
  };
}

// A mandatory requirement the company's documents contradict keeps the band at
// REVIEW (not GO) until a person looked; the panel must say why.
describe("Go/No-Go score - contradicted mandatory requirement", () => {
  afterEach(() => vi.restoreAllMocks());

  it("explains why a high score is not Go", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(200, recommendation({ score: 75, band: "REVIEW", hard_fail: null,
      review: "1 mandatory requirement(s) contradicted by your documents - review before bidding." }))));
    const { default: RecommendationPanel } = await import("../RecommendationPanel.jsx");
    render(<RecommendationPanel tenderId="T1" />);
    fireEvent.click(screen.getByTestId("load-recommendation"));
    const note = await screen.findByTestId("score-review");
    expect(note.textContent).toContain("Not Go until reviewed");
    expect(note.textContent).toContain("1 mandatory requirement(s) contradicted by your documents");
  });

  it("shows only the No-Go reason when there is also a hard failure", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(200, recommendation({ score: 75, band: "NO_GO",
      hard_fail: "1 mandatory requirement(s) contradicted by your documents.",
      review: "1 mandatory requirement(s) contradicted by your documents - review before bidding." }))));
    const { default: RecommendationPanel } = await import("../RecommendationPanel.jsx");
    render(<RecommendationPanel tenderId="T1" />);
    fireEvent.click(screen.getByTestId("load-recommendation"));
    expect(await screen.findByText(/No-Go regardless of the score/)).toBeTruthy();
    expect(screen.queryByTestId("score-review")).toBeNull();
  });
});
