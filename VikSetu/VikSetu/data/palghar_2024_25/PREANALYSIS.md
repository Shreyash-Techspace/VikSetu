# Palghar FY 2024-25 — pre-analysis (sanity check)

Generated from documents in `raw/`. Not a full study; confirms material is real and agent-worthy.

## Files pulled locally

| File | Size | Machine-readable text? |
|------|------|------------------------|
| `ps_palghar_annual_report_2024_25.pdf` | ~1.5 MB, 61 pp | **Yes** — Marathi text extracts cleanly |
| `zp_budget_2024_25.pdf` | ~10 MB, 62 pp | **No** — scanned pages (image PDF); needs OCR |
| `zp_citizen_charter_mgnrega.pdf` | ~690 KB | **Scanned** — OCR needed |
| `zp_citizen_charter_finance.pdf` | ~1.9 MB | **Scanned** — OCR needed |

Live pulls attempted but failed this session: MGNREGA district portal (503), some ZP direct URLs (connection reset).

---

## Burst 1 — PS Annual Report is the star for 2024-25

**Source:** Panchayat Samiti Palghar, *वार्षिक प्रशासन अहवाल सन 2024-25*.

- Title page explicitly: **2024-25**, Palghar Panchayat Samiti.
- **36** explicit FY 2024-25 references in extracted text.
- **546** numeric tokens; sector narrative (agriculture, PMAY-G, seeds, health, etc.).

### Budget vs actual (₹ — PS consolidated table)

| Head (Marathi) | Opening budget | Final allocation | **Actual spend** |
|----------------|----------------|------------------|------------------|
| सामान्य (General) | 5,00,000 | 3,40,000 | **3,39,638** |
| शिक्षण (Education) | 30,00,000 | 0 | **0** |
| बांधकाम व दळणवळण (Works/roads) | 25,50,000 | 7,50,000 | **7,49,986** |
| सार्वजनिक आरोग्य (Health) | 3,00,000 | 0 | **0** |
| पाणी पुरवठा (Water) | 18,00,000 | 3,40,000 | **3,40,000** |
| कृषि / पशुसंवर्धन | 2,00,000 each | 0 | **0** |
| समाजकल्याण | 18,00,000 | 4,40,000 | **4,00,680** |
| दिव्यांग कल्याण | 4,50,000 | 1,10,000 | **1,08,900** |
| महिला व बालकल्याण | 9,00,000 | 2,20,000 | **0** |
| **एकुण (Total)** | **90,00,000** | **22,00,000** | **19,39,204** |

**Takeaway:** Real fiscal table — you can chart **budget vs spend by sector**, flag **education/health zero spend**, and compare **works + water** as top spenders. Multi-year history also appears (e.g. general admin spend 2021-22 → 2024-25).

---

## Burst 2 — Scheme / “what government did” (same PDF)

- **PMAY-G (2024-25):** **8,335** eligible beneficiaries listed (SC/ST/OBC breakdown); housing approval narrative for FY 2024-25.
- **Agriculture:** Kharif 2024 seed distribution (e.g. rice seed quantities in quintals), Birsa Munda scheme borewells, crop protection — **activity + quantities**, not just prose.
- **Large totals** appear in works sections (e.g. eight-digit rupee figures in project blocks) — suitable for extraction after table cleanup.

**Takeaway:** Mix of **narrative + counts + money** — good for an agent that classifies “scheme / metric / currency” fields.

---

## Burst 3 — ZP Budget 2024-25 (downloaded, harder path)

- Official **जिल्हा परिषद पालघर मूळ अर्थसंकल्प 2024-25** (~10 MB).
- **0 characters** via standard PDF text layer; **5 images on first 5 pages** → treated as **scan**.
- **Agent implication:** Same file is valid primary source, but pipeline needs **OCR (Marathi)** or **vision model** before numeric analysis. Do not skip it — it is the district-level budget counterpart to PS tables.

---

## Burst 4 — What we could not pre-analyze live (still valid for agent)

| Source | Status | Role |
|--------|--------|------|
| MGNREGA MIS Palghar 2024-25 | Portal 503 | Work-wise wages, assets — best **granular** spend |
| eGramSwaraj 2024-25 | Timeout | GP-level receipts/payments |
| Open Budgets India XLSX | Intermittent | Central schemes filtered to Palghar |

These remain in the **source manifest**; agent should **cache downloads** and retry.

---

## Verdict for your project

| Question | Answer |
|----------|--------|
| Is data real? | **Yes** — government PDFs with FY 2024-25 headers and matching numbers. |
| Can you analyze without an agent? | **Partially** — PS report works today with PDF text extraction. |
| Is it broad enough? | **Yes** — finance, works, water, welfare, housing, agriculture in one doc; ZP budget + portals add depth. |
| Good agent demo? | **Yes** — multi-format (text PDF + scanned PDF + future HTML/CSV), Marathi, tables broken across lines (normalization task). |

**Suggested first agent milestone:** ingest PS 2024-25 → emit `sector,budget,spent` CSV + one bar chart. **Second:** OCR ZP budget → reconcile totals with PS where heads overlap.

**Proof CSV (manual extract from PS report):** `derived/ps_sector_spend_2024_25.csv`

Run: `python data/palghar_2024_25/preanalyze.py`
