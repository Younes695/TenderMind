"""Edit the TenderMind 3-year plan into an investor-ready model (keeps the original file untouched)."""
from copy import copy

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

SRC = r"C:\Users\EgyTech\Downloads\Tender_Platform_3_Year_Plan (3).xlsx"
OUT = r"C:\Users\EgyTech\Downloads\Tender_Platform_3_Year_Plan_Investor_Ready_v4.xlsx"

wb = load_workbook(SRC)

# ---------- styles (the workbook's own conventions)
ARIAL = "Arial"
F_TXT = Font(name=ARIAL, size=10)
F_B = Font(name=ARIAL, size=10, bold=True)
F_IN = Font(name=ARIAL, size=10, color="FF0000FF")
F_LINK = Font(name=ARIAL, size=10, color="FF008000")
F_LINK_B = Font(name=ARIAL, size=10, color="FF008000", bold=True)
F_CALC = Font(name=ARIAL, size=10, color="FF000000")
F_CALC_B = Font(name=ARIAL, size=10, color="FF000000", bold=True)
F_TITLE = Font(name=ARIAL, size=14, bold=True, color="FF1F3864")
F_NOTE = Font(name=ARIAL, size=9, italic=True, color="FF595959")
F_HDR = Font(name=ARIAL, size=10, bold=True, color="FFFFFFFF")
F_RED_B = Font(name=ARIAL, size=10, bold=True, color="FFC00000")
FILL_HDR = PatternFill("solid", fgColor="FF1F3864")
FILL_SEC = PatternFill("solid", fgColor="FFD9E1F2")
FILL_Y = PatternFill("solid", fgColor="FFFFFF00")
FILL_RED = PatternFill("solid", fgColor="FFF8CBAD")
NUM = '#,##0;\\(#,##0\\);\\-'
NUM1 = '#,##0.0;\\(#,##0.0\\);\\-'
NUM2 = '#,##0.00;\\(#,##0.00\\);\\-'
PCT = '0.0%;\\(0.0%\\);\\-'
USD = '\\$#,##0;"($"#,##0\\);\\-'
USD2 = '\\$#,##0.00;"($"#,##0.00\\);\\-'
WRAP = Alignment(wrap_text=True, vertical="top")

QC = list("CDEFGHIJKLMN")  # quarter columns (index 1..12)
YC = {"P": ("C", "F"), "Q": ("G", "J"), "R": ("K", "N")}
QLAB = [f"Y{(i // 4) + 1}-Q{(i % 4) + 1}" for i in range(12)]


def put(ws, ref, value, font=F_CALC, fmt=None, fill=None, wrap=False):
    c = ws[ref]
    c.value = value
    c.font = font
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    if wrap:
        c.alignment = WRAP
    return c


def title(ws, text, note=None):
    put(ws, "A1", text, F_TITLE)
    if note:
        put(ws, "A2", note, F_NOTE)


def section(ws, row, text, last="S"):
    put(ws, f"A{row}", text, F_B, fill=FILL_SEC)


def header(ws, row, cells):
    for ref, text in cells:
        put(ws, f"{ref}{row}", text, F_HDR, fill=FILL_HDR, wrap=True)


def quarter_header(ws, row, idx_row=None, label_col_a=None):
    if label_col_a:
        put(ws, f"A{row}", label_col_a, F_HDR, fill=FILL_HDR)
    for i, col in enumerate(QC):
        put(ws, f"{col}{row}", QLAB[i], F_HDR, fill=FILL_HDR)
    for col, lab in (("P", "Year 1"), ("Q", "Year 2"), ("R", "Year 3"), ("S", "3-Year total")):
        put(ws, f"{col}{row}", lab, F_HDR, fill=FILL_HDR)
    if idx_row:
        put(ws, f"A{idx_row}", "Quarter index", F_TXT)
        for i, col in enumerate(QC):
            put(ws, f"{col}{idx_row}", i + 1, F_TXT)


def qrow(ws, row, label, tpl, first_tpl=None, agg="sum", fmt=NUM, font=F_CALC, label_font=F_TXT, total_fmt=None):
    """Formula across the 12 quarters: {c} this column, {p} previous column."""
    put(ws, f"A{row}", label, label_font)
    for i, col in enumerate(QC):
        t = first_tpl if (i == 0 and first_tpl is not None) else tpl
        prev = QC[i - 1] if i else None
        f = t.replace("{c}", col).replace("{p}", prev or "")
        put(ws, f"{col}{row}", f, font, fmt)
    tf = total_fmt or fmt
    if agg == "sum":
        for y, (a, b) in YC.items():
            put(ws, f"{y}{row}", f"=SUM({a}{row}:{b}{row})", F_CALC, tf)
        put(ws, f"S{row}", f"=SUM(P{row}:R{row})", F_CALC, tf)
    elif agg == "end":
        for y, (a, b) in YC.items():
            put(ws, f"{y}{row}", f"={b}{row}", F_CALC, tf)
        put(ws, f"S{row}", f"=R{row}", F_CALC, tf)
    elif agg == "avg":
        for y, (a, b) in YC.items():
            put(ws, f"{y}{row}", f"=AVERAGE({a}{row}:{b}{row})", F_CALC, tf)
        put(ws, f"S{row}", f"=AVERAGE(C{row}:N{row})", F_CALC, tf)


def inputs_row(ws, row, label, values, fmt=NUM, fill=FILL_Y, agg="sum"):
    put(ws, f"A{row}", label, F_TXT)
    for col, v in zip(QC, values):
        put(ws, f"{col}{row}", v, F_IN, fmt, fill)
    if agg == "sum":
        for y, (a, b) in YC.items():
            put(ws, f"{y}{row}", f"=SUM({a}{row}:{b}{row})", F_CALC, fmt)
        put(ws, f"S{row}", f"=SUM(P{row}:R{row})", F_CALC, fmt)


def widths(ws, a=46, b=None, rest=12, cols="BCDEFGHIJKLMNOPQRS"):
    ws.column_dimensions["A"].width = a
    for c in cols:
        ws.column_dimensions[c].width = rest
    if b:
        ws.column_dimensions["B"].width = b


def fresh(name, index):
    """Replace a sheet with an empty one of the same name at the same position."""
    if name in wb.sheetnames:
        idx = wb.sheetnames.index(name)
        wb.remove(wb[name])
        index = idx
    ws = wb.create_sheet(name, index)
    ws.sheet_view.showGridLines = False
    return ws


# =====================================================================================
# 1. ASSUMPTIONS (edit in place)
A = wb["Assumptions"]
put(A, "A5", "FX rate - EGP per USD (CBE, 29 Sep 2026)", F_TXT)
put(A, "B5", 52.19, F_IN, NUM2, FILL_Y)
put(A, "D5", "VALIDATED - Central Bank of Egypt sell rate 52.19 (buy 52.05) on 29 Sep 2026, as reported by "
             "matnnews.com/305183. Every USD / SAR <-> EGP conversion references this cell.", F_TXT)
put(A, "A6", "Management Planning Buffer", F_TXT)
put(A, "D6", "Planning buffer added to funding needs (deficits x (1 + buffer)). Management choice, not a forecast.", F_TXT)
put(A, "B7", 0.0275, F_IN, PCT, FILL_Y)
put(A, "D7", "VALIDATED - Paymob Egypt published card rate 2.75% (+ ~EGP 3 per transaction, ignored). "
             "paymob.com/en/pricing", F_TXT)
put(A, "A8", "Employer social insurance (share of insurable wage)", F_TXT)
put(A, "B8", 0.1875, F_IN, PCT, FILL_Y)
put(A, "D8", "VALIDATED - employer 18.75%, employee 11% (Egypt Law 148/2019); insurable wage 2026: min EGP 2,700, "
             "max EGP 16,700 (B34:B35). Sources: PwC Tax Summaries Egypt; teamed.global Egypt payroll 2026.", F_TXT)
put(A, "B11", 1580, F_IN, NUM, FILL_Y)
put(A, "D11", "VALIDATED price - 4 x WE Space 250 GB home internet at EGP 395 / month (Telecom Egypt, 2026).", F_TXT)
put(A, "D12", "ESTIMATE - outsourced part-time accountant; a junior accountant earns EGP 6,000-8,000 / month "
              "full-time in Egypt (babelsoftco.com accountant salary guide 2026).", F_TXT)
put(A, "A9", "Founder / MVP compensation - Year 1 (per founder)", F_TXT)
put(A, "C9", "EGP / month", F_TXT)
put(A, "D9", "Founder / MVP compensation - below-market by design (founders' decision for the MVP year). "
             "Not a market salary. Used by Personnel for all four founders in Year 1.", F_TXT)
put(A, "A11", "Internet & connectivity (team)", F_TXT)
put(A, "A13", "PRICING - set against competitor prices (see Market_Research). Egypt in EGP, GCC in SAR.", F_B, fill=FILL_SEC)
put(A, "A18", "Enterprise - Dedicated Cloud (hosted by us)", F_IN, fill=FILL_Y)
put(A, "B15", "Individual / small business", F_IN)
put(A, "B16", "Tender team / growing company", F_IN)
put(A, "B17", "Larger company / multiple users", F_IN)
put(A, "B18", "Enterprise - dedicated cloud (private deployment / on-premise priced separately below)", F_IN)
header(A, 14, [("D", "Blended price EGP / month (Egypt + GCC mix)"), ("I", "Egypt price EGP / month"),
               ("J", "GCC price SAR / month"), ("K", "Nearest competitor prices (Market_Research)")])
prices = [(15, 1499.99, 299, "Tenders Alerts KSA 290 SAR/mo; Jorpex $49/mo; Tenders Egypt 1,320 EGP/yr (alerts only)"),
          (16, 4899.99, 899, "Tenderwolf EUR 79-149/mo; Stotles Growth GBP 475/mo"),
          (17, 14899.99, 2900, "Inventive AI $830/mo; AutoRFP.ai $899-1,299/mo"),
          (18, 44999.99, 9500, "Loopio ~$20,000/yr; AutogenAI ~$30,000+/yr")]
for r, egp, sar, comp in prices:
    put(A, f"I{r}", egp, F_IN, NUM, FILL_Y)
    put(A, f"J{r}", sar, F_IN, NUM, FILL_Y)
    put(A, f"K{r}", comp, F_TXT)
    put(A, f"D{r}", f"=I{r}*(1-$B$33)+J{r}/$B$32*$B$5*$B$33", F_CALC, NUM)
A.column_dimensions["I"].width = 13
A.column_dimensions["J"].width = 13
A.column_dimensions["K"].width = 60
put(A, "A19", "Prices are the company's pricing decision, set between regional alert services (no AI) and Western AI "
              "tender / RFP tools - every competitor price is sourced on Market_Research (checked 30 Sep 2026). "
              "No customer has paid them yet.", F_B)
put(A, "A21", "Enterprise deployment - On-Premise (staged: none in Year 1, selected deals from Year 2/3)", F_HDR, fill=FILL_HDR)
put(A, "A22", "On-premise: one-time setup / licence fee (EGP, from SAR list price in E22)", F_TXT)
put(A, "E22", 110000, F_IN, NUM, FILL_Y)
put(A, "F22", "SAR list price", F_TXT)
put(A, "B22", "=E22/$B$32*$B$5", F_CALC, NUM)
put(A, "D22", "Priced at about one year of an enterprise RFP platform: AutogenAI ~$30,000+/yr, Loopio ~$20,000/yr "
              "(ailucius.com 2026 comparison). Customer hosts servers and AI keys.", F_TXT)
put(A, "A23", "On-premise: recurring annual support / licence", F_TXT)
put(A, "D23", "Industry norm 18-22% of licence per year (Oracle 22%, SAP 19%) - vendorbenchmark.com.", F_TXT)
put(A, "B26", 180, F_IN, USD, FILL_Y)
put(A, "D26", "VALIDATED list prices (DigitalOcean, Sep 2026): 2 x 8 GB droplets $96 + PostgreSQL $15.15 x 2 (with "
              "standby) + Valkey $15 + Spaces $5 + backups ~$19 = ~$180 per dedicated customer.", F_TXT)
put(A, "A28", "Planning allowances & opening position", F_B, fill=FILL_SEC)
rows = [
    (29, "Allowance per data source without a public price", 105, "USD / month",
     "Proxy = a real regional tender-data subscription: TenderGlobal Gulf plan USD 1,260 / 12 months (tendersa.com). "
     "Used where a portal publishes no price (Etimad, Egypt portal, UAE, Kuwait, Bahrain) - never treated as free.", NUM),
    (30, "Allowance for legal & contract review (one-off)", 50000, "EGP / one-off",
     "ESTIMATE - no public price list for Egyptian law-firm contract reviews.", NUM),
    (31, "Opening cash", 0, "EGP", "Cash in the bank at the start of Y1-Q1 before any funding (edit if any).", NUM),
    (32, "SAR per USD (official peg)", 3.75, "SAR / USD", "VALIDATED - SAMA official peg 3.75 since 1986 (sama.gov.sa).", NUM2),
    (33, "GCC share of new customers", 0.40, "%", "Company go-to-market plan (Egypt + GCC target market).", PCT),
    (34, "Social insurance - maximum insurable wage", 16700, "EGP / month", "VALIDATED - 2026 cap (teamed.global, PwC).", NUM),
    (35, "Social insurance - minimum insurable wage", 2700, "EGP / month", "VALIDATED - 2026 floor (teamed.global, PwC).", NUM),
    (36, "Annual salary increase", 0.145, "% / year",
     "Proxy = Egypt annual urban inflation 14.5% (CAPMAS, Aug 2026; EnterpriseAM 13 Sep 2026).", PCT),
]
for r, lab, v, unit, note, fmt in rows:
    put(A, f"A{r}", lab, F_TXT)
    put(A, f"B{r}", v, F_IN, fmt, FILL_Y)
    put(A, f"C{r}", unit, F_TXT)
    put(A, f"D{r}", note, F_TXT)

# =====================================================================================
# 2. AI_MODELS: provider / source / verification columns - nothing is verified
M = wb["AI_Models"]
put(M, "A2", "Standard (non-batch, no caching) list prices checked on each provider's official pricing page on "
             "30 Sep 2026. Sources in column G.", F_NOTE)
header(M, 4, [("B", "Provider"), ("G", "Source (official pricing page)"), ("H", "Verification status"),
              ("I", "Last verified")])
put(M, "A10", "Qwen2.5 3B (self-hosted, Ollama)", F_IN)
put(M, "B10", "Self-hosted (open weights)", F_TXT)
put(M, "C10", "Local", F_TXT)
put(M, "D10", 0, F_IN, USD2)
put(M, "E10", 0, F_IN, USD2)
put(M, "F10", "Primary extraction, normalization, assistant and summaries in the current product", F_TXT)
put(M, "A15", "Claude Sonnet 5.5", F_IN)
put(M, "D15", 2, F_IN, USD2)
put(M, "E15", 10, F_IN, USD2)
put(M, "A16", "Claude Opus 5.5", F_IN)
put(M, "D16", 4, F_IN, USD2)
put(M, "E16", 20, F_IN, USD2)
src = {5: "ai.google.dev/gemini-api/docs/pricing - $0.75/$3.75 until 31 Dec 2026, $1.50/$7.50 from 1 Jan 2027 "
          "(model uses the 2027 price)",
       6: "ai.google.dev/gemini-api/docs/pricing - Gemini 3.1 Pro Preview, prompts <= 200k tokens",
       7: "developers.openai.com/api/docs/pricing - gpt-5.4, < 272K context",
       8: "developers.openai.com/api/docs/pricing - gpt-5.4-mini",
       9: "developers.openai.com/api/docs/pricing - gpt-5.5, < 272K context",
       10: "Current product: open-weights Qwen2.5 3B run by us with Ollama - no per-token fee (server cost is in Servers_Infra)",
       11: "alibabacloud.com/help/en/model-studio/model-pricing - Singapore (international) endpoint",
       12: "alibabacloud.com/help/en/model-studio/model-pricing - Singapore, 0-256K tier",
       13: "alibabacloud.com/help/en/model-studio/model-pricing - Singapore",
       14: "platform.claude.com/docs/en/about-claude/pricing",
       15: "platform.claude.com/docs/en/about-claude/pricing",
       16: "platform.claude.com/docs/en/about-claude/pricing"}
for r in range(5, 17):
    put(M, f"G{r}", src[r], F_TXT)
    ok = True
    put(M, f"H{r}", "VALIDATED" if ok else "ASSUMPTION", F_B if ok else F_RED_B)
    put(M, f"I{r}", "2026-09-30" if ok else "-", F_IN)
M.column_dimensions["G"].width = 70
M.column_dimensions["I"].width = 14

# =====================================================================================
# 3. AI_COST: tiered - not every model on every tender
C = wb["AI_Cost"]
put(C, "A1", "AI APIs - Tiered AI Cost per Tender and per Plan", F_TITLE)
put(C, "A2", "Paid models run on every tender: the tenders we serve are large and complex (hundreds to 1,500+ pages), "
             "so a second model checks that each tender was split and extracted correctly. Low-confidence tenders add "
             "a second verifier and an adjudicator. Prices on AI_Models are official list prices.", F_NOTE)
put(C, "C15", "VALIDATED - Azure Document Intelligence Read $1.50 per 1,000 pages (S0), azure.microsoft.com 2026. "
              "Large scanned tenders need production OCR.", F_TXT)
put(C, "C26", "Claude Opus 5.5", F_IN)
put(C, "A20", "Share of tenders that are large / complex (verification model runs)", F_TXT)
put(C, "B20", 1.0, F_IN, PCT, FILL_Y)
put(C, "C20", "All our tenders are large / complex (company decision)", F_TXT)
put(C, "A21", "Share of tenders low-confidence / high-risk (2nd verifier + adjudicator)", F_TXT)
put(C, "B21", 0.1, F_IN, PCT, FILL_Y)
put(C, "C21", "ASSUMPTION - measure on real tenders", F_TXT)
tiers = [
    (23, "Tier 1 - Primary extraction (all tenders)",
     "Classifies documents, extracts sections, requirements, BOQ, dates", "=1"),
    (24, "Tier 2 - Verification: is the split / extraction right? (all tenders)",
     "Checks that the tender was split and extracted correctly; runs only on the large / complex share", "=$B$20"),
    (25, "Tier 3 - Second verifier (low-confidence only)",
     "Checks disputed facts against document / page evidence", "=$B$21"),
    (26, "Tier 3 - Adjudicator (low-confidence only)",
     "Resolves remaining disagreements", "=$B$21"),
    (27, "Small model - normalization & summaries (all tenders)",
     "Material normalization, similarity, fit score text, decision summary", "=1"),
]
for r, a, b, f in tiers:
    put(C, f"A{r}", a, F_TXT)
    put(C, f"B{r}", b, F_TXT)
    put(C, f"F{r}", f, F_CALC, PCT)
put(C, "A31", "BLENDED AI COST PER TENDER (USD)", F_B)
put(C, "A32", "BLENDED AI COST PER TENDER (EGP)", F_B)
put(C, "A33", "Primary + small model + OCR only (USD)", F_TXT)
put(C, "I33", "=(I23+I27)*(1+B16)+I29", F_CALC, USD2)
put(C, "A34", "Blended cost vs standard tender (multiplier)", F_TXT)
put(C, "I34", "=IF(I33=0,0,I31/I33)", F_CALC, "0.00x")
section(C, 46, "Cost per tender by tier (USD) - full cost when the tier runs")
put(C, "A47", "Standard tender (primary + small model + OCR)", F_TXT)
put(C, "I47", "=I33", F_CALC, USD2)
put(C, "A48", "Complex tender (standard + verification model)", F_TXT)
put(C, "I48", "=I47+IF(F24=0,0,I24/F24)*(1+B16)", F_CALC, USD2)
put(C, "A49", "Low-confidence / high-risk tender (complex + second verifier + adjudicator)", F_TXT)
put(C, "I49", "=I48+(IF(F25=0,0,I25/F25)+IF(F26=0,0,I26/F26))*(1+B16)", F_CALC, USD2)
put(C, "A50", "Blended average used by the model (= row 31)", F_B)
put(C, "I50", "=I31", F_CALC_B, USD2)
put(C, "A51", "Input tokens per tender (primary pass)", F_TXT)
put(C, "I51", "=G23", F_CALC, NUM)
put(C, "A52", "Output tokens per tender (primary pass)", F_TXT)
put(C, "I52", "=H23", F_CALC, NUM)

# =====================================================================================
# 4. SCENARIOS (new)
S = fresh("Scenarios", 2)
title(S, "Planning Scenarios - Customer Funnel & Enterprise Adoption",
      "Planning Scenarios. Choose 1, 2 or 3 in B4. The Upside scenario is NOT the expected outcome; "
      "the Base case is the planning case. Every lever is an ASSUMPTION to be validated.")
put(S, "A4", "Active scenario (1 = Conservative, 2 = Base, 3 = Upside)", F_B)
put(S, "B4", 2, F_IN, "0", FILL_Y)
put(S, "C4", '=CHOOSE($B$4,"Conservative","Base","Upside")', F_CALC_B)
dv = DataValidation(type="whole", operator="between", formula1="1", formula2="3", allow_blank=False)
S.add_data_validation(dv)
dv.add("B4")
header(S, 6, [("A", "Lever"), ("B", "Unit"), ("C", "Conservative"), ("D", "Base"), ("E", "Upside"),
              ("F", "Active (used)"), ("G", "Status")])
levers = [
    (7, "Founder-led outbound leads per month (rows 30-35)", "leads / month",
     "=$B$35*$B$30*C31", "=$B$35*$B$30*D31", "=$B$35*$B$30*E31", NUM1,
     "Outreach capacity (Bridge Group SDR benchmark) x cold-outreach reply rate; a sales hire adds one more SDR-equivalent"),
    (8, "Blended cost per marketing lead (= USD row 32 x FX)", "EGP / lead",
     "=C32*Assumptions!$B$5", "=D32*Assumptions!$B$5", "=E32*Assumptions!$B$5", NUM, "Benchmark: The B2B House LinkedIn benchmarks (EMEA $120), 'good CPL' $67 content offer, Lead Gen Forms from $45"),
    (9, "Lead -> Qualified lead (MQL) %", "%", 0.40, 0.40, 0.40, PCT, "Benchmark: First Page Sage B2B SaaS funnel - lead->MQL ~40%"),
    (10, "Lead -> Demo (SQL meeting) %", "%", 0.104, 0.152, 0.204, PCT,
     "Benchmark: 40% x MQL->SQL (26% PPC / 38% average / 51% SEO), First Page Sage"),
    (11, "Demo -> Pilot (opportunity) %", "%", 0.24, 0.44, 0.60, PCT,
     "Benchmark: SQL->opportunity 24% (low) / 44% (blended, First Page Sage) / 60% (demo->opp, average performers)"),
    (12, "Pilot -> Paid % (converts the quarter after the pilot)", "%", 0.27, 0.30, 0.36, PCT,
     "Benchmark: opportunity->close 27-30% average, 36% blended (First Page Sage 2026)"),
    (13, "Monthly logo churn %", "% / month", 0.065, 0.035, 0.02, PCT,
     "Benchmark: 6.5% ChartMogul median < $300K ARR / 3.5% Recurly B2B average / < 2% top performers"),
    (14, "Enterprise adoption factor (x base enterprise schedule)", "x", 0.5, 1.0, 1.5, "0.0x",
     "Scenario construct (company plan)"),
    (15, "Growth of founder-led leads per quarter", "% / quarter", 0.0, 0.0, 0.0, PCT,
     "Not used (no source) - lead growth comes from the marketing budget"),
]
for r, lab, unit, c, b, u, fmt, status in levers:
    put(S, f"A{r}", lab, F_TXT)
    put(S, f"B{r}", unit, F_TXT)
    for col, v in zip("CDE", (c, b, u)):
        is_f = isinstance(v, str)
        put(S, f"{col}{r}", v, F_CALC if is_f else F_IN, fmt, None if is_f else FILL_Y)
    put(S, f"F{r}", f"=CHOOSE($B$4,C{r},D{r},E{r})", F_CALC_B, fmt)
    put(S, f"G{r}", status, F_TXT)
section(S, 29, "Outreach plan and paid-lead cost (inputs to rows 7-8)")
put(S, "A30", "Outreach contacts per month per SDR-equivalent (= B33 x B34)", F_TXT)
put(S, "B30", "=B33*B34", F_CALC, NUM)
put(S, "G30", "Calculated", F_TXT)
put(S, "A33", "Outreach emails per day per SDR", F_TXT)
put(S, "B33", 33.8, F_IN, NUM1, FILL_Y)
put(S, "G33", "Benchmark: Bridge Group SDR metrics - median 33.8 emails/day (top quartile 54)", F_TXT)
put(S, "A34", "Working days per month", F_TXT)
put(S, "B34", 21, F_IN, NUM, FILL_Y)
put(S, "G34", "Sunday-Thursday week (Egypt / GCC), ~21 working days", F_TXT)
put(S, "A35", "Founders' outreach capacity (SDR-equivalents)", F_TXT)
put(S, "B35", 1, F_IN, NUM1, FILL_Y)
put(S, "G35", "Company plan: 4 founders together give about one full-time SDR of outreach while building the product", F_TXT)
put(S, "A31", "Cold-outreach reply rate (lead)", F_TXT)
for col, v in zip("CDE", (0.021, 0.0343, 0.058)):
    put(S, f"{col}31", v, F_IN, PCT, FILL_Y)
put(S, "G31", "Benchmark 2026: 2.1% large sends / 3.43% average / 5.8% tightly targeted lists (cold-email benchmark reports)", F_TXT)
put(S, "F31", "=CHOOSE($B$4,C31,D31,E31)", F_CALC_B, PCT)
put(S, "A32", "Cost per paid lead (USD)", F_TXT)
for col, v in zip("CDE", (120, 67, 45)):
    put(S, f"{col}32", v, F_IN, USD, FILL_Y)
put(S, "G32", "Benchmark: LinkedIn B2B SaaS EMEA $120 / good content-offer CPL $67 / Lead Gen Forms from $45", F_TXT)
put(S, "A16", "Retention % (monthly, = 1 - churn)", F_TXT)
put(S, "F16", "=1-F13", F_CALC, PCT)
section(S, 17, "Plan mix of new paid customers (all scenarios)")
for r, lab, v in ((18, "Starter share", 0.40), (19, "Growth share", 0.40), (20, "Business share", 0.20)):
    put(S, f"A{r}", lab, F_TXT)
    put(S, f"B{r}", v, F_IN, PCT, FILL_Y)
    put(S, f"G{r}", "Company plan - sales focus on contractors (companies), not individuals", F_TXT)
put(S, "A21", "Check: shares add up to 100%", F_TXT)
put(S, "B21", '=IF(ABS(SUM(B18:B20)-1)<0.0001,"OK","FIX: must total 100%")', F_CALC_B)
section(S, 23, "Enterprise - base schedule before the adoption factor (staged: none in Year 1)")
quarter_header(S, 24)
for c in "PQRS":
    S[f"{c}24"].value = None
    S[f"{c}24"].fill = PatternFill()
inputs_row(S, 25, "Dedicated Cloud customers active (end of quarter)", [0, 0, 0, 0, 0, 0, 1, 1, 1, 2, 2, 2], agg=None)
inputs_row(S, 26, "On-premise new deals signed in quarter", [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1], agg=None)
put(S, "A27", "Year 1 is pilots / SaaS only. Enterprise deals are staged and scaled by the scenario factor "
              "(rounded down below 1x, so the Conservative case can have none).", F_NOTE)
widths(S, 62, 14, 11)
S.column_dimensions["G"].width = 95

# =====================================================================================
# 5. MARKETING: keep, relabel, connect to the funnel
MK = wb["Marketing"]
put(MK, "A1", "Marketing Budget (EGP) - drives paid leads on the Funnel sheet", F_TITLE)
put(MK, "A8", "Pilot programs & webinars (onboarding)", F_TXT)
put(MK, "A9", "Partner / referral commissions (industry partnerships)", F_TXT)
put(MK, "A12", "All marketing figures are ASSUMPTIONS. Paid leads on Funnel = spend / blended cost per lead "
               "(Scenarios). Founder-led sales, direct outreach, LinkedIn, partnerships and referrals done by the "
               "founders add leads at no cash cost (Scenarios row 7).", F_NOTE)

# =====================================================================================
# 6. FUNNEL (new)
FN = fresh("Funnel", 3)
title(FN, "Customer Funnel - Leads -> Qualified -> Demos -> Pilots -> Paid -> Retained",
      "All conversion rates are scenario ASSUMPTIONS (Scenarios sheet). Customers are calculated, not typed in. "
      "No real customer or pilot exists yet.")
quarter_header(FN, 3, 4)
qrow(FN, 6, "Marketing spend (EGP)", "=Marketing!{c}10", font=F_LINK)
qrow(FN, 7, "Outbound leads (founders + sales hire, SDR benchmark x reply rate)",
     "=(Scenarios!$B$35+Personnel!{c}26)*Scenarios!$B$30*Scenarios!$F$31*3", fmt=NUM1)
qrow(FN, 8, "Marketing leads (spend / cost per lead)", "=IF(Scenarios!$F$8>0,{c}6/Scenarios!$F$8,0)", fmt=NUM1)
qrow(FN, 9, "Total leads", "={c}7+{c}8", fmt=NUM1, label_font=F_B)
qrow(FN, 10, "Qualified leads", "={c}9*Scenarios!$F$9", fmt=NUM1)
qrow(FN, 11, "Demos", "={c}9*Scenarios!$F$10", fmt=NUM1)
qrow(FN, 12, "Pilots (free, 1 month)", "={c}11*Scenarios!$F$11", fmt=NUM1)
qrow(FN, 13, "New paid customers (from last quarter's pilots)", "={p}12*Scenarios!$F$12", first_tpl="=0", fmt=NUM1)
qrow(FN, 14, "Churned customers", "={p}16*(1-(1-Scenarios!$F$13)^3)", first_tpl="=0", fmt=NUM1)
qrow(FN, 15, "Retained customers (start of quarter - churned)", "={p}16-{c}14", first_tpl="=0", agg="end", fmt=NUM1)
qrow(FN, 16, "Paid SaaS customers - end of quarter", "={c}15+{c}13", agg="end", fmt=NUM1, label_font=F_B)
qrow(FN, 17, "Average paid SaaS customers in quarter", "=({p}16+{c}16)/2", first_tpl="={c}16/2", agg="avg", fmt=NUM1)
section(FN, 18, "Average paying customers by plan (feeds Revenue)")
qrow(FN, 19, "Starter", "={c}17*Scenarios!$B$18", agg="avg", fmt=NUM1)
qrow(FN, 20, "Growth", "={c}17*Scenarios!$B$19", agg="avg", fmt=NUM1)
qrow(FN, 21, "Business", "={c}17*Scenarios!$B$20", agg="avg", fmt=NUM1)
qrow(FN, 23, "Pilot AI cost (EGP) - pilots use 1 month of the Growth quota", "={c}12*Assumptions!$F$16")
widths(FN, 50, None, 10)

# =====================================================================================
# 7. REVENUE: customers from the funnel; enterprise staged by scenario
R = wb["Revenue"]
for i, col in enumerate(QC):
    for row, frow in ((7, 19), (14, 20), (21, 21)):
        put(R, f"{col}{row}", f"=Funnel!{col}{frow}", F_LINK, NUM1)
    put(R, f"{col}28", f"=IF(Scenarios!$F$14<1,ROUNDDOWN(Scenarios!{col}25*Scenarios!$F$14,0),"
                       f"ROUND(Scenarios!{col}25*Scenarios!$F$14,0))", F_LINK, NUM)
    put(R, f"{col}35", f"=IF(Scenarios!$F$14<1,ROUNDDOWN(Scenarios!{col}26*Scenarios!$F$14,0),"
                       f"ROUND(Scenarios!{col}26*Scenarios!$F$14,0))", F_LINK, NUM)
for r in (7, 14, 21, 44):
    for c in "PQRS":
        R[f"{c}{r}"].number_format = NUM1
    for c in QC:
        R[f"{c}{r}"].number_format = NUM1
put(R, "A27", "Plan 4 - Enterprise: Dedicated Cloud (hosted by us)", F_B, fill=FILL_SEC)
put(R, "A34", "Plan 5 - Enterprise: On-Premise (customer hosts)", F_B, fill=FILL_SEC)
put(R, "A37", "One-time setup / licence revenue", F_TXT)
put(R, "A38", "Recurring support / licence revenue (annual %, billed quarterly)", F_TXT)
put(R, "A50", "Customer numbers are CALCULATED from the Funnel (Scenarios). Enterprise counts follow the staged "
              "schedule on Scenarios x adoption factor. All are projections, not actual customers.", F_NOTE)

# =====================================================================================
# 8. DATA_SOURCES (rebuilt: TBD is not $0)
D = fresh("Data_Sources", wb.sheetnames.index("Data_Sources"))
title(D, "Data Sources - Tender Portals, Aggregators & Price Sources",
      "A TBD cost is NOT free: each active TBD source carries the planning allowance (Assumptions B29). "
      "Access checks noted below were run by the product in Sept 2026; legal terms-of-use review is still pending.")
header(D, 4, [("A", "#"), ("B", "Source"), ("C", "Country / region"), ("D", "Type"), ("E", "Access method"),
              ("F", "API available"), ("G", "What we obtain"), ("H", "Monthly cost USD"), ("I", "Start quarter"),
              ("J", "Verification status"), ("K", "Notes")])
sources = [
    ("Egypt Government e-Procurement Portal", "Egypt", "Government portal", "Official access / scraping only if terms allow",
     "Unknown", "Active tenders, documents, deadlines", "TBD", 1, "TBD",
     "No public API or price. Portal did not respond to our automated test (2026-09)."),
    ("Etimad", "Saudi Arabia", "Government portal", "Official API / partnership required", "Unknown",
     "Active tenders, documents, deadlines", "TBD", 1, "TBD",
     "robots.txt disallows automated access (checked 2026-09) - not scraped. Needs official API or partnership."),
    ("UAE federal & emirate procurement portals", "UAE", "Government portal", "Official API / supplier registration", "Unknown",
     "Active tenders", "TBD", 5, "TBD",
     "Dubai eSupply returned 401 (login) and DEWA 403 in our test (2026-09). Access method TBD."),
    ("Monaqasat (available tenders list)", "Qatar", "Government portal", "Public web list (read by the product)", "No (public page)",
     "Active tenders, closing dates", 0, 1, "ESTIMATE",
     "robots.txt allows; read by the product since 2026-09. No fee observed; terms-of-use review pending."),
    ("Central Agency for Public Tenders (CAPT)", "Kuwait", "Government portal", "TBD", "Unknown", "Active tenders", "TBD", 7,
     "TBD", "Page redirected in our test (2026-09); access not confirmed."),
    ("Bahrain Tender Board", "Bahrain", "Government portal", "TBD", "Unknown", "Active tenders", "TBD", 7, "TBD",
     "Returned 403 in our test (2026-09)."),
    ("EWA Bahrain - published tenders table", "Bahrain", "Utility (public)", "Public web table (read by the product)",
     "No (public page)", "Electricity & water tenders", 0, 1, "ESTIMATE",
     "robots.txt allows; read by the product since 2026-09. No fee observed; terms-of-use review pending."),
    ("Oman Tender Board - new tenders list", "Oman", "Government portal", "Public web list (read by the product)",
     "No (public page)", "New tenders, closing dates", 0, 1, "ESTIMATE",
     "robots.txt allows; read by the product since 2026-09. No fee observed; terms-of-use review pending."),
    ("World Bank procurement notices API", "Egypt (World Bank projects)", "Official open API", "Official public API",
     "Yes", "Procurement notices", 0, 1, "VALIDATED",
     "Official open-data API used by the product since 2026-09 (World Bank projects in Egypt; few GCC projects)."),
    ("JONEPS", "Jordan", "Government portal", "TBD", "Unknown", "Active tenders", "TBD", 99, "TBD",
     "Outside the current target market (Egypt + GCC) - not active in this plan (start quarter 99)."),
    ("GCC tender-data subscription (TenderGlobal Gulf plan)", "GCC", "Paid aggregator", "Subscription", "No",
     "Government + private tenders, broader coverage", 105, 5, "VALIDATED",
     "USD 1,260 per 12 months (+1 month free), 3-5 users - tendersa.com/plans.aspx (checked 30 Sep 2026)."),
    ("Construction / energy project database (e.g. MEED Projects)", "Gulf", "Paid database", "Licence",
     "TBD", "Pre-tender project pipeline", "TBD", 9, "TBD",
     "No public price (quote-only). Carries the allowance in Assumptions B29. Enterprise phase."),
    ("Global tender coverage (TenderGlobal all-countries plan)", "Global", "Paid aggregator", "Subscription", "No",
     "Extra coverage and cross-checking", 167, 9, "VALIDATED",
     "USD 1,999 per 12 months - tendersa.com/plans.aspx (checked 30 Sep 2026)."),
    ("Private-sector tender platforms", "Regional", "Private platforms", "Partnership", "TBD", "Private tenders",
     "TBD", 9, "TBD", "Partnership terms not public. Carries the allowance in Assumptions B29."),
    ("Customer-uploaded supplier price lists (Egypt)", "Egypt", "Customer data", "Upload (Excel / CSV) in the product",
     "n/a", "Unit price + supplier + date", 0, 1, "ASSUMPTION",
     "Current product design: prices come only from lists the customer uploads - no data fee to us."),
    ("Customer-uploaded supplier price lists (GCC)", "GCC", "Customer data", "Upload (Excel / CSV) in the product",
     "n/a", "Unit price + supplier + date", 0, 1, "ASSUMPTION",
     "Current product design: prices come only from lists the customer uploads - no data fee to us."),
    ("Metal benchmark prices (copper / aluminium) - Metals-API Silver plan", "Global", "Market data API", "Paid API",
     "Yes", "Benchmark raw-material prices for cables", 79.99, 5, "VALIDATED",
     "USD 79.99/month, 10,000 calls, 20 symbols - metals-api.com/pricing (checked 30 Sep 2026)."),
    ("Steel / rebar / cement market indices", "Regional", "Market data", "Subscription / API", "TBD",
     "Market price indices", "TBD", 9, "TBD", "No public price found. Carries the allowance in Assumptions B29."),
    ("Supplier data partnerships (distributors' feeds)", "Egypt + GCC", "Supplier feeds", "Partnership / feed", "TBD",
     "Live supplier prices", "TBD", 9, "TBD", "Terms not public. Carries the allowance in Assumptions B29."),
    ("Foreign-exchange rates API - ExchangeRate-API Pro", "Global", "API", "API", "Yes", "Multi-currency conversion",
     10, 1, "VALIDATED", "USD 10/month, 30,000 requests - exchangerate-api.com (checked 30 Sep 2026)."),
    ("Scraping / parser maintenance & data refresh", "All", "Engineering time", "Internal", "n/a",
     "Keeping sources working", 0, 1, "ASSUMPTION", "Covered by team time on Personnel (not a separate fee)."),
]
for i, s in enumerate(sources):
    r = 5 + i
    put(D, f"A{r}", i + 1, F_TXT)
    for col, v in zip("BCDEFG", s[:6]):
        put(D, f"{col}{r}", v, F_TXT, wrap=True)
    put(D, f"H{r}", s[6], F_IN, USD, FILL_Y)
    put(D, f"I{r}", s[7], F_IN, "0", FILL_Y)
    put(D, f"J{r}", s[8], F_B if s[8] == "TBD" else F_TXT)
    put(D, f"K{r}", s[9], F_TXT, wrap=True)
last = 4 + len(sources)
put(D, f"B{last + 1}", "Total monthly of PRICED sources when all active (USD)", F_B)
put(D, f"H{last + 1}", f"=SUM(H5:H{last})", F_CALC_B, USD)
put(D, f"B{last + 2}", "Number of sources with TBD cost (carry the planning allowance)", F_B)
put(D, f"H{last + 2}", f'=COUNTIF(H5:H{last},"TBD")', F_CALC_B, "0")
qs = last + 4
section(D, qs, "Quarterly data-source cost (EGP)")
quarter_header(D, qs + 1, qs + 2)
ix = qs + 2
qrow(D, qs + 3, "Priced sources (EGP)",
     f'=SUMIFS($H$5:$H${last},$I$5:$I${last},"<="&{{c}}{ix})*3*Assumptions!$B$5')
qrow(D, qs + 4, "Planning allowance for TBD sources (EGP)",
     f'=COUNTIFS($H$5:$H${last},"TBD",$I$5:$I${last},"<="&{{c}}{ix})*Assumptions!$B$29*3*Assumptions!$B$5')
qrow(D, qs + 5, "Data sources & APIs cost (EGP)", f"={{c}}{qs + 3}+{{c}}{qs + 4}", label_font=F_B)
DS_ROW = qs + 5
D.column_dimensions["A"].width = 4
for col, w in zip("BCDEFGHIJK", (38, 16, 16, 24, 12, 26, 12, 9, 14, 60)):
    D.column_dimensions[col].width = w
for c in "LMNOPQRS":
    D.column_dimensions[c].width = 11

# =====================================================================================
# 9. SERVERS_INFRA (rebuilt: MVP / Growth / Enterprise tiers, no Y1 over-provisioning)
SI = fresh("Servers_Infra", wb.sheetnames.index("Servers_Infra"))
title(SI, "Servers & Infrastructure - staged MVP -> Growth -> Enterprise",
      "Published list prices checked 30 Sep 2026 (DigitalOcean, Grafana, Cloudflare, GitHub, Postmark). Paid "
      "servers from day one - the system processes 1,500-page tenders; the Enterprise tier adds capacity from Year 3.")
header(SI, 4, [("A", "#"), ("B", "Item"), ("C", "Category"), ("D", "Tier"), ("E", "Fixed USD / month"),
               ("F", "Variable USD / customer / month"), ("G", "Start quarter"), ("H", "Note")])
infra = [
    ("SSL, CDN, DDoS protection - Cloudflare Free plan", "Security", "MVP", 0, 0, 1, "VALIDATED - cloudflare.com/plans"),
    ("Domain name", "Security", "MVP", 1, 0, 1, "ESTIMATE - about USD 10-15 per year for a .com"),
    ("Team tools - GitHub Team, 4 users x $4 (incl. secret scanning / Dependabot)", "Tools", "MVP", 16, 0, 1,
     "VALIDATED - github.com/pricing ($4/user/month, first 12 months)"),
    ("Document-processing server (OCR, parsing, queue workers) - droplet 8 GB / 4 vCPU", "AI", "Core", 48, 0, 1,
     "VALIDATED - digitalocean.com/pricing/droplets"),
    ("App servers - 2 x DigitalOcean droplets 4 GB / 2 vCPU", "Compute", "Core", 48, 0, 1,
     "VALIDATED - digitalocean.com/pricing/droplets ($24 each)"),
    ("Managed PostgreSQL - primary + standby (1 GB / 1 vCPU each)", "Database", "Core", 30.30, 0, 1,
     "VALIDATED - digitalocean.com/pricing/managed-databases ($15.15 per node)"),
    ("Queue + cache - Managed Valkey (Redis-compatible)", "Compute", "Core", 15, 0, 1,
     "VALIDATED - digitalocean.com/pricing/managed-databases"),
    ("Object storage for tender documents - Spaces (250 GB + 1 TB transfer)", "Storage", "Core", 1, 0.05, 1,
     "VALIDATED - digitalocean.com/pricing/spaces-object-storage ($5; extra $0.02/GB ~2.5 GB per customer)"),
    ("Fetch / parsing worker - droplet 2 GB", "Data collection", "Core", 12, 0, 1,
     "VALIDATED - digitalocean.com/pricing/droplets"),
    ("Staging environment - droplet 4 GB", "Compute", "Core", 24, 0, 1, "VALIDATED - digitalocean.com/pricing/droplets"),
    ("Monitoring - Grafana Cloud Pro platform fee", "Operations", "Core", 19, 0, 1, "VALIDATED - grafana.com/pricing"),
    ("Transactional email - Postmark Basic (10,000 emails)", "Communications", "Core", 15, 0, 1,
     "VALIDATED - postmarkapp.com/pricing"),
    ("Droplet backups (~20% of droplet price)", "Resilience", "Core", 17, 0, 1,
     "ESTIMATE - 20% of the droplet prices above"),
    ("Semantic search node - droplet 8 GB / 4 vCPU", "Search", "Enterprise", 48, 0, 9,
     "VALIDATED - digitalocean.com/pricing/droplets"),
    ("Extra capacity - 2 x droplets 8 GB / 4 vCPU", "Compute", "Enterprise", 96, 0, 9,
     "VALIDATED - digitalocean.com/pricing/droplets"),
]
for i, it in enumerate(infra):
    r = 5 + i
    put(SI, f"A{r}", i + 1, F_TXT)
    put(SI, f"B{r}", it[0], F_TXT, wrap=True)
    put(SI, f"C{r}", it[1], F_TXT)
    put(SI, f"D{r}", it[2], F_IN, fill=FILL_Y)
    put(SI, f"E{r}", it[3], F_IN, USD, FILL_Y)
    put(SI, f"F{r}", it[4], F_IN, USD2, FILL_Y)
    put(SI, f"G{r}", it[5], F_IN, "0", FILL_Y)
    put(SI, f"H{r}", it[6], F_TXT)
il = 4 + len(infra)
put(SI, f"B{il + 1}", "Total when all items active", F_B)
put(SI, f"E{il + 1}", f"=SUM(E5:E{il})", F_CALC_B, USD)
put(SI, f"F{il + 1}", f"=SUM(F5:F{il})", F_CALC_B, USD2)
for k, tier in enumerate(("MVP", "Core", "Enterprise")):
    put(SI, f"B{il + 2 + k}", f"Fixed USD / month - {tier} tier", F_TXT)
    put(SI, f"E{il + 2 + k}", f'=SUMIFS(E5:E{il},D5:D{il},"{tier}")', F_CALC, USD)
qs = il + 6
section(SI, qs, "Quarterly infrastructure cost (EGP)")
quarter_header(SI, qs + 1, qs + 2)
ix = qs + 2
qrow(SI, qs + 3, "Fixed infrastructure (EGP)", f'=SUMIFS($E$5:$E${il},$G$5:$G${il},"<="&{{c}}{ix})*3*Assumptions!$B$5')
qrow(SI, qs + 4, "Variable infrastructure by customers (EGP)",
     f'=SUMIFS($F$5:$F${il},$G$5:$G${il},"<="&{{c}}{ix})*Revenue!{{c}}44*3*Assumptions!$B$5')
qrow(SI, qs + 5, "Dedicated-Cloud customer infrastructure (EGP)", "=Revenue!{c}28*Assumptions!$B$26*3*Assumptions!$B$5")
qrow(SI, qs + 6, "TOTAL SERVERS & INFRASTRUCTURE (EGP)", f"=SUM({{c}}{qs + 3}:{{c}}{qs + 5})", label_font=F_B)
SI_ROW = qs + 6
SI.column_dimensions["A"].width = 4
for col, w in zip("BCDEFGH", (60, 15, 11, 12, 14, 9, 70)):
    SI.column_dimensions[col].width = w
for c in "IJKLMNOPQRS":
    SI.column_dimensions[c].width = 11
# the quarter grid starts in column C, which is narrow here: widen the label column instead
for c in QC + ["P", "Q", "R", "S"]:
    SI.column_dimensions[c].width = max(SI.column_dimensions[c].width or 11, 11)

# =====================================================================================
# 10. PERSONNEL (rebuilt: 4 founders + staged hires)
P = fresh("Personnel", wb.sheetnames.index("Personnel"))
title(P, "Personnel (EGP) - founders + hires staged by customer growth",
      "Year 1: Founder / MVP compensation - below-market by design. Hires start only when paid customers reach the "
      "trigger. Market salaries = Glassdoor Cairo 2026 averages (checked 30 Sep 2026). Employer social insurance "
      "18.75% on the insurable wage (capped at EGP 16,700).")
header(P, 4, [("A", "Founder role"), ("B", "Person"), ("C", "Y1 EGP / month"), ("D", "Y2 EGP / month"),
              ("E", "Y3 EGP / month"), ("F", "Market average (Glassdoor Cairo 2026)"), ("G", "Market reference role")])
founders = [
    ("Founder - AI & system development", "Abdelrahman", 13667, "Machine Learning Engineer"),
    ("Founder - Full-stack development", "Esraa", 14000, "Full Stack Developer"),
    ("Founder - Data analysis & data engineering", "Janna", 21333, "Data Engineer"),
    ("Founder - Security (SOC) & UI/UX", "Rahma", 20708, "SOC Analyst (UI/UX Designer avg 8,917)"),
]
for i, (role, who, mkt, ref) in enumerate(founders):
    r = 5 + i
    put(P, f"A{r}", role, F_TXT)
    put(P, f"B{r}", who, F_IN)
    put(P, f"C{r}", "=Assumptions!$B$9", F_LINK, NUM)
    put(P, f"D{r}", f"=ROUND(F{r}*$C$17,-2)", F_CALC, NUM)
    put(P, f"E{r}", f"=ROUND(F{r}*(1+Assumptions!$B$36),-2)", F_CALC, NUM)
    put(P, f"F{r}", mkt, F_IN, NUM, FILL_Y)
    put(P, f"G{r}", ref, F_TXT)
header(P, 10, [("A", "Planned hire"), ("B", "Earliest quarter"), ("C", "Salary EGP / month (Y1 terms)"),
               ("D", "Trigger: paid customers >="), ("E", "Type"), ("F", "Status"), ("G", "")])
hires = [
    ("Operations / customer success", 5, 14396, 20, "Glassdoor Cairo 2026 - Customer Success Manager 25th percentile (avg 25,000)"),
    ("Sales / business development", 5, 13000, 8, "Glassdoor Cairo 2026 - Account Manager average"),
    ("Full-stack developer", 5, 14000, 40, "Glassdoor Cairo 2026 - Full Stack Developer average"),
    ("AI / ML engineer", 5, 13667, 60, "Glassdoor Cairo 2026 - Machine Learning Engineer average"),
    ("Data engineer", 5, 21333, 90, "Glassdoor Cairo 2026 - Data Engineer average"),
]
for i, (role, q, sal, trig, srcnote) in enumerate(hires):
    r = 11 + i
    put(P, f"A{r}", role, F_TXT)
    put(P, f"B{r}", q, F_IN, "0", FILL_Y)
    put(P, f"C{r}", sal, F_IN, NUM, FILL_Y)
    put(P, f"D{r}", trig, F_IN, NUM, FILL_Y)
    put(P, f"E{r}", srcnote, F_TXT)
    put(P, f"F{r}", "ESTIMATE", F_TXT)
put(P, "A16", "Annual salary increase for hires (from Year 2)", F_TXT)
put(P, "C16", "=Assumptions!B36", F_LINK, PCT)
put(P, "E16", "Egypt urban inflation 14.5% (CAPMAS, Aug 2026) used as the raise", F_TXT)
put(P, "A17", "Founders' Year-2 pay as % of their market average", F_TXT)
put(P, "C17", 0.7, F_IN, PCT, FILL_Y)
put(P, "E17", "Company plan: 70% of market in Y2, full market (+ raise) in Y3", F_TXT)
quarter_header(P, 18, 19)
section(P, 20, "Headcount")
for i, (role, who, *_x) in enumerate(founders):
    inputs_row(P, 21 + i, f"{role} ({who})", [1] * 12, fill=None, agg=None)
    for y, (a, b) in YC.items():
        put(P, f"{y}{21 + i}", f"={b}{21 + i}", F_CALC, NUM)
    put(P, f"S{21 + i}", f"=R{21 + i}", F_CALC, NUM)
for i, (role, *_rest) in enumerate(hires):
    r, h = 25 + i, 11 + i
    trig = f"Funnel!{{p}}16+Revenue!{{p}}28"
    qrow(P, r, f"{role} (hired when trigger met)",
         f"=IF({{c}}$19<$B${h},0,MAX({{p}}{r},IF({trig}>=$D${h},1,0)))",
         first_tpl=f"=IF(C$19<$B${h},0,IF(0>=$D${h},1,0))", agg="end")
qrow(P, 30, "Total headcount", "=SUM({c}21:{c}29)", agg="end", label_font=F_B)
section(P, 32, "Personnel cost per quarter (EGP)")
SI = "MIN(MAX({s},Assumptions!$B$35),Assumptions!$B$34)*Assumptions!$B$8"  # employer share on the capped wage
for i, (role, who, *_x) in enumerate(founders):
    f = 5 + i
    sal = f"CHOOSE(INT(({{c}}$19-1)/4)+1,$C${f},$D${f},$E${f})"
    qrow(P, 33 + i, f"{role} ({who})",
         f"={{c}}{21 + i}*({sal}+{SI.format(s=sal)})*3")
for i, (role, *_rest) in enumerate(hires):
    h = 11 + i
    sal = f"$C${h}*(1+$C$16)^INT(({{c}}$19-1)/4)"
    qrow(P, 37 + i, role, f"={{c}}{25 + i}*({sal}+{SI.format(s=sal)})*3")
qrow(P, 42, "TOTAL PERSONNEL COST", "=SUM({c}33:{c}41)", label_font=F_B)
qrow(P, 43, "of which sales & business development (used in CAC)", "={c}38")
qrow(P, 44, "New hires in quarter (for workstations)", "=SUM({c}25:{c}29)-SUM({p}25:{p}29)",
     first_tpl="=SUM({c}25:{c}29)")
put(P, "A46", "Hiring is staged: nobody is hired until paid customers (end of the previous quarter) reach the "
              "trigger. Change triggers, salaries and the earliest quarter above.", F_NOTE)
widths(P, 52, 13, 11)
P.column_dimensions["C"].width = 14
P.column_dimensions["D"].width = 14
P.column_dimensions["E"].width = 14
P.column_dimensions["F"].width = 16
P.column_dimensions["G"].width = 34

# =====================================================================================
# 11. ASSETS: workstations for new hires
AS = wb["Assets"]
put(AS, "A10", "New-hire workstation (laptop + monitor)", F_TXT)
put(AS, "B10", "=B6+B7", F_CALC, NUM)
for col in QC:
    put(AS, f"{col}10", f"=Personnel!{col}44", F_LINK, NUM)
    put(AS, f"{col}11", f"=SUMPRODUCT($B$6:$B$10,{col}6:{col}10)", F_CALC, NUM)
for y, (a, b) in YC.items():
    put(AS, f"{y}10", f"=SUM({a}10:{b}10)", F_CALC, NUM)
put(AS, "S10", "=SUM(P10:R10)", F_CALC, NUM)

# =====================================================================================
# 12. SECURITY_COMPLIANCE (new)
SC = fresh("Security_Compliance", wb.sheetnames.index("Assets") + 1)
title(SC, "Security & Compliance - planning categories",
      "The startup does NOT hold ISO 27001, SOC 2 or any other certification today. Certification lines are "
      "'Future compliance / certification target'. Amounts use the low end of published 2026 price ranges.")
header(SC, 4, [("A", "#"), ("B", "Category"), ("C", "Where the cost sits"), ("D", "One-off cost EGP"),
               ("E", "Quarter"), ("F", "Status"), ("G", "Note")])
sec = [
    ("Secure cloud infrastructure (network isolation, hardened hosts)", "Servers_Infra", "In Servers_Infra", "", "ESTIMATE",
     "Included in infrastructure lines"),
    ("Encrypted document storage", "Servers_Infra", "In Servers_Infra", "", "ESTIMATE", ""),
    ("Backups & disaster recovery", "Servers_Infra", "In Servers_Infra", "", "ESTIMATE", ""),
    ("Monitoring & logging (incl. audit logs)", "Servers_Infra", "In Servers_Infra", "", "ESTIMATE", ""),
    ("Access control & tenant isolation", "Personnel (built in the product)", "In Personnel", "", "ASSUMPTION",
     "Per-account isolation and audit trail already exist in the product"),
    ("Encryption keys / secrets management", "Servers_Infra", "In Servers_Infra", "", "ESTIMATE", ""),
    ("External security testing (web-app penetration test) #1", "This sheet", "=5000*Assumptions!$B$5", 6, "ESTIMATE",
     "USD 5,000 - low end of 2026 small web-app pentest range $5,000-15,000 (brightdefense.com, redfoxsec.com)"),
    ("External security testing (web-app penetration test) #2", "This sheet", "=5000*Assumptions!$B$5", 10, "ESTIMATE",
     "USD 5,000 - same source"),
    ("Legal & security review (terms, DPA, customer contracts)", "This sheet", "=Assumptions!$B$30", 4, "ESTIMATE",
     "No public Egyptian price list - planning allowance (Assumptions B30)"),
    ("Future compliance / certification target (ISO 27001 readiness)", "This sheet", "=15000*Assumptions!$B$5", 11,
     "ESTIMATE", "USD 15,000 - small-organisation first-year range $12,000-38,000 (hightable.io, factorialhr.com 2026). "
     "Future compliance / certification target - NOT held today"),
]
for i, s in enumerate(sec):
    r = 5 + i
    put(SC, f"A{r}", i + 1, F_TXT)
    put(SC, f"B{r}", s[0], F_TXT, wrap=True)
    put(SC, f"C{r}", s[1], F_TXT)
    put(SC, f"D{r}", s[2], F_CALC if str(s[2]).startswith("=") else F_IN, NUM, FILL_Y)
    put(SC, f"E{r}", s[3] if s[3] != "" else None, F_IN, "0", FILL_Y)
    put(SC, f"F{r}", s[4], F_TXT)
    put(SC, f"G{r}", s[5], F_TXT, wrap=True)
sl = 4 + len(sec)
qs = sl + 2
section(SC, qs, "Quarterly security & compliance cash cost (EGP)")
quarter_header(SC, qs + 1, qs + 2)
ix = qs + 2
qrow(SC, qs + 3, "Security & compliance (priced items + TBD allowances)",
     f'=SUMIFS($D$5:$D${sl},$E$5:$E${sl},{{c}}{ix})+COUNTIFS($D$5:$D${sl},"TBD",$E$5:$E${sl},{{c}}{ix})'
     f'*Assumptions!$B$30', label_font=F_B)
SEC_ROW = qs + 3
SC.column_dimensions["A"].width = 4
for col, w in zip("BCDEFG", (50, 26, 16, 9, 13, 44)):
    SC.column_dimensions[col].width = w
for c in "HIJKLMNOPQRS":
    SC.column_dimensions[c].width = 11

# =====================================================================================
# 13. CASH_BUDGET: keep revenue & COGS, rebuild opex / cash / funding / break-even
CB = wb["Cash_Budget"]
for col in QC:
    put(CB, f"{col}13", f"=Revenue!{col}10+Revenue!{col}17+Revenue!{col}24+Revenue!{col}31+Funnel!{col}23", F_LINK, NUM)
    # card / gateway fees apply to subscriptions, not to on-premise invoices paid by bank transfer
    put(CB, f"{col}15", f"=({col}6+{col}7)*Assumptions!$B$7", F_CALC, NUM)
put(CB, "A13", "AI processing (analysis + radar screening + pilots)", F_TXT)
put(CB, "A15", "Payment gateway fees (subscriptions only)", F_TXT)
for row in CB.iter_rows(min_row=19, max_row=CB.max_row):
    for c in row:
        c.value = None
        c.font = F_TXT
        c.fill = PatternFill()
        c.number_format = "General"
section(CB, 19, "OPERATING EXPENSES")
qrow(CB, 20, "Personnel", "=Personnel!{c}42", font=F_LINK)
qrow(CB, 21, "Servers & infrastructure", f"=Servers_Infra!{{c}}{SI_ROW}", font=F_LINK)
qrow(CB, 22, "Data sources & APIs (tender portals, price data, TBD allowances)", f"=Data_Sources!{{c}}{DS_ROW}", font=F_LINK)
qrow(CB, 23, "Marketing", "=Marketing!{c}10", font=F_LINK)
qrow(CB, 24, "Internet, accounting & legal", "=(Assumptions!$B$11+Assumptions!$B$12)*3")
qrow(CB, 25, "Security & compliance (planning allowances)", f"=Security_Compliance!{{c}}{SEC_ROW}", font=F_LINK)
qrow(CB, 26, "Total operating expenses", "=SUM({c}20:{c}25)", label_font=F_B)
section(CB, 28, "CASH FLOW")
qrow(CB, 29, "Operating cash flow", "={c}17-{c}26", label_font=F_B)
qrow(CB, 30, "Capex - team devices", "=Assets!{c}11", font=F_LINK)
qrow(CB, 31, "Net cash flow (before funding)", "={c}29-{c}30", label_font=F_B)
qrow(CB, 32, "Cumulative net cash flow (before funding)", "={p}32+{c}31", first_tpl="={c}31", agg="end")
qrow(CB, 33, "Cumulative incl. Management Planning Buffer", "=IF({c}32<0,{c}32*(1+Assumptions!$B$6),{c}32)", agg="end")
qrow(CB, 34, "Operating cash flow positive (flag)", "=IF({c}29>0,1,0)", agg=None, fmt="0")
qrow(CB, 35, "Operating cash flow positive and stays positive (flag)", "=IF(MIN({c}29:$N$29)>0,1,0)", agg=None, fmt="0")
qrow(CB, 36, "Cumulative cash recovered and stays >= 0 (flag)", "=IF(MIN({c}32:$N$32)>=0,1,0)", agg=None, fmt="0")
section(CB, 38, "FUNDING & ENDING CASH")
qrow(CB, 39, "Phase", '=IF({c}$4<=4,"Phase 1 - MVP",IF({c}$4<=8,"Phase 2 - Product","Phase 3 - Expansion"))',
     agg=None, fmt="General")
qrow(CB, 40, "Funding received (planned, start of each phase)",
     "=IF({c}$4=1,$C$47,IF({c}$4=5,$C$48,IF({c}$4=9,$C$49,0)))")
qrow(CB, 41, "Beginning cash", "={p}43", first_tpl="=Assumptions!$B$31", agg=None)
for y, first in (("P", "C"), ("Q", "G"), ("R", "K")):
    put(CB, f"{y}41", f"={first}41", F_CALC, NUM)
put(CB, "S41", "=C41", F_CALC, NUM)
qrow(CB, 42, "Net cash flow", "={c}31")
qrow(CB, 43, "Ending cash", "={c}41+{c}40+{c}42", agg="end", label_font=F_B)
qrow(CB, 44, "Cash check", '=IF({c}43<0,"NEGATIVE","OK")', agg=None, fmt="General")
section(CB, 46, "FUNDING REQUIREMENT BY PHASE (incl. Management Planning Buffer)")
put(CB, "C46", "EGP", F_HDR, fill=FILL_HDR)
put(CB, "D46", "USD", F_HDR, fill=FILL_HDR)
fund = [
    (47, "Phase 1 - Initial MVP + Validation Funding Requirement (Y1)",
     "=MAX(0,-MIN(C32:F32))*(1+Assumptions!$B$6)"),
    (48, "Phase 2 - Post-Validation / Productization Funding (Y2)",
     "=MAX(0,MAX(0,-MIN(C32:J32))*(1+Assumptions!$B$6)-C47)"),
    (49, "Phase 3 - Expansion Funding within this model (Y3)",
     "=MAX(0,MAX(0,-MIN(C32:N32))*(1+Assumptions!$B$6)-C47-C48)"),
    (50, "Total funding requirement in this model", "=SUM(C47:C49)"),
]
for r, lab, f in fund:
    put(CB, f"A{r}", lab, F_B if r == 50 else F_TXT)
    put(CB, f"C{r}", f, F_CALC_B, NUM)
    put(CB, f"D{r}", f"=C{r}/Assumptions!$B$5", F_CALC_B, USD)
put(CB, "A51", "Not included: MENA-scale expansion (more countries, on-premise programme, certification, "
               "enterprise integrations) - separate raise, costs TBD. ~1.1M EGP does NOT fund the whole roadmap.",
    F_RED_B)
section(CB, 53, "BREAK-EVEN")
be = [
    (54, "First quarter with positive operating cash flow", "=IFERROR(INDEX($C$3:$N$3,MATCH(1,C34:N34,0)),\"Not within 3 years\")"),
    (55, "Operating break-even (positive and stays positive)", "=IFERROR(INDEX($C$3:$N$3,MATCH(1,C35:N35,0)),\"Not within 3 years\")"),
    (56, "Cash payback (cumulative cash >= 0 and stays)", "=IFERROR(INDEX($C$3:$N$3,MATCH(1,C36:N36,0)),\"Not within 3 years\")"),
]
for r, lab, f in be:
    put(CB, f"A{r}", lab, F_TXT)
    put(CB, f"C{r}", f, F_CALC_B)
section(CB, 58, "MONTHLY VIEW (average month in the quarter / year)")
qrow(CB, 59, "Monthly revenue", "={c}10/3", agg=None)
qrow(CB, 60, "Monthly operating costs (cost of revenue + opex)", "=({c}16+{c}26)/3", agg=None)
qrow(CB, 61, "Monthly gross profit", "={c}17/3", agg=None)
qrow(CB, 62, "Monthly net cash flow", "={c}31/3", agg=None)
for r, src in ((59, 10), (61, 17), (62, 31)):
    for y in "PQR":
        put(CB, f"{y}{r}", f"={y}{src}/12", F_CALC, NUM)
for y in "PQR":
    put(CB, f"{y}60", f"=({y}16+{y}26)/12", F_CALC, NUM)
qrow(CB, 64, "Total costs (cost of revenue + opex + capex)", "={c}16+{c}26+{c}30")
CB.conditional_formatting.add("C43:S43", CellIsRule(operator="lessThan", formula=["0"], fill=FILL_RED, font=F_RED_B))
CB.conditional_formatting.add("C32:S33", CellIsRule(operator="lessThan", formula=["0"], font=F_RED_B))
CB.conditional_formatting.add("C44:N44", FormulaRule(formula=['C44="NEGATIVE"'], fill=FILL_RED, font=F_RED_B))
CB.conditional_formatting.add("C31:S31", CellIsRule(operator="lessThan", formula=["0"], font=F_RED_B))

# =====================================================================================
# 14. SAAS_METRICS (new)
SM = fresh("SaaS_Metrics", wb.sheetnames.index("Cash_Budget") + 1)
title(SM, "Key SaaS Metrics (EGP) - calculated from the Planning Scenario",
      "CAC, churn, LTV and conversion are TO BE VALIDATED - no customer data exists yet. Year columns: flows are "
      "summed, stocks show the year-end value.")
quarter_header(SM, 3, 4)
section(SM, 5, "Customers")
qrow(SM, 6, "Paid SaaS customers (end)", "=Funnel!{c}16", agg="end", fmt=NUM1, font=F_LINK)
qrow(SM, 7, "Enterprise - Dedicated Cloud (end)", "=Revenue!{c}28", agg="end", font=F_LINK)
qrow(SM, 8, "Enterprise - On-premise deployed (cumulative)", "=Revenue!{c}36", agg="end", font=F_LINK)
qrow(SM, 9, "Total customers (end)", "=SUM({c}6:{c}8)", agg="end", fmt=NUM1, label_font=F_B)
qrow(SM, 10, "New paid SaaS customers", "=Funnel!{c}13", fmt=NUM1, font=F_LINK)
qrow(SM, 11, "Churned customers", "=Funnel!{c}14", fmt=NUM1, font=F_LINK)
qrow(SM, 12, "Monthly churn % - To Be Validated", "=Scenarios!$F$13", agg="avg", fmt=PCT, font=F_LINK)
qrow(SM, 13, "Quarterly logo retention %", "=(1-{c}12)^3", agg="avg", fmt=PCT)
section(SM, 14, "Recurring revenue")
qrow(SM, 15, "MRR (end of quarter)",
     "={c}6*(Scenarios!$B$18*Assumptions!$D$15+Scenarios!$B$19*Assumptions!$D$16+Scenarios!$B$20*Assumptions!$D$17)"
     "+{c}7*Assumptions!$D$18+{c}8*Assumptions!$B$22*Assumptions!$B$23/12", agg="end", label_font=F_B)
qrow(SM, 16, "ARR (MRR x 12)", "={c}15*12", agg="end", label_font=F_B)
qrow(SM, 17, "ARPA (MRR / customers, per month)", "=IF({c}9>0,{c}15/{c}9,0)", agg="end")
section(SM, 18, "Unit economics")
qrow(SM, 19, "Gross revenue", "=Cash_Budget!{c}10", font=F_LINK)
qrow(SM, 20, "AI costs", "=Cash_Budget!{c}13", font=F_LINK)
qrow(SM, 21, "AI cost as % of revenue", "=IF({c}19>0,{c}20/{c}19,0)", agg=None, fmt=PCT)
qrow(SM, 22, "Gross margin after AI costs only", "=IF({c}19>0,1-{c}20/{c}19,0)", agg=None, fmt=PCT)
qrow(SM, 23, "Infrastructure costs", "=Cash_Budget!{c}21", font=F_LINK)
qrow(SM, 24, "Gross profit", "=Cash_Budget!{c}17", font=F_LINK)
qrow(SM, 25, "Gross margin %", "=IF({c}19>0,{c}24/{c}19,0)", agg=None, fmt=PCT)
qrow(SM, 26, "Operating expenses", "=Cash_Budget!{c}26", font=F_LINK)
qrow(SM, 27, "Sales & marketing spend (marketing + sales staff)", "=Marketing!{c}10+Personnel!{c}43")
qrow(SM, 28, "CAC - To Be Validated (S&M / new customers)", "=IF({c}10>0,{c}27/{c}10,0)", agg=None)
qrow(SM, 29, "LTV - To Be Validated (ARPA x gross margin / monthly churn)", "=IF({c}12>0,{c}17*{c}25/{c}12,0)", agg=None)
qrow(SM, 30, "LTV / CAC", "=IF({c}28>0,{c}29/{c}28,0)", agg=None, fmt="0.0x")
section(SM, 31, "Cash")
qrow(SM, 32, "Net cash flow (before funding)", "=Cash_Budget!{c}31", font=F_LINK)
qrow(SM, 33, "Monthly cash burn", "=MAX(0,-{c}32/3)", agg=None)
qrow(SM, 34, "Ending cash (after planned funding)", "=Cash_Budget!{c}43", agg="end", font=F_LINK)
qrow(SM, 35, "Runway at this burn (months)", '=IF({c}33>0,{c}34/{c}33,"Not burning")', agg=None, fmt=NUM1)
for y, (a, b) in YC.items():  # yearly ratios from yearly totals
    put(SM, f"{y}21", f"=IF({y}19>0,{y}20/{y}19,0)", F_CALC, PCT)
    put(SM, f"{y}22", f"=IF({y}19>0,1-{y}20/{y}19,0)", F_CALC, PCT)
    put(SM, f"{y}25", f"=IF({y}19>0,{y}24/{y}19,0)", F_CALC, PCT)
    put(SM, f"{y}28", f"=IF({y}10>0,{y}27/{y}10,0)", F_CALC, NUM)
put(SM, "S21", "=IF(S19>0,S20/S19,0)", F_CALC, PCT)
put(SM, "S22", "=IF(S19>0,1-S20/S19,0)", F_CALC, PCT)
put(SM, "S25", "=IF(S19>0,S24/S19,0)", F_CALC, PCT)
put(SM, "S28", "=IF(S10>0,S27/S10,0)", F_CALC, NUM)
widths(SM, 52, None, 11)

# =====================================================================================
# 15. ASSUMPTIONS_VALIDATION (new)
AV = fresh("Assumptions_Validation", 1)
title(AV, "Assumptions & Validation",
      "Every important number, what kind of number it is, and whether it has been validated. VALIDATED means "
      "checked against a real source or real data; everything else must be confirmed before relying on it.")
put(AV, "A4", "Status summary", F_B, fill=FILL_SEC)
statuses = ["VALIDATED", "ASSUMPTION", "ESTIMATE", "TBD", "TO VALIDATE"]
for i, s in enumerate(statuses):
    put(AV, f"A{5 + i}", s, F_TXT)
    put(AV, f"B{5 + i}", f'=COUNTIF($G$13:$G$80,"{s}")', F_CALC_B, "0")
put(AV, "A10", "Total", F_B)
put(AV, "B10", "=SUM(B5:B9)", F_CALC_B, "0")
header(AV, 12, [("A", "#"), ("B", "Assumption"), ("C", "Value"), ("D", "Unit"), ("E", "Type"), ("F", "Source"),
                ("G", "Status"), ("H", "Notes")])
av = [
    ("FX rate EGP per USD", "=Assumptions!B5", "EGP / USD", "Official rate", "CBE sell rate 29 Sep 2026 (matnnews.com/305183)", "VALIDATED", "", NUM2),
    ("SAR per USD", "=Assumptions!B32", "SAR / USD", "Official peg", "SAMA (sama.gov.sa)", "VALIDATED", "", NUM2),
    ("Starter price Egypt / GCC", "=Assumptions!I15", "EGP / month", "Pricing decision", "Benchmarked: Tenders Alerts KSA 290 SAR/mo; Jorpex $49/mo (Market_Research)", "ASSUMPTION", "GCC: 299 SAR", NUM),
    ("Growth price Egypt / GCC", "=Assumptions!I16", "EGP / month", "Pricing decision", "Benchmarked: Tenderwolf EUR 79-149; Stotles GBP 475 (Market_Research)", "ASSUMPTION", "GCC: 899 SAR", NUM),
    ("Business price Egypt / GCC", "=Assumptions!I17", "EGP / month", "Pricing decision", "Benchmarked: Inventive AI $830; AutoRFP $899-1,299 (Market_Research)", "ASSUMPTION", "GCC: 2,900 SAR", NUM),
    ("Enterprise dedicated price", "=Assumptions!I18", "EGP / month", "Pricing decision", "Benchmarked: Loopio ~$20k/yr; AutogenAI ~$30k+/yr", "ASSUMPTION", "GCC: 9,500 SAR", NUM),
    ("On-premise licence (SAR list)", "=Assumptions!E22", "SAR / deal", "Pricing decision", "~1 year of enterprise RFP platform (ailucius.com comparison)", "ASSUMPTION", "", NUM),
    ("On-premise annual support", "=Assumptions!B23", "% / year", "Industry norm", "vendorbenchmark.com: 18-22% (Oracle 22%, SAP 19%)", "VALIDATED", "", PCT),
    ("GCC share of new customers", "=Assumptions!B33", "%", "Go-to-market plan", "Company decision", "ASSUMPTION", "", PCT),
    ("Payment gateway fee", "=Assumptions!B7", "% of subscriptions", "Published rate", "Paymob Egypt 2.75% (+EGP 3/txn)", "VALIDATED", "", PCT),
    ("Employer social insurance", "=Assumptions!B8", "% of insurable wage", "Law", "Law 148/2019; cap EGP 16,700, floor 2,700 (PwC, teamed.global)", "VALIDATED", "", PCT),
    ("Annual salary increase", "=Assumptions!B36", "% / year", "Proxy", "Urban inflation 14.5% Aug 2026 (CAPMAS via EnterpriseAM)", "ESTIMATE", "", PCT),
    ("Founder pay Y1", "=Assumptions!B9", "EGP / month", "Founders' decision", "Below-market by design", "ASSUMPTION", "", NUM),
    ("Hire salaries (5 roles, sum)", "=SUM(Personnel!C11:C15)", "EGP / month", "Market average", "Glassdoor Cairo 2026 (CSM, Account Manager, Full Stack, ML, Data Engineer)", "ESTIMATE", "", NUM),
    ("Hiring triggers", "=Personnel!D12", "paid customers (first)", "Company plan", "Company decision", "ASSUMPTION", "", NUM),
    ("Outreach emails per SDR per day", "=Scenarios!B33", "emails / day", "Benchmark", "Bridge Group SDR metrics (median 33.8)", "ESTIMATE", "", NUM1),
    ("Founders' outreach capacity", "=Scenarios!B35", "SDR-equivalents", "Company plan", "Company decision", "ASSUMPTION", "", NUM1),
    ("Cold-outreach reply rate", "=Scenarios!D31", "%", "Benchmark", "2026 cold-email benchmark reports (Instantly / Apollo / Cleanlist)", "ESTIMATE", "", PCT),
    ("Cost per paid lead", "=Scenarios!D32", "USD", "Benchmark", "The B2B House LinkedIn benchmarks; content-offer CPL guidance", "ESTIMATE", "", USD),
    ("Lead -> Demo %", "=Scenarios!D10", "%", "Benchmark", "First Page Sage B2B SaaS funnel benchmarks", "ESTIMATE", "", PCT),
    ("Demo -> Pilot %", "=Scenarios!D11", "%", "Benchmark", "First Page Sage (SQL->opportunity 44%)", "ESTIMATE", "", PCT),
    ("Pilot -> Paid %", "=Scenarios!D12", "%", "Benchmark", "Opportunity->close 27-36% (First Page Sage)", "ESTIMATE", "", PCT),
    ("Monthly churn", "=Scenarios!D13", "% / month", "Benchmark", "Recurly B2B SaaS average 3.5%/month", "ESTIMATE", "", PCT),
    ("Plan mix (Starter share)", "=Scenarios!B18", "%", "Company plan", "Sales focus on companies", "ASSUMPTION", "", PCT),
    ("Active scenario", "=Scenarios!C4", "", "Planning scenario", "Model control", "ASSUMPTION", "Upside is not the expected case", None),
    ("AI model prices (12 models)", "Official pages", "USD / 1M tokens", "Published prices", "Google, OpenAI, Anthropic, Alibaba pricing pages 30 Sep 2026", "VALIDATED", "Azure row assumed = OpenAI", None),
    ("OCR price", "=AI_Cost!B15", "USD / 1,000 pages", "Published price", "Azure Document Intelligence Read $1.50", "VALIDATED", "", USD2),
    ("Pages per tender", "=AI_Cost!B11", "pages", "Company data", "Real tenders processed range 30-1,500 pages", "ESTIMATE", "", NUM),
    ("Infrastructure list prices", f"=Servers_Infra!E{il + 1}", "USD / month (all active)", "Published prices", "DigitalOcean, Grafana, Cloudflare, GitHub, Postmark", "VALIDATED", "", USD),
    ("Dedicated-cloud infra per customer", "=Assumptions!B26", "USD / month", "Composed from list prices", "DigitalOcean price list", "VALIDATED", "", USD),
    ("Government portal data access", "No public price", "", "Not published", "Etimad robots.txt disallows; Egypt portal no response; UAE login", "TBD", "Allowance B29 applied", None),
    ("Allowance per no-price data source", "=Assumptions!B29", "USD / month", "Proxy", "TenderGlobal Gulf USD 1,260 / 12 months", "ESTIMATE", "", USD),
    ("Paid data sources with public prices", "Metals-API $79.99; FX API $10; TenderGlobal $105/$167", "USD / month", "Published prices", "metals-api.com, exchangerate-api.com, tendersa.com", "VALIDATED", "", None),
    ("Penetration test", "=Security_Compliance!D11", "EGP each", "Price range (low end)", "USD 5,000 - 2026 pentest pricing guides", "ESTIMATE", "", NUM),
    ("ISO 27001 readiness (future target)", "=Security_Compliance!D14", "EGP", "Price range", "USD 15,000 - small-org first year $12k-38k", "ESTIMATE", "Not held today", NUM),
    ("Legal & contract review", "=Assumptions!B30", "EGP one-off", "No public price", "Planning allowance", "ESTIMATE", "", NUM),
    ("Internet (team)", "=Assumptions!B11", "EGP / month", "Published price", "WE Space 250 GB EGP 395 x 4", "VALIDATED", "", NUM),
    ("Accounting", "=Assumptions!B12", "EGP / month", "Derived", "Junior accountant EGP 6-8k/month full-time (babelsoftco.com)", "ESTIMATE", "part-time", NUM),
    ("Marketing budget", "=Marketing!S10", "EGP (3 years)", "Company plan", "Company decision", "ASSUMPTION", "", NUM),
]
for i, (name, val, unit, typ, src, st, note, fmt) in enumerate(av):
    r = 13 + i
    put(AV, f"A{r}", i + 1, F_TXT)
    put(AV, f"B{r}", name, F_TXT)
    is_f = isinstance(val, str) and val.startswith("=")
    put(AV, f"C{r}", val, F_LINK if is_f else F_TXT, fmt)
    put(AV, f"D{r}", unit, F_TXT)
    put(AV, f"E{r}", typ, F_TXT)
    put(AV, f"F{r}", src, F_TXT)
    put(AV, f"G{r}", st, F_B)
    put(AV, f"H{r}", note, F_TXT)
AV.column_dimensions["A"].width = 16
for col, w in zip("BCDEFGH", (46, 16, 22, 24, 30, 14, 50)):
    AV.column_dimensions[col].width = w
AV.conditional_formatting.add("G13:G80", FormulaRule(formula=['G13="VALIDATED"'], fill=PatternFill("solid", fgColor="FFC6EFCE")))
AV.conditional_formatting.add("G13:G80", FormulaRule(formula=['OR(G13="TBD",G13="TO VALIDATE")'], fill=PatternFill("solid", fgColor="FFFFEB9C")))

# =====================================================================================
# 15b. MARKET_RESEARCH (new): competitor prices and every external source used
MR = fresh("Market_Research", 2)
title(MR, "Market Research - competitor prices and sources (checked 30 Sep 2026)",
      "Published or reported prices only. USD per month is computed for SAR / EGP / USD prices with the FX cells on "
      "Assumptions; EUR / GBP prices stay in their own currency (no unsourced conversion).")
header(MR, 4, [("A", "Competitor / product"), ("B", "Region"), ("C", "What it does"), ("D", "Price"), ("E", "Currency"),
               ("F", "Billing period (months)"), ("G", "USD per month"), ("H", "Source"), ("I", "Type")])
comp = [
    ("Tenders Alerts - monthly", "Saudi Arabia", "Etimad tender alerts, AI summaries & match score, BOQ to Excel, per user", 290, "SAR", 1, "tendersalerts.com/en (list 550, offer price)", "Published"),
    ("Tenders Alerts - annual", "Saudi Arabia", "Same, 12 months", 1850, "SAR", 12, "tendersalerts.com/en (list 3,500)", "Published"),
    ("Tenders Egypt (BizTech) - annual", "Egypt", "Tender alerts from official papers, no AI analysis", 1320, "EGP", 12, "tenderegypt.com/plans", "Published"),
    ("Tenders Egypt - 3 months", "Egypt", "Same, 3 months", 480, "EGP", 3, "tenderegypt.com/plans", "Published"),
    ("TenderGlobal - Gulf countries", "GCC", "Tender alerts & documents, 3-5 users", 1260, "USD", 12, "tendersa.com/plans.aspx", "Published"),
    ("TenderGlobal - all countries", "Global", "Same, all countries", 1999, "USD", 12, "tendersa.com/plans.aspx", "Published"),
    ("Jorpex", "EU", "Tender monitoring", 49, "USD", 1, "ailucius.com 2026 comparison", "Published"),
    ("Tenderwolf - top plan", "EU", "Tender search & AI", 149, "EUR", 1, "ailucius.com 2026 comparison (EUR 0 / 79 / 149)", "Published"),
    ("Lucius AI - per tender", "EU", "AI analysis of one tender", 149, "EUR", None, "ailucius.com (pack EUR 149 per tender)", "Published"),
    ("Stotles - Growth", "UK", "Public-sector sales intelligence", 475, "GBP", 1, "ailucius.com 2026 comparison", "Published"),
    ("Stotles - Bid Studio", "UK", "Bid writing workspace", 990, "GBP", 1, "ailucius.com 2026 comparison", "Published"),
    ("Mercell / Tracker Intelligence", "UK / EU", "Tender intelligence, annual contract", 5100, "GBP", 12, "ailucius.com (GBP 5,100+/yr)", "Reported"),
    ("Inventive AI", "US", "AI RFP response, unlimited users", 830, "USD", 1, "inventive.ai RFP pricing guide 2026", "Published"),
    ("AutoRFP.ai - Scale", "US", "AI RFP response, 24 projects", 899, "USD", 1, "inventive.ai / autorfp.ai 2026", "Published"),
    ("AutoRFP.ai - Accelerate", "US", "AI RFP response, 50 projects", 1299, "USD", 1, "inventive.ai / autorfp.ai 2026", "Published"),
    ("Loopio", "Global", "RFP response library, ~10 seats", 20000, "USD", 12, "ailucius.com / autorfp.ai (reported)", "Reported"),
    ("AutogenAI", "UK / Global", "AI bid writing, 5-seat minimum", 30000, "USD", 12, "ailucius.com (reported ~$30,000+/yr)", "Reported"),
]
for i, (name, reg, what, price, cur, months, src_, typ) in enumerate(comp):
    r = 5 + i
    put(MR, f"A{r}", name, F_TXT)
    put(MR, f"B{r}", reg, F_TXT)
    put(MR, f"C{r}", what, F_TXT)
    put(MR, f"D{r}", price, F_IN, NUM)
    put(MR, f"E{r}", cur, F_TXT)
    put(MR, f"F{r}", months if months else "per tender", F_TXT)
    if months and cur in ("USD", "SAR", "EGP"):
        conv = {"USD": "1", "SAR": "1/Assumptions!$B$32", "EGP": "1/Assumptions!$B$5"}[cur]
        put(MR, f"G{r}", f"=D{r}*{conv}/F{r}", F_CALC, USD)
    else:
        put(MR, f"G{r}", "n/a (" + cur + ")", F_TXT)
    put(MR, f"H{r}", src_, F_TXT)
    put(MR, f"I{r}", typ, F_TXT)
cl = 4 + len(comp)
section(MR, cl + 2, "Our prices against the market (USD per month, using the FX cells on Assumptions)")
header(MR, cl + 3, [("A", "Plan"), ("B", "Egypt EGP"), ("C", "Egypt USD"), ("D", "GCC SAR"), ("E", "GCC USD"),
                    ("F", "Analyses / month"), ("G", "Egypt USD per analysis"), ("H", "Positioning")])
pos = ["Above Egyptian alert-only services (no AI), far below one Lucius per-tender pack",
       "Between Tenderwolf and Stotles Growth; a tender team shares one plan",
       "Below Inventive AI / AutoRFP.ai for GCC; adds eligibility, BOQ and RFQ packages",
       "Below Loopio / AutogenAI annual cost; includes dedicated hosting"]
for k in range(4):
    r, ar = cl + 4 + k, 15 + k
    put(MR, f"A{r}", f"=Assumptions!A{ar}", F_LINK)
    put(MR, f"B{r}", f"=Assumptions!I{ar}", F_LINK, NUM)
    put(MR, f"C{r}", f"=B{r}/Assumptions!$B$5", F_CALC, USD)
    put(MR, f"D{r}", f"=Assumptions!J{ar}", F_LINK, NUM)
    put(MR, f"E{r}", f"=D{r}/Assumptions!$B$32", F_CALC, USD)
    put(MR, f"F{r}", f"=Assumptions!C{ar}", F_LINK, NUM)
    put(MR, f"G{r}", f"=IF(F{r}>0,C{r}/F{r},0)", F_CALC, USD2)
    put(MR, f"H{r}", pos[k], F_TXT)
sr = cl + 10
section(MR, sr, "Other external sources used in the model")
header(MR, sr + 1, [("A", "Input"), ("B", "Value"), ("C", "Source")])
others = [
    ("FX EGP/USD", "52.19 (sell), 29 Sep 2026", "Central Bank of Egypt rate reported by matnnews.com/305183"),
    ("SAR/USD", "3.75 official peg", "SAMA - sama.gov.sa"),
    ("Employer social insurance", "18.75%, cap EGP 16,700, floor 2,700 (2026)", "PwC Worldwide Tax Summaries Egypt; teamed.global Egypt payroll 2026"),
    ("Salary increase proxy", "14.5% urban inflation, Aug 2026", "CAPMAS via EnterpriseAM (13 Sep 2026)"),
    ("Salaries (Cairo, 2026, EGP/month)", "ML 13,667; Full-stack 14,000; Data eng 21,333; SOC 20,708; UI/UX 8,917; CSM 25,000 (25th pct 14,396); Account Mgr 13,000", "glassdoor.com salary pages, Cairo, 2026"),
    ("Payment gateway", "2.75% + EGP 3 per transaction", "paymob.com/en/pricing"),
    ("AI APIs", "Gemini, GPT-5.x, Claude, Qwen list prices", "Official pricing pages (AI_Models column G)"),
    ("OCR", "$1.50 per 1,000 pages (Read, S0)", "azure.microsoft.com/pricing/details/document-intelligence"),
    ("Hosting", "Oracle Always Free; DigitalOcean droplets $12/$24/$48, PostgreSQL $15.15, Valkey $15, Spaces $5", "docs.oracle.com; digitalocean.com/pricing"),
    ("SaaS tools", "GitHub Team $4/user; Postmark $15; Grafana Pro $19; Cloudflare Free", "github.com/pricing; postmarkapp.com/pricing; grafana.com/pricing; cloudflare.com/plans"),
    ("Funnel benchmarks", "Lead->MQL 40%; MQL->SQL 26/38/51%; SQL->Opp 24-44%; Opp->Close 27-36%", "First Page Sage B2B SaaS funnel benchmarks 2026"),
    ("Churn benchmarks", "3.5%/month average; 6.5% under $300K ARR; <2% top performers", "Recurly churn report; ChartMogul benchmarks"),
    ("Cost per lead", "LinkedIn B2B SaaS EMEA $120; content-offer CPL $67; Lead Gen Forms from $45", "theb2bhouse.com LinkedIn ad benchmarks; stackmatix.com"),
    ("Cold outreach reply rate", "3.43% average 2026; 2.1% large sends; 5.8% small targeted lists", "2026 cold-email benchmark reports (Instantly, Apollo, Cleanlist)"),
    ("Security", "Pentest $5,000-15,000 small web app; ISO 27001 $12,000-38,000 small org year 1", "brightdefense.com, redfoxsec.com; hightable.io, factorialhr.com"),
    ("Software support norm", "18-22% of licence per year", "vendorbenchmark.com"),
    ("Internet", "WE Space 250 GB EGP 395 / month", "Telecom Egypt (te.eg) via 2026 price guides"),
    ("Tender data subscriptions", "Metals-API Silver $79.99/mo; ExchangeRate-API Pro $10/mo", "metals-api.com/pricing; exchangerate-api.com"),
]
for i, (a, b, c) in enumerate(others):
    r = sr + 2 + i
    put(MR, f"A{r}", a, F_B)
    put(MR, f"B{r}", b, F_TXT)
    put(MR, f"C{r}", c, F_TXT)
for col, w in zip("ABCDEFGHI", (34, 40, 52, 12, 10, 12, 14, 52, 11)):
    MR.column_dimensions[col].width = w

# =====================================================================================
# 16. SUMMARY (existing): rewire to the new structure
SU = wb["Summary"]
for row in SU.iter_rows(min_row=3, max_row=max(SU.max_row, 45)):
    for c in row:
        c.value = None
        c.fill = PatternFill()
        c.font = F_TXT
put(SU, "A2", "All figures update from the other sheets. Planning Scenario shown in B4. Estimates and hypotheses "
              "are marked on Assumptions_Validation.", F_NOTE)
section(SU, 3, "KEY NUMBERS")
put(SU, "A4", "Planning Scenario", F_TXT)
put(SU, "B4", "=Scenarios!C4", F_LINK_B)
key = [
    (5, "Phase 1 - Initial MVP + Validation Funding Requirement (EGP)", "=Cash_Budget!C47", NUM),
    (6, "Phase 2 - Post-Validation Funding (EGP)", "=Cash_Budget!C48", NUM),
    (7, "Phase 3 - Expansion Funding within model (EGP)", "=Cash_Budget!C49", NUM),
    (8, "Total funding requirement in model (USD)", "=Cash_Budget!D50", USD),
    (9, "Operating break-even (sustained)", "=Cash_Budget!C55", None),
    (10, "Customers at end of Year 3 (SaaS + enterprise)", "=SaaS_Metrics!R9", NUM),
    (11, "AI cost per tender - blended (USD)", "=AI_Cost!I31", USD2),
    (12, "Team size at end of Year 3", "=Personnel!R30", NUM),
    (13, "Planning FX Assumption (EGP per USD)", "=Assumptions!B5", NUM2),
]
for r, lab, f, fmt in key:
    put(SU, f"A{r}", lab, F_TXT)
    put(SU, f"B{r}", f, F_LINK_B, fmt)
section(SU, 15, "YEARLY VIEW (EGP)")
for col, lab in zip("BCDE", ("Year 1", "Year 2", "Year 3", "3-Year total")):
    put(SU, f"{col}15", lab, F_HDR, fill=FILL_HDR)
lines = [
    (16, "Total revenue", 10), (17, "Cost of revenue", 16), (18, "Gross profit", 17), (19, "Personnel", 20),
    (20, "Servers & infrastructure", 21), (21, "Data sources & APIs", 22), (22, "Marketing", 23),
    (23, "Internet, accounting & legal", 24), (24, "Security & compliance", 25), (25, "Capex - devices", 30),
    (26, "Net cash flow (before funding)", 31),
]
for r, lab, src in lines:
    put(SU, f"A{r}", lab, F_B if r in (16, 18, 26) else F_TXT)
    for col, yc in zip("BCDE", "PQRS"):
        put(SU, f"{col}{r}", f"=Cash_Budget!{yc}{src}", F_LINK, NUM)
put(SU, "A27", "Net cash flow (USD)", F_TXT)
for col in "BCDE":
    put(SU, f"{col}27", f"={col}26/Assumptions!$B$5", F_CALC, USD)
section(SU, 29, "WHERE THE MONEY GOES (3 years)")
put(SU, "B29", "EGP", F_HDR, fill=FILL_HDR)
put(SU, "C29", "Share of costs", F_HDR, fill=FILL_HDR)
wm = [(30, "Personnel", "=E19"), (31, "Servers & infrastructure", "=E20"), (32, "Data sources & APIs", "=E21"),
      (33, "Marketing", "=E22"), (34, "AI processing (variable)", "=Cash_Budget!S13"),
      (35, "Security & compliance", "=E24"),
      (36, "Other (internet, accounting, devices, fees, on-prem delivery)", "=E17-Cash_Budget!S13+E23+E25")]
for r, lab, f in wm:
    put(SU, f"A{r}", lab, F_TXT)
    put(SU, f"B{r}", f, F_CALC, NUM)
    put(SU, f"C{r}", f"=IF($B$37=0,0,B{r}/$B$37)", F_CALC, PCT)
put(SU, "A37", "Total costs", F_B)
put(SU, "B37", "=SUM(B30:B36)", F_CALC_B, NUM)
put(SU, "C37", "=SUM(C30:C36)", F_CALC_B, PCT)
section(SU, 39, "PLAN ECONOMICS (per customer / month) - Initial Pricing Hypothesis")
for col, lab in zip("BCD", ("Price EGP", "AI cost EGP", "Gross margin on AI cost")):
    put(SU, f"{col}39", lab, F_HDR, fill=FILL_HDR)
for i in range(4):
    r, ar = 40 + i, 15 + i
    put(SU, f"A{r}", f"=Assumptions!A{ar}", F_LINK)
    put(SU, f"B{r}", f"=Assumptions!D{ar}", F_LINK, NUM)
    put(SU, f"C{r}", f"=Assumptions!F{ar}", F_LINK, NUM2)
    put(SU, f"D{r}", f"=Assumptions!G{ar}", F_LINK, PCT)

# =====================================================================================
# 17. INVESTOR_SUMMARY (new, first sheet)
IV = fresh("Investor_Summary", 0)
title(IV, "TenderMind - AI Tender Intelligence (Egypt + GCC) - Investor View",
      "Planning model, not a forecast of actual results. No paying customer exists yet; every price, conversion "
      "rate and cost below is a hypothesis or estimate unless marked VALIDATED on Assumptions_Validation.")
put(IV, "A3", "Planning Scenario", F_B)
put(IV, "B3", "=Scenarios!C4", F_LINK_B)
put(IV, "C3", "(Upside is not the expected outcome)", F_NOTE)
section(IV, 5, "BUSINESS MODEL")
bm = [
    ("SaaS subscriptions", "Starter (individual / small business) and Growth (tender team) - monthly plans"),
    ("Team / company plans", "Business - larger companies, multiple users, higher tender quota"),
    ("Dedicated cloud", "Enterprise - isolated environment hosted by us, monthly fee + our infrastructure cost"),
    ("On-premise / enterprise", "One-time setup / licence + recurring annual support; customer hosts servers & AI keys"),
]
for i, (a, b) in enumerate(bm):
    put(IV, f"A{6 + i}", a, F_B)
    put(IV, f"B{6 + i}", b, F_TXT)
section(IV, 11, "3-YEAR SNAPSHOT (EGP)")
for col, lab in zip("BCDE", ("Year 1", "Year 2", "Year 3", "3-Year total")):
    put(IV, f"{col}11", lab, F_HDR, fill=FILL_HDR)
snap = [
    (12, "Customers (end of year)", "SaaS_Metrics!{y}9", NUM, True),
    (13, "Revenue", "Cash_Budget!{y}10", NUM, False),
    (14, "MRR (end of year)", "SaaS_Metrics!{y}15", NUM, True),
    (15, "ARR (end of year)", "SaaS_Metrics!{y}16", NUM, True),
    (16, "Gross margin %", "SaaS_Metrics!{y}25", PCT, False),
    (17, "AI cost as % of revenue", "SaaS_Metrics!{y}21", PCT, False),
    (18, "Operating expenses", "Cash_Budget!{y}26", NUM, False),
    (19, "Net cash flow before funding (negative = burn)", "Cash_Budget!{y}31", NUM, False),
    (20, "Ending cash after planned funding", "Cash_Budget!{y}43", NUM, True),
    (21, "Team size (end of year)", "Personnel!{y}30", NUM, True),
]
for r, lab, tpl, fmt, stock in snap:
    put(IV, f"A{r}", lab, F_TXT)
    for col, y in zip("BCD", "PQR"):
        put(IV, f"{col}{r}", "=" + tpl.replace("{y}", y), F_LINK, fmt)
    put(IV, f"E{r}", ("=" + tpl.replace("{y}", "S")) if not stock else ("=" + tpl.replace("{y}", "R")), F_LINK, fmt)
section(IV, 23, "FUNDING REQUIREMENT (incl. Management Planning Buffer)")
put(IV, "B23", "EGP", F_HDR, fill=FILL_HDR)
put(IV, "C23", "USD", F_HDR, fill=FILL_HDR)
for i, (lab, r) in enumerate((("Phase 1 - Initial MVP + Validation (Y1)", 47), ("Phase 2 - Post-validation / Productization (Y2)", 48),
                              ("Phase 3 - Expansion within this model (Y3)", 49), ("Total in this model", 50))):
    put(IV, f"A{24 + i}", lab, F_B if r == 50 else F_TXT)
    put(IV, f"B{24 + i}", f"=Cash_Budget!C{r}", F_LINK_B, NUM)
    put(IV, f"C{24 + i}", f"=Cash_Budget!D{r}", F_LINK_B, USD)
put(IV, "A28", "MENA-scale expansion is NOT funded by these amounts (separate raise, costs TBD).", F_RED_B)
section(IV, 30, "BREAK-EVEN")
for i, (lab, r) in enumerate((("First quarter with positive operating cash flow", 54),
                              ("Operating break-even (stays positive)", 55),
                              ("Cash payback (cumulative cash recovered)", 56))):
    put(IV, f"A{31 + i}", lab, F_TXT)
    put(IV, f"B{31 + i}", f"=Cash_Budget!C{r}", F_LINK_B)
section(IV, 35, "KEY ASSUMPTIONS (all editable)")
ka = [
    ("Pricing (benchmarked on Market_Research)", '="Egypt EGP/month: Starter "&TEXT(Assumptions!I15,"#,##0")&", Growth "&TEXT(Assumptions!I16,"#,##0")&", Business "&TEXT(Assumptions!I17,"#,##0")&", Dedicated "&TEXT(Assumptions!I18,"#,##0")&"  |  GCC SAR/month: "&TEXT(Assumptions!J15,"#,##0")&" / "&TEXT(Assumptions!J16,"#,##0")&" / "&TEXT(Assumptions!J17,"#,##0")&" / "&TEXT(Assumptions!J18,"#,##0")'),
    ("Customer growth", '="Funnel: "&TEXT(Scenarios!F7,"0")&" founder-led leads/month, lead->demo "&TEXT(Scenarios!F10,"0%")&", demo->pilot "&TEXT(Scenarios!F11,"0%")&", pilot->paid "&TEXT(Scenarios!F12,"0%")&", churn "&TEXT(Scenarios!F13,"0.0%")&"/month"'),
    ("CAC (To Be Validated)", '="Year 2: "&TEXT(SaaS_Metrics!Q28,"#,##0")&" EGP per new customer"'),
    ("AI cost", '="Blended "&TEXT(AI_Cost!I31,"$0.00")&" per tender (standard "&TEXT(AI_Cost!I47,"$0.00")&", complex "&TEXT(AI_Cost!I48,"$0.00")&") - official API prices, 30 Sep 2026"'),
    ("Hiring", '="4 founders at "&TEXT(Assumptions!B9,"#,##0")&" EGP/month in Y1 (below-market by design), market pay by Y3; hires at Glassdoor Cairo 2026 averages, staged by customer triggers; "&TEXT(Personnel!R30,"0")&" people end of Y3"'),
    ("Infrastructure", f'="Paid servers from day one: "&TEXT(Servers_Infra!E{il + 3},"$#,##0")&"/month core tier; Enterprise capacity from Y3"'),
    ("Data sources", f'=TEXT(Data_Sources!H{last + 2},"0")&" sources publish no price and carry a USD "&TEXT(Assumptions!B29,"0")&"/month allowance (TenderGlobal Gulf proxy) - never treated as free"'),
]
for i, (a, f) in enumerate(ka):
    put(IV, f"A{36 + i}", a, F_B)
    put(IV, f"B{36 + i}", f, F_LINK)
section(IV, 44, "VALIDATION STATUS OF MAJOR ASSUMPTIONS")
for i, s in enumerate(statuses):
    put(IV, f"A{45 + i}", s, F_TXT)
    put(IV, f"B{45 + i}", f"=Assumptions_Validation!B{5 + i}", F_LINK_B, "0")
section(IV, 51, "THE ASK: 100,000 EGP - go to market in 6 months")
put(IV, "A52", "Use of funds", F_B)
put(IV, "B52", "EGP", F_HDR, fill=FILL_HDR)
put(IV, "C52", "Basis", F_HDR, fill=FILL_HDR)
uses = [("Paid cloud servers - 6 months (Y1-Q1 + Q2)", "=Cash_Budget!C21+Cash_Budget!D21", "Servers_Infra - DigitalOcean list prices"),
        ("AI processing - models + OCR, 6 months incl. pilots", "=Cash_Budget!C13+Cash_Budget!D13", "AI_Cost - official API prices"),
        ("Marketing & customer pilots (rest of the 100,000)", "=100000-B53-B54", "Marketing plan Y1-Q1 + Q2 is 16,000"),
        ("Company set-up, legal & office running costs", 0, "Covered by the founders during these 6 months"),
        ("Contingency", 0, "")]
for i, (a, v, basis) in enumerate(uses):
    put(IV, f"A{53 + i}", a, F_TXT)
    put(IV, f"B{53 + i}", v, F_CALC if str(v).startswith("=") else F_IN, NUM, FILL_Y)
    put(IV, f"C{53 + i}", basis, F_TXT)
put(IV, "A58", "Total", F_B)
put(IV, "B58", "=SUM(B53:B57)", F_CALC_B, NUM)
put(IV, "A60", "Milestones in 6 months", F_B)
ms = ["Product live online (Oracle Cloud)", "5 companies piloting on their own tenders", "First 2 paying customers",
      "50 real tenders analysed"]
for i, m in enumerate(ms):
    put(IV, f"A{61 + i}", "- " + m, F_TXT)
put(IV, "A65", "Recurring revenue of 2 Growth customers (EGP / year)", F_TXT)
put(IV, "B65", "=2*Assumptions!I16*12", F_CALC_B, NUM)
put(IV, "C65", "Egypt Growth price x 12 months", F_TXT)
put(IV, "A66", "Founders work unpaid during these 6 months; the full Year-1 plan above follows once paying customers "
              "are proven.", F_NOTE)
IV.column_dimensions["A"].width = 52
for c in "BCDE":
    IV.column_dimensions[c].width = 16

# =====================================================================================
# 18. READ_ME
RM = wb["Read_Me"]
put(RM, "B5", "Investor_Summary | Assumptions_Validation | Summary | Read_Me | Assumptions | Scenarios | Funnel | "
              "AI_Models | AI_Cost | Revenue | Data_Sources | Servers_Infra | Personnel | Assets | Security_Compliance | "
              "Marketing | Cash_Budget | SaaS_Metrics", F_TXT, wrap=True)
put(RM, "A6", "Tiered AI", F_B)
put(RM, "B6", "Every tender: primary model + OCR + small model. Complex tenders add a verification model; "
              "low-confidence tenders add a second verifier and an adjudicator (AI_Cost B20:B21).", F_TXT, wrap=True)
put(RM, "A11", "Team", F_B)
put(RM, "B11", "4 founders (Founder / MVP compensation in Y1 - below-market by design). Five hires are staged by "
               "customer triggers on Personnel. Salaries are planning assumptions.", F_TXT, wrap=True)
extra = [
    ("Scenarios", "Pick 1 Conservative / 2 Base / 3 Upside on Scenarios!B4. Upside is not the expected outcome."),
    ("Customers", "Calculated on Funnel: leads -> qualified -> demos -> pilots -> paid -> retained."),
    ("Status labels", "VALIDATED = official / published source checked; ESTIMATE = market benchmark or price range; ASSUMPTION = company decision; TBD = no public price exists. Sources on Market_Research."),
    ("TBD costs", "TBD is never treated as 0: TBD data sources and security items carry planning allowances."),
    ("Funding", "Funding is split by phase on Cash_Budget rows 47-50. It does not fund MENA-scale expansion."),
    ("Certifications", "The startup holds no ISO 27001 / SOC 2 today - only future targets."),
]
for i, (a, b) in enumerate(extra):
    put(RM, f"A{13 + i}", a, F_B)
    put(RM, f"B{13 + i}", b, F_TXT, wrap=True)

# ---------- order sheets and save
order = ["Investor_Summary", "Assumptions_Validation", "Market_Research", "Summary", "Read_Me", "Assumptions", "Scenarios", "Funnel",
         "AI_Models", "AI_Cost", "Revenue", "Data_Sources", "Servers_Infra", "Personnel", "Assets",
         "Security_Compliance", "Marketing", "Cash_Budget", "SaaS_Metrics"]
wb._sheets = [wb[n] for n in order]
wb.active = 0
for ws in wb.worksheets:
    ws.sheet_view.tabSelected = ws.title == "Investor_Summary"
wb.save(OUT)
print("saved", OUT, "DS_ROW", DS_ROW, "SI_ROW", SI_ROW, "SEC_ROW", SEC_ROW)
