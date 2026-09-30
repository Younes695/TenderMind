import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

// Stage 5G: processing could only be started from the new-tender wizard. A tender
// created there but left before "Start Processing" had no way to be analysed.

function json(status, data) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => "application/json" },
    json: async () => data,
    text: async () => JSON.stringify(data),
  };
}

function routeFetch(docs, calls) {
  return vi.fn(async (url, opts = {}) => {
    calls.push(`${opts.method || "GET"} ${url}`);
    if (url.endsWith("/process")) return json(200, { job_id: "JOB-9", status: "QUEUED" });
    if (url.endsWith("/documents")) return json(200, { tender_id: "T1", documents: docs, count: docs.length });
    if (url.endsWith("/analysis")) return json(404, { detail: "No processing job found for tender" });
    if (url.endsWith("/api/tenders/T1")) return json(200, { id: "T1", title: "New" });
    return json(200, {});
  });
}

async function renderWorkspace() {
  const { default: TenderWorkspace } = await import("../TenderWorkspace.jsx");
  render(
    <MemoryRouter initialEntries={["/tenders/T1"]}>
      <Routes><Route path="/tenders/:tender_id" element={<TenderWorkspace />} /></Routes>
    </MemoryRouter>
  );
}

describe("Stage 5G - start processing from the workspace", () => {
  let calls;
  beforeEach(() => { calls = []; });
  afterEach(() => vi.restoreAllMocks());

  it("offers Start processing for an uploaded but never processed tender", async () => {
    vi.stubGlobal("fetch", routeFetch([{ id: "D1", title: "a.pdf" }], calls));
    vi.stubGlobal("location", { ...window.location, reload: vi.fn() });
    await renderWorkspace();
    const btn = await screen.findByTestId("start-processing");
    fireEvent.click(btn);
    await waitFor(() => expect(calls.some((c) => c.startsWith("POST") && c.endsWith("/api/tenders/T1/process"))).toBe(true));
  });

  it("does not offer it when there are no files", async () => {
    vi.stubGlobal("fetch", routeFetch([], calls));
    await renderWorkspace();
    await screen.findByTestId("processing-status");
    expect(screen.queryByTestId("start-processing")).toBeNull();
  });
});

describe("Stage 5G - unknown tender", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows 'Tender not found' instead of an empty workspace", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (url.endsWith("/api/tenders/T1")) return json(404, { detail: "Tender not found" });
      return json(404, { detail: "Not found" });
    }));
    await renderWorkspace();
    expect(await screen.findByTestId("tender-not-found")).toBeTruthy();
    expect(screen.queryByTestId("processing-status")).toBeNull();
  });
});
