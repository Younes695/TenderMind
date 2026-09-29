"""Trial data for hands-on testing (all names fictional and marked DEMO).

1. Seeds the running server (auth off, http://localhost:8001): company profile, capabilities, a team,
   two past tenders (won / lost) with RFQ quotations — so similar tenders, client history and
   suggested suppliers have something to show.
2. Writes two tender packages to demo/trial/ for you to upload through "New Tender":
   - DEMO-OBOUR-132: fits the company; contains certificates, prequalification, a contradiction,
     a words-vs-digits mismatch, a TBD value, key dates, submission items and technical sections.
   - DEMO-KUWAIT-500: 500 kV line in Kuwait — the eligibility check stops it.
Run: python scripts/make_trial_data.py
"""
import os
import sys

import requests
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

B = os.environ.get("TM_URL", "http://localhost:8001") + "/api"
OUT = os.path.join(os.path.dirname(__file__), "..", "demo", "trial")
CLIENT = "Nile Delta Power Authority (NDPA) - DEMO"


def pdf(path, pages):
    c = canvas.Canvas(path, pagesize=A4)
    for lines in pages:
        y = 800
        for ln in lines:
            c.setFont("Helvetica-Bold" if ln.isupper() and len(ln) < 70 else "Helvetica", 10)
            c.drawString(50, y, ln)
            y -= 16
        c.showPage()
    c.save()


def docx(path, paras):
    d = Document()
    for p in paras:
        d.add_paragraph(p)
    d.save(path)


def packages():
    a = os.path.join(OUT, "DEMO-OBOUR-132")
    k = os.path.join(OUT, "DEMO-KUWAIT-500")
    os.makedirs(a, exist_ok=True)
    os.makedirs(k, exist_ok=True)
    pdf(os.path.join(a, "01 Invitation and ITB.pdf"), [
        ["INVITATION TO BID - DEMO",
         f"Client: {CLIENT}",
         "Subject: Construction of El-Obour 132/11 kV GIS Substation (DEMO), Egypt",
         "The Job Explanation Meeting is scheduled as follows:",
         "Date : 20.10.2026",
         "All bids must be submitted to the Nile Delta Power Authority, as follows:",
         "Date : 15.11.2026",
         "Only firms or joint ventures prequalified and invited by NDPA may submit bids.",
         "Where a contractor is not pre-qualified for a portion of the works, such a contractor",
         "must sub-contract such portion to a pre-qualified contractor."],
        ["INSTRUCTIONS TO BIDDERS",
         "The Bidder shall be certified to ISO 9001 and ISO 45001.",
         "The Bidder shall have a minimum of 10 years of experience in similar substation works.",
         "Average annual turnover not less than EGP 300 million over the last 3 years.",
         "The Project Manager shall have a minimum of 15 years experience in GIS substations.",
         "Bids shall remain valid for 90 days from the closing date.",
         "The bid bond shall be 2% of the bid price.",
         "Bidder shall provide duly signed and stamped copy of the complete tender documents.",
         "Bidder shall provide a Quality Assurance / Quality Control Plan with the proposal.",
         "Completely filled-in Data Schedules, duly signed and stamped, shall be submitted.",
         "The Bidder shall use the format given in Appendix A for the price schedule."],
    ])
    docx(os.path.join(a, "02 General and Particular Conditions.docx"), [
        "GENERAL AND PARTICULAR CONDITIONS - DEMO",
        "This offer shall remain valid for 120 days.",
        "The performance bond shall be 10% of the Contract Price.",
        "The Advance Payment shall be fifteen percent (10%) of the Contract Price.",
        "Liquidated damages shall not exceed ten percent (10%) of the Contract Price.",
        "The warranty period is 24 months from Preliminary Acceptance.",
        "The retention amount is TBD and will be advised by the Client.",
        "Termination at the convenience of the Client may be exercised with 30 days notice.",
        "Force Majeure events shall be notified within 14 days.",
    ])
    pdf(os.path.join(a, "03 Technical Specification.pdf"), [
        ["SECTION 1 - GENERAL", "The works include the design, supply, installation and commissioning of a",
         "132/11 kV GIS substation with two 40 MVA power transformers."],
        ["SECTION 2 - 132 KV GIS SWITCHGEAR", "The GIS shall be rated 132 kV, 3150 A, 40 kA for 3 s.",
         "Equipment shall be from the Client's list of pre-qualified manufacturers.",
         "Type test reports from KEMA or CESI shall be submitted for the GIS."],
        ["SECTION 3 - POWER TRANSFORMERS", "Two 40 MVA 132/11 kV power transformers shall be supplied.",
         "The transformer manufacturer shall be certified to ISO 14001."],
        ["SECTION 4 - PROTECTION AND CONTROL", "Numerical protection relays shall be provided for all bays."],
        ["SECTION 5 - SCADA AND TELECOM", "An RTU and fibre optic communication to the national control centre."],
        ["SECTION 6 - CIVIL WORKS", "Civil works include the GIS building, foundations, cable trenches and roads."],
        ["SECTION 7 - HVAC AND FIRE FIGHTING", "HVAC and fire alarm and fire fighting systems for the building."],
    ])
    pdf(os.path.join(k, "Invitation.pdf"), [
        ["INVITATION TO BID - DEMO",
         "Client: Gulf Grid Holding - DEMO",
         "Subject: 500 kV Overhead Transmission Line (DEMO), Kuwait",
         "The Bidder shall be certified to ISO 9001.",
         "Bids shall remain valid for 120 days."],
    ])
    return a, k


def seed():
    s = requests.Session()
    ok = lambda r: r.status_code < 300 or print("  !", r.status_code, r.text[:120])
    ok(s.put(f"{B}/company-profile", json={
        "name": "Delta Grid Contracting (DEMO)", "intro": "EPC contractor for 11-220 kV substations and cables (demo data).",
        "contact_name": "Demo Manager", "contact_title": "Tender Manager", "email": "tenders@deltagrid.example",
        "phone": "+20 100 000 0000", "website": "deltagrid.example", "address": "Cairo, Egypt"}))
    ok(s.put(f"{B}/company-capability", json={
        "work_types": ["substation", "cable"], "max_kv": 220, "countries": ["Egypt", "Saudi Arabia"],
        "registrations": ["NDPA prequalified contractor"], "certifications": ["ISO 9001", "ISO 45001"],
        "years_experience": 18, "annual_turnover": 500e6, "turnover_currency": "EGP"}))
    for n, d, r in (("Omar (DEMO)", "Engineering", "Tender Manager"), ("Sara (DEMO)", "Finance", ""),
                    ("Khaled (DEMO)", "Legal", ""), ("Mona (DEMO)", "Procurement", "")):
        ok(s.post(f"{B}/team", json={"name": n, "department": d, "role": r}))
    past = [("DEMO-PAST-NDPA-01", "Sherouk 132/11 kV GIS Substation (DEMO, past)", "WON"),
            ("DEMO-PAST-NDPA-02", "Badr 66/11 kV Substation (DEMO, past)", "LOST")]
    for tid, title, outcome in past:
        ok(s.post(f"{B}/tenders", json={"id": tid, "title": title, "client": CLIENT, "location": "Egypt"}))
        ok(s.put(f"{B}/tenders/{tid}/outcome", json={"outcome": outcome}))
    for pkg, disc, quotes in (("HVAC package", "HVAC", [("CoolAir Egypt (DEMO)", 86, True), ("Breeze Systems (DEMO)", 74, False)]),
                              ("Civil works", "Civil", [("Nile Builders (DEMO)", 82, True)]),
                              ("SCADA and telecom", "SCADA", [("GridLink Systems (DEMO)", 90, True)]),
                              ("Fire fighting", "Fire", [("SafeFire (DEMO)", 80, True)])):
        r = s.post(f"{B}/tenders/{past[0][0]}/rfqs", json={"reference": f"RFQ-{disc}-DEMO", "package_name": pkg,
                                                         "discipline": disc})
        if not ok(r) and r.status_code >= 300:
            continue
        for name, fit, sel in quotes:
            q = s.post(f"{B}/rfqs/{r.json()['id']}/quotations", json={"contractor": name, "price": 1_000_000,
                                                                      "duration_weeks": 12, "technical_fit": fit,
                                                                      "payment_terms_days": 60})
            if sel and q.status_code < 300:
                s.post(f"{B}/quotations/{q.json()['id']}/select")


if __name__ == "__main__":
    a, k = packages()
    try:
        seed()
    except requests.ConnectionError:
        sys.exit("Start the server first (http://localhost:8001).")
    print("Seeded company, capabilities, team and 2 past tenders.")
    print("Upload these folders through New Tender:\n ", os.path.abspath(a), "\n ", os.path.abspath(k))
