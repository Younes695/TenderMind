/**
 * TenderMind Frontend API Client — Single source for backend calls
 * Backend contract (real):
 * POST /api/tenders
 * POST /api/tenders/{tender_id}/documents (multipart, field "files")
 * GET  /api/tenders/{tender_id}/documents
 * POST /api/tenders/{tender_id}/process
 * GET  /api/processing-jobs/{job_id}
 * GET  /api/tenders/{tender_id}/analysis
 * GET  /api/tenders
 *
 * Keep API base configurable via VITE_API_BASE / VITE_API_BASE_URL.
 * Do not hardcode localhost in components.
 */

const API_BASE = (import.meta.env.VITE_API_BASE || import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function apiUrl(path) {
  // path must start with /api or /health etc.
  if (!API_BASE) return path;
  return `${API_BASE}${path}`;
}

async function apiFetch(path, options = {}) {
  return fetch(apiUrl(path), {
    credentials: "include",
    ...options,
  });
}

async function handleResponse(resp) {
  const contentType = resp.headers.get("content-type") || "";
  let data = null;
  if (contentType.includes("application/json")) {
    try {
      data = await resp.json();
    } catch {
      data = null;
    }
  } else {
    try {
      const text = await resp.text();
      data = text ? { detail: text } : null;
    } catch {
      data = null;
    }
  }
  if (!resp.ok) {
    const detail = data?.detail || data?.message || `HTTP ${resp.status}`;
    const err = new Error(detail);
    err.status = resp.status;
    err.data = data;
    throw err;
  }
  return data;
}

export async function listTenders() {
  const resp = await apiFetch("/api/tenders", { method: "GET" });
  return handleResponse(resp);
}

export async function createTender({ id, tender_id, title, client, location }) {
  const tenderId = id || tender_id;
  const payload = { id: tenderId, title, client, location };
  const resp = await apiFetch("/api/tenders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(resp);
}

export async function getTender(tenderId) {
  const resp = await apiFetch(`/api/tenders/${encodeURIComponent(tenderId)}`, {
    method: "GET",
  });
  return handleResponse(resp);
}

export async function uploadTenderDocument(tenderId, files) {
  // files: File | File[] | FileList
  const form = new FormData();
  const arr = Array.isArray(files) ? files : Array.from(files || []);
  if (arr.length === 0) {
    const err = new Error("No files provided");
    err.status = 400;
    throw err;
  }
  for (const f of arr) {
    form.append("files", f);
  }
  const resp = await apiFetch(`/api/tenders/${encodeURIComponent(tenderId)}/documents`, {
    method: "POST",
    body: form,
  });
  return handleResponse(resp);
}

export async function getTenderDocuments(tenderId) {
  const resp = await apiFetch(`/api/tenders/${encodeURIComponent(tenderId)}/documents`, {
    method: "GET",
  });
  return handleResponse(resp);
}

// Remove one uploaded file so it is not used in processing.
export async function deleteTenderDocument(tenderId, docId) {
  const resp = await apiFetch(
    `/api/tenders/${encodeURIComponent(tenderId)}/documents/${encodeURIComponent(docId)}`,
    { method: "DELETE" },
  );
  return handleResponse(resp);
}

// Remove every uploaded file of a tender.
export async function deleteAllTenderDocuments(tenderId) {
  const resp = await apiFetch(`/api/tenders/${encodeURIComponent(tenderId)}/documents`, { method: "DELETE" });
  return handleResponse(resp);
}

export async function startTenderProcessing(tenderId) {
  const resp = await apiFetch(`/api/tenders/${encodeURIComponent(tenderId)}/process`, {
    method: "POST",
  });
  return handleResponse(resp);
}

export async function getProcessingJob(jobId) {
  const resp = await apiFetch(`/api/processing-jobs/${encodeURIComponent(jobId)}`, {
    method: "GET",
  });
  return handleResponse(resp);
}

export async function getTenderAnalysis(tenderId) {
  const resp = await apiFetch(`/api/tenders/${encodeURIComponent(tenderId)}/analysis`, {
    method: "GET",
  });
  return handleResponse(resp);
}

// ---- Stage 5C: decision with evidence for uploaded tenders
export async function getDecisionDetail(tenderId) {
  const resp = await apiFetch(`/api/tenders/${encodeURIComponent(tenderId)}/decision-detail`, { method: "GET" });
  return handleResponse(resp);
}

export async function startEvaluation(tenderId) {
  const resp = await apiFetch(`/api/tenders/${encodeURIComponent(tenderId)}/evaluate`, { method: "POST" });
  return handleResponse(resp);
}

export async function getEvaluation(tenderId) {
  const resp = await apiFetch(`/api/tenders/${encodeURIComponent(tenderId)}/evaluation`, { method: "GET" });
  return handleResponse(resp);
}

export async function listCompanyDocuments() {
  const resp = await apiFetch("/api/company-documents", { method: "GET" });
  return handleResponse(resp);
}

export async function uploadCompanyDocuments(files) {
  const form = new FormData();
  for (const f of Array.from(files || [])) form.append("files", f);
  const resp = await apiFetch("/api/company-documents", { method: "POST", body: form });
  return handleResponse(resp);
}

export async function deleteCompanyDocument(docId) {
  const resp = await apiFetch(`/api/company-documents/${encodeURIComponent(docId)}`, { method: "DELETE" });
  return handleResponse(resp);
}

export async function overrideDecision(tenderId, { reviewer, new_decision, reason }) {
  const resp = await apiFetch(`/api/tenders/${encodeURIComponent(tenderId)}/decision/override`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer, new_decision, reason }),
  });
  return handleResponse(resp);
}

export async function signup({ name, email, password }) {
  const resp = await apiFetch("/api/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password }),
  });
  return handleResponse(resp);
}

// Which sign-in methods the server has configured: {password, signup, google, microsoft}.
export async function getAuthProviders() {
  const resp = await apiFetch("/api/auth/providers", { method: "GET" });
  return handleResponse(resp);
}

export async function login({ email, password }) {
  const resp = await apiFetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse(resp);
}

export async function getCurrentUser() {
  const resp = await apiFetch("/api/auth/me", {
    method: "GET",
  });
  return handleResponse(resp);
}

export async function logout() {
  const resp = await apiFetch("/api/auth/logout", {
    method: "POST",
  });
  return handleResponse(resp);
}

// Convenience: poll until terminal (COMPLETED/PARTIAL/FAILED)
export async function pollProcessingJob(jobId, { intervalMs = 1500, maxAttempts = 40, onUpdate } = {}) {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const job = await getProcessingJob(jobId);
    if (onUpdate) onUpdate(job);
    if (["COMPLETED", "PARTIAL", "FAILED"].includes(job.status)) {
      return job;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Polling timeout: job did not reach terminal state");
}

const apiClient = {
  listTenders,
  createTender,
  getTender,
  uploadTenderDocument,
  getTenderDocuments,
  deleteTenderDocument,
  deleteAllTenderDocuments,
  startTenderProcessing,
  getProcessingJob,
  getTenderAnalysis,
  login,
  signup,
  getAuthProviders,
  getCurrentUser,
  logout,
  pollProcessingJob,
  getDecisionDetail,
  startEvaluation,
  getEvaluation,
  listCompanyDocuments,
  uploadCompanyDocuments,
  deleteCompanyDocument,
  overrideDecision,
  apiUrl,
};

export default apiClient;
