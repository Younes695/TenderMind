import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import DecisionPanel from "../DecisionPanel.jsx";

function json(data, ok = true, status = 200) {
  return { ok, status, headers: { get: () => "application/json" }, json: async () => data, text: async () => JSON.stringify(data) };
}

const detail = {
  tender_id: "T1",
  available: true,
  decision: { decision: "REVIEW", confidence: "LOW", decision_id: "DEC-1", rules_triggered: ["MANDATORY_GATE_MISSING"], is_override: false },
  mandatory_status_counts: { PASS: 1, MISSING_EVIDENCE: 1 },
  requirements: [
    { requirement_id: "REQ-001", category: "QA_QC", requirement: "ISO 9001 quality system", mandatory: true, status: "PASS",
      source_document: "vol1.pdf", page_or_section: "p.117", source_quote: "Quality Assurance System with certificate",
      evidence: [{ evidence_id: "EV-1", status: "PASS", source_document: "profile.pdf", page_or_section: "p.3",
                   quote: "certified to ISO 9001:2015", confidence: "HIGH", reason: "PASS by evidence judge" }] },
    { requirement_id: "REQ-002", category: "FINANCIAL", requirement: "Audited statements", mandatory: true, status: "MISSING_EVIDENCE",
      source_document: "vol1.pdf", page_or_section: "p.20", evidence: [], reason: "No company evidence found yet for this requirement." },
    { requirement_id: "REQ-003", category: "TECHNICAL", requirement: "125 MVA transformers", mandatory: false, status: "MISSING_EVIDENCE",
      source_document: "vol2.pdf", page_or_section: "p.3", evidence: [] },
  ],
};

describe("DecisionPanel (Stage 5C)", () => {
  let fetchMock;
  beforeEach(() => {
    fetchMock = vi.fn(async (url) => {
      if (String(url).includes("/decision-detail")) return json(detail);
      if (String(url).includes("/company-documents")) return json({ documents: [{ id: "C1", title: "profile.pdf" }] });
      if (String(url).includes("/evaluation")) return json({ status: "NOT_STARTED" });
      return json({});
    });
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.restoreAllMocks());

  it("shows the decision, mandatory counts and hides informational rows by default", async () => {
    render(<DecisionPanel tenderId="T1" />);
    await waitFor(() => expect(screen.getByTestId("decision-badge")).toHaveTextContent("REVIEW"));
    expect(screen.getByText(/have no company evidence yet/)).toBeInTheDocument();
    expect(screen.getAllByTestId("decision-requirement")).toHaveLength(2);
    fireEvent.click(screen.getByLabelText(/Show informational/));
    expect(screen.getAllByTestId("decision-requirement")).toHaveLength(3);
  });

  it("expands a requirement to show tender source and company evidence with pages", async () => {
    render(<DecisionPanel tenderId="T1" />);
    await waitFor(() => screen.getByText("ISO 9001 quality system"));
    fireEvent.click(screen.getByText("ISO 9001 quality system"));
    expect(screen.getByText(/vol1.pdf/)).toHaveTextContent("p.117");
    expect(screen.getByTestId("decision-evidence")).toHaveTextContent("profile.pdf • p.3");
    expect(screen.getByTestId("decision-evidence")).toHaveTextContent("certified to ISO 9001:2015");
  });

  it("override requires a reviewer and a reason", async () => {
    render(<DecisionPanel tenderId="T1" />);
    await waitFor(() => screen.getByText("Override"));
    fireEvent.click(screen.getByText("Override"));
    expect(await screen.findByTestId("decision-error")).toHaveTextContent(/Reviewer and reason are required/);
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/decision/override"))).toBe(false);
  });

  it("explains when the tender has not been processed yet", async () => {
    fetchMock.mockImplementation(async (url) =>
      String(url).includes("/decision-detail") ? json({ available: false, reason: "process the tender first" }) : json({ documents: [] }));
    render(<DecisionPanel tenderId="T2" />);
    expect(await screen.findByText(/process the tender first/)).toBeInTheDocument();
  });
});
