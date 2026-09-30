import { useEffect, useState } from "react";
import { Boxes, Upload, Trash2, Layers, AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";
import apiClient from "../api/client";
import { useT } from "../i18n";

/** Materials & prices: the account's supplier price lists (the only price source) and the same
 *  material across active tenders — total quantity, today's listed price and a bulk scenario only
 *  when a list itself quotes a lower price for the larger quantity. */

const num = (v, d = 0) => (v == null ? "—" : Number(v).toLocaleString("en-US", { maximumFractionDigits: d }));
const money = (v, c) => (v == null ? "—" : `${c} ${num(v, 2)}`);
const card = "rounded-2xl border border-[#e8e4dc] bg-white p-5";

function PriceTag({ price }) {
  const t = useT();
  if (!price) return <span data-testid="price-unavailable" className="rounded-md bg-[#f2f4f7] px-2 py-0.5 text-[11px] font-bold text-[#667085]">{t("PRICE UNAVAILABLE")}</span>;
  return (
    <span className="text-[13px]">
      <b className="text-[#101828]">{money(price.price, price.currency)}</b> / {t(price.unit)}
      <span className="block text-[11px] text-[#667085]">{price.supplier} · {price.price_date}{price.stale ? ` · ${t("older than 90 days")}` : ""}</span>
    </span>
  );
}
export { PriceTag, num, money };

function PriceLists({ lists, reload }) {
  const t = useT();
  const [form, setForm] = useState({ supplier: "", currency: "EGP", price_date: new Date().toISOString().slice(0, 10), file: null });
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const upload = async (e) => {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      const r = await apiClient.uploadPriceList(form);
      setMsg({ ok: true, text: t("{n} prices read, {k} recognised as materials", { n: r.items, k: r.recognised }) });
      setForm({ ...form, file: null });
      e.target.reset();
      reload();
    } catch (err) {
      setMsg({ ok: false, text: t(err.message) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className={card} data-testid="price-lists">
      <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Upload size={17} /> {t("Supplier price lists")}</h2>
      <p className="mt-1 text-[13px] text-[#667085]">{t("Prices come only from lists you upload (Excel or CSV with Description, Unit and Price columns; optional Min Qty for price breaks). Nothing is estimated.")}</p>
      <form onSubmit={upload} className="mt-3 grid gap-2 sm:grid-cols-[1fr_110px_150px_1fr_auto]">
        <input required aria-label={t("Supplier")} placeholder={t("Supplier")} value={form.supplier} onChange={(e) => setForm({ ...form, supplier: e.target.value })} className="rounded-lg border border-[#d0d5dd] px-3 py-2 text-[14px]" />
        <select aria-label={t("Currency")} value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} className="rounded-lg border border-[#d0d5dd] px-3 py-2 text-[14px]">
          {["EGP", "SAR", "AED", "QAR", "KWD", "BHD", "OMR", "USD", "EUR"].map((c) => <option key={c}>{c}</option>)}
        </select>
        <input required type="date" aria-label={t("Price date")} value={form.price_date} onChange={(e) => setForm({ ...form, price_date: e.target.value })} className="rounded-lg border border-[#d0d5dd] px-3 py-2 text-[14px]" />
        <input required type="file" accept=".xlsx,.xlsm,.csv" aria-label={t("Price list file")} onChange={(e) => setForm({ ...form, file: e.target.files[0] })} className="text-[13px]" />
        <button disabled={busy} className="rounded-lg bg-[#162A4C] px-4 py-2 text-[14px] font-semibold text-white disabled:opacity-50">{t("Upload")}</button>
      </form>
      {msg && <p className={`mt-2 text-[13px] ${msg.ok ? "text-[#1f7a4d]" : "text-[#a33a3a]"}`}>{msg.text}</p>}
      {lists.length > 0 && (
        <ul className="mt-3 divide-y divide-[#f0ede6] text-[13px]">
          {lists.map((l) => (
            <li key={l.id} className="flex items-center justify-between gap-3 py-2">
              <span><b className="text-[#101828]">{l.supplier}</b> · {l.currency} · {l.price_date} · {t("{n} items", { n: l.items })} <span className="text-[#98a2b3]">({l.filename})</span></span>
              <button type="button" aria-label={t("Delete")} onClick={async () => { await apiClient.deletePriceList(l.id); reload(); }} className="text-[#a33a3a]"><Trash2 size={15} /></button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Bulk({ data }) {
  const t = useT();
  if (!data) return <p className="text-[14px] text-[#667085]">{t("Loading…")}</p>;
  return (
    <section className={card} data-testid="bulk-opportunities">
      <h2 className="flex items-center gap-2 text-[16px] font-bold text-[#101828]"><Layers size={17} /> {t("Same material across active tenders")}</h2>
      <p className="mt-1 text-[13px] text-[#667085]">{t("{a} active tender(s), {b} with a readable BOQ. Lines are merged only when size, rating, type and unit are identical.", { a: data.active_tenders, b: data.tenders_with_boq })}</p>
      {!data.bulk.length ? <p className="mt-3 text-[13px] text-[#667085]">{t("No material appears in two or more active tenders yet.")}</p> : (
        <div className="mt-3 space-y-3">
          {data.bulk.map((b) => (
            <article key={b.key} data-testid="bulk-row" className="rounded-xl border border-[#eef0f3] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[15px] font-bold text-[#101828]">{b.name}</p>
                  <p className="text-[12px] text-[#667085]">{t("In {n} tenders", { n: b.tenders.length })}: {b.tenders.map((x) => `${x.title || x.tender_id} (${num(x.quantity)} ${t(b.unit)})`).join(" · ")}</p>
                </div>
                <div className="text-end">
                  <p className="text-[12px] text-[#667085]">{t("Total quantity")}</p>
                  <p className="text-[20px] font-black text-[#162A4C]">{num(b.total_quantity)} <span className="text-[13px] font-semibold">{t(b.unit)}</span></p>
                </div>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <div><p className="text-[12px] text-[#667085]">{t("Today's listed price")}</p><PriceTag price={b.price} /></div>
                <div><p className="text-[12px] text-[#667085]">{t("Estimated material cost")} <span className="rounded bg-[#f2f4f7] px-1 text-[10px] font-bold">{t("ESTIMATE")}</span></p>
                  <p className="text-[15px] font-bold text-[#101828]">{b.price ? money(b.estimated_cost, b.price.currency) : "—"}</p></div>
                <div><p className="text-[12px] text-[#667085]">{t("Estimated bulk scenario")}</p>
                  {b.bulk_scenario ? (
                    <p className="text-[13px]"><b className="text-[#1f7a4d]">{money(b.bulk_scenario.estimated_cost, b.price.currency)}</b>
                      <span className="block text-[11px] text-[#667085]">{t("{s} quotes {p} from {q} {u} — difference {d}", { s: b.bulk_scenario.price.supplier, p: money(b.bulk_scenario.price.price, b.price.currency), q: num(b.bulk_scenario.price.min_qty), u: t(b.unit), d: money(b.bulk_scenario.difference, b.price.currency) })}</span></p>
                  ) : <p className="text-[12px] text-[#98a2b3]">{t("No price break in your lists for this quantity.")}</p>}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      {data.review?.length > 0 && (
        <div className="mt-4" data-testid="materials-review">
          <p className="flex items-center gap-1.5 text-[13px] font-bold text-[#8a6a22]"><AlertTriangle size={14} /> {t("Possible matches — requires review")}</p>
          <ul className="mt-1 space-y-1 text-[12px] text-[#475467]">
            {data.review.map((r) => <li key={r.family_key}>{r.lines.map((l) => `${l.description} (${num(l.quantity)} ${t(l.unit)}, ${l.tender_id})`).join(" ↔ ")}</li>)}
          </ul>
        </div>
      )}
    </section>
  );
}

export default function Materials() {
  const t = useT();
  const [lists, setLists] = useState([]);
  const [agg, setAgg] = useState(null);
  const [error, setError] = useState(null);
  const reload = () => {
    apiClient.listPriceLists().then((d) => setLists(d.lists || [])).catch((e) => setError(e.message));
    apiClient.getPortfolioMaterials().then(setAgg).catch((e) => setError(e.message));
  };
  useEffect(reload, []);
  return (
    <div className="mx-auto max-w-[1100px] space-y-4 p-4 sm:p-6 lg:p-8">
      <div>
        <h1 className="flex items-center gap-2 text-[24px] font-black text-[#101828]"><Boxes size={22} /> {t("Materials & prices")}</h1>
        <p className="mt-1 text-[14px] text-[#667085]">{t("BOQ materials across your tenders, priced only from your suppliers' lists. Each tender's own list is in its workspace.")} <Link to="/tenders" className="font-semibold text-[#162A4C] underline">{t("Tenders")}</Link></p>
      </div>
      {error && <div className="rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] p-3 text-[14px] text-[#a33a3a]">{t(error)}</div>}
      <Bulk data={agg} />
      <PriceLists lists={lists} reload={reload} />
    </div>
  );
}
