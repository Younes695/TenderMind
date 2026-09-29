import { useEffect, useState } from "react";
import { Download, CheckCircle2 } from "lucide-react";
import apiClient from "../api/client";
import { useT } from "../i18n";

/** RFQ packages: one RFQ per equipment package, the way the tender engineer splits them —
 *  brief, scope pages, design criteria, drawings and data schedules to fill — as a ZIP. */

const FOLDERS = [["scope", "Scope of work"], ["design", "Design criteria"], ["drawings", "Drawings"], ["schedules", "Data schedules to fill"]];
const pages = (parts) => (parts || []).reduce((n, p) => n + p.pages, 0);

export default function RfqPackages({ tenderId }) {
  const t = useT();
  const [data, setData] = useState(null);
  const [picked, setPicked] = useState([]);
  const [closes, setCloses] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    apiClient.getRfqPackages(tenderId)
      .then((d) => { setData(d.packages || []); setPicked((d.packages || []).map((p) => p.key)); })
      .catch(() => setData([]));
  }, [tenderId]);

  if (!data) return <p className="text-[13px] text-[#667085]">{t("Reading the tender pages…")}</p>;
  if (!data.length) return <p className="text-[13px] text-[#667085]">{t("No equipment packages found yet — process the tender first.")}</p>;

  const toggle = (k) => setPicked(picked.includes(k) ? picked.filter((x) => x !== k) : [...picked, k]);
  const register = async () => {
    setBusy(true);
    setMsg("");
    try {
      const r = await apiClient.createRfqPackages(tenderId, { keys: picked, closes_at: closes || undefined });
      setData(r.packages);
      setMsg(t("{n} RFQ(s) added to Subcontractors", { n: r.created }));
    } catch (e) {
      setMsg(e.message || t("Could not save"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-[13px] text-[#667085]">{t("One RFQ per equipment package. Each ZIP folder holds the project brief, the scope pages cut from the tender, design criteria, drawings and the data schedules the supplier fills.")}</p>
      <ul className="divide-y divide-[#f0ede6] rounded-lg border border-[#eef0f3]">
        {data.map((p, i) => (
          <li key={p.key} data-testid={`rfq-package-${p.key}`} className="flex flex-wrap items-start gap-3 px-3 py-2.5">
            <input type="checkbox" className="mt-1" checked={picked.includes(p.key)} onChange={() => toggle(p.key)}
              aria-label={p.name} />
            <div className="min-w-0 flex-1">
              <p className="text-[14px] font-bold text-[#101828]">
                <span className="me-1.5 text-[#98a2b3]">{String(i + 1).padStart(2, "0")}</span>{t(p.label?.key || p.name, p.label?.vars)}
                {p.rfq_id && <span className="ms-2 inline-flex items-center gap-1 text-[12px] font-semibold text-[#1f7a4d]"><CheckCircle2 size={13} /> {t("RFQ added")}</span>}
              </p>
              <p className="mt-0.5 flex flex-wrap gap-x-3 text-[12px] text-[#667085]">
                {FOLDERS.filter(([k]) => pages(p.parts[k])).map(([k, label]) => (
                  <span key={k}>{t(label)}: <b className="text-[#344054]">{pages(p.parts[k])}</b> {t("pages")}</span>
                ))}
              </p>
              {p.specs?.length > 0 && <p className="mt-0.5 truncate text-[11px] text-[#98a2b3]" title={p.specs.join(", ")}>{p.specs.slice(0, 8).join(" · ")}{p.specs.length > 8 ? " …" : ""}</p>}
              {p.suppliers?.length > 0 && <p className="mt-0.5 text-[12px] text-[#344054]">{t("Past suppliers")}: {p.suppliers.map((s) => s.contractor).join("، ")}</p>}
            </div>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-[12px] text-[#667085]">{t("Quotation due")}
          <input type="date" value={closes} onChange={(e) => setCloses(e.target.value)}
            className="mt-1 block rounded-lg border border-[#d0d5dd] px-3 py-1.5 text-[14px]" />
        </label>
        <a data-testid="rfq-zip" href={apiClient.rfqPackagesZipUrl(tenderId, picked, closes)}
          className={`flex items-center gap-1.5 rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white ${picked.length ? "" : "pointer-events-none opacity-50"}`}>
          <Download size={15} /> {t("Download RFQ packages (ZIP)")}</a>
        <button type="button" disabled={busy || !picked.length} onClick={register} data-testid="rfq-register"
          className="rounded-lg border border-[#162A4C] px-4 py-2 text-[14px] font-semibold text-[#162A4C] disabled:opacity-50">
          {t("Add to Subcontractors as RFQs")}</button>
        {msg && <span className="text-[12px] text-[#1f7a4d]">{msg}</span>}
      </div>
    </div>
  );
}
