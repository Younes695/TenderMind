import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

function json(status, data) {
  return { ok: status < 300, status, headers: { get: () => "application/json" },
           json: async () => data, text: async () => JSON.stringify(data) };
}
const issue = (over = {}) => ({ id: "ISS-1", tender_id: "T1", category: "missing", kind: "missing-file",
  title: "File listed but missing", detail: "x.pdf listed but not found", source_document: "x.pdf", page: null,
  priority: "HIGH", status: "OPEN", answer: null, ...over });

describe("Stage 5H pages", () => {
  afterEach(() => vi.restoreAllMocks());

  it("Notifications lists open review items and marks one reviewed", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn(async (url, opts = {}) => {
      calls.push(`${opts.method || "GET"} ${url}`);
      if (url.includes("/api/issues/ISS-1")) return json(200, issue({ status: "RESOLVED", resolved_by: "me@x.test" }));
      return json(200, { count: 1, notifications: [issue()] });
    }));
    const { default: Notifications } = await import("../Notifications.jsx");
    render(<MemoryRouter><Notifications /></MemoryRouter>);
    expect(await screen.findByText("File listed but missing")).toBeTruthy();
    fireEvent.click(screen.getByTestId("resolve-issue"));
    await waitFor(() => expect(screen.getByText("Resolved")).toBeTruthy());
    expect(calls).toContain("PATCH /api/issues/ISS-1");
  });

  it("Q&A saves an answer for the selected tender", async () => {
    const bodies = [];
    vi.stubGlobal("fetch", vi.fn(async (url, opts = {}) => {
      if (url.endsWith("/api/tenders")) return json(200, [{ id: "SA-2018-HV2" }, { id: "T1", title: "Turaif" }]);
      if (url.includes("/api/tenders/T1/issues")) return json(200, { count: 1, issues: [issue({ category: "question", kind: "missing-value", title: "Unclear wording - ask for clarification", priority: "MEDIUM" })] });
      if (opts.method === "PATCH") { bodies.push(JSON.parse(opts.body)); return json(200, issue({ category: "question", answer: "Bond is 2%" })); }
      return json(200, {});
    }));
    const { default: QA } = await import("../QA.jsx");
    render(<MemoryRouter initialEntries={["/qa"]}><QA /></MemoryRouter>);
    const box = await screen.findByPlaceholderText(/What the client answered/);
    fireEvent.change(box, { target: { value: "Bond is 2%" } });
    fireEvent.click(screen.getByText("Save answer"));
    await waitFor(() => expect(bodies).toEqual([{ answer: "Bond is 2%" }]));
    expect(screen.queryByText("SA-2018-HV2")).toBeNull(); // demo tender not offered
  });

  it("News hides notices whose deadline has passed when 'open only' is on", async () => {
    const future = new Date(Date.now() + 10 * 864e5).toISOString();
    const past = new Date(Date.now() - 10 * 864e5).toISOString();
    vi.stubGlobal("fetch", vi.fn(async () => json(200, { count: 2, countries: ["Egypt"], sources: ["World Bank"], items: [
      { id: "N1", title: "132 kV substation EPC", deadline_at: future, notice_type: "Invitation for Bids", source: "World Bank", country: "Egypt", url: "https://x" },
      { id: "N2", title: "Old transformer supply", deadline_at: past, notice_type: "Invitation for Bids", source: "World Bank", country: "Egypt" },
    ] })));
    const { default: News } = await import("../News.jsx");
    render(<MemoryRouter><News /></MemoryRouter>);
    expect(await screen.findByText("132 kV substation EPC")).toBeTruthy();
    expect(screen.queryByText("Old transformer supply")).toBeNull();
    fireEvent.click(screen.getByLabelText(/Open for bidding only/));
    expect(await screen.findByText("Old transformer supply")).toBeTruthy();
  });
});

describe("Stage 5H - delete asks first", () => {
  afterEach(() => vi.restoreAllMocks());

  it("cancelling the confirmation keeps the company document", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn(async (url, opts = {}) => {
      calls.push(`${opts.method || "GET"} ${url}`);
      return json(200, { count: 1, documents: [{ id: "CD1", title: "profile.pdf", document_type: "PDF" }] });
    }));
    const ask = vi.spyOn(window, "confirm").mockReturnValue(false);
    const { default: CompanyKnowledge } = await import("../CompanyKnowledge.jsx");
    render(<MemoryRouter><CompanyKnowledge /></MemoryRouter>);
    fireEvent.click(await screen.findByLabelText(/Remove profile.pdf/));
    expect(ask).toHaveBeenCalledWith(expect.stringContaining("profile.pdf"));
    expect(calls.some((c) => c.startsWith("DELETE"))).toBe(false);
    ask.mockReturnValue(true);
    fireEvent.click(screen.getByLabelText(/Remove profile.pdf/));
    await waitFor(() => expect(calls.some((c) => c.startsWith("DELETE"))).toBe(true));
  });
});
