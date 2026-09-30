import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import apiClient from "../api/client";
import { useT } from "../i18n";
import { PriceTag, num, money } from "../pages/Materials";

/** The tender's BOQ lines with today's listed price, estimated material cost and the source row. */
export default function TenderMaterials({ tenderId }) {
  const t = useT();
  const [data, setData] = useState(null);
  const [all, setAll] = useState(false);
  useEffect(() => {
    apiClient.getTenderMaterials(tenderId)
      .then((d) => setData({ ...d, lines: d?.lines || [], totals: d?.totals || [] }))
      .catch(() => setData({ lines: [], totals: [] }));
  }, [tenderId]);
  if (!data) return <p className="text-[13px] text-[#667085]">{t("Reading the BOQ…")}</p>;
  if (!data.lines.length) return <p className="text-[13px] text-[#667085]">{t("No BOQ table with quantities found in this tender — INSUFFICIENT DATA.")}</p>;
  const lines = all ? data.lines : data.lines.slice(0, 12);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 text-[13px]">
        {data.totals.map((x) => (
          <span key={x.currency} className="rounded-lg border border-[#cfe6d8] bg-[#f1f8f4] px-3 py-1.5 text-[#1f7a4d]">
            {t("Estimated material cost")}: <b>{money(x.amount, x.currency)}</b> <span className="rounded bg-white px-1 text-[10px] font-bold">{t("ESTIMATE")}</span>
          </span>
        ))}
        <span className="rounded-lg border border-[#e8e4dc] px-3 py-1.5">{t("{p} priced · {u} price unavailable", { p: data.priced, u: data.unavailable })}</span>
        {data.unavailable > 0 && <Link to="/materials" className="px-1 py-1.5 font-semibold text-[#162A4C] underline">{t("Upload a supplier price list")}</Link>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-start text-[13px]" data-testid="boq-table">
          <thead><tr className="text-[12px] text-[#667085]">
            <th className="py-1 text-start">{t("Material")}</th><th className="text-start">{t("Quantity")}</th>
            <th className="text-start">{t("Current price")}</th><th className="text-start">{t("Cost")}</th></tr></thead>
          <tbody>
            {lines.map((l, i) => (
              <tr key={i} className="border-t border-[#f0ede6] align-top">
                <td className="py-1.5 pe-2"><b className="text-[#101828]">{l.key ? l.name : l.description}</b>
                  <span className="block text-[11px] text-[#98a2b3]">{l.document} · {t("p.")} {l.page} · {t("row")} {l.row}{l.key ? "" : ` · ${t("not matched to a material")}`}</span></td>
                <td className="whitespace-nowrap pe-2">{num(l.quantity, 2)} {t(l.unit)}</td>
                <td className="pe-2"><PriceTag price={l.price} /></td>
                <td className="whitespace-nowrap">{l.cost != null ? money(l.cost, l.price.currency) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.lines.length > 12 && <button type="button" onClick={() => setAll(!all)} className="text-[13px] font-semibold text-[#162A4C] underline">{all ? t("Show less") : t("Show all {n} lines", { n: data.lines.length })}</button>}
    </div>
  );
}
