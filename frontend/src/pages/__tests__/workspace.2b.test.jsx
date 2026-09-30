import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

function mockResponse({ ok = true, status = 200, jsonData = null } = {}) {
  return {
    ok,
    status,
    headers: { get: (n) => (n.toLowerCase() === "content-type" ? "application/json" : null) },
    json: async () => jsonData,
    text: async () => JSON.stringify(jsonData || ""),
  };
}

function makeAnalysis(overrides = {}) {
  return {
    tender: { id: "T1", title: "Test Tender", client: "C", location: "L" },
    documents: [{ filename: "doc.pdf", page_count: 2, text_length: 500, extraction_status: "COMPLETE", document_type: "TECHNICAL", extraction_method: "fitz" }],
    requirements: [
      { requirement_id: "REQ-001", summary: "First requirement", category: "TECHNICAL", mandatory: true, applicable_entity: "CONSORTIUM", confidence: 0.85, source_document: "doc.pdf", page_number: 1, provenance: { quote_en: "source text 1" }, extraction_method: "deterministic", source_text: "source text 1" },
      { requirement_id: "REQ-002", summary: "Second requirement", category: "LEGAL", mandatory: false, applicable_entity: "GIZA", confidence: 0.55, source_document: "doc.pdf", page_number: 2, provenance: { quote_en: "source text 2" }, extraction_method: "deterministic" },
      { requirement_id: "REQ-003", summary: "Third requirement", category: "HSE", mandatory: null, applicable_entity: null, confidence: 0.4, source_document: null, page_number: null, provenance: null },
    ],
    evidence: [
      { evidence_id: "E-001", requirement_id: "REQ-001", fact: "Evidence for first", source_document: "doc.pdf", page_number: 1, confidence: 0.9, provenance: { quote_en: "evidence text" } },
    ],
    deadlines: [{ type: "submission", date: "2025-08-16", source_snippet: "Submission 16 of August, 2025", source_document: "doc.pdf", page_number: 1 }],
    commercial: { currency: "EGP", amount: "5,700,000", payment: "90 days" },
    risks: [{ risk_id: "R-001", description: "Risk one", severity: "HIGH", type: "COMMERCIAL", mitigation: "Mitigate" }],
    derived_features: { requirement_count: 3, mandatory_missing_count: 1 },
    processing: { job_id: "JOB-1", status: "COMPLETED", progress: 100, documents_total: 1, documents_processed: 1 },
    status: "COMPLETED",
    ...overrides,
  };
}

describe("Stage 2B — Tender Workspace", () => {
  let fetchMock;
  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.restoreAllMocks());

  // 1. complete requirements rendering (all, not just 8)
  it("1. complete requirements rendering", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis();
    // Make 12 requirements to ensure >8
    analysis.requirements = Array.from({ length: 12 }, (_, i) => ({
      requirement_id: `REQ-${String(i + 1).padStart(3, "0")}`,
      summary: `Requirement ${i + 1}`,
      category: "TECHNICAL",
      mandatory: i % 2 === 0,
      applicable_entity: "CONSORTIUM",
      confidence: 0.7,
      source_document: "doc.pdf",
      page_number: 1,
      provenance: { quote_en: `quote ${i + 1}` },
    }));
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test", client: "C", location: "L" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("Requirements — 12")).toBeInTheDocument());
    expect(screen.getAllByTestId("requirement-item").length).toBe(12);
  });

  // 2. requirement provenance visible
  it("2. requirement provenance", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis();
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("First requirement")).toBeInTheDocument());
    expect(screen.getAllByText(/Source: doc.pdf/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Page 1/).length).toBeGreaterThan(0);
    expect(screen.getByText(/source text 1/)).toBeInTheDocument();
  });

  // 3. missing provenance
  it("3. missing provenance shows Not available, not crash", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis();
    analysis.requirements[2].source_document = null;
    analysis.requirements[2].page_number = null;
    analysis.requirements[2].provenance = null;
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("Third requirement")).toBeInTheDocument());
    // Should show Not available for missing source
    expect(screen.getAllByText(/Not available/).length).toBeGreaterThan(0);
  });

  // 4. document statuses
  it("4. document statuses COMPLETE/PARTIAL/FAILED/UNSUPPORTED", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis({
      documents: [
        { filename: "a.pdf", page_count: 2, extraction_status: "COMPLETE", document_type: "TECHNICAL", text_length: 500 },
        { filename: "b.pdf", page_count: 1, extraction_status: "PARTIAL", document_type: "LEGAL", text_length: 50 },
        { filename: "c.pdf", page_count: 0, extraction_status: "FAILED", document_type: "OTHER", text_length: 0, error: "OCR failed" },
        { filename: "d.dwg", page_count: 0, extraction_status: "UNSUPPORTED", document_type: "UNSUPPORTED", text_length: 0 },
      ],
    });
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: analysis.documents, count: 4 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("a.pdf")).toBeInTheDocument());
    expect(screen.getByText("b.pdf")).toBeInTheDocument();
    expect(screen.getByText("c.pdf")).toBeInTheDocument();
    expect(screen.getByText("d.dwg")).toBeInTheDocument();
    expect(screen.getByText("COMPLETE")).toBeInTheDocument();
    expect(screen.getByText("PARTIAL")).toBeInTheDocument();
    expect(screen.getByText("FAILED")).toBeInTheDocument();
    expect(screen.getByText("UNSUPPORTED")).toBeInTheDocument();
  });

  // 5. deadlines available
  it("5. deadlines available", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis();
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText(/Submission 16 of August/)).toBeInTheDocument());
    expect(screen.getByText(/Type: submission/)).toBeInTheDocument();
  });

  // 6. deadlines empty
  it("6. deadlines empty", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis({ deadlines: [] });
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("No deadlines identified")).toBeInTheDocument());
  });

  // 7. commercial available
  it("7. commercial available", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis();
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("currency")).toBeInTheDocument());
    expect(screen.getByText("EGP")).toBeInTheDocument();
  });

  // 8. commercial unavailable
  it("8. commercial unavailable", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis({ commercial: null });
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("Commercial information not available")).toBeInTheDocument());
  });

  // 9. risks/missing/ambiguities
  it("9. risks/missing/ambiguities", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis();
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("Risk one")).toBeInTheDocument());
    expect(screen.getByText(/Severity: HIGH/)).toBeInTheDocument();
  });

  it("9b. no risks shows Not identified, not HIGH", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis({ risks: [] });
    // Make all mandatory known to avoid ambiguous count
    analysis.requirements.forEach((r) => (r.mandatory = true));
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [{ filename: "doc.pdf", extraction_status: "COMPLETE" }], count: 1 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("Not identified")).toBeInTheDocument());
  });

  // 10. partial processing
  it("10. partial processing", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis({ status: "PARTIAL", processing: { status: "PARTIAL", progress: 100, documents_total: 2, documents_processed: 1, documents_unsupported: 1 } });
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getAllByText("PARTIAL").length).toBeGreaterThan(0));
    expect(screen.getAllByText(/Analysis is incomplete/).length).toBeGreaterThan(0);
  });

  // 11. failed processing
  it("11. failed processing", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    // Simulate analysis fetch returning job status FAILED via raw
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { status: "FAILED", last_error: "PERSISTENCE failed: disk full" } }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getAllByText("FAILED").length).toBeGreaterThan(0));
    expect(screen.getAllByText(/Processing failed/).length).toBeGreaterThan(0);
  });

  // 12. neutral Go/No-Go page
  it("12. neutral Go/No-Go page", async () => {
    const { default: GoNoGo } = await import("../GoNoGo.jsx");
    fetchMock.mockResolvedValueOnce(mockResponse({ jsonData: [{ id: "T1", title: "Test" }] }));
    // Also need to mock analysis fetch for T1 inside GoNoGo (it fetches up to 10)
    fetchMock.mockResolvedValueOnce(mockResponse({ jsonData: { tender: { id: "T1" }, requirements: [], documents: [] } }));
    const { BrowserRouter } = await import("react-router-dom");
    render(
      <BrowserRouter>
        <GoNoGo />
      </BrowserRouter>
    );
    await waitFor(() => expect(screen.getByTestId("decision-board")).toBeInTheDocument());
    expect(screen.queryByText("CONDITIONAL GO")).not.toBeInTheDocument();
    expect(screen.queryByText("BID")).not.toBeInTheDocument();
  });

  // 13. no BID/NO-BID recommendation
  it("13. no BID/NO-BID recommendation", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis();
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("First requirement")).toBeInTheDocument());
    expect(screen.queryByText("BID")).not.toBeInTheDocument();
    expect(screen.queryByText("NO-BID")).not.toBeInTheDocument();
    // Also check GoNoGo doesn't have BID/NO-BID
    expect(document.body.textContent).not.toContain("NO-BID");
  });

  // 14. no fake scores
  it("14. no fake scores", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis();
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("First requirement")).toBeInTheDocument());
    expect(screen.queryByText("82 / 100")).not.toBeInTheDocument();
    expect(screen.queryByText("92%")).not.toBeInTheDocument();
    expect(screen.queryByText("Technical Fit")).not.toBeInTheDocument();
  });

  // 15. no fake commercial values
  it("15. no fake commercial values", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis({ commercial: null });
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("Commercial information not available")).toBeInTheDocument());
    expect(screen.queryByText("SAR 12.5M")).not.toBeInTheDocument();
    expect(screen.queryByText("18 Oct 2026")).not.toBeInTheDocument();
  });

  // 16. no fake risk severity
  it("16. no fake risk severity when backend null", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis({ risks: [{ risk_id: "R-1", description: "Test risk", severity: null, type: "COMMERCIAL" }] });
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("Test risk")).toBeInTheDocument());
    expect(screen.getByText(/Severity: Not available/)).toBeInTheDocument();
    expect(screen.queryByText("Severity: HIGH")).not.toBeInTheDocument();
  });

  // Evidence interaction
  it("evidence — clicking requirement shows evidence", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis();
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("First requirement")).toBeInTheDocument());
    fireEvent.click(screen.getByText("First requirement"));
    await waitFor(() => expect(screen.getByText("Evidence for first")).toBeInTheDocument());
    expect(screen.getByText(/evidence text/)).toBeInTheDocument();
  });

  it("evidence — no evidence available", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const analysis = makeAnalysis();
    // Second req has no evidence
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: analysis }));
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("Second requirement")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Second requirement"));
    await waitFor(() => expect(screen.getByText("No evidence available")).toBeInTheDocument());
  });
});
