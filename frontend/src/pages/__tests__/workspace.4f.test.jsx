import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

function mockResponse({ jsonData = null } = {}) {
  return {
    ok: true,
    status: 200,
    headers: { get: () => "application/json" },
    json: async () => jsonData,
    text: async () => JSON.stringify(jsonData || ""),
  };
}

function makeAnalysis(derivedExtra = {}) {
  return {
    tender: { id: "T1", title: "Test Tender", client: "C", location: "L" },
    documents: [],
    requirements: [],
    evidence: [],
    deadlines: [],
    commercial: null,
    risks: [],
    derived_features: { requirement_count: 0, ...derivedExtra },
    processing: { job_id: "JOB-1", status: "COMPLETED", progress: 100 },
    status: "COMPLETED",
  };
}

describe("Stage 4F — intelligence plumbing", () => {
  let fetchMock;
  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.restoreAllMocks());

  async function renderWith(analysis) {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
  }

  it("renders intelligence section when derived features carry 4F data", async () => {
    await renderWith(makeAnalysis({
      commercial_facts: { currency: "EGP", payment_terms: null, line_items: [{}, {}] },
      schedule_facts: [{}],
      gaps: [{}, {}],
      ambiguities: [{}],
      conflicts: [],
      risk_signals: [{}, {}, {}],
      synthesis: { status: "SYNTHESIS_MVP_DETERMINISTIC" },
    }));
    await waitFor(() => expect(screen.getByTestId("intelligence-section")).toBeInTheDocument());
    expect(screen.getByTestId("intel-commercial")).toHaveTextContent("EGP");
    expect(screen.getByTestId("intel-risks")).toHaveTextContent("no severity");
  });

  it("hides intelligence section on legacy analyses without 4F data", async () => {
    await renderWith(makeAnalysis());
    await waitFor(() => expect(screen.queryByTestId("intelligence-section")).not.toBeInTheDocument());
  });

  it("shows neutral fallbacks, never fake scores", async () => {
    await renderWith(makeAnalysis({ gaps: [], synthesis: {} }));
    await waitFor(() => expect(screen.getByTestId("intelligence-section")).toBeInTheDocument());
    expect(screen.queryByText(/92%|score|BID/i)).not.toBeInTheDocument();
  });

  it("shows coverage line when backend provides it", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis();
    analysis.processing = { job_id: "JOB-1", status: "COMPLETED", progress: 100,
      documents_total: 3, documents_processed: 2, documents_failed: 0, documents_unsupported: 1,
      analysis_coverage: "PARTIAL",
      document_status_counts: { complete: 2, failed: 0, unsupported: 1, total: 3 } };
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    const { MemoryRouter: MR, Routes: R2, Route: Rt } = await import("react-router-dom");
    render(
      <MR initialEntries={["/tenders/T1"]}>
        <R2><Rt path="/tenders/:tender_id" element={<TenderWorkspace />} /></R2>
      </MR>
    );
    await waitFor(() => expect(screen.getByTestId("coverage-line")).toBeInTheDocument());
    expect(screen.getByTestId("coverage-line")).toHaveTextContent("PARTIAL");
  });

  it("renders grouped ambiguities with evidence, neutral wording", async () => {
    await renderWith(makeAnalysis({
      ambiguities: [{ group_id: "AMBG-001", ambiguity_type: "missing-value",
        description: "Submit TBD documents", signal_count: 3,
        source_document: "VOL1.pdf", pages: [4], evidence: ["VOL1.pdf#p4"],
        raw_signals: [], clarification_needed: true, human_review_required: true }],
      ambiguity_report: { raw_signals: 3, grouped_items: 1, reduction_pct: 66.7 },
    }));
    await waitFor(() => expect(screen.getByTestId("intel-ambiguity-groups")).toBeInTheDocument());
    expect(screen.getByTestId("intel-ambiguities")).toHaveTextContent("requires clarification/review");
    expect(screen.queryByText(/critical|high risk/i)).not.toBeInTheDocument();
  });
});
