import {
  FolderOpen,
  Stamp,
  MessageSquare,
  AlertTriangle,
  CheckSquare,
} from "lucide-react";

const stats = [
  {
    icon: FolderOpen,
    label: "Active Tenders",
    value: "14",
    note: "+3 this month",
    iconBg: "bg-[#eef2f8]",
    iconColor: "text-[#162A4C]",
  },
  {
    icon: Stamp,
    label: "Awaiting Approval",
    value: "4",
    note: "2 urgent",
    iconBg: "bg-[#f7efdf]",
    iconColor: "text-[#a98238]",
  },
  {
    icon: MessageSquare,
    label: "Q&A Deadlines",
    value: "6",
    note: "2 this week",
    iconBg: "bg-[#eef2f8]",
    iconColor: "text-[#162A4C]",
  },
  {
    icon: AlertTriangle,
    label: "High Risk",
    value: "3",
    note: "needs review",
    iconBg: "bg-[#fae8e8]",
    iconColor: "text-[#df6b6b]",
  },
  {
    icon: CheckSquare,
    label: "Tasks Due Today",
    value: "11",
    note: "4 overdue",
    iconBg: "bg-[#e4f1eb]",
    iconColor: "text-[#3c8b68]",
  },
];

const tenders = [
  {
    tender: "Riyadh Smart Infrastructure",
    client: "MOMRA",
    match: "86%",
    recommendation: "Conditional Go",
    recommendationType: "conditional",
    risk: "Medium",
    deadline: "18d",
    approval: "Finance Review",
    owner: "Khalid",
  },
  {
    tender: "NEOM Staff Housing Ph.2",
    client: "NEOM Co.",
    match: "74%",
    recommendation: "Go",
    recommendationType: "go",
    risk: "Low",
    deadline: "32d",
    approval: "Technical",
    owner: "Sara",
  },
  {
    tender: "Jeddah Hospital HVAC",
    client: "MOH",
    match: "61%",
    recommendation: "Conditional Go",
    recommendationType: "conditional",
    risk: "High",
    deadline: "9d",
    approval: "CEO",
    owner: "Omar",
  },
  {
    tender: "Dammam Port CCTV",
    client: "Ports Authority",
    match: "58%",
    recommendation: "No-Go",
    recommendationType: "no-go",
    risk: "High",
    deadline: "24d",
    approval: "Closed",
    owner: "Lina",
  },
  {
    tender: "KAUST Lab Fit-out",
    client: "KAUST",
    match: "91%",
    recommendation: "Go",
    recommendationType: "go",
    risk: "Low",
    deadline: "41d",
    approval: "Draft",
    owner: "Khalid",
  },
];

function RecommendationBadge({ type, children }) {
  const styles = {
    go: "bg-[#e5f2eb] text-[#3c8b68]",
    conditional: "bg-[#f8edcf] text-[#a98238]",
    "no-go": "bg-[#f9dfdf] text-[#d56565]",
  };

  return (
    <span
      className={`inline-flex rounded-full px-3 py-1.5 text-[13px] font-semibold whitespace-nowrap ${
        styles[type]
      }`}
    >
      {children}
    </span>
  );
}

function Dashboard() {
  return (
    <main className="min-h-screen bg-[#f8f7f3] p-4 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-[1450px]">

        {/* ================= Stats ================= */}
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 lg:gap-5 xl:grid-cols-5">
          {stats.map(
            ({ icon: Icon, label, value, note, iconBg, iconColor }) => (
              <div
                key={label}
                className="min-h-[150px] rounded-2xl border border-[#e5e1d9] bg-white p-5"
              >
                <div className="flex items-start justify-between gap-2">
                  <div
                    className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${iconBg}`}
                  >
                    <Icon
                      size={22}
                      strokeWidth={1.8}
                      className={iconColor}
                    />
                  </div>

                  <span className="pt-1 text-right text-[13px] font-medium text-[#46618c]">
                    {note}
                  </span>
                </div>

                <div className="mt-4">
                  <p className="text-[32px] font-bold leading-none text-[#102b50]">
                    {value}
                  </p>

                  <p className="mt-2 text-[14px] text-[#566b8e]">
                    {label}
                  </p>
                </div>
              </div>
            )
          )}
        </section>

        {/* ================= Table ================= */}
        <section className="mt-5 overflow-hidden rounded-2xl border border-[#e5e1d9] bg-white">

          {/* Desktop / Tablet table */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[900px] border-collapse">
              <thead>
                <tr className="border-b border-[#e8e4dc] bg-[#faf9f6]">
                  <th className="px-5 py-4 text-left text-[13px] font-semibold text-[#657594]">
                    Tender
                  </th>

                  <th className="px-5 py-4 text-left text-[13px] font-semibold text-[#657594]">
                    Client
                  </th>

                  <th className="px-5 py-4 text-left text-[13px] font-semibold text-[#657594]">
                    Match
                  </th>

                  <th className="px-5 py-4 text-left text-[13px] font-semibold text-[#657594]">
                    Recommendation
                  </th>

                  <th className="px-5 py-4 text-left text-[13px] font-semibold text-[#657594]">
                    Risk
                  </th>

                  <th className="px-5 py-4 text-left text-[13px] font-semibold text-[#657594]">
                    Deadline
                  </th>

                  <th className="px-5 py-4 text-left text-[13px] font-semibold text-[#657594]">
                    Approval
                  </th>

                  <th className="px-5 py-4 text-left text-[13px] font-semibold text-[#657594]">
                    Owner
                  </th>
                </tr>
              </thead>

              <tbody>
                {tenders.map((item) => (
                  <tr
                    key={item.tender}
                    className="border-b border-[#eeeae3] last:border-b-0 hover:bg-[#faf9f6]"
                  >
                    <td className="px-5 py-4 text-[15px] font-bold text-[#102b50]">
                      {item.tender}
                    </td>

                    <td className="px-5 py-4 text-[14px] text-[#647494]">
                      {item.client}
                    </td>

                    <td className="px-5 py-4 text-[15px] font-bold text-[#102b50]">
                      {item.match}
                    </td>

                    <td className="px-5 py-4">
                      <RecommendationBadge type={item.recommendationType}>
                        {item.recommendation}
                      </RecommendationBadge>
                    </td>

                    <td
                      className={`px-5 py-4 text-[14px] ${
                        item.risk === "High"
                          ? "text-[#c65d5d]"
                          : "text-[#647494]"
                      }`}
                    >
                      {item.risk}
                    </td>

                    <td className="px-5 py-4 text-[15px] font-bold text-[#102b50]">
                      {item.deadline}
                    </td>

                    <td className="px-5 py-4 text-[14px] text-[#647494]">
                      {item.approval}
                    </td>

                    <td className="px-5 py-4 text-[14px] text-[#647494]">
                      {item.owner}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="divide-y divide-[#eeeae3] md:hidden">
            {tenders.map((item) => (
              <div key={item.tender} className="p-5">

                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-[16px] font-bold leading-snug text-[#102b50]">
                      {item.tender}
                    </h3>

                    <p className="mt-1 text-[14px] text-[#647494]">
                      {item.client}
                    </p>
                  </div>

                  <span className="shrink-0 text-[16px] font-bold text-[#102b50]">
                    {item.match}
                  </span>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <RecommendationBadge type={item.recommendationType}>
                    {item.recommendation}
                  </RecommendationBadge>

                  <span className="text-[14px] text-[#647494]">
                    Risk: {item.risk}
                  </span>

                  <span className="text-[14px] font-bold text-[#102b50]">
                    {item.deadline}
                  </span>
                </div>

                <div className="mt-3 flex justify-between text-[14px] text-[#647494]">
                  <span>{item.approval}</span>
                  <span>{item.owner}</span>
                </div>

              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

export default Dashboard;
