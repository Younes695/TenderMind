import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

function json(status, data) {
  return { ok: status < 300, status, headers: { get: () => "application/json" },
           json: async () => data, text: async () => JSON.stringify(data) };
}

const PACK = {
  tender: { id: "T1", title: "Riyadh 132kV Substation", client: "SEC" }, generated_at: "2026-09-29T10:00:00Z",
  certifications: { summary: { MISSING: 0, PARTNER_NEEDED: 1, CHECK: 1, HELD: 0, needs_partner: true }, items: [
    { name: "Type-test certificates (KEMA / CESI / IEC) of the equipment", kind: "type_test", who: "partner", status: "PARTNER_NEEDED",
      optional: false, evidence: [{ file: "ITB.doc", page: 1, quote: "Certified Type (Design) Test Reports" }],
      suggested: [{ contractor: "Hyosung" }], disciplines: [] },
    { name: "Prequalification (invited / approved bidders)", kind: "prequal", who: "bidder", status: "CHECK", optional: false,
      evidence: [{ file: "ITB.doc", page: 1, quote: "Only firms prequalified and invited" }] }] },
  eligibility: null, score: null, recommendation: { headline: "Recommendation: bid only if the conditions below are met." },
  compliance: { PASS: 0, FAIL: 0, REVIEW: 0, MISSING_EVIDENCE: 5, mandatory_total: 5, total: 9, compliance_percent: null },
  gaps: [], conflicts: [{ fact: "words_vs_digits", label: "Number in words differs from the digits",
    values: [{ value: "twenty six (26)", file: "Sch C.doc", page: 1, quote: "twenty six percent (13%)" }, { value: "13", file: "Sch C.doc", page: 1, quote: "q" }] }],
  questions: [], missing_documents: [], checklist: { items: [], progress: { TODO: 0, READY: 0, NOT_APPLICABLE: 0, total: 0 } },
  votes: { votes: [], summary: { overall: {}, by_department: [] } }, tasks: [],
  audit: [{ action: "vote_saved", detail: { member: "Sara", vote: "APPROVE" }, actor: "local", actor_name: "Sara", at: "2026-09-29T09:00:00Z" }],
};

describe("Stage 7 - decision pack", () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it("puts certificates first, says a partner is needed, and shows conflicts and the audit trail", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(200, PACK)));
    const { default: DecisionPack } = await import("../DecisionPack.jsx");
    render(<MemoryRouter initialEntries={["/tenders/T1/pack"]}><Routes><Route path="/tenders/:tender_id/pack" element={<DecisionPack />} /></Routes></MemoryRouter>);
    const sections = await screen.findAllByRole("heading", { level: 2 });
    expect(sections[0].textContent).toContain("Certificates and qualifications");
    expect(screen.getByTestId("pack-certs-summary").textContent).toContain("A partner, supplier or certificate is needed");
    expect(screen.getByText(/Hyosung/)).toBeTruthy();
    expect(screen.getByText("Number in words differs from the digits")).toBeTruthy();
    expect(screen.getByText("Vote saved")).toBeTruthy();
    expect(screen.getByText(/decision to bid belongs to the company's authorised team/)).toBeTruthy();
  });
});
