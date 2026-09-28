import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

function json(data, ok = true, status = 200) {
  return { ok, status, headers: { get: () => "application/json" }, json: async () => data, text: async () => JSON.stringify(data) };
}

describe("Stage 5D — sidebar pages and file removal", () => {
  let fetchMock;
  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });
  afterEach(() => vi.restoreAllMocks());

  it("every sidebar link resolves to a real route (no blank pages)", async () => {
    const { default: App } = await import("../../App.jsx");
    const src = (await import("../../components/DashboardSidebare.jsx?raw")).default;
    const appSrc = (await import("../../App.jsx?raw")).default;
    const links = [...src.matchAll(/to: "([^"]+)"/g)].map((m) => m[1]);
    expect(links.length).toBeGreaterThan(10);
    for (const l of links) expect(appSrc).toContain(`"${l}"`);
    expect(src).not.toMatch(/badge: \d/); // no hardcoded fake counters
    expect(App).toBeTruthy();
  }, 20000); // imports the whole app graph; slow when the full suite runs in parallel

  it("Tenders page lists tenders with links to their workspace", async () => {
    fetchMock.mockResolvedValue(json([{ id: "T-1", title: "First", client: "EETC" }, { id: "T-2", title: "Second" }]));
    const { default: TendersList } = await import("../TendersList.jsx");
    render(<MemoryRouter><TendersList /></MemoryRouter>);
    const rows = await screen.findAllByTestId("tender-row");
    expect(rows).toHaveLength(2);
    expect(rows.map((r) => r.getAttribute("href"))).toContain("/tenders/T-1");
  });

  it("Coming-soon page names the section instead of rendering nothing", async () => {
    const { default: ComingSoon } = await import("../ComingSoon.jsx");
    render(<MemoryRouter><ComingSoon title="Approvals" description="Route the decision" /></MemoryRouter>);
    expect(screen.getByTestId("coming-soon")).toHaveTextContent("Approvals");
  });

  it("new tender: remove a selected file, clear all, and remove an uploaded file", async () => {
    fetchMock.mockImplementation(async (url, opts = {}) => {
      const u = String(url);
      if (u.endsWith("/api/tenders") && opts.method === "POST") return json({ id: "T-NEW" });
      if (u.endsWith("/documents") && opts.method === "POST")
        return json({ documents: [{ id: "D1", filename: "a.pdf", doc_type: "PDF", size: 2048 }, { id: "D2", filename: "b.pdf", doc_type: "PDF", size: 4096 }] });
      if (u.includes("/documents/D1") && opts.method === "DELETE") return json({ removed_count: 1 });
      return json({});
    });
    const { default: NewTender } = await import("../NewTender.jsx");
    render(<MemoryRouter><NewTender /></MemoryRouter>);
    fireEvent.change(screen.getByTestId("tender-id-input"), { target: { value: "T-NEW" } });
    fireEvent.change(screen.getByTestId("tender-title-input"), { target: { value: "New" } });
    fireEvent.click(screen.getByText("Create Tender"));
    await screen.findByTestId("tender-created");

    const input = screen.getByTestId("file-input");
    const a = new File(["x"], "a.pdf", { type: "application/pdf" });
    const b = new File(["y"], "b.pdf", { type: "application/pdf" });
    const wrong = new File(["z"], "wrong.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [a, b, wrong] } });
    expect(screen.getAllByTestId("selected-file")).toHaveLength(3);
    fireEvent.click(screen.getByLabelText("Remove wrong.pdf"));
    expect(screen.getAllByTestId("selected-file")).toHaveLength(2);

    fireEvent.click(screen.getByText("Upload Documents"));
    await waitFor(() => expect(screen.getAllByTestId("uploaded-doc")).toHaveLength(2));
    expect(screen.queryAllByTestId("selected-file")).toHaveLength(0); // selection cleared: no double upload
    const uploadCall = fetchMock.mock.calls.find(([u, o]) => String(u).endsWith("/documents") && o?.method === "POST");
    expect(uploadCall[1].body.getAll("files").map((f) => f.name)).toEqual(["a.pdf", "b.pdf"]);

    fireEvent.click(screen.getByLabelText("Remove a.pdf"));
    await waitFor(() => expect(screen.getAllByTestId("uploaded-doc")).toHaveLength(1));
    expect(fetchMock.mock.calls.some(([u, o]) => String(u).includes("/documents/D1") && o?.method === "DELETE")).toBe(true);

    fireEvent.change(input, { target: { files: [wrong] } });
    fireEvent.click(screen.getByTestId("clear-selected"));
    expect(screen.queryAllByTestId("selected-file")).toHaveLength(0);
  });

  it("company knowledge page uploads and removes company documents", async () => {
    let docs = [{ id: "C1", title: "profile.pdf", document_type: "PDF" }];
    fetchMock.mockImplementation(async (url, opts = {}) => {
      if (String(url).includes("/company-documents/C1") && opts.method === "DELETE") { docs = []; return json({ deleted: "C1" }); }
      return json({ documents: docs });
    });
    const { default: CompanyKnowledge } = await import("../CompanyKnowledge.jsx");
    render(<MemoryRouter><CompanyKnowledge /></MemoryRouter>);
    const row = await screen.findByTestId("company-doc-row");
    fireEvent.click(within(row).getByLabelText("Remove profile.pdf"));
    await waitFor(() => expect(screen.queryAllByTestId("company-doc-row")).toHaveLength(0));
  });
});

describe("Stage 5D — unsupported files stand out", () => {
  afterEach(() => vi.restoreAllMocks());
  it("UNSUPPORTED uploads get a red badge and a skip warning; PDFs stay green", async () => {
    const fetchMock = vi.fn(async (url, opts = {}) => {
      const u = String(url);
      if (u.endsWith("/api/tenders") && opts.method === "POST") return json({ id: "T-U" });
      if (u.endsWith("/documents") && opts.method === "POST")
        return json({ documents: [{ id: "D1", filename: "plan.dwg", doc_type: "UNSUPPORTED", size: 10 }, { id: "D2", filename: "spec.pdf", doc_type: "PDF", size: 10 }] });
      return json({});
    });
    vi.stubGlobal("fetch", fetchMock);
    const { default: NewTender } = await import("../NewTender.jsx");
    render(<MemoryRouter><NewTender /></MemoryRouter>);
    fireEvent.change(screen.getByTestId("tender-id-input"), { target: { value: "T-U" } });
    fireEvent.change(screen.getByTestId("tender-title-input"), { target: { value: "U" } });
    fireEvent.click(screen.getByText("Create Tender"));
    await screen.findByTestId("tender-created");
    fireEvent.change(screen.getByTestId("file-input"), { target: { files: [new File(["a"], "plan.dwg"), new File(["b"], "spec.pdf")] } });
    fireEvent.click(screen.getByText("Upload Documents"));
    const badges = await screen.findAllByTestId("doc-type-badge");
    const byText = Object.fromEntries(badges.map((b) => [b.textContent, b.className]));
    expect(byText.UNSUPPORTED).toMatch(/b42318/);
    expect(byText.PDF).toMatch(/2E7D5B/);
    expect(screen.getByTestId("unsupported-warning")).toHaveTextContent("1 file is not supported");
  });
});

describe("Stage 5E — sidebar shows the signed-in account", () => {
  afterEach(() => vi.restoreAllMocks());
  it("renders the email from /api/auth/me, no hardcoded name, and signs out", async () => {
    const fetchMock = vi.fn(async (url) =>
      String(url).includes("/auth/me") ? json({ authenticated: true, email: "eng.sara@company.com" }) : json({ authenticated: false }));
    vi.stubGlobal("fetch", fetchMock);
    const { default: DashboardSidebar } = await import("../../components/DashboardSidebare.jsx");
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<DashboardSidebar />} />
          <Route path="/login" element={<div>login page</div>} />
        </Routes>
      </MemoryRouter>,
    );
    const emails = await screen.findAllByTestId("sidebar-user-email");
    await waitFor(() => expect(emails[0]).toHaveTextContent("eng.sara@company.com"));
    expect(screen.queryByText("Khalid Alotaibi")).toBeNull();
    expect(screen.getAllByText("ES")[0]).toBeInTheDocument();
    fireEvent.click(screen.getAllByLabelText("Sign out")[0]);
    expect(await screen.findByText("login page")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/auth/logout"))).toBe(true);
  });
});
