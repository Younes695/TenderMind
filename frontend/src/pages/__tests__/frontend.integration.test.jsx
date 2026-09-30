import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";

function mockResponse({ ok = true, status = 200, jsonData = null } = {}) {
  return {
    ok,
    status,
    headers: { get: (n) => (n.toLowerCase() === "content-type" ? "application/json" : null) },
    json: async () => jsonData,
    text: async () => JSON.stringify(jsonData || ""),
  };
}

describe("Frontend Integration — Real API", () => {
  let fetchMock;
  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.restoreAllMocks());

  it("Dashboard — fetches real tenders, no mock data leaking", async () => {
    const { default: Dashboard } = await import("../Dashboard.jsx");
    // Mock API returns real tender, not mock Riyadh etc
    fetchMock.mockResolvedValueOnce(mockResponse({ jsonData: [{ id: "REAL-001", title: "Real Project", client: "RealClient", location: "Cairo" }] }));
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );
    await waitFor(() => expect(screen.getAllByText("Real Project").length).toBeGreaterThan(0));
    expect(screen.queryByText("Riyadh Smart Infrastructure")).not.toBeInTheDocument();
    expect(screen.queryByText("SAR 12.5M")).not.toBeInTheDocument();
    expect(screen.queryByText("RUH-2026-184")).not.toBeInTheDocument();
    expect(screen.getAllByText("REAL-001").length).toBeGreaterThan(0);
  });

  it("Dashboard — empty state when no tenders", async () => {
    const { default: Dashboard } = await import("../Dashboard.jsx");
    fetchMock.mockResolvedValueOnce(mockResponse({ jsonData: [] }));
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );
    await waitFor(() => expect(screen.getByTestId("empty-state")).toBeInTheDocument());
    expect(screen.getByTestId("empty-state").textContent).toContain("No tenders yet");
  });

  it("Dashboard — API error handled", async () => {
    const { default: Dashboard } = await import("../Dashboard.jsx");
    fetchMock.mockResolvedValueOnce(mockResponse({ ok: false, status: 500, jsonData: { detail: "Network error" } }));
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );
    await waitFor(() => expect(screen.getByTestId("error-banner")).toBeInTheDocument());
    expect(screen.getByTestId("error-banner").textContent).toContain("Network error");
  });

  it("TenderWorkspace — no tender selected", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    // Render without route param — we need to provide a param via route
    // Use a wrapper that provides a fake param of undefined
    // Instead, test the component directly renders "No tender selected" when id missing
    // We'll render with BrowserRouter and no param -> useParams returns {}
    const { MemoryRouter, Routes, Route } = await import("react-router-dom");
    render(
      <MemoryRouter initialEntries={["/tenders/"]}>
        <Routes>
          <Route path="/tenders/" element={<TenderWorkspace />} />
          <Route path="/tenders/:tender_id" element={<TenderWorkspace />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("No tender selected")).toBeInTheDocument());
  });

  it("TenderWorkspace — analysis unavailable empty state", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const { MemoryRouter, Routes, Route } = await import("react-router-dom");
    // Mock tender and docs exist, but analysis 404
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Test", client: "C", location: "L" } })) // getTender
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [{ id: "DOC-1", title: "test.pdf", doc_type: "PDF" }], count: 1 } })) // getTenderDocuments
      .mockResolvedValueOnce(mockResponse({ ok: false, status: 404, jsonData: { detail: "No processing job found for tender" } })); // getTenderAnalysis
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes>
          <Route path="/tenders/:tender_id" element={<TenderWorkspace />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getAllByTestId("empty-state").length).toBeGreaterThan(0));
    // Should show at least one empty state for requirements or analysis
    expect(screen.getByText(/No requirements — analysis not available/i)).toBeInTheDocument();
  });

  it("TenderWorkspace — shows real analysis, not mock", async () => {
    const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
    const { MemoryRouter, Routes, Route } = await import("react-router-dom");
    fetchMock
      .mockResolvedValueOnce(mockResponse({ jsonData: { id: "T1", title: "Real Title", client: "RealClient", location: "RealCity" } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", documents: [], count: 0 } }))
      .mockResolvedValueOnce(
        mockResponse({
          jsonData: {
            tender: { id: "T1", title: "Real Title" },
            documents: [{ filename: "real.pdf", page_count: 1 }],
            requirements: [{ requirement_id: "REQ-001", summary: "Real requirement", category: "TECHNICAL", mandatory: null, confidence: 0.8, source_document: "real.pdf", page_number: 1 }],
            evidence: [],
            risks: [],
            derived_features: {},
          },
        })
      );
    render(
      <MemoryRouter initialEntries={["/tenders/T1"]}>
        <Routes>
          <Route path="/tenders/:tender_id" element={<TenderWorkspace />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("Real Title")).toBeInTheDocument());
    expect(screen.getByText("Real requirement")).toBeInTheDocument();
    expect(screen.queryByText("Riyadh Smart Infrastructure")).not.toBeInTheDocument();
    expect(screen.queryByText("92%")).not.toBeInTheDocument();
  });

  it("GoNoGo — no mock fit score leaking", async () => {
    const { default: GoNoGo } = await import("../GoNoGo.jsx");
    fetchMock.mockResolvedValueOnce(mockResponse({ jsonData: [] }));
    render(
      <BrowserRouter>
        <GoNoGo />
      </BrowserRouter>
    );
    await waitFor(() => expect(screen.getByTestId("decision-board")).toBeInTheDocument());
    expect(screen.queryByText("82 / 100")).not.toBeInTheDocument();
    expect(screen.queryByText("CONDITIONAL GO")).not.toBeInTheDocument();
    expect(screen.queryByText("92%")).not.toBeInTheDocument();
    expect(screen.getAllByText(/never replaces your team's decision|No tenders yet/).length).toBeGreaterThan(0);
  });

  it("NewTender — create tender validation error shown", async () => {
    const { default: NewTender } = await import("../NewTender.jsx");
    fetchMock.mockResolvedValueOnce(mockResponse({ ok: false, status: 400, jsonData: { detail: "id and title are required" } }));
    render(
      <BrowserRouter>
        <NewTender />
      </BrowserRouter>
    );
    // Fill form and try create
    const idInput = screen.getByTestId("tender-id-input");
    const titleInput = screen.getByTestId("tender-title-input");
    fireEvent.change(idInput, { target: { value: "" } });
    fireEvent.change(titleInput, { target: { value: "" } });
    // Click Create without filling should show client validation first
    const createBtn = screen.getByText("Create Tender");
    fireEvent.click(createBtn);
    await waitFor(() => expect(screen.getByTestId("error-banner")).toBeInTheDocument());
    expect(screen.getByTestId("error-banner").textContent).toContain("required");
  });

  it("NewTender — successful create shows badge, not fake", async () => {
    const { default: NewTender } = await import("../NewTender.jsx");
    fetchMock.mockResolvedValueOnce(mockResponse({ jsonData: { id: "NEW-001", title: "New Tender" } }));
    render(
      <BrowserRouter>
        <NewTender />
      </BrowserRouter>
    );
    fireEvent.change(screen.getByTestId("tender-id-input"), { target: { value: "NEW-001" } });
    fireEvent.change(screen.getByTestId("tender-title-input"), { target: { value: "New Tender" } });
    fireEvent.click(screen.getByText("Create Tender"));
    await waitFor(() => expect(screen.getByTestId("tender-created")).toBeInTheDocument());
    expect(screen.getByTestId("tender-created").textContent).toContain("NEW-001");
    expect(screen.queryByText("Riyadh Smart Infrastructure Project")).not.toBeInTheDocument();
  });
});
