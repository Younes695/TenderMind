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
    if (["COMPLETED", "PARTIAL", "FAILED", "INELIGIBLE"].includes(job.status)) {
      return job;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Polling timeout: job did not reach terminal state");
}

// ---- Stage 5H: review items, Q&A, notifications, news
export async function getTenderIssues(tenderId, { category, status } = {}) {
  const q = new URLSearchParams();
  if (category) q.set("category", category);
  if (status) q.set("status", status);
  const resp = await apiFetch(`/api/tenders/${encodeURIComponent(tenderId)}/issues${q.toString() ? `?${q}` : ""}`, { method: "GET" });
  return handleResponse(resp);
}

export async function updateIssue(issueId, patch) {
  const resp = await apiFetch(`/api/issues/${encodeURIComponent(issueId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return handleResponse(resp);
}

export async function getNotifications() {
  const resp = await apiFetch(`/api/notifications`, { method: "GET" });
  return handleResponse(resp);
}

export async function getNews({ country, q, relevant = true, sort } = {}) {
  const p = new URLSearchParams({ relevant: String(relevant) });
  if (sort) p.set("sort", sort);
  if (country) p.set("country", country);
  if (q) p.set("q", q);
  const resp = await apiFetch(`/api/news?${p}`, { method: "GET" });
  return handleResponse(resp);
}

export async function refreshNews() {
  const resp = await apiFetch(`/api/news/refresh`, { method: "POST" });
  return handleResponse(resp);
}

// ---- Stage 5I: subcontractor RFQs, account settings, feedback
async function jsonCall(path, method = "GET", body) {
  const opts = { method };
  if (body !== undefined) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  return handleResponse(await apiFetch(path, opts));
}

export const listRfqs = (tenderId) => jsonCall(`/api/rfqs${tenderId ? `?tender_id=${encodeURIComponent(tenderId)}` : ""}`);
export const createRfq = (tenderId, data) => jsonCall(`/api/tenders/${encodeURIComponent(tenderId)}/rfqs`, "POST", data);
export const deleteRfq = (rfqId) => jsonCall(`/api/rfqs/${encodeURIComponent(rfqId)}`, "DELETE");
export const addQuotation = (rfqId, data) => jsonCall(`/api/rfqs/${encodeURIComponent(rfqId)}/quotations`, "POST", data);
export const deleteQuotation = (quoteId) => jsonCall(`/api/quotations/${encodeURIComponent(quoteId)}`, "DELETE");
export const selectQuotation = (quoteId) => jsonCall(`/api/quotations/${encodeURIComponent(quoteId)}/select`, "POST");
export const getRfqDraft = (rfqId) => jsonCall(`/api/rfqs/${encodeURIComponent(rfqId)}/draft`);
export const updateProfile = (data) => jsonCall(`/api/auth/me`, "PATCH", data);
export const changePassword = (data) => jsonCall(`/api/auth/change-password`, "POST", data);
export const sendFeedback = (data) => jsonCall(`/api/feedback`, "POST", data);
export const listFeedback = () => jsonCall(`/api/feedback`);
export const getRecommendation = (id, lang = "en") => jsonCall(`/api/tenders/${encodeURIComponent(id)}/recommendation?lang=${lang}`);
export const getEmailDraft = (id, lang = "en") => jsonCall(`/api/tenders/${encodeURIComponent(id)}/email-draft?lang=${lang}`);
export const getCompanyProfile = () => jsonCall(`/api/company-profile`);
export const saveCompanyProfile = (data) => jsonCall(`/api/company-profile`, "PUT", data);
// Stage 6
const T = (id) => `/api/tenders/${encodeURIComponent(id)}`;
export const getCapability = () => jsonCall(`/api/company-capability`);
export const saveCapability = (data) => jsonCall(`/api/company-capability`, "PUT", data);
export const getEligibility = (id) => jsonCall(`${T(id)}/eligibility`);
export const overrideEligibility = (id, data) => jsonCall(`${T(id)}/eligibility/override`, "POST", data);
export const getSections = (id) => jsonCall(`${T(id)}/sections`);
export const listTeam = () => jsonCall(`/api/team`);
export const addTeamMember = (data) => jsonCall(`/api/team`, "POST", data);
export const deleteTeamMember = (mid) => jsonCall(`/api/team/${encodeURIComponent(mid)}`, "DELETE");
export const listTasks = (id) => jsonCall(`${T(id)}/tasks`);
export const addTask = (id, data) => jsonCall(`${T(id)}/tasks`, "POST", data);
export const updateTask = (id, taskId, data) => jsonCall(`${T(id)}/tasks/${encodeURIComponent(taskId)}`, "PUT", data);
export const deleteTask = (id, taskId) => jsonCall(`${T(id)}/tasks/${encodeURIComponent(taskId)}`, "DELETE");
export const getTaskGroups = () => jsonCall(`/api/tasks/groups`);
export const getVotes = (id) => jsonCall(`${T(id)}/votes`);
export const putVote = (id, data) => jsonCall(`${T(id)}/votes`, "PUT", data);
export const deleteVote = (id, name) => jsonCall(`${T(id)}/votes/${encodeURIComponent(name)}`, "DELETE");
export const setOutcome = (id, outcome) => jsonCall(`${T(id)}/outcome`, "PUT", { outcome });
export const getScore = (id) => jsonCall(`${T(id)}/score`);
export const getScoreWeights = () => jsonCall(`/api/score-weights`);
export const saveScoreWeights = (data) => jsonCall(`/api/score-weights`, "PUT", data);
// Stage 7
export const getChecklist = (id) => jsonCall(`${T(id)}/checklist`);
export const updateChecklistItem = (id, key, data) => jsonCall(`${T(id)}/checklist/${encodeURIComponent(key)}`, "PUT", data);
export const getDecisionPack = (id, lang = "en") => jsonCall(`${T(id)}/decision-pack?lang=${lang}`);
export const complianceMatrixUrl = (id, lang = "en") => apiUrl(`${T(id)}/compliance-matrix.xlsx?lang=${lang}`);
// Materials: BOQ, supplier price lists, bulk opportunities
export const getTenderMaterials = (id) => jsonCall(`${T(id)}/materials`);
export const getPortfolioMaterials = () => jsonCall(`/api/portfolio/materials`);
export const listPriceLists = () => jsonCall(`/api/price-lists`);
export const deletePriceList = (id) => jsonCall(`/api/price-lists/${encodeURIComponent(id)}`, "DELETE");
export async function uploadPriceList({ file, supplier, currency, price_date }) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("supplier", supplier);
  fd.append("currency", currency);
  fd.append("price_date", price_date);
  const resp = await apiFetch(`/api/price-lists`, { method: "POST", body: fd });
  return handleResponse(resp);
}
// RFQ packages
export const getRfqPackages = (id) => jsonCall(`${T(id)}/rfq-packages`);
export const createRfqPackages = (id, data) => jsonCall(`${T(id)}/rfq-packages`, "POST", data);
export const rfqPackagesZipUrl = (id, keys = [], closesAt = "") =>
  apiUrl(`${T(id)}/rfq-packages.zip?keys=${encodeURIComponent(keys.join(","))}${closesAt ? `&closes_at=${closesAt}` : ""}`);
// Stage 8
export const getSummary = (id) => jsonCall(`${T(id)}/summary`);
export const getSimilar = (id) => jsonCall(`${T(id)}/similar`);
export const setPlan = (id, data) => jsonCall(`${T(id)}/plan`, "PUT", data);
export const listNotes = (id) => jsonCall(`${T(id)}/notes`);
export const addNote = (id, data) => jsonCall(`${T(id)}/notes`, "POST", data);
export const deleteNote = (id, noteId) => jsonCall(`${T(id)}/notes/${encodeURIComponent(noteId)}`, "DELETE");
export const getReminders = () => jsonCall(`/api/reminders`);
export const getAttention = () => jsonCall(`/api/dashboard/attention`);
export const askAssistant = (data) => jsonCall(`/api/assistant/ask`, "POST", data);
// Stage 9
export const getBoard = () => jsonCall(`/api/portfolio/board`);
export const getApprovals = () => jsonCall(`/api/portfolio/approvals`);
export const setFinalDecision = (id, data) => jsonCall(`${T(id)}/final-decision`, "PUT", data);
export const getWorkPackages = () => jsonCall(`/api/portfolio/work-packages`);
export const getDocuments = (q = "") => jsonCall(`/api/portfolio/documents?q=${encodeURIComponent(q)}`);
export const getAnalytics = () => jsonCall(`/api/portfolio/analytics`);

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
  getTenderIssues,
  updateIssue,
  getNotifications,
  getNews,
  refreshNews,
  listRfqs,
  createRfq,
  deleteRfq,
  addQuotation,
  deleteQuotation,
  selectQuotation,
  getRfqDraft,
  updateProfile,
  changePassword,
  sendFeedback,
  listFeedback,
  getRecommendation,
  getEmailDraft,
  getCompanyProfile,
  saveCompanyProfile,
  getCapability,
  saveCapability,
  getEligibility,
  overrideEligibility,
  getSections,
  listTeam,
  addTeamMember,
  deleteTeamMember,
  listTasks,
  addTask,
  updateTask,
  deleteTask,
  getTaskGroups,
  getVotes,
  putVote,
  deleteVote,
  setOutcome,
  getScore,
  getScoreWeights,
  saveScoreWeights,
  getChecklist,
  updateChecklistItem,
  getDecisionPack,
  complianceMatrixUrl,
  getRfqPackages,
  getTenderMaterials,
  getPortfolioMaterials,
  listPriceLists,
  deletePriceList,
  uploadPriceList,
  createRfqPackages,
  rfqPackagesZipUrl,
  getSummary,
  getSimilar,
  setPlan,
  listNotes,
  addNote,
  deleteNote,
  getReminders,
  getAttention,
  askAssistant,
  getBoard,
  getApprovals,
  setFinalDecision,
  getWorkPackages,
  getDocuments,
  getAnalytics,
  apiUrl,
};

export default apiClient;
