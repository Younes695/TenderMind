import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  UploadCloud,
  FileText,
  FileSpreadsheet,
  FileArchive,
  ShieldCheck,
  Lock,
  Check,
  CheckCircle2,
  AlertTriangle,
  Info,
  Download,
} from "lucide-react";
import logo from "../assets/logo.jpg";

const STEPS = ["Upload", "Review", "Analyze", "Results", "Fit", "Gaps", "Create"];

/* ================= Top bar — site logo & name ================= */

function TopBar() {
  return (
    <header className="bg-[#162A4C]">
      <div className="mx-auto flex max-w-[1200px] items-center justify-between gap-3 px-4 py-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <img
            src={logo}
            alt="TenderMind logo"
            className="h-9 w-9 shrink-0 rounded-lg object-cover"
          />
          <span className="text-[19px] font-black tracking-wide text-white">
            TENDER<span className="text-[#C8A96B]">MIND</span>
          </span>
          <span className="hidden truncate rounded-lg bg-white/10 px-3 py-1.5 text-[13px] text-[#c5d0e6] md:block">
            First tender setup • Al Yamamah Co.
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

/* ================= Stepper ================= */

function Stepper({ step }) {
  return (
    <div>
      {/* Mobile: current step only */}
      <div className="md:hidden">
        <p className="text-[14px] font-bold text-[#162A4C]">
          Step {step} of 7: {STEPS[step - 1]}
        </p>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#e8e2d4]">
          <div
            className="h-full rounded-full bg-[#2E7D5B] transition-all"
            style={{ width: `${(step / 7) * 100}%` }}
          />
        </div>
      </div>

      {/* Desktop: full stepper */}
      <ol className="hidden items-center gap-2 md:flex lg:gap-3">
        {STEPS.map((label, i) => {
          const n = i + 1;
          const done = n < step;
          const current = n === step;
          return (
            <li key={label} className="flex min-w-0 flex-1 items-center gap-2">
              <span
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[15px] font-bold ${
                  done
                    ? "bg-[#2E7D5B] text-white"
                    : current
                      ? "bg-[#162A4C] text-white"
                      : "border border-[#ddd5c2] bg-white text-[#8a8fa0]"
                }`}
              >
                {done ? <Check size={17} strokeWidth={3} /> : n}
              </span>
              <span
                className={`truncate text-[15px] ${
                  current ? "font-bold text-[#162A4C]" : "text-[#6b7280]"
                }`}
              >
                {label}
              </span>
              {n < 7 && (
                <span
                  className={`mx-1 h-[2px] min-w-4 flex-1 rounded ${
                    n < step ? "bg-[#2E7D5B]" : "bg-[#e3ddd0]"
                  }`}
                />
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/* ================= Shared bits ================= */

function PageTitle({ title, subtitle }) {
  return (
    <div className="mt-6">
      <h1 className="text-[28px] font-black leading-tight text-[#101828] sm:text-[33px]">
        {title}
      </h1>
      <p className="mt-2 max-w-[720px] text-[15px] leading-relaxed text-[#667085] sm:text-[16px]">
        {subtitle}
      </p>
    </div>
  );
}

function PrimaryButton({ children, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-[52px] items-center justify-center rounded-xl bg-[#162A4C] px-7 text-[15px] font-bold whitespace-nowrap text-white transition-colors hover:bg-[#0F1D38] sm:text-[16px]"
    >
      {children}
    </button>
  );
}

function GhostButton({ children, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-[52px] items-center justify-center rounded-xl border border-[#e2e6ee] bg-white px-7 text-[15px] font-bold whitespace-nowrap text-[#101828] transition-colors hover:bg-[#f5f6f9] sm:text-[16px]"
    >
      {children}
    </button>
  );
}

/* ================= Step 1: Upload ================= */

const initialFiles = [
  { name: "RFP_Main_Document.pdf", size: "24.6 MB", status: "Uploaded", kind: "pdf" },
  { name: "BOQ.xlsx", size: "3.1 MB", status: "Uploaded", kind: "xlsx" },
  { name: "Technical_Specifications.pdf", size: "41.2 MB", status: "Processing", kind: "pdf" },
  { name: "Drawings.zip", size: "68.9 MB", status: "Uploading... 72%", kind: "zip" },
];

function FileIcon({ kind }) {
  const cls = "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-[#e8e4dc] bg-[#faf9f6] text-[#162A4C]";
  if (kind === "xlsx") return <span className={cls}><FileSpreadsheet size={22} /></span>;
  if (kind === "zip") return <span className={cls}><FileArchive size={22} /></span>;
  return <span className={cls}><FileText size={22} /></span>;
}

function StatusBadge({ status }) {
  if (status === "Uploaded")
    return <span className="rounded-lg bg-[#e5f2eb] px-3 py-1.5 text-[13px] font-bold text-[#2E7D5B]">Uploaded</span>;
  if (status === "Processing")
    return <span className="rounded-lg bg-[#f8edcf] px-3 py-1.5 text-[13px] font-bold text-[#a98238]">Processing</span>;
  return <span className="rounded-lg bg-[#f3eee2] px-3 py-1.5 text-[13px] font-bold text-[#162A4C]">{status}</span>;
}

function UploadStep({ onNext }) {
  const [files, setFiles] = useState(initialFiles);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const addFiles = (list) => {
    const added = Array.from(list).map((f) => ({
      name: f.name,
      size: `${(f.size / 1024 / 1024).toFixed(1)} MB`,
      status: "Uploaded",
      kind: /\.xlsx?$/i.test(f.name) ? "xlsx" : /\.zip$/i.test(f.name) ? "zip" : "pdf",
    }));
    if (added.length) setFiles((prev) => [...prev, ...added]);
  };

  return (
    <div>
      <PageTitle
        title="Start a New Tender"
        subtitle="Upload the RFP and TenderMind will organize the requirements, deadlines, risks and evaluation criteria for you."
      />

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-5">
        {/* Dropzone */}
        <div>
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files); }}
            className={`flex min-h-[420px] flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
              dragOver ? "border-[#162A4C] bg-[#eef2f8]" : "border-[#cbbd93] bg-white/60"
            }`}
          >
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#162A4C] text-white">
              <UploadCloud size={30} />
            </span>
            <p className="mt-5 text-[19px] font-bold text-[#101828] sm:text-[21px]">
              Drag & Drop your tender files here
            </p>
            <p className="mt-1 text-[15px] text-[#667085]">or</p>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="mt-4 flex h-[52px] items-center rounded-xl bg-[#162A4C] px-8 text-[16px] font-bold text-white transition-colors hover:bg-[#0F1D38]"
            >
              Browse Files
            </button>
            <input
              ref={inputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => addFiles(e.target.files)}
            />
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {["PDF", "Word", "Excel", "ZIP"].map((t) => (
                <span key={t} className="rounded-lg border border-[#e3ddd0] bg-[#faf9f6] px-3 py-1.5 text-[14px] font-bold text-[#101828]">
                  {t}
                </span>
              ))}
            </div>
            <p className="mt-4 text-[14px] text-[#667085]">
              Maximum file size: 100 MB • Multiple files allowed
            </p>
          </div>

          <div className="mt-4 flex items-center gap-2.5 rounded-xl border border-[#e8e4dc] bg-white p-4">
            <ShieldCheck size={20} className="shrink-0 text-[#162A4C]" />
            <p className="text-[14px] text-[#667085] sm:text-[15px]">
              Your tender documents are handled as confidential business information.
            </p>
          </div>
        </div>

        {/* Files card */}
        <div className="h-fit rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <p className="text-[16px] font-bold text-[#101828]">Files • {files.length}</p>
            <p className="text-[14px] text-[#667085]">186 pages total</p>
          </div>

          <div className="mt-4 divide-y divide-[#eeeae3]">
            {files.map((f) => (
              <div key={f.name} className="flex items-center gap-3 py-3.5">
                <FileIcon kind={f.kind} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-bold text-[#101828]">{f.name}</p>
                  <p className="mt-0.5 text-[14px] text-[#667085]">{f.size}</p>
                </div>
                <StatusBadge status={f.status} />
              </div>
            ))}
          </div>

          <div className="mt-4">
            <PrimaryButton onClick={onNext}>
              <span className="w-full">Continue Analysis</span>
            </PrimaryButton>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ================= Step 2: Review ================= */

const initialFields = [
  { label: "Tender Name", value: "Riyadh Smart Infrastructure Project", extracted: true },
  { label: "Client", value: "Example Client", extracted: true },
  { label: "Tender ID", value: "RUH-2026-184", extracted: false },
  { label: "Estimated Contract Value", value: "SAR 12.5M", extracted: true },
  { label: "Submission Deadline", value: "18 October 2026", extracted: false },
  { label: "Q&A Deadline", value: "02 October 2026", extracted: false },
  { label: "Project Duration", value: "24 Months", extracted: true },
  { label: "Location", value: "Riyadh, Saudi Arabia", extracted: true },
];

function ReviewStep({ onNext, onBack }) {
  const [fields, setFields] = useState(initialFields);
  const [editing, setEditing] = useState(null);

  return (
    <div>
      <PageTitle
        title="Review Tender Information"
        subtitle="Verify the details extracted from your documents. Every field is editable."
      />

      <div className="mt-6 rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-8">
        <div className="grid grid-cols-1 gap-x-6 gap-y-5 md:grid-cols-2">
          {fields.map((f, i) => (
            <div key={f.label}>
              <p className="flex flex-wrap items-center gap-2 text-[15px] text-[#667085]">
                {f.label}
                {f.extracted && (
                  <span className="rounded-md bg-[#efe9d6] px-2 py-0.5 text-[12px] font-bold tracking-wide text-[#5c5340]">
                    AI EXTRACTED
                  </span>
                )}
              </p>
              <div className="mt-2 flex items-center gap-2 rounded-xl border border-[#e8e4dc] bg-[#faf8f2] px-4">
                {editing === i ? (
                  <input
                    autoFocus
                    value={f.value}
                    onChange={(e) =>
                      setFields((prev) => prev.map((x, xi) => (xi === i ? { ...x, value: e.target.value } : x)))
                    }
                    onBlur={() => setEditing(null)}
                    onKeyDown={(e) => e.key === "Enter" && setEditing(null)}
                    className="h-[56px] w-full bg-transparent text-[15px] font-medium text-[#101828] outline-none sm:text-[16px]"
                  />
                ) : (
                  <p className="flex h-[56px] w-full items-center truncate text-[15px] font-medium text-[#101828] sm:text-[16px]">
                    {f.value}
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => setEditing(editing === i ? null : i)}
                  className="shrink-0 border-b border-[#d8d2c2] text-[15px] font-bold text-[#162A4C]"
                >
                  Edit
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-7 flex flex-col gap-4 border-t border-[#eeeae3] pt-5 lg:flex-row lg:items-center lg:justify-between">
          <p className="flex items-center gap-2 text-[14px] text-[#667085] sm:text-[15px]">
            <Info size={18} className="shrink-0" />
            Sources linked to RFP pages — hover any field to see evidence.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <GhostButton onClick={onBack}>Back</GhostButton>
            <PrimaryButton onClick={onNext}>Continue Analysis</PrimaryButton>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ================= Step 3: Analyze ================= */

const analyzeItems = [
  "Documents uploaded",
  "Document structure identified",
  "Requirements extracted",
  "Deadlines identified",
  "Evaluation criteria being analyzed",
  "Financial conditions",
  "Risk conditions",
  "Company fit",
];

function AnalyzeStep({ onNext }) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setProgress((p) => {
        if (p >= 100) {
          clearInterval(id);
          return 100;
        }
        return p + 2;
      });
    }, 110);
    return () => clearInterval(id);
  }, []);

  const doneCount = Math.min(8, Math.floor((progress / 100) * 8));

  return (
    <div>
      <PageTitle
        title="TenderMind is understanding your tender"
        subtitle="Structuring requirements, deadlines, financial and risk conditions from your documents."
      />

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-5">
        <div className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-8">
          <div className="flex items-center justify-between">
            <p className="text-[16px] font-bold text-[#101828]">Analyzing documents</p>
            <p className="text-[16px] font-bold text-[#162A4C]">{Math.round(progress)}%</p>
          </div>
          <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-[#efe9dc]">
            <div
              className="h-full rounded-full bg-[#162A4C] transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>

          <ul className="mt-6 divide-y divide-[#eeeae3]">
            {analyzeItems.map((label, i) => {
              const done = i < doneCount;
              const active = i === doneCount && progress < 100;
              return (
                <li key={label} className="flex items-center gap-3 py-3.5">
                  {done ? (
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#2E7D5B] text-white">
                      <Check size={15} strokeWidth={3} />
                    </span>
                  ) : active ? (
                    <span className="h-7 w-7 rounded-full border-[2.5px] border-[#162A4C]" />
                  ) : (
                    <span className="h-7 w-7 rounded-full border border-[#ddd5c2]" />
                  )}
                  <span className={`text-[15px] sm:text-[16px] ${done || active ? "font-bold text-[#101828]" : "text-[#98a2b3]"}`}>
                    {label}
                  </span>
                </li>
              );
            })}
          </ul>

          {progress >= 100 && (
            <div className="mt-5">
              <PrimaryButton onClick={onNext}>
                <span className="w-full">Continue to Results</span>
              </PrimaryButton>
            </div>
          )}
        </div>

        <div>
          <div className="rounded-2xl bg-[#162A4C] p-6 sm:p-8">
            <div className="grid grid-cols-3 gap-2 text-center">
              {[
                ["186", "pages"],
                ["4", "documents"],
                ["2,341", "data points"],
              ].map(([v, l]) => (
                <div key={l}>
                  <p className="text-[26px] font-black text-[#C8A96B] sm:text-[30px]">{v}</p>
                  <p className="mt-1 text-[13px] text-[#c5d0e6] sm:text-[14px]">{l}</p>
                </div>
              ))}
            </div>
            <p className="mt-6 border-t border-white/10 pt-5 text-[14px] leading-relaxed text-[#e6ebf5] sm:text-[15px]">
              Enterprise extraction — every data point is traced to its source page and section. No guessing.
            </p>
          </div>
          <div className="mt-4 flex items-center gap-2.5 rounded-xl border border-[#e8e4dc] bg-white p-4">
            <Lock size={18} className="shrink-0 text-[#667085]" />
            <p className="text-[14px] text-[#667085] sm:text-[15px]">
              Documents remain confidential throughout processing.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ================= Step 4: Results ================= */

function ResultsStep({ onNext }) {
  const stats = [
    ["47", "Requirements"],
    ["8", "Critical Req."],
    ["4", "Deadlines"],
    ["7", "Risk Flags"],
    ["5", "Eval. Criteria"],
    ["3", "Missing Info"],
  ];
  const findings = [
    { level: "HIGH", text: "Payment terms: 90 days after certification", src: "Page 47 · Section 8.2" },
    { level: "HIGH", text: "Performance Bond: 10% — SAR 1.25M locked", src: "Page 52 · Section 9.1" },
    { level: "MEDIUM", text: "Liquidated Damages: 0.5% per week, capped 10%", src: "Page 60 · Section 11.4" },
  ];

  return (
    <div>
      <PageTitle
        title="Tender Analysis Complete"
        subtitle="All findings are traced to the source document — page and section included."
      />

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6 lg:gap-4">
        {stats.map(([v, l]) => (
          <div key={l} className="rounded-2xl border border-[#e8e4dc] bg-white p-5 text-center">
            <p className="text-[28px] font-black text-[#162A4C] sm:text-[32px]">{v}</p>
            <p className="mt-1 text-[13px] text-[#667085] sm:text-[14px]">{l}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-7">
        <p className="text-[17px] font-bold text-[#101828] sm:text-[18px]">Critical Findings</p>
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          {findings.map((f) => (
            <div key={f.text} className="rounded-xl border border-[#e8e4dc] bg-[#faf8f2] p-5">
              <span className={`inline-block rounded-md px-2.5 py-1 text-[12px] font-bold tracking-wide ${
                f.level === "HIGH" ? "bg-[#f9e3e3] text-[#b44444]" : "bg-[#f8edcf] text-[#a98238]"
              }`}>
                {f.level}
              </span>
              <p className="mt-3 text-[15px] font-bold leading-snug text-[#101828] sm:text-[16px]">{f.text}</p>
              <p className="mt-2 text-[14px] text-[#667085]">
                <span className="font-bold">Source:</span> {f.src}
              </p>
            </div>
          ))}
        </div>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            className="flex h-[52px] items-center justify-center gap-2 rounded-xl border border-[#e2e6ee] bg-white px-7 text-[15px] font-bold text-[#101828] transition-colors hover:bg-[#f5f6f9] sm:text-[16px]"
          >
            <Download size={18} /> Download Report
          </button>
          <PrimaryButton onClick={onNext}>Check Company Fit</PrimaryButton>
        </div>
      </div>
    </div>
  );
}

/* ================= Step 5: Fit ================= */

function FitStep({ onNext }) {
  const bars = [
    ["Technical Fit", 92, "8 similar projects · SAR 96M delivered"],
    ["Financial Fit", 68, "90-day terms exceed 60-day policy"],
    ["Risk", 74, "Bond + retention lock SAR 2.5M"],
    ["Evaluation Fit", 88, "Strong on Approach + Experience"],
    ["Capacity", 80, "2 crews free · Riyadh hub available"],
  ];

  return (
    <div>
      <PageTitle
        title="How does this tender fit your company?"
        subtitle="Compared against Al Yamamah Co. knowledge base, policies and capacity."
      />

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-5">
        <div className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-8">
          <div className="space-y-6">
            {bars.map(([label, value, note]) => (
              <div key={label}>
                <div className="flex items-center justify-between">
                  <p className="text-[15px] font-bold text-[#101828] sm:text-[16px]">{label}</p>
                  <p className="text-[15px] font-bold text-[#162A4C] sm:text-[16px]">{value}%</p>
                </div>
                <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-[#efe9dc]">
                  <div className="h-full rounded-full bg-[#162A4C]" style={{ width: `${value}%` }} />
                </div>
                <p className="mt-1.5 text-[14px] text-[#667085]">{note}</p>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="rounded-2xl bg-[#162A4C] p-6 text-center sm:p-8">
            <p className="text-[13px] font-bold tracking-[0.18em] text-[#C8A96B]">AI RECOMMENDATION</p>
            <p className="mt-2 text-[26px] font-black text-white sm:text-[29px]">CONDITIONAL GO</p>
            <p className="mt-2">
              <span className="text-[52px] font-black leading-none text-white">82</span>
              <span className="text-[19px] font-bold text-white/40"> / 100</span>
            </p>
            <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-white/15">
              <div className="h-full w-[82%] rounded-full bg-[#C8A96B]" />
            </div>
            <button
              type="button"
              onClick={onNext}
              className="mt-5 flex h-[52px] w-full items-center justify-center rounded-xl bg-[#C8A96B] text-[16px] font-bold text-[#162A4C] transition-colors hover:bg-[#b8965a]"
            >
              Review Gaps
            </button>
          </div>
          <div className="mt-4 flex items-start gap-2.5 rounded-xl border border-[#e6d3a3] bg-[#fdf4de] p-4">
            <AlertTriangle size={20} className="mt-0.5 shrink-0 text-[#101828]" />
            <p className="text-[14px] leading-relaxed text-[#101828] sm:text-[15px]">
              This is an AI recommendation. Human approval is required before a Go / No-Go decision.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ================= Step 6: Gaps ================= */

function GapsStep({ onNext, onBack }) {
  const rows = [
    ["ISO 9001", "SATISFIED", "Cert. #QA-2210 valid to 2027", "Page 22"],
    ["Similar project experience", "SATISFIED", "Project Alpha · SAR 12M", "Page 31"],
    ["Required technical team", "SATISFIED", "14 CVs matched", "Page 33"],
    ["ISO 27001", "MISSING", "No certificate on file", "Page 23"],
    ["Local Saudization cert.", "MISSING", "Expired Mar 2026", "Page 24"],
    ["Min. 5 years experience", "VERIFY", "JV partner proof needed", "Page 30"],
    ["Financial capacity", "VERIFY", "Bank letter pending", "Page 52"],
  ];

  const badge = (s) =>
    s === "SATISFIED"
      ? "bg-[#e5f2eb] text-[#2E7D5B]"
      : s === "MISSING"
        ? "bg-[#f9e3e3] text-[#b44444]"
        : "bg-[#f8edcf] text-[#a98238]";

  return (
    <div>
      <PageTitle
        title="Requirements that need attention"
        subtitle="Each requirement is linked to evidence and its RFP source."
      />

      <div className="mt-6 overflow-hidden rounded-2xl border border-[#e8e4dc] bg-white">
        {/* Desktop table */}
        <div className="hidden overflow-x-auto md:block">
          <table className="w-full min-w-[820px] border-collapse">
            <thead>
              <tr className="bg-[#faf9f6]">
                {["REQUIREMENT", "STATUS", "EVIDENCE", "RFP PAGE", ""].map((h) => (
                  <th key={h} className="px-6 py-4 text-left text-[13px] font-bold tracking-wide text-[#667085]">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(([req, status, ev, page]) => (
                <tr key={req} className="border-t border-[#eeeae3]">
                  <td className="px-6 py-4 text-[15px] font-bold text-[#101828]">{req}</td>
                  <td className="px-6 py-4">
                    <span className={`rounded-lg px-3 py-1.5 text-[12px] font-bold tracking-wide ${badge(status)}`}>
                      {status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-[14px] text-[#667085]">{ev}</td>
                  <td className="px-6 py-4 text-[15px] text-[#101828]">{page}</td>
                  <td className="px-6 py-4 text-right">
                    <button type="button" className="border-b border-[#d8d2c2] text-[15px] font-bold text-[#162A4C]">
                      Fix
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile cards */}
        <div className="divide-y divide-[#eeeae3] md:hidden">
          {rows.map(([req, status, ev, page]) => (
            <div key={req} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <p className="text-[15px] font-bold text-[#101828]">{req}</p>
                <span className={`shrink-0 rounded-lg px-2.5 py-1 text-[12px] font-bold ${badge(status)}`}>
                  {status}
                </span>
              </div>
              <p className="mt-2 text-[14px] text-[#667085]">{ev} • {page}</p>
              <button type="button" className="mt-2 border-b border-[#d8d2c2] text-[14px] font-bold text-[#162A4C]">
                Fix
              </button>
            </div>
          ))}
        </div>

        <div className="flex flex-col gap-3 border-t border-[#eeeae3] p-5 sm:flex-row sm:justify-end">
          <GhostButton onClick={onBack}>Back</GhostButton>
          <PrimaryButton onClick={onNext}>Create Workspace Plan</PrimaryButton>
        </div>
      </div>
    </div>
  );
}

/* ================= Step 7: Create ================= */

function CreateStep({ onBack, onDone }) {
  const items = [
    "Tender overview",
    "Go / No-Go assessment",
    "Financial analysis",
    "Risk register",
    "Evaluation criteria",
    "Work packages",
    "Q&A tracker",
    "Approval workflow",
    "Submission checklist",
    "Document library",
  ];

  return (
    <div>
      <PageTitle
        title="Ready to create your Tender Workspace"
        subtitle="TenderMind will assemble everything your team needs to go from RFP to ready-to-bid."
      />

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-5">
        <div className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-8">
          <p className="text-[16px] font-bold text-[#101828]">TenderMind will create</p>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {items.map((t) => (
              <div key={t} className="flex items-center gap-3 rounded-xl border border-[#e8e4dc] bg-[#faf8f2] p-4">
                <span className="h-8 w-8 shrink-0 rounded-lg bg-[#e5f2eb]" />
                <p className="text-[14px] font-medium text-[#101828] sm:text-[15px]">{t}</p>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="rounded-2xl bg-[#162A4C] p-6 sm:p-8">
            <p className="text-[17px] font-black text-white">RUH-2026-184</p>
            <p className="mt-1 text-[14px] text-[#c5d0e6] sm:text-[15px]">
              Riyadh Smart Infrastructure · SAR 12.5M
            </p>
            <div className="mt-5 grid grid-cols-3 gap-2 text-center">
              {[
                ["82", "CONDITIONAL GO"],
                ["64%", "READINESS"],
                ["left", "18 DAYS"],
              ].map(([v, l]) => (
                <div key={l} className="rounded-xl bg-white/10 p-3">
                  <p className="text-[17px] font-black text-[#C8A96B]">{v}</p>
                  <p className="mt-1 text-[10px] font-medium tracking-wide text-[#c5d0e6] sm:text-[11px]">{l}</p>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={onDone}
              className="mt-5 flex h-[54px] w-full items-center justify-center rounded-xl bg-[#C8A96B] text-[16px] font-bold text-[#162A4C] transition-colors hover:bg-[#b8965a]"
            >
              Create Tender Workspace
            </button>
            <button
              type="button"
              onClick={onBack}
              className="mt-3 w-full text-center text-[14px] font-medium text-[#c5d0e6] underline underline-offset-4 sm:text-[15px]"
            >
              Review Analysis
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ================= Wizard container ================= */

function NewTender() {
  const [step, setStep] = useState(1);
  const navigate = useNavigate();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [step ]);

  return (
    <div className="min-h-screen bg-[#f6f4ee]">
      <TopBar />
      <main className="mx-auto max-w-[1200px] px-4 pb-14 pt-6 sm:px-6">
        <Stepper step={step} />

        {step === 1 && <UploadStep onNext={() => setStep(2)} />}
        {step === 2 && <ReviewStep onNext={() => setStep(3)} onBack={() => setStep(1)} />}
        {step === 3 && <AnalyzeStep onNext={() => setStep(4)} />}
        {step === 4 && <ResultsStep onNext={() => setStep(5)} />}
        {step === 5 && <FitStep onNext={() => setStep(6)} />}
        {step === 6 && <GapsStep onNext={() => setStep(7)} onBack={() => setStep(5)} />}
        {step === 7 && (
          <CreateStep onBack={() => setStep(4)} onDone={() => navigate("/tenders/RUH-2026-184")} />
        )}
      </main>
    </div>
  );
}

export default NewTender;
