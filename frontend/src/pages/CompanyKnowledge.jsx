import { useEffect, useRef, useState } from "react";
import { confirmRemoval } from "../utils/confirm";
import { Database, Upload, Trash2, FileText } from "lucide-react";
import apiClient from "../api/client";
import { useT } from "../i18n";

function CompanyKnowledge() {
  const t = useT();
  const [docs, setDocs] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const load = () =>
    apiClient.listCompanyDocuments().then((r) => setDocs(r?.documents || [])).catch((e) => setError(e.message || "Failed to load documents"));

  useEffect(() => { load(); }, []);

  const onUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setBusy(true);
    setError(null);
    try { await apiClient.uploadCompanyDocuments(files); await load(); }
    catch (err) { setError(err.message || t("Upload failed")); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const onDelete = async (doc) => {
    if (!confirmRemoval(doc.title, "document")) return;
    setBusy(true);
    setError(null);
    try { await apiClient.deleteCompanyDocument(doc.id); await load(); }
    catch (err) { setError(err.message || t("Failed to remove document")); }
    finally { setBusy(false); }
  };

  const onDeleteAll = async () => {
    if (!docs?.length || !window.confirm(t("Remove all {count} company documents?", { count: docs.length }))) return;
    setBusy(true);
    setError(null);
    try {
      for (const d of docs) await apiClient.deleteCompanyDocument(d.id);
      await load();
    } catch (err) { setError(err.message || t("Failed to remove documents")); }
    finally { setBusy(false); }
  };

  return (
    <div className="mx-auto max-w-[1100px] p-4 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-[22px] font-black text-[#101828]"><Database size={22} /> {t("Company Knowledge")}</h1>
          <p className="max-w-[640px] text-[14px] text-[#667085]">
            {t("Your company's evidence: profile, experience lists, certificates, financial statements, CVs. Upload once — every tender's")}
            <span className="font-semibold"> {t("Evaluate")}</span> {t("step matches its requirements against these documents.")}
          </p>
        </div>
        <label className={`flex h-[44px] cursor-pointer items-center justify-center gap-2 rounded-xl bg-[#162A4C] px-5 text-[14px] font-bold text-white hover:bg-[#0F1D38] ${busy ? "pointer-events-none opacity-60" : ""}`}>
          <Upload size={18} /> {t("Upload documents")}
          <input ref={fileRef} type="file" multiple className="hidden" onChange={onUpload} accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.md,.csv,.jpg,.jpeg,.png,.bmp,.gif,.tif,.tiff,.webp,.zip,.rar,.7z,.dxf,.bak" data-testid="company-knowledge-upload" />
        </label>
      </div>
      <p className="mt-2 text-[12px] text-[#98a2b3]">{t("PDF, Word, Excel, scanned images, ZIP/RAR archives, TXT • up to 5 GB per file")}</p>

      {error && <div className="mt-4 rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] p-3 text-[14px] text-[#a33a3a]">{error}</div>}
      {!docs && !error && <p className="mt-6 text-[14px] text-[#667085]">{t("Loading documents...")}</p>}
      {docs && docs.length === 0 && (
        <div className="mt-6 rounded-2xl border border-dashed border-[#d0c7b5] bg-white p-8 text-center text-[14px] text-[#667085]">
          {t("No company documents yet. Without them every qualification requirement stays")} <span className="font-semibold">{t("MISSING EVIDENCE")}</span>.
        </div>
      )}

      {docs && docs.length > 0 && (
        <div className="mt-5 rounded-2xl border border-[#e8e4dc] bg-white p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <p className="text-[15px] font-bold text-[#101828]">{t("Documents")} • {docs.length}</p>
            <button type="button" onClick={onDeleteAll} disabled={busy} className="text-[13px] font-semibold text-[#a33a3a] hover:underline disabled:opacity-50">{t("Remove all")}</button>
          </div>
          <div className="mt-3 divide-y divide-[#eeeae3]">
            {docs.map((d) => (
              <div key={d.id} data-testid="company-doc-row" className="flex items-center gap-3 py-3">
                <FileText size={20} className="shrink-0 text-[#162A4C]" />
                <p className="min-w-0 flex-1 truncate text-[14px] font-semibold text-[#101828]">{d.title}</p>
                <span className="rounded-lg bg-[#eef2f8] px-2 py-1 text-[12px] font-bold text-[#162A4C]">{d.document_type}</span>
                <button type="button" aria-label={`Remove ${d.title}`} onClick={() => onDelete(d)} disabled={busy}
                  className="flex h-9 w-9 items-center justify-center rounded-lg text-[#667085] hover:bg-[#fdf0f0] hover:text-[#a33a3a] disabled:opacity-50">
                  <Trash2 size={17} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default CompanyKnowledge;
