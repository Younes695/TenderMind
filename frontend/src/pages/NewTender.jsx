import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  UploadCloud,
  FileText,
  FileSpreadsheet,
  FileArchive,
  FileImage,
  ShieldCheck,
  Lock,
  Check,
  CheckCircle2,
  AlertTriangle,
  Info,
  Download,
  X,
  Trash2,
} from "lucide-react";
import logo from "../assets/logo.jpg";
import apiClient from "../api/client";

function formatSize(bytes) {
  const n = Number(bytes) || 0;
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(2)} GB`;
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${n} bytes`;
}

const isUnsupported = (d) => String(d?.doc_type || "").toUpperCase() === "UNSUPPORTED";

// Supported types green, UNSUPPORTED red so it stands out before processing.
function DocTypeBadge({ type }) {
  const unsupported = String(type || "").toUpperCase() === "UNSUPPORTED";
  return (
    <span data-testid="doc-type-badge" className={`shrink-0 rounded-lg px-2 py-1 text-[12px] font-bold ${unsupported ? "border border-[#f5c6c6] bg-[#fdf0f0] text-[#b42318]" : "bg-[#e5f2eb] text-[#2E7D5B]"}`}>
      {type || "Not available"}
    </span>
  );
}


function UnsupportedWarning({ docs }) {
  const n = (docs || []).filter(isUnsupported).length;
  if (!n) return null;
  return (
    <div data-testid="unsupported-warning" className="mt-2 flex items-start gap-2 rounded-lg border border-[#f5c6c6] bg-[#fdf0f0] p-2.5 text-[12px] text-[#b42318]">
      <AlertTriangle size={15} className="mt-0.5 shrink-0" />
      <span>{n} file{n > 1 ? "s are" : " is"} not supported (for example AutoCAD DWG drawings) and will be skipped. Remove {n > 1 ? "them" : "it"} if uploaded by mistake.</span>
    </div>
  );
}

const STEPS = ["Upload", "Review", "Analyze", "Results", "Fit", "Gaps", "Create"];

function TopBar() {
  return (
    <header className="bg-[#162A4C]">
      <div className="mx-auto flex max-w-[1200px] items-center justify-between gap-3 px-4 py-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <img src={logo} alt="TenderMind logo" className="h-9 w-9 shrink-0 rounded-lg object-cover" />
          <span className="text-[19px] font-black tracking-wide text-white">
            TENDER<span className="text-[#C8A96B]">MIND</span>
          </span>
          <span className="hidden truncate rounded-lg bg-white/10 px-3 py-1.5 text-[13px] text-[#c5d0e6] md:block">
            Tender setup
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-[14px] text-[#c5d0e6]">
          <Lock size={16} />
          <span className="hidden sm:inline">Confidential handling</span>
          <span className="sm:hidden">Confidential</span>
        </div>
      </div>
    </header>
  );
}

function Stepper({ step }) {
  return (
    <div>
      <div className="md:hidden">
        <p className="text-[14px] font-bold text-[#162A4C]">Step {step} of 7: {STEPS[step - 1]}</p>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#e8e2d4]">
          <div className="h-full rounded-full bg-[#2E7D5B] transition-all" style={{ width: `${(step / 7) * 100}%` }} />
        </div>
      </div>
      <ol className="hidden items-center gap-2 md:flex lg:gap-3">
        {STEPS.map((label, i) => {
          const n = i + 1;
          const done = n < step;
          const current = n === step;
          return (
            <li key={label} className="flex min-w-0 flex-1 items-center gap-2">
              <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[15px] font-bold ${done ? "bg-[#2E7D5B] text-white" : current ? "bg-[#162A4C] text-white" : "border border-[#ddd5c2] bg-white text-[#8a8fa0]"}`}>{done ? <Check size={17} strokeWidth={3} /> : n}</span>
              <span className={`truncate text-[15px] ${current ? "font-bold text-[#162A4C]" : "text-[#6b7280]"}`}>{label}</span>
              {n < 7 && <span className={`mx-1 h-[2px] min-w-4 flex-1 rounded ${n < step ? "bg-[#2E7D5B]" : "bg-[#e3ddd0]"}`} />}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function PageTitle({ title, subtitle }) {
  return (
    <div className="mt-6">
      <h1 className="text-[28px] font-black leading-tight text-[#101828] sm:text-[33px]">{title}</h1>
      <p className="mt-2 max-w-[720px] text-[15px] leading-relaxed text-[#667085] sm:text-[16px]">{subtitle}</p>
    </div>
  );
}

function PrimaryButton({ children, onClick, disabled, loading }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={`flex h-[52px] items-center justify-center rounded-xl px-7 text-[15px] font-bold whitespace-nowrap transition-colors sm:text-[16px] ${disabled ? "bg-[#9aa3b8] text-white cursor-not-allowed" : "bg-[#162A4C] text-white hover:bg-[#0F1D38]"}`}>
      {loading ? "Loading..." : children}
    </button>
  );
}
function GhostButton({ children, onClick, disabled }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} className="flex h-[52px] items-center justify-center rounded-xl border border-[#e2e6ee] bg-white px-7 text-[15px] font-bold whitespace-nowrap text-[#101828] transition-colors hover:bg-[#f5f6f9] sm:text-[16px] disabled:opacity-50">
      {children}
    </button>
  );
}
function ErrorBanner({ message }) {
  if (!message) return null;
  return <div data-testid="error-banner" className="mt-4 rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] px-4 py-3 text-[14px] text-[#a33a3a]">{message}</div>;
}
function EmptyState({ message }) {
  return <div data-testid="empty-state" className="rounded-xl border border-[#e8e4dc] bg-[#faf9f6] p-6 text-center text-[15px] text-[#667085]">{message}</div>;
}

// --- UploadStep: create tender + upload documents ---
function UploadStep({ tenderId, setTenderId, tenderForm, setTenderForm, files, setFiles, uploadedDocs, setUploadedDocs, onNext, globalError, setGlobalError }) {
  const inputRef = useRef(null);
  const [formError, setFormError] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const [removing, setRemoving] = useState(false);

  const addFiles = (list) => {
    const added = Array.from(list);
    if (added.length) setFiles((prev) => [...prev, ...added]);
    if (inputRef.current) inputRef.current.value = ""; // allow re-selecting the same file
  };

  // Selected but not uploaded yet: removal is local only.
  const removeSelected = (idx) => setFiles((prev) => prev.filter((_, i) => i !== idx));
  const clearSelected = () => setFiles([]);

  // Already uploaded: remove from the server so it never enters processing.
  const removeUploaded = async (doc) => {
    setRemoving(true);
    setUploadError(null);
    try {
      await apiClient.deleteTenderDocument(tenderId, doc.id);
      setUploadedDocs((prev) => prev.filter((d) => d.id !== doc.id));
    } catch (e) {
      setUploadError(e.message || "Failed to remove file");
    } finally {
      setRemoving(false);
    }
  };

  const removeAllUploaded = async () => {
    if (!window.confirm(`Remove all ${uploadedDocs.length} uploaded files from this tender?`)) return;
    setRemoving(true);
    setUploadError(null);
    try {
      await apiClient.deleteAllTenderDocuments(tenderId);
      setUploadedDocs([]);
    } catch (e) {
      setUploadError(e.message || "Failed to remove files");
    } finally {
      setRemoving(false);
    }
  };

  const handleCreateTender = async () => {
    setFormError(null);
    setGlobalError(null);
    if (!tenderForm.id?.trim() || !tenderForm.title?.trim()) {
      setFormError("Tender ID and Title are required");
      return;
    }
    setCreating(true);
    try {
      const data = await apiClient.createTender({
        id: tenderForm.id.trim(),
        title: tenderForm.title.trim(),
        client: tenderForm.client?.trim() || undefined,
        location: tenderForm.location?.trim() || undefined,
      });
      setTenderId(data.id);
      setFormError(null);
    } catch (e) {
      setFormError(e.message || "Failed to create tender");
    } finally {
      setCreating(false);
    }
  };

  const handleUpload = async () => {
    if (!tenderId) {
      setUploadError("Create tender first");
      return;
    }
    if (!files || files.length === 0) {
      setUploadError("Select at least one file");
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      const res = await apiClient.uploadTenderDocument(tenderId, files);
      // Append (a second batch must not hide the first) and clear the selection
      // so pressing Upload again cannot send the same files twice.
      setUploadedDocs((prev) => [...prev, ...(res.documents || [])]);
      setFiles([]);
      setUploadError(null);
    } catch (e) {
      setUploadError(e.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const fileKind = (name) => {
    if (/\.xlsx?$/i.test(name)) return "xlsx";
    if (/\.(zip|rar|7z)$/i.test(name)) return "zip";
    if (/\.(jpe?g|png|bmp|gif|tiff?|webp)$/i.test(name)) return "image";
    return "pdf";
  };
  const FileIcon = ({ kind }) => {
    const cls = "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-[#e8e4dc] bg-[#faf9f6] text-[#162A4C]";
    if (kind === "xlsx") return <span className={cls}><FileSpreadsheet size={22} /></span>;
    if (kind === "zip") return <span className={cls}><FileArchive size={22} /></span>;
    if (kind === "image") return <span className={cls}><FileImage size={22} /></span>;
    return <span className={cls}><FileText size={22} /></span>;
  };

  return (
    <div>
      <PageTitle title="Start a New Tender" subtitle="Create a tender and upload its documents. The backend will process and analyze them." />
      {/* Tender form */}
      <div className="mt-6 rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
        <p className="text-[16px] font-bold text-[#101828]">Tender Information</p>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="text-[14px] font-medium text-[#667085]">Tender ID *</label>
            <input data-testid="tender-id-input" value={tenderForm.id} onChange={(e) => setTenderForm({ ...tenderForm, id: e.target.value })} placeholder="e.g. TEST-2024-001" className="mt-1 h-[48px] w-full rounded-xl border border-[#e8e4dc] bg-[#faf8f2] px-4 text-[15px] outline-none" />
          </div>
          <div>
            <label className="text-[14px] font-medium text-[#667085]">Title *</label>
            <input data-testid="tender-title-input" value={tenderForm.title} onChange={(e) => setTenderForm({ ...tenderForm, title: e.target.value })} placeholder="Tender title" className="mt-1 h-[48px] w-full rounded-xl border border-[#e8e4dc] bg-[#faf8f2] px-4 text-[15px] outline-none" />
          </div>
          <div>
            <label className="text-[14px] font-medium text-[#667085]">Client</label>
            <input data-testid="tender-client-input" value={tenderForm.client} onChange={(e) => setTenderForm({ ...tenderForm, client: e.target.value })} placeholder="Client (optional)" className="mt-1 h-[48px] w-full rounded-xl border border-[#e8e4dc] bg-[#faf8f2] px-4 text-[15px] outline-none" />
          </div>
          <div>
            <label className="text-[14px] font-medium text-[#667085]">Location</label>
            <input data-testid="tender-location-input" value={tenderForm.location} onChange={(e) => setTenderForm({ ...tenderForm, location: e.target.value })} placeholder="Location (optional)" className="mt-1 h-[48px] w-full rounded-xl border border-[#e8e4dc] bg-[#faf8f2] px-4 text-[15px] outline-none" />
          </div>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <PrimaryButton onClick={handleCreateTender} disabled={creating || !!tenderId} loading={creating}>{tenderId ? `Created: ${tenderId}` : "Create Tender"}</PrimaryButton>
          {tenderId && <span data-testid="tender-created" className="flex items-center gap-1 text-[14px] font-bold text-[#2E7D5B]"><CheckCircle2 size={16} /> Tender created: {tenderId}</span>}
        </div>
        <ErrorBanner message={formError} />
        <ErrorBanner message={globalError} />
      </div>

      {/* Dropzone */}
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-5">
        <div>
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); if (tenderId) addFiles(e.dataTransfer.files); }}
            className={`flex min-h-[320px] flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors ${dragOver ? "border-[#162A4C] bg-[#eef2f8]" : "border-[#cbbd93] bg-white/60"}`}
          >
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#162A4C] text-white"><UploadCloud size={30} /></span>
            <p className="mt-5 text-[19px] font-bold text-[#101828] sm:text-[21px]">Drag & Drop your tender files here</p>
            <p className="mt-1 text-[15px] text-[#667085]">or</p>
            <button type="button" onClick={() => inputRef.current?.click()} disabled={!tenderId} className={`mt-4 flex h-[52px] items-center rounded-xl px-8 text-[16px] font-bold transition-colors ${!tenderId ? "bg-[#9aa3b8] text-white cursor-not-allowed" : "bg-[#162A4C] text-white hover:bg-[#0F1D38]"}`}>Browse Files</button>
            <input ref={inputRef} type="file" multiple data-testid="file-input" className="hidden" onChange={(e) => addFiles(e.target.files)} />
            <div className="mt-6 flex flex-wrap justify-center gap-2">{["PDF", "Word", "Excel", "Images", "ZIP", "RAR", "7z", "DXF", ".bak"].map((t) => (<span key={t} className="rounded-lg border border-[#e3ddd0] bg-[#faf9f6] px-3 py-1.5 text-[14px] font-bold text-[#101828]">{t}</span>))}</div>
            <p className="mt-4 text-[14px] text-[#667085]">{tenderId ? "Select files, then upload" : "Create tender before uploading"}</p>
            <p className="mt-1 text-[13px] text-[#98a2b3]">Up to 5 GB per file</p>
          </div>
          <ErrorBanner message={uploadError} />
          <div className="mt-4 flex items-center gap-2.5 rounded-xl border border-[#e8e4dc] bg-white p-4">
            <ShieldCheck size={20} className="shrink-0 text-[#162A4C]" />
            <p className="text-[14px] text-[#667085] sm:text-[15px]">Your tender documents are handled as confidential business information.</p>
          </div>
        </div>
        {/* Files card — shows selected Files and uploadedDocs */}
        <div className="h-fit rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <p className="text-[16px] font-bold text-[#101828]">Files • {files.length}</p>
            {files.length > 0 ? (
              <button type="button" data-testid="clear-selected" onClick={clearSelected} disabled={uploading} className="text-[13px] font-semibold text-[#a33a3a] hover:underline disabled:opacity-50">Clear all</button>
            ) : (
              <p className="text-[14px] text-[#667085]">{uploadedDocs.length > 0 ? `${uploadedDocs.length} uploaded` : "No uploads yet"}</p>
            )}
          </div>
          {files.length === 0 ? (
            <EmptyState message="No files selected" />
          ) : (
            <div className="mt-4 divide-y divide-[#eeeae3]">
              {files.map((f, idx) => (
                <div key={`${f.name}-${idx}`} data-testid="selected-file" className="flex items-center gap-3 py-3.5">
                  <FileIcon kind={fileKind(f.name)} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[15px] font-bold text-[#101828]">{f.name}</p>
                    <p className="mt-0.5 text-[14px] text-[#667085]">{formatSize(f.size)}</p>
                  </div>
                  <button type="button" aria-label={`Remove ${f.name}`} onClick={() => removeSelected(idx)} disabled={uploading} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[#667085] hover:bg-[#fdf0f0] hover:text-[#a33a3a] disabled:opacity-50">
                    <X size={18} />
                  </button>
                </div>
              ))}
            </div>
          )}
          {/* Uploaded docs from backend */}
          {uploadedDocs.length > 0 && (
            <div className="mt-4">
              <div className="flex items-center justify-between">
                <p className="text-[14px] font-bold text-[#2E7D5B]">Uploaded documents • {uploadedDocs.length}</p>
                <button type="button" data-testid="remove-all-uploaded" onClick={removeAllUploaded} disabled={removing} className="text-[13px] font-semibold text-[#a33a3a] hover:underline disabled:opacity-50">Remove all</button>
              </div>
              <UnsupportedWarning docs={uploadedDocs} />
              <div className="mt-2 divide-y divide-[#eeeae3]">
                {uploadedDocs.map((d) => (
                  <div key={d.id} data-testid="uploaded-doc" className={`flex items-center gap-3 py-2 ${isUnsupported(d) ? "-mx-2 rounded-lg bg-[#fdf0f0] px-2" : ""}`}>
                    <FileIcon kind={fileKind(d.filename || d.title)} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[14px] font-bold text-[#101828]">{d.filename || d.title}</p>
                      <p className={`text-[12px] ${isUnsupported(d) ? "text-[#a33a3a]" : "text-[#667085]"}`}>
                        {isUnsupported(d) ? "Not supported — will not be analyzed" : d.doc_type} • {formatSize(d.size || d.file_size)}
                      </p>
                    </div>
                    <DocTypeBadge type={d.doc_type} />
                    <button type="button" aria-label={`Remove ${d.filename || d.title}`} onClick={() => removeUploaded(d)} disabled={removing} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[#667085] hover:bg-[#fdf0f0] hover:text-[#a33a3a] disabled:opacity-50">
                      <Trash2 size={17} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="mt-4 flex gap-3">
            <PrimaryButton onClick={handleUpload} disabled={!tenderId || files.length === 0 || uploading} loading={uploading}>Upload Documents</PrimaryButton>
          </div>
          {uploadedDocs.length > 0 && (
            <div className="mt-4">
              <PrimaryButton onClick={onNext}>Continue</PrimaryButton>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ReviewStep({ tenderId, uploadedDocs, onNext, onBack }) {
  const [docs, setDocs] = useState(uploadedDocs || []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!tenderId) return;
    // fetch fresh from backend to confirm
    setLoading(true);
    apiClient.getTenderDocuments(tenderId).then((res) => {
      if (res.documents) setDocs(res.documents);
      setLoading(false);
    }).catch((e) => { setError(e.message); setLoading(false); });
  }, [tenderId]);

  const [removing, setRemoving] = useState(false);

  const removeDoc = async (doc) => {
    setRemoving(true);
    setError(null);
    try {
      await apiClient.deleteTenderDocument(tenderId, doc.id);
      setDocs((prev) => prev.filter((d) => d.id !== doc.id));
    } catch (e) {
      setError(e.message || "Failed to remove file");
    } finally {
      setRemoving(false);
    }
  };

  const removeAll = async () => {
    if (!window.confirm(`Remove all ${docs.length} files from this tender?`)) return;
    setRemoving(true);
    setError(null);
    try {
      await apiClient.deleteAllTenderDocuments(tenderId);
      setDocs([]);
    } catch (e) {
      setError(e.message || "Failed to remove files");
    } finally {
      setRemoving(false);
    }
  };

  if (!tenderId) return <EmptyState message="No tender selected" />;
  if (loading) return <div className="mt-6">Loading documents...</div>;
  return (
    <div>
      <PageTitle title="Review Tender Documents" subtitle="Documents persisted for your tender. Verify before processing." />
      <ErrorBanner message={error} />
      <div className="mt-6 rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-8">
        {docs.length > 0 && (
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[14px] text-[#667085]">Remove anything uploaded by mistake — removed files are not processed.</p>
            <button type="button" data-testid="review-remove-all" onClick={removeAll} disabled={removing} className="shrink-0 text-[13px] font-semibold text-[#a33a3a] hover:underline disabled:opacity-50">Remove all</button>
          </div>
        )}
        <UnsupportedWarning docs={docs} />
        {docs.length === 0 ? (
          <EmptyState message="No documents" />
        ) : (
          <div className="divide-y divide-[#eeeae3]">
            {docs.map((d) => (
              <div key={d.id} data-testid="review-doc" className={`flex items-center gap-3 py-3 ${isUnsupported(d) ? "-mx-2 rounded-lg bg-[#fdf0f0] px-2" : ""}`}>
                <FileText size={22} className="text-[#162A4C]" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-bold text-[#101828]">{d.title || d.filename}</p>
                  <p className="text-[14px] text-[#667085]">
                    {d.doc_type || "Document"} • {d.original_filename || d.title || "Unnamed file"}
                  </p>
                </div>
                <DocTypeBadge type={d.doc_type} />
                <button type="button" aria-label={`Remove ${d.title || d.filename}`} onClick={() => removeDoc(d)} disabled={removing} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[#667085] hover:bg-[#fdf0f0] hover:text-[#a33a3a] disabled:opacity-50">
                  <Trash2 size={17} />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="mt-7 flex gap-3">
          <GhostButton onClick={onBack}>Back</GhostButton>
          <PrimaryButton onClick={onNext} disabled={docs.length === 0}>Start Processing</PrimaryButton>
        </div>
      </div>
    </div>
  );
}

function AnalyzeStep({ tenderId, jobId, setJobId, onNext }) {
  const [status, setStatus] = useState(null);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);

  const startProcessing = async () => {
    if (!tenderId) { setError("No tender selected"); return; }
    setStarting(true);
    setError(null);
    try {
      const res = await apiClient.startTenderProcessing(tenderId);
      setJobId(res.job_id);
      setStatus(res.status);
    } catch (e) {
      setError(e.message);
    } finally {
      setStarting(false);
    }
  };

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const job = await apiClient.getProcessingJob(jobId);
        if (cancelled) return;
        setStatus(job.status);
        setProgress(job.progress);
        if (["COMPLETED", "PARTIAL", "FAILED"].includes(job.status)) {
          return; // terminal
        }
        setTimeout(poll, 1500);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    };
    poll();
    return () => { cancelled = true; };
  }, [jobId]);

  const terminal = ["COMPLETED", "PARTIAL", "FAILED"].includes(status);
  const isProcessing = status === "PROCESSING" || status === "QUEUED";

  return (
    <div>
      <PageTitle title="TenderMind is processing your tender" subtitle="Real backend extraction — polling job status." />
      <div className="mt-6 rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-8">
        {!jobId ? (
          <div>
            <p className="text-[15px] text-[#667085]">Tender: <span className="font-bold text-[#101828]">{tenderId || "Not available"}</span></p>
            <div className="mt-4">
              <PrimaryButton onClick={startProcessing} disabled={starting} loading={starting}>Start Processing</PrimaryButton>
            </div>
            <ErrorBanner message={error} />
          </div>
        ) : (
          <div data-testid="job-status">
            <div className="flex items-center justify-between">
              <p className="text-[16px] font-bold text-[#101828]">Job {jobId}</p>
              <span data-testid="job-status-badge" className={`rounded-lg px-3 py-1 text-[13px] font-bold ${status === "COMPLETED" ? "bg-[#e5f2eb] text-[#2E7D5B]" : status === "FAILED" ? "bg-[#f9e3e3] text-[#b44444]" : status === "PARTIAL" ? "bg-[#f8edcf] text-[#a98238]" : "bg-[#eef2f8] text-[#162A4C]"}`}>{status || "Not available"}</span>
            </div>
            {progress != null ? (
              <div className="mt-3">
                <div className="h-2.5 overflow-hidden rounded-full bg-[#efe9dc]"><div className="h-full rounded-full bg-[#162A4C] transition-all" style={{ width: `${progress}%` }} /></div>
                <p className="mt-1 text-[14px] text-[#667085]">{progress}%</p>
              </div>
            ) : (
              <p className="mt-2 text-[14px] text-[#667085]">Progress: Not available</p>
            )}
            <ErrorBanner message={error} />
            {isProcessing && <p className="mt-3 text-[14px] text-[#667085]">Processing — polling every 1.5s</p>}
            {status === "FAILED" && <div className="mt-3 rounded-xl bg-[#fdf0f0] p-4 text-[14px] text-[#a33a3a]">Processing failed</div>}
            {terminal && status !== "FAILED" && (
              <div className="mt-5">
                <PrimaryButton onClick={onNext}>View Results</PrimaryButton>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ResultsStep({ tenderId, analysis, setAnalysis, onNext }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (!tenderId) return;
    if (analysis) return;
    setLoading(true);
    apiClient.getTenderAnalysis(tenderId).then((data) => {
      // backend returns {status: "QUEUED"/"PROCESSING"} while not ready, or analysis object when ready
      if (data.status && ["QUEUED", "PROCESSING"].includes(data.status)) {
        setError(`Analysis not ready: ${data.status}`);
        setLoading(false);
        return;
      }
      if (data.status === "FAILED") {
        setError(data.last_error || "Processing failed");
        setLoading(false);
        return;
      }
      // if fallback metadata without requirements, still show but mark empty
      setAnalysis(data);
      setLoading(false);
    }).catch((e) => { setError(e.message); setLoading(false); });
  }, [tenderId, analysis, setAnalysis]);

  if (loading) return <div className="mt-6">Loading analysis...</div>;
  if (error) return <div className="mt-6"><ErrorBanner message={error} /><div className="mt-4"><GhostButton onClick={() => window.location.reload()}>Retry</GhostButton></div></div>;
  if (!analysis) return <EmptyState message="Analysis unavailable" />;
  const reqs = analysis.requirements || [];
  const docs = analysis.documents || [];
  const risks = analysis.risks || [];
  const deadlines = analysis.deadlines || [];
  if (reqs.length === 0 && docs.length === 0) return <EmptyState message="Analysis empty" />;

  return (
    <div>
      <PageTitle title="Tender Analysis Complete" subtitle="Data from backend — no mock values." />
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6 lg:gap-4">
        {[
          [reqs.length, "Requirements"],
          [reqs.filter(r=>r.mandatory).length || "Not available", "Mandatory"],
          [deadlines.length || "Not available", "Deadlines"],
          [risks.length || "Not available", "Risks"],
          [docs.length || "Not available", "Documents"],
          [analysis.derived_features?.requirement_count ?? "Not available", "Derived"],
        ].map(([v,l]) => (
          <div key={l} className="rounded-2xl border border-[#e8e4dc] bg-white p-5 text-center">
            <p className="text-[28px] font-black text-[#162A4C] sm:text-[32px]">{v}</p>
            <p className="mt-1 text-[13px] text-[#667085] sm:text-[14px]">{l}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-7">
        <p className="text-[17px] font-bold text-[#101828]">Requirements (real)</p>
        {reqs.length === 0 ? <EmptyState message="No requirements" /> : (
          <div className="mt-4 space-y-3">
            {reqs.slice(0,6).map((r) => (
              <div key={r.requirement_id || r.candidate_id} data-testid="requirement-item" className="rounded-xl border border-[#e8e4dc] bg-[#faf8f2] p-4">
                <p className="text-[15px] font-bold text-[#101828]">{r.summary || "Not available"}</p>
                <p className="mt-1 text-[13px] text-[#667085]">Category: {r.category || "Not available"} • Mandatory: {r.mandatory == null ? "Not available" : String(r.mandatory)} • Confidence: {r.confidence ?? "Not available"}</p>
                <p className="mt-1 text-[12px] text-[#667085]">Source: {r.source_document || "Not available"} • Page {r.page_number ?? "Not available"}</p>
                {r.provenance?.quote_en && <p className="mt-1 text-[12px] italic text-[#667085]">“{r.provenance.quote_en.slice(0,120)}”</p>}
              </div>
            ))}
            {reqs.length > 6 && <p className="text-[14px] text-[#667085]">+{reqs.length - 6} more</p>}
          </div>
        )}
        <div className="mt-6 flex justify-end">
          <PrimaryButton onClick={onNext}>Check Company Fit</PrimaryButton>
        </div>
      </div>
    </div>
  );
}

function FitStep({ analysis, onNext }) {
  // Do NOT invent fit scores — show Not available or derived from analysis if present
  const derived = analysis?.derived_features;
  const hasData = derived && typeof derived.requirement_count === "number";
  return (
    <div>
      <PageTitle title="How does this tender fit your company?" subtitle="Fit scoring will be available in Stage 2B — currently showing analysis-derived info only." />
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-5">
        <div className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-8">
          {hasData ? (
            <div className="space-y-4">
              <div><p className="font-bold">Requirement count</p><p>{derived.requirement_count}</p></div>
              <div><p className="font-bold">Evidence coverage</p><p>{derived.evidence_coverage ?? "Not available"}</p></div>
              <div><p className="font-bold">Provenance coverage</p><p>{analysis.provenance_coverage ?? "Not available"}</p></div>
            </div>
          ) : (
            <EmptyState message="Fit data not available — analysis pending or empty" />
          )}
        </div>
        <div>
          <div className="rounded-2xl bg-[#162A4C] p-6 text-center sm:p-8">
            <p className="text-[13px] font-bold tracking-[0.18em] text-[#C8A96B]">AI RECOMMENDATION</p>
            <p className="mt-2 text-[26px] font-black text-white">Not available</p>
            <p className="mt-2 text-[14px] text-[#c5d0e6]">Fit scoring not implemented in Stage 2A</p>
            <button type="button" onClick={onNext} className="mt-5 flex h-[52px] w-full items-center justify-center rounded-xl bg-[#C8A96B] text-[16px] font-bold text-[#162A4C]">Review Gaps</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function GapsStep({ analysis, onNext, onBack }) {
  const reqs = analysis?.requirements || [];
  const gaps = reqs.filter(r => r.confidence != null && r.confidence < 0.7);
  return (
    <div>
      <PageTitle title="Requirements that need attention" subtitle="Derived from real analysis — no mock gaps." />
      <div className="mt-6 overflow-hidden rounded-2xl border border-[#e8e4dc] bg-white">
        {reqs.length === 0 ? <EmptyState message="No requirements to review" /> : (
          <div className="p-5">
            {gaps.length === 0 ? <EmptyState message="No gaps — all requirements high confidence or no data" /> : (
              <div className="space-y-3">
                {gaps.map((r) => (
                  <div key={r.requirement_id} data-testid="gap-item" className="rounded-xl border border-[#e8e4dc] p-4">
                    <p className="font-bold">{r.summary || "Not available"}</p>
                    <p className="text-[14px] text-[#667085]">Category {r.category || "Not available"} • Confidence {r.confidence ?? "Not available"} • Mandatory {r.mandatory == null ? "Not available" : String(r.mandatory)}</p>
                    <p className="text-[12px] text-[#667085]">Source: {r.source_document || "Not available"} Page {r.page_number ?? "Not available"}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        <div className="flex gap-3 p-5 border-t border-[#eeeae3] justify-end">
          <GhostButton onClick={onBack}>Back</GhostButton>
          <PrimaryButton onClick={onNext}>Create Workspace Plan</PrimaryButton>
        </div>
      </div>
    </div>
  );
}

function CreateStep({ tenderId, analysis, onBack, onDone }) {
  const tenderTitle = analysis?.tender?.title || analysis?.tender?.id || tenderId || "Not available";
  return (
    <div>
      <PageTitle title="Ready to create your Tender Workspace" subtitle="Workspace will be created from real tender data." />
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-5">
        <div className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-8">
          <p className="font-bold">Tender</p>
          <p data-testid="create-tender-id" className="text-[16px]">{tenderId || "Not available"}</p>
          <p className="mt-2 text-[14px] text-[#667085]">{tenderTitle}</p>
          <p className="mt-4 text-[14px] text-[#667085]">Requirements: {analysis?.requirements?.length ?? "Not available"}</p>
          <p className="text-[14px] text-[#667085]">Documents: {analysis?.documents?.length ?? "Not available"}</p>
        </div>
        <div>
          <div className="rounded-2xl bg-[#162A4C] p-6 sm:p-8">
            <p className="text-[17px] font-black text-white">{tenderId || "Not available"}</p>
            <p className="mt-1 text-[14px] text-[#c5d0e6]">{tenderTitle}</p>
            <button type="button" onClick={onDone} data-testid="create-workspace" className="mt-5 flex h-[54px] w-full items-center justify-center rounded-xl bg-[#C8A96B] text-[16px] font-bold text-[#162A4C]">Create Tender Workspace</button>
            <button type="button" onClick={onBack} className="mt-3 w-full text-center text-[14px] font-medium text-[#c5d0e6] underline underline-offset-4">Review Analysis</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function NewTender() {
  const [step, setStep] = useState(1);
  const navigate = useNavigate();
  const [tenderId, setTenderId] = useState(null);
  const [tenderForm, setTenderForm] = useState({ id: "", title: "", client: "", location: "" });
  const [files, setFiles] = useState([]);
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [globalError, setGlobalError] = useState(null);

  useEffect(() => { window.scrollTo(0, 0); }, [step]);

  return (
    <div className="min-h-screen bg-[#f6f4ee]">
      <TopBar />
      <main className="mx-auto max-w-[1200px] px-4 pb-14 pt-6 sm:px-6">
        <Stepper step={step} />
        {step === 1 && <UploadStep tenderId={tenderId} setTenderId={setTenderId} tenderForm={tenderForm} setTenderForm={setTenderForm} files={files} setFiles={setFiles} uploadedDocs={uploadedDocs} setUploadedDocs={setUploadedDocs} onNext={() => setStep(2)} globalError={globalError} setGlobalError={setGlobalError} />}
        {step === 2 && <ReviewStep tenderId={tenderId} uploadedDocs={uploadedDocs} onNext={() => setStep(3)} onBack={() => setStep(1)} />}
        {step === 3 && <AnalyzeStep tenderId={tenderId} jobId={jobId} setJobId={setJobId} onNext={() => setStep(4)} />}
        {step === 4 && <ResultsStep tenderId={tenderId} analysis={analysis} setAnalysis={setAnalysis} onNext={() => setStep(5)} />}
        {step === 5 && <FitStep analysis={analysis} onNext={() => setStep(6)} />}
        {step === 6 && <GapsStep analysis={analysis} onNext={() => setStep(7)} onBack={() => setStep(5)} />}
        {step === 7 && <CreateStep tenderId={tenderId} analysis={analysis} onBack={() => setStep(4)} onDone={() => navigate(`/tenders/${encodeURIComponent(tenderId)}`)} />}
      </main>
    </div>
  );
}

export default NewTender;
