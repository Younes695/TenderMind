import bgHome from "../assets/bg_home.jpg";

function HeroHome() {
  return (
    <main className="min-h-[calc(100vh-54px)]">

      <section
        className="relative min-h-[calc(100vh-54px)] text-white"
        style={{
          backgroundImage: `url(${bgHome})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        {/* Navy overlay for readability */}
        <div className="absolute inset-0 bg-[#0B1F3A]/85" />
        {/* Subtle grid overlay */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.055)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.055)_1px,transparent_1px)] bg-[size:40px_40px]" />

        <div className="relative mx-auto grid max-w-[1120px] grid-cols-1 items-center gap-14 px-[18px] py-[70px] lg:grid-cols-2">

          {/* Left Side */}
          <div className="max-w-[500px]">

            {/* Badge */}
            <div className="mb-[18px] flex w-fit items-center gap-2 rounded-full border border-white/20 px-3 py-[5px] text-[10px] text-[#D7DFEB]">
              <span className="h-[5px] w-[5px] rounded-full bg-[#D5AD58]" />
              Built for Saudi & GCC tender teams
            </div>

            {/* Heading */}
            <h1 className="text-[42px] font-bold leading-[0.98] tracking-[-2px] text-white sm:text-[50px] lg:text-[59px]">
              Turn Complex RFPs
              <br />
              Into Confident
              <br />
              Decisions.
            </h1>

            {/* Description */}
            <p className="mt-7 max-w-[490px] text-sm leading-[1.65] text-[#D2DBE7]">
              AI-powered tender intelligence and workflow management
              for teams that can’t afford to miss the details.
            </p>

            <p className="max-w-[485px] text-[11px] leading-[1.65] text-[#9EAFC7]">
              TenderMind reads your RFPs, evaluates Go / No-Go,
              analyzes financial and contractual risks, coordinates
              your teams, manages approvals, and helps prepare your bid.
            </p>

            {/* Buttons */}
            <div className="mt-6 flex gap-2">
            <button
                to="/demo"
                className="rounded-md bg-[#D7B15F] px-4 py-2 text-xs font-semibold text-[#102542] transition-colors hover:bg-[#F7D387]"
            >
                Book a Demo
            </button>

              <button className="h-9 rounded-md border border-white/20 bg-transparent py-2 px-[17px] text-xs font-semibold text-white hover:bg-[#102542]">
                Explore TenderMind
              </button>
            </div>

            {/* Features */}
            <div className="mt-6 flex flex-wrap gap-6 text-[9px] text-[#A9B8CC]">
              <span>◉ Role-based access</span>
              <span>◈ Evidence on every claim</span>
              <span>◷ KSA data residency</span>
            </div>

          </div>


          {/* Right Side */}
          <div className="flex justify-center lg:justify-end">

            <div className="w-full max-w-[425px] overflow-hidden rounded-2xl bg-white text-[#172F55] shadow-2xl">

              {/* Browser Bar */}
              <div className="flex h-9 items-center gap-3 border-b border-[#E6E1D8] bg-[#F5F3EE] px-[13px]">

                <div className="flex gap-[5px]">
                  <span className="h-[7px] w-[7px] rounded-full bg-[#DDD8CA]" />
                  <span className="h-[7px] w-[7px] rounded-full bg-[#DDD8CA]" />
                  <span className="h-[7px] w-[7px] rounded-full bg-[#C9A65D]" />
                </div>

                <span className="flex-1 text-center text-[7px] text-[#63718A]">
                  app.tendermind.sa / tenders / RUH-2026-184
                </span>

                <span className="rounded bg-[#E7F3ED] px-2 py-1 text-[7px] text-[#438164]">
                  ✓ Secure
                </span>

              </div>

              {/* Dashboard */}
              <div className="p-5">

                <div className="flex justify-between gap-4">

                  <div>
                    <span className="text-[7px] text-[#60718A]">
                      RIYADH SMART INFRASTRUCTURE · RUH-2026-184
                    </span>

                    <h2 className="my-2 text-lg font-bold text-[#142D52]">
                      Riyadh Smart Infrastructure
                    </h2>

                    <div className="flex items-center gap-2">
                      <span className="rounded bg-[#F7ECD5] px-2 py-1 text-[7px] text-[#B78328]">
                        CONDITIONAL GO
                      </span>

                      <span className="text-[7px] text-[#738096]">
                        Ministry of Municipalities · SAR 12.5M
                      </span>
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="block text-[8px] text-[#697890]">
                      Match Score
                    </span>

                    <strong className="text-[28px] leading-none text-[#142D52]">
                      86%
                    </strong>
                  </div>

                </div>


                {/* Cards */}
                <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">

                  <div className="min-h-14 rounded-lg border border-[#E3C984] bg-[#F7ECD5] p-2">
                    <span className="mb-2 block text-[7px] text-[#68768C]">
                      Recommendation
                    </span>
                    <strong className="text-[9px]">
                      Conditional Go
                    </strong>
                  </div>

                  <div className="min-h-14 rounded-lg border border-[#E8E4DC] bg-[#F8F7F4] p-2">
                    <span className="mb-2 block text-[7px] text-[#68768C]">
                      Risk
                    </span>
                    <strong className="text-[9px]">
                      Medium
                    </strong>
                  </div>

                  <div className="min-h-14 rounded-lg border border-[#E8E4DC] bg-[#F8F7F4] p-2">
                    <span className="mb-2 block text-[7px] text-[#68768C]">
                      Deadline
                    </span>
                    <strong className="text-[9px]">
                      18 Days
                    </strong>
                  </div>

                  <div className="min-h-14 rounded-lg border border-[#E8E4DC] bg-[#F8F7F4] p-2">
                    <span className="mb-2 block text-[7px] text-[#68768C]">
                      Approval
                    </span>
                    <strong className="text-[9px]">
                      Finance Review
                    </strong>
                  </div>

                </div>


                {/* Analysis */}
                <div className="mt-3 rounded-lg border border-[#E8E4DC] bg-[#F8F7F4] p-3">

                  <div className="flex items-center justify-between text-[7px]">

                    <strong className="text-[#314765]">
                      AI ANALYSIS PROGRESS
                    </strong>

                    <span className="flex items-center gap-1 text-[#C89E45]">
                      <i className="h-[6px] w-[6px] rounded-full bg-[#C89E45]" />
                      AI LIVE
                    </span>

                  </div>

                  <div className="mt-2 h-[6px] overflow-hidden rounded-full bg-[#DEDDD8]">
                    <div className="h-full w-[83%] rounded-full bg-[#173154]" />
                  </div>

                  <div className="mt-2 flex flex-col gap-1 text-[6.5px] text-[#697890] sm:flex-row sm:justify-between">
                    <span>✓ Requirements 214/248</span>
                    <span>✓ Risks 14 flagged</span>
                    <span>✓ Evidence linked</span>
                  </div>

                </div>

              </div>

            </div>

          </div>

        </div>

      </section>

    </main>
  );
}

export default HeroHome;