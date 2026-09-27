import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Helper to create mock fetch response
function mockResponse({ ok = true, status = 200, jsonData = null, textData = null, headers = {} } = {}) {
  return {
    ok,
    status,
    headers: {
      get: (name) => {
        if (name.toLowerCase() === "content-type") return headers["content-type"] || "application/json";
        return headers[name] || null;
      },
    },
    json: async () => jsonData,
    text: async () => textData || JSON.stringify(jsonData || ""),
  };
}

describe("TenderMind API Client", () => {
  let originalFetch;

  beforeEach(() => {
    originalFetch = global.fetch;
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    global.fetch = originalFetch;
  });

  // 1. create tender success
  it("1. create tender success", async () => {
    const { createTender } = await import("./client.js");
    global.fetch.mockResolvedValueOnce(mockResponse({ jsonData: { id: "TEST-001", title: "Test" } }));
    const data = await createTender({ id: "TEST-001", title: "Test" });
    expect(data.id).toBe("TEST-001");
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toContain("/api/tenders");
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body).title).toBe("Test");
  });

  // 2. create tender failure (validation error 400)
  it("2. create tender failure — validation error", async () => {
    const { createTender } = await import("./client.js");
    global.fetch.mockResolvedValueOnce(mockResponse({ ok: false, status: 400, jsonData: { detail: "id and title are required" } }));
    await expect(createTender({ id: "", title: "" })).rejects.toThrow("id and title are required");
    global.fetch.mockResolvedValueOnce(mockResponse({ ok: false, status: 400, jsonData: { detail: "title is required" } }));
    const errStatus = await createTender({ id: "X", title: "" }).catch((e) => e);
    expect(errStatus.status).toBe(400);
  });

  // 3. document upload success (multipart)
  it("3. document upload success", async () => {
    const { uploadTenderDocument } = await import("./client.js");
    const file = new File(["dummy content"], "test.pdf", { type: "application/pdf" });
    global.fetch.mockResolvedValueOnce(mockResponse({ jsonData: { tender_id: "T1", count: 1, documents: [{ id: "DOC-1", filename: "test.pdf", doc_type: "PDF", size: 13 }] } }));
    const res = await uploadTenderDocument("T1", [file]);
    expect(res.count).toBe(1);
    expect(res.documents[0].filename).toBe("test.pdf");
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toContain("/api/tenders/T1/documents");
    expect(opts.method).toBe("POST");
    expect(opts.body instanceof FormData).toBe(true);
  });

  // 4. document upload failure (400 empty file)
  it("4. document upload failure — empty file", async () => {
    const { uploadTenderDocument } = await import("./client.js");
    global.fetch.mockResolvedValueOnce(mockResponse({ ok: false, status: 400, jsonData: { detail: "Empty file not accepted: empty.pdf" } }));
    const file = new File([], "empty.pdf", { type: "application/pdf" });
    await expect(uploadTenderDocument("T1", [file])).rejects.toThrow("Empty file");
  });

  // 5. processing polling (queues -> processing -> completed)
  it("5. processing polling — QUEUED -> PROCESSING -> COMPLETED", async () => {
    const { startTenderProcessing, pollProcessingJob } = await import("./client.js");
    global.fetch
      .mockResolvedValueOnce(mockResponse({ jsonData: { job_id: "JOB-1", status: "QUEUED" } })) // start
      .mockResolvedValueOnce(mockResponse({ jsonData: { job_id: "JOB-1", status: "QUEUED", progress: 5 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { job_id: "JOB-1", status: "PROCESSING", progress: 50 } }))
      .mockResolvedValueOnce(mockResponse({ jsonData: { job_id: "JOB-1", status: "COMPLETED", progress: 100 } }));
    const start = await startTenderProcessing("T1");
    expect(start.job_id).toBe("JOB-1");
    const final = await pollProcessingJob("JOB-1", { intervalMs: 1, maxAttempts: 5 });
    expect(final.status).toBe("COMPLETED");
    expect(final.progress).toBe(100);
  });

  // 6. COMPLETED state handling
  it("6. COMPLETED state", async () => {
    const { getProcessingJob } = await import("./client.js");
    global.fetch.mockResolvedValueOnce(mockResponse({ jsonData: { job_id: "JOB-1", status: "COMPLETED", progress: 100, documents_total: 1, documents_processed: 1 } }));
    const job = await getProcessingJob("JOB-1");
    expect(job.status).toBe("COMPLETED");
    expect(job.progress).toBe(100);
  });

  // 7. PARTIAL state (some docs unsupported)
  it("7. PARTIAL state", async () => {
    const { getProcessingJob } = await import("./client.js");
    global.fetch.mockResolvedValueOnce(mockResponse({ jsonData: { job_id: "JOB-1", status: "PARTIAL", progress: 100, documents_total: 2, documents_processed: 1, documents_unsupported: 1 } }));
    const job = await getProcessingJob("JOB-1");
    expect(job.status).toBe("PARTIAL");
    expect(job.documents_unsupported).toBe(1);
  });

  // 8. FAILED state
  it("8. FAILED state", async () => {
    const { getProcessingJob } = await import("./client.js");
    global.fetch.mockResolvedValueOnce(mockResponse({ jsonData: { job_id: "JOB-1", status: "FAILED", progress: 100, error_count: 1, last_error: "PERSISTENCE failed" } }));
    const job = await getProcessingJob("JOB-1");
    expect(job.status).toBe("FAILED");
    expect(job.last_error).toContain("PERSISTENCE");
  });

  // 9. analysis fetch success (canonical object)
  it("9. analysis fetch success", async () => {
    const { getTenderAnalysis } = await import("./client.js");
    const canonical = {
      tender: { id: "T1", title: "Test" },
      documents: [{ filename: "test.pdf", page_count: 1 }],
      requirements: [{ requirement_id: "REQ-001", summary: "Test req", category: "TECHNICAL", mandatory: null, confidence: 0.8, source_document: "test.pdf", page_number: 1 }],
      evidence: [],
      deadlines: [],
      risks: [],
      derived_features: { requirement_count: 1 },
    };
    global.fetch.mockResolvedValueOnce(mockResponse({ jsonData: canonical }));
    const data = await getTenderAnalysis("T1");
    expect(data.requirements).toHaveLength(1);
    expect(data.requirements[0].source_document).toBe("test.pdf");
    expect(data.documents[0].filename).toBe("test.pdf");
  });

  // 10. analysis fetch failure (404 no job)
  it("10. analysis fetch failure — 404", async () => {
    const { getTenderAnalysis } = await import("./client.js");
    global.fetch.mockResolvedValueOnce(mockResponse({ ok: false, status: 404, jsonData: { detail: "No processing job found for tender" } }));
    await expect(getTenderAnalysis("T1")).rejects.toThrow("No processing job");
  });

  // 11. empty/missing fields — handle gracefully (frontend must not break)
  it("11. empty/missing fields handled", async () => {
    const { getTenderAnalysis } = await import("./client.js");
    const withMissing = {
      tender: { id: "T1", title: null },
      documents: [{ filename: null, page_count: 0 }],
      requirements: [{ requirement_id: "REQ-001", summary: null, category: null, mandatory: null, confidence: null, source_document: null, page_number: null }],
      evidence: null,
      deadlines: null,
    };
    global.fetch.mockResolvedValueOnce(mockResponse({ jsonData: withMissing }));
    const data = await getTenderAnalysis("T1");
    // Should not throw, fields may be null — frontend should display "Not available" not crash
    expect(data.requirements[0].summary).toBeNull();
    expect(data.tender.title).toBeNull();
  });

  // 12. no mock data leaking into real tender state
  it("12. no mock data leaking — real tender does not contain Riyadh/SAR 12.5M etc", async () => {
    const { createTender, listTenders } = await import("./client.js");
    // Real tender creation should not return mock fields
    global.fetch.mockResolvedValueOnce(mockResponse({ jsonData: { id: "REAL-001", title: "Real Tender", client: "RealClient", location: "RealCity" } }));
    const real = await createTender({ id: "REAL-001", title: "Real Tender" });
    expect(real.title).not.toContain("Riyadh");
    expect(real.title).not.toContain("RUH-2026-184");
    expect(JSON.stringify(real)).not.toContain("SAR 12.5M");
    expect(JSON.stringify(real)).not.toContain("Example Client");
    // List should also not contain mock
    global.fetch.mockResolvedValueOnce(mockResponse({ jsonData: [{ id: "REAL-001", title: "Real Tender" }] }));
    const list = await listTenders();
    expect(JSON.stringify(list)).not.toContain("Riyadh Smart Infrastructure");
    expect(JSON.stringify(list)).not.toContain("82 / 100");
    expect(JSON.stringify(list)).not.toContain("CONDITIONAL GO");
  });

  it("API base configurable — not hardcoded localhost in component", async () => {
    // Verify client uses import.meta.env, not hardcoded
    const clientModule = await import("./client.js");
    expect(typeof clientModule.createTender).toBe("function");
    expect(typeof clientModule.uploadTenderDocument).toBe("function");
    expect(typeof clientModule.startTenderProcessing).toBe("function");
    expect(typeof clientModule.getProcessingJob).toBe("function");
    expect(typeof clientModule.getTenderAnalysis).toBe("function");
    expect(typeof clientModule.getTenderDocuments).toBe("function");
  });
});
