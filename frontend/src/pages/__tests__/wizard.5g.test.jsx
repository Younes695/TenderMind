import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// Stage 5G: after a server restart the wizard showed "Failed to fetch", stopped
// polling for good, and offered no way to restart a failed job.

function json(status, data) {
  return { ok: status < 300, status, headers: { get: () => "application/json" },
           json: async () => data, text: async () => JSON.stringify(data) };
}

describe("Stage 5G - wizard analyze step recovers", () => {
  afterEach(() => vi.restoreAllMocks());

  it("keeps polling through a dropped connection, then offers Retry on FAILED", async () => {
    const calls = [];
    let jobGets = 0;
    vi.stubGlobal("fetch", vi.fn(async (url, opts = {}) => {
      calls.push(`${opts.method || "GET"} ${url}`);
      if (url.includes("/processing-jobs/")) {
        jobGets += 1;
        if (jobGets === 1) throw new TypeError("Failed to fetch");
        return json(200, { job_id: "JOB-1", status: "FAILED", progress: 28,
                           last_error: "Interrupted: the server stopped while this job was running." });
      }
      if (url.endsWith("/process")) return json(200, { job_id: "JOB-2", status: "QUEUED" });
      return json(200, {});
    }));
    const { AnalyzeStep } = await import("../NewTender.jsx");
    const setJobId = vi.fn();
    render(<AnalyzeStep tenderId="T1" jobId="JOB-1" setJobId={setJobId} onNext={() => {}} pollMs={10} retryMs={10} />);

    expect(await screen.findByText(/Connection lost/)).toBeTruthy();
    expect(await screen.findByText(/server stopped while this job was running/)).toBeTruthy();
    expect(screen.queryByText(/Connection lost/)).toBeNull();
    fireEvent.click(screen.getByTestId("retry-processing"));
    await waitFor(() => expect(setJobId).toHaveBeenCalledWith("JOB-2"));
    expect(calls.some((c) => c === "POST /api/tenders/T1/process")).toBe(true);
  });
});
