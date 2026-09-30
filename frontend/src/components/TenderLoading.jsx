import { useT } from "../i18n";

/** Calm loading state for the tender pages: a quiet skeleton shaped like the
 *  page that is coming, and one small mark — a tender page whose lines are
 *  read one after another. Motion stops under prefers-reduced-motion. */

function ReadingMark() {
  return (
    <svg className="tm-read" width="38" height="46" viewBox="0 0 38 46" aria-hidden="true">
      <path d="M6 2h19l11 11v29a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" className="tm-read-page" />
      <path d="M25 2v9a2 2 0 0 0 2 2h9" className="tm-read-fold" />
      {[16, 22, 28, 34].map((y, i) => (
        <line key={y} x1="10" x2={i === 3 ? 22 : 29} y1={y} y2={y} className="tm-read-line" style={{ animationDelay: `${i * 0.45}s` }} />
      ))}
    </svg>
  );
}

const Bar = ({ className = "" }) => <span className={`tm-skel block rounded-md ${className}`} />;

function Caption({ text }) {
  return (
    <div className="flex items-center gap-3">
      <ReadingMark />
      <p className="text-[14px] font-semibold text-[#162A4C]">{text}</p>
    </div>
  );
}

export function TendersListLoading() {
  const t = useT();
  return (
    <div role="status" aria-live="polite" data-testid="tenders-loading" className="mt-6 space-y-4">
      <Caption text={t("Loading tenders...")} />
      <div className="space-y-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex items-center gap-4 rounded-2xl border border-[#e8e4dc] bg-white p-4" style={{ opacity: 1 - i * 0.18 }}>
            <div className="min-w-0 flex-1 space-y-2">
              <Bar className={`h-4 ${["w-2/3", "w-1/2", "w-3/5", "w-2/5"][i]}`} />
              <Bar className="h-3 w-1/3" />
            </div>
            <Bar className="h-7 w-24 rounded-lg" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function WorkspaceLoading() {
  const t = useT();
  return (
    <div role="status" aria-live="polite" data-testid="workspace-loading" className="mx-auto max-w-[1200px] space-y-5 p-4 sm:p-6 lg:p-8">
      <Caption text={t("Loading workspace...")} />
      <section className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
        <Bar className="h-6 w-1/2" />
        <Bar className="mt-3 h-3 w-1/4" />
        <div className="mt-5 grid gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="rounded-xl bg-[#faf9f6] p-3">
              <Bar className="h-3 w-1/2" />
              <Bar className="mt-2 h-4 w-3/4" />
            </div>
          ))}
        </div>
      </section>
      <section className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
        <Bar className="h-4 w-40" />
        <Bar className="mt-4 h-2 w-full rounded-full" />
      </section>
      <section className="rounded-2xl border border-[#e8e4dc] bg-white p-5 sm:p-6">
        <Bar className="h-4 w-48" />
        <div className="mt-4 space-y-3">
          {[0, 1, 2].map((i) => <Bar key={i} className={`h-3 ${["w-full", "w-11/12", "w-4/5"][i]}`} />)}
        </div>
      </section>
    </div>
  );
}
