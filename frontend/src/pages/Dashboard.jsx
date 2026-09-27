import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FolderOpen, Stamp, MessageSquare, AlertTriangle, CheckSquare } from "lucide-react";
import apiClient from "../api/client";

function RecommendationBadge({ type, children }) {
  const styles = { go: "bg-[#e5f2eb] text-[#3c8b68]", conditional: "bg-[#f8edcf] text-[#a98238]", "no-go": "bg-[#f9dfdf] text-[#d56565]" };
  const cls = styles[type] || "bg-[#f3f3f3] text-[#667085]";
  return <span className={`inline-flex rounded-full px-3 py-1.5 text-[13px] font-semibold whitespace-nowrap ${cls}`}>{children || "Not available"}</span>;
}

function Dashboard() {
  const [tenders, setTenders] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient.listTenders()
      .then((data) => {
        setTenders(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message || "Failed to load tenders");
        setTenders([]);
        setLoading(false);
      });
  }, []);

  const stats = [
    { icon: FolderOpen, label: "Active Tenders", value: tenders ? String(tenders.length) : "Not available", note: tenders ? `${tenders.length} total` : "Not available", iconBg: "bg-[#eef2f8]", iconColor: "text-[#162A4C]" },
    { icon: Stamp, label: "Awaiting Approval", value: "Not available", note: "Not available", iconBg: "bg-[#f7efdf]", iconColor: "text-[#a98238]" },
    { icon: MessageSquare, label: "Q&A Deadlines", value: "Not available", note: "Not available", iconBg: "bg-[#eef2f8]", iconColor: "text-[#162A4C]" },
    { icon: AlertTriangle, label: "High Risk", value: "Not available", note: "Not available", iconBg: "bg-[#fae8e8]", iconColor: "text-[#df6b6b]" },
    { icon: CheckSquare, label: "Tasks Due Today", value: "Not available", note: "Not available", iconBg: "bg-[#e4f1eb]", iconColor: "text-[#3c8b68]" },
  ];

  if (loading) return <main className="min-h-screen bg-[#f8f7f3] p-8">Loading tenders...</main>;

  return (
    <main className="min-h-screen bg-[#f8f7f3] p-4 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-[1450px]">
        {error && <div data-testid="error-banner" className="mb-4 rounded-xl border border-[#f5c6c6] bg-[#fdf0f0] px-4 py-3 text-[14px] text-[#a33a3a]">{error}</div>}
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 lg:gap-5 xl:grid-cols-5">
          {stats.map(({ icon: Icon, label, value, note, iconBg, iconColor }) => (
            <div key={label} className="min-h-[150px] rounded-2xl border border-[#e5e1d9] bg-white p-5">
              <div className="flex items-start justify-between gap-2">
                <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${iconBg}`}><Icon size={22} strokeWidth={1.8} className={iconColor} /></div>
                <span className="pt-1 text-right text-[13px] font-medium text-[#46618c]">{note}</span>
              </div>
              <div className="mt-4">
                <p data-testid={`stat-${label}`} className="text-[32px] font-bold leading-none text-[#102b50]">{value}</p>
                <p className="mt-2 text-[14px] text-[#566b8e]">{label}</p>
              </div>
            </div>
          ))}
        </section>

        <section className="mt-5 overflow-hidden rounded-2xl border border-[#e5e1d9] bg-white">
          <div className="flex items-center justify-between px-5 py-4 border-b border-[#e8e4dc] bg-[#faf9f6]">
            <h2 className="text-[16px] font-bold text-[#102b50]">Tenders</h2>
            <Link to="/tenders/new" className="rounded-xl bg-[#162A4C] px-4 py-2 text-[14px] font-bold text-white">New Tender</Link>
          </div>

          {tenders && tenders.length === 0 ? (
            <div data-testid="empty-state" className="p-8 text-center text-[15px] text-[#667085]">No tenders yet — create your first tender.</div>
          ) : (
            <>
              <div className="hidden overflow-x-auto md:block">
                <table className="w-full min-w-[900px] border-collapse">
                  <thead>
                    <tr className="border-b border-[#e8e4dc] bg-[#faf9f6]">
                      {["Tender", "Client", "Tender ID", "Location", ""].map((h) => (
                        <th key={h} className="px-5 py-4 text-left text-[13px] font-semibold text-[#657594]">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tenders.map((item) => (
                      <tr key={item.id} className="border-b border-[#eeeae3] last:border-b-0 hover:bg-[#faf9f6]">
                        <td className="px-5 py-4 text-[15px] font-bold text-[#102b50]">
                          <Link to={`/tenders/${encodeURIComponent(item.id)}`} className="hover:underline">{item.title || "Not available"}</Link>
                        </td>
                        <td className="px-5 py-4 text-[14px] text-[#647494]">{item.client || "Not available"}</td>
                        <td className="px-5 py-4 text-[14px] text-[#647494]">{item.id || "Not available"}</td>
                        <td className="px-5 py-4 text-[14px] text-[#647494]">{item.location || "Not available"}</td>
                        <td className="px-5 py-4">
                          <Link to={`/tenders/${encodeURIComponent(item.id)}`} className="text-[13px] font-bold text-[#162A4C] underline">Open</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="divide-y divide-[#eeeae3] md:hidden">
                {tenders.map((item) => (
                  <div key={item.id} className="p-5">
                    <h3 className="text-[16px] font-bold leading-snug text-[#102b50]">{item.title || "Not available"}</h3>
                    <p className="mt-1 text-[14px] text-[#647494]">{item.client || "Not available"} • {item.id}</p>
                    <p className="mt-1 text-[14px] text-[#647494]">{item.location || "Not available"}</p>
                    <Link to={`/tenders/${encodeURIComponent(item.id)}`} className="mt-3 inline-block text-[14px] font-bold text-[#162A4C] underline">Open workspace</Link>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}

export default Dashboard;
