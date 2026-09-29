import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

function json(status, data) {
  return { ok: status < 300, status, headers: { get: () => "application/json" },
           json: async () => data, text: async () => JSON.stringify(data) };
}

describe("Stage 8 - summary, attention, assistant", () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it("summary shows facts, dates with source, actions, and uses the suggested deadline", async () => {
    const puts = [];
    vi.stubGlobal("fetch", vi.fn(async (url, opts = {}) => {
      if (opts.method === "PUT") { puts.push(JSON.parse(opts.body)); return json(200, {}); }
      return json(200, { tender: { id: "T1", stage: null, submission_deadline: null },
        client: { name: "National Grid SA", evidence: { file: "ITB.doc", page: 1 } },
        facts: { work_type: "substation", voltage_kv: 132, country: "Saudi Arabia", documents: 28, pages: 1587, requirements: 2501, mandatory: 582 },
        eligibility: { status: null }, certificates: { needs_partner: true }, contradictions: 1,
        dates: [{ label: "Pre-bid / job explanation meeting", date: "2024-01-17", source: { file: "BID.pdf", page: 1 } }],
        suggested_deadline: { date: "2024-02-12", file: "BID.pdf", page: 1 },
        actions: [{ key: "Prepare {n} submission item(s) on the checklist.", vars: { n: 9 }, text: "x" }] });
    }));
    const { SummaryCard } = await import("../TenderIntel.jsx");
    render(<MemoryRouter><SummaryCard tenderId="T1" /></MemoryRouter>);
    expect(await screen.findByText("National Grid SA")).toBeTruthy();
    expect(screen.getByText("132 kV")).toBeTruthy();
    expect(screen.getByTestId("summary-actions").textContent).toContain("Prepare 9 submission item(s)");
    fireEvent.click(screen.getByTestId("use-suggested-deadline"));
    await waitFor(() => expect(puts[0]).toEqual({ submission_deadline: "2024-02-12" }));
  });

  it("attention panel lists reminders and tenders awaiting a decision", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(200, {
      reminders: [{ kind: "task-overdue", tender_id: "T1", priority: "HIGH", key: "Task overdue by {n} day(s): {task}", vars: { n: 2, task: "Get bond" } }],
      awaiting_decision: [{ id: "T1", title: "Turaif", score: 56, band: "REVIEW" }], blocked: [], client_history: [],
      stages: { STUDY: 1 }, total: 1 })));
    const { default: AttentionPanel } = await import("../Attention.jsx");
    render(<MemoryRouter><AttentionPanel /></MemoryRouter>);
    expect((await screen.findByTestId("attention-reminders")).textContent).toContain("Task overdue by 2 day(s): Get bond");
    expect(screen.getByTestId("attention-awaiting").textContent).toContain("56");
  });

  it("assistant knows the tender from the URL and shows answer with sources", async () => {
    const bodies = [];
    vi.stubGlobal("fetch", vi.fn(async (url, opts = {}) => {
      bodies.push(JSON.parse(opts.body || "{}"));
      return json(200, { intent: "search", lines: [{ text: "Advance payment is 10% [1]." }],
        sources: [{ file: "Sch C.doc", page: 1, quote: "Advance Payment equal to Ten percent (10%)" }], links: [] });
    }));
    const { default: Assistant } = await import("../Assistant.jsx");
    render(<MemoryRouter initialEntries={["/tenders/TURAIF-01"]}><Routes><Route path="/tenders/:tender_id" element={<Assistant />} /></Routes></MemoryRouter>);
    fireEvent.click(screen.getByTestId("assistant-open"));
    fireEvent.change(screen.getByTestId("assistant-input"), { target: { value: "advance payment?" } });
    fireEvent.click(screen.getByLabelText("Send"));
    expect(await screen.findByText("Advance payment is 10% [1].")).toBeTruthy();
    expect(screen.getByText(/Sch C.doc/)).toBeTruthy();
    expect(bodies[0]).toMatchObject({ question: "advance payment?", tender_id: "TURAIF-01" });
  });
});
