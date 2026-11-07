"""Build a synthetic mixed inbox for an end-to-end agent bench, and zip it.

The zip is a drop-folder: budget and development files sit next to unrelated
clutter. Numbers are seeded. This script prints the control totals. Those
totals are not written into the zip.
"""

from __future__ import annotations

import json
import random
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "bench" / "viksetu_agent_bench.zip"

TALUKAS = ["Vasai", "Palghar", "Dahanu", "Talasari", "Jawhar", "Mokhada", "Wada", "Vikramgad"]
SCALE = {
    "Vasai": 1.40,
    "Palghar": 1.15,
    "Dahanu": 1.00,
    "Talasari": 0.62,
    "Jawhar": 0.58,
    "Mokhada": 0.52,
    "Wada": 0.70,
    "Vikramgad": 0.60,
}
SECTOR_BASE = {
    "Education": 2_500_000,
    "Public health": 1_800_000,
    "Water supply": 3_200_000,
    "Roads": 2_000_000,
    "Agriculture": 900_000,
    "Women and child welfare": 700_000,
}
MONTHS = [f"2024-{m:02d}" for m in range(4, 13)] + [f"2025-{m:02d}" for m in range(1, 4)]
BBOX = (72.6526112, 19.286998, 73.5045111, 20.2279324)  # lon_min, lat_min, lon_max, lat_max
CENTROIDS = {
    "Vasai": (72.82, 19.40),
    "Palghar": (72.76, 19.70),
    "Dahanu": (72.74, 19.97),
    "Talasari": (72.85, 20.12),
    "Jawhar": (73.23, 19.91),
    "Mokhada": (73.34, 19.94),
    "Wada": (73.14, 19.65),
    "Vikramgad": (73.08, 19.78),
}
PROFILE = [
    # taluka, population, households, area_km2, literacy_pct
    ("Vasai", 1_350_000, 310_000, 364, 86),
    ("Palghar", 550_000, 125_000, 395, 81),
    ("Dahanu", 402_000, 86_000, 820, 68),
    ("Talasari", 154_000, 32_000, 270, 64),
    ("Jawhar", 140_000, 28_000, 520, 59),
    ("Mokhada", 118_000, 24_000, 450, 57),
    ("Wada", 178_000, 40_000, 230, 72),
    ("Vikramgad", 137_000, 30_000, 195, 61),
]
JJM = {
    "Vasai": 92,
    "Palghar": 88,
    "Dahanu": 71,
    "Talasari": 64,
    "Wada": 58,
    "Vikramgad": 49,
    "Jawhar": 41,
    "Mokhada": 37,
}
CLASSROOMS = {
    # sanctioned, completed
    "Vasai": (120, 117),
    "Palghar": (80, 66),
    "Dahanu": (70, 54),
    "Talasari": (36, 14),
    "Jawhar": (48, 31),
    "Mokhada": (44, 27),
    "Wada": (40, 29),
    "Vikramgad": (40, 11),
}
ROADS = {
    "Vasai": (42, 39),
    "Palghar": (38, 30),
    "Dahanu": (55, 41),
    "Talasari": (28, 16),
    "Jawhar": (36, 19),
    "Mokhada": (33, 15),
    "Wada": (30, 22),
    "Vikramgad": (34, 18),
}
VENDORS = [
    "Konkan Works Co",
    "Sahyadri Supplies",
    "Agri Input Mandli",
    "Coastal Civil",
    "Tribal Health Camp Unit",
    "Northwind Stationery",
    "Palghar Print House",
    "Wada Stone Quarry",
]


def month_budget(taluka: str, sector: str) -> int:
    return int(round(SECTOR_BASE[sector] * SCALE[taluka] / 1000.0) * 1000)


def parts(total: int, count: int, rng: random.Random) -> list[int]:
    weights = [rng.uniform(0.6, 1.4) for _ in range(count)]
    whole = sum(weights)
    raw = [int(total * weight / whole) for weight in weights]
    raw[-1] += total - sum(raw)
    if raw[-1] < 0:
        raw[0] += raw[-1]
        raw[-1] = 0
    return raw


def edu_ratio(taluka: str) -> float:
    if taluka in ("Vikramgad", "Talasari"):
        return 0.60
    if taluka == "Vasai":
        return 0.98
    return 0.86


def build_vouchers(rng: random.Random) -> list[dict]:
    rows: list[dict] = []
    serial = 1
    for taluka in TALUKAS:
        for sector in SECTOR_BASE:
            for month in MONTHS:
                budget = month_budget(taluka, sector)
                if sector == "Water supply":
                    jjm = int(round(budget * 0.70))
                    other = budget - jjm
                    groups = [("JJM-TAPS", parts(jjm, 4, rng), 0.35 if taluka in ("Jawhar", "Mokhada") else 0.84)]
                    groups.append(("WATER-OTHER", parts(other, 2, rng), 0.80))
                elif sector == "Education":
                    groups = [("SS-CLASS", parts(budget, 6, rng), edu_ratio(taluka))]
                elif sector == "Public health":
                    ratio = 1.0 if month == "2024-07" and taluka in ("Jawhar", "Mokhada") else 0.92
                    groups = [("PHC-OPS", parts(budget, 4, rng), ratio)]
                elif sector == "Women and child welfare":
                    groups = [("ICDS-NUTR", parts(budget, 3, rng), 0.78)]
                elif sector == "Roads":
                    groups = [("PMGSY", parts(budget, 4, rng), 0.88)]
                else:
                    groups = [("AGRI-EXT", parts(budget, 3, rng), 0.75)]
                for scheme, chunks, ratio in groups:
                    for chunk in chunks:
                        actual = int(round(chunk * ratio))
                        rows.append(
                            {
                                "voucher_id": f"VCH-{serial:05d}",
                                "fy": "2024-25",
                                "month": month,
                                "taluka": taluka,
                                "sector": sector,
                                "scheme": scheme,
                                "budget_inr": chunk,
                                "actual_inr": actual,
                                "vendor": rng.choice(VENDORS),
                                "invoice_no": f"INV-{serial:05d}",
                            }
                        )
                        serial += 1
                if sector == "Public health" and month == "2024-07" and taluka in ("Jawhar", "Mokhada"):
                    rows.append(
                        {
                            "voucher_id": f"VCH-{serial:05d}",
                            "fy": "2024-25",
                            "month": month,
                            "taluka": taluka,
                            "sector": sector,
                            "scheme": "HEALTH-CAMP",
                            "budget_inr": 0,
                            "actual_inr": int(round(budget * 0.85)),
                            "vendor": "Tribal Health Camp Unit",
                            "invoice_no": f"INV-{serial:05d}",
                        }
                    )
                    serial += 1
                if sector == "Women and child welfare" and month == "2024-10" and taluka == "Wada":
                    rows.append(
                        {
                            "voucher_id": f"VCH-{serial:05d}",
                            "fy": "2024-25",
                            "month": month,
                            "taluka": taluka,
                            "sector": sector,
                            "scheme": "ANG-REPAIR",
                            "budget_inr": 14 * 185_000,
                            "actual_inr": 0,
                            "vendor": "Wada Stone Quarry",
                            "invoice_no": f"INV-{serial:05d}",
                        }
                    )
                    serial += 1
    for taluka in ("Vasai", "Palghar"):
        rows.append(
            {
                "voucher_id": f"VCH-{serial:05d}",
                "fy": "2024-25",
                "month": "2024-11",
                "taluka": taluka,
                "sector": "Education",
                "scheme": "EDU-SUPPLY",
                "budget_inr": 48_600,
                "actual_inr": 48_600,
                "vendor": "Northwind Stationery",
                "invoice_no": "INV-EDU-88421",
            }
        )
        serial += 1
    return rows


def sector_totals(rows: list[dict]) -> dict[str, tuple[int, int]]:
    out: dict[str, list[int]] = {}
    for row in rows:
        slot = out.setdefault(row["sector"], [0, 0])
        slot[0] += row["budget_inr"]
        slot[1] += row["actual_inr"]
    return {key: (value[0], value[1]) for key, value in out.items()}


# --- Office and PDF writers -------------------------------------------------

def docx_bytes(paragraphs: list[str]) -> bytes:
    body = []
    for paragraph in paragraphs:
        body.append(
            "<w:p><w:r><w:t xml:space=\"preserve\">"
            + escape(paragraph)
            + "</w:t></w:r></w:p>"
        )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        + "".join(body)
        + "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
        "<w:pgMar w:top=\"1134\" w:right=\"1134\" w:bottom=\"1134\" w:left=\"1134\"/></w:sectPr>"
        "</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    return _zip_bytes(
        {
            "[Content_Types].xml": content_types,
            "_rels/.rels": rels,
            "word/document.xml": document,
        }
    )


def xlsx_bytes(sheets: list[tuple[str, list[str], list[list]]]) -> bytes:
    files: dict[str, str] = {}
    overrides = [
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    ]
    workbook_sheets = []
    rels = []
    for index, (name, headers, data) in enumerate(sheets, start=1):
        path = f"xl/worksheets/sheet{index}.xml"
        files[path] = _sheet_xml(headers, data)
        overrides.append(
            f'<Override PartName="/{path}" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        workbook_sheets.append(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>')
        rels.append(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
        )
    files["[Content_Types].xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + "".join(overrides)
        + "</Types>"
    )
    files["_rels/.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    files["xl/workbook.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + "".join(workbook_sheets)
        + "</sheets></workbook>"
    )
    files["xl/_rels/workbook.xml.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels)
        + "</Relationships>"
    )
    return _zip_bytes(files)


def _sheet_xml(headers: list[str], data: list[list]) -> str:
    rows = [_xlsx_row(1, headers)]
    for offset, record in enumerate(data, start=2):
        rows.append(_xlsx_row(offset, record))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        + "".join(rows)
        + "</sheetData></worksheet>"
    )


def _xlsx_row(index: int, values: list) -> str:
    cells = []
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            cells.append(f'<c><v>{value}</v></c>')
        else:
            cells.append(f'<c t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
    return f'<row r="{index}">{"".join(cells)}</row>'


def _zip_bytes(files: dict[str, str]) -> bytes:
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, text in files.items():
            archive.writestr(name, text.encode("utf-8"))
    return buffer.getvalue()


FONT = Path(r"C:\Windows\Fonts\Nirmala.ttc")


def pdf_bytes(title: str, lines: list[str]) -> bytes:
    """Unicode PDF. Nirmala covers Latin and Devanagari, so Hindi and Marathi survive."""
    from fpdf import FPDF

    if not FONT.exists():
        raise FileNotFoundError(f"Need a Devanagari font at {FONT}")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("Nirmala", fname=str(FONT))
    pdf.add_page()
    pdf.set_font("Nirmala", size=14)
    pdf.multi_cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Nirmala", size=11)
    for line in lines:
        pdf.multi_cell(0, 6, line if line else " ", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def csv_bytes(headers: list[str], rows: list[list]) -> bytes:
    lines = [",".join(headers)]
    for row in rows:
        cells = []
        for value in row:
            text = str(value)
            if any(mark in text for mark in ",\"\n"):
                text = '"' + text.replace('"', '""') + '"'
            cells.append(text)
        lines.append(",".join(cells))
    return ("\n".join(lines) + "\n").encode("utf-8")


def inside(lon: float, lat: float) -> bool:
    return BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]


# English key -> Hindi and Marathi. English stays the join key in every folder.
TALUKA_I18N = {
    "Vasai": {"hi": "वसई", "mr": "वसई"},
    "Palghar": {"hi": "पालघर", "mr": "पालघर"},
    "Dahanu": {"hi": "डहाणू", "mr": "डहाणू"},
    "Talasari": {"hi": "तलासरी", "mr": "तलासरी"},
    "Jawhar": {"hi": "जव्हार", "mr": "जव्हार"},
    "Mokhada": {"hi": "मोखाडा", "mr": "मोखाडा"},
    "Wada": {"hi": "वाडा", "mr": "वाडा"},
    "Vikramgad": {"hi": "विक्रमगढ़", "mr": "विक्रमगड"},
}
SECTOR_I18N = {
    "Education": {"hi": "शिक्षा", "mr": "शिक्षण"},
    "Public health": {"hi": "सार्वजनिक स्वास्थ्य", "mr": "सार्वजनिक आरोग्य"},
    "Water supply": {"hi": "जलापूर्ति", "mr": "पाणी पुरवठा"},
    "Roads": {"hi": "सड़क", "mr": "रस्ते"},
    "Agriculture": {"hi": "कृषि", "mr": "शेती"},
    "Women and child welfare": {"hi": "महिला एवं बाल कल्याण", "mr": "महिला व बालकल्याण"},
}
SCHEME_I18N = {
    "JJM-TAPS": {"hi": "जल जीवन मिशन घरेलू नल", "mr": "जल जीवन अभियान घरगुती नळ"},
    "WATER-OTHER": {"hi": "अन्य जलापूर्ति", "mr": "इतर पाणी पुरवठा"},
    "SS-CLASS": {"hi": "समग्र शिक्षा कक्षाएँ", "mr": "समग्र शिक्षा वर्गखोल्या"},
    "PHC-OPS": {"hi": "प्राथमिक स्वास्थ्य केंद्र संचालन", "mr": "प्राथमिक आरोग्य केंद्र संचालन"},
    "HEALTH-CAMP": {"hi": "स्वास्थ्य शिविर", "mr": "आरोग्य शिबिर"},
    "ICDS-NUTR": {"hi": "पोषण आहार", "mr": "पोषण आहार"},
    "PMGSY": {"hi": "प्रधानमंत्री ग्राम सड़क योजना", "mr": "प्रधानमंत्री ग्राम सडक योजना"},
    "AGRI-EXT": {"hi": "कृषि विस्तार", "mr": "कृषी विस्तार"},
    "ANG-REPAIR": {"hi": "आंगनवाड़ी मरम्मत", "mr": "अंगणवाडी दुरुस्ती"},
    "EDU-SUPPLY": {"hi": "शिक्षा सामग्री", "mr": "शिक्षण साहित्य"},
}
SCHEME_EN = {
    "JJM-TAPS": "Jal Jeevan Mission household taps",
    "WATER-OTHER": "Other water supply",
    "SS-CLASS": "Samagra Shiksha classrooms",
    "PHC-OPS": "Primary health centre operations",
    "HEALTH-CAMP": "Health camp",
    "ICDS-NUTR": "Nutrition meals",
    "PMGSY": "Rural roads",
    "AGRI-EXT": "Agriculture extension",
    "ANG-REPAIR": "Anganwadi repair",
    "EDU-SUPPLY": "Education supplies",
}
VENDOR_I18N = {
    "Konkan Works Co": {"hi": "कोंकण वर्क्स कंपनी", "mr": "कोकण वर्क्स कंपनी"},
    "Sahyadri Supplies": {"hi": "सह्याद्री सप्लाईज", "mr": "सह्याद्री सप्लायज"},
    "Agri Input Mandli": {"hi": "कृषि इनपुट मंडली", "mr": "कृषी इनपुट मंडळी"},
    "Coastal Civil": {"hi": "कोस्टल सिविल", "mr": "कोस्टल सिव्हिल"},
    "Tribal Health Camp Unit": {"hi": "आदिवासी स्वास्थ्य शिविर इकाई", "mr": "आदिवासी आरोग्य शिबिर एकक"},
    "Northwind Stationery": {"hi": "नॉर्थविंड स्टेशनरी", "mr": "नॉर्थविंड स्टेशनरी"},
    "Palghar Print House": {"hi": "पालघर प्रिंट हाउस", "mr": "पालघर प्रिंट हाउस"},
    "Wada Stone Quarry": {"hi": "वाडा स्टोन क्वारी", "mr": "वाडा स्टोन क्वारी"},
}
KIND_I18N = {
    "school": {"hi": "स्कूल", "mr": "शाळा"},
    "phc": {"hi": "प्राथमिक स्वास्थ्य केंद्र", "mr": "प्राथमिक आरोग्य केंद्र"},
    "anganwadi": {"hi": "आंगनवाड़ी", "mr": "अंगणवाडी"},
}
CONDITION_I18N = {
    "good": {"hi": "अच्छा", "mr": "चांगली"},
    "fair": {"hi": "ठीक", "mr": "मध्यम"},
    "poor": {"hi": "खराब", "mr": "खराब"},
    "critical": {"hi": "अति संवेदनशील", "mr": "अतिधोकादायक"},
}
FUNDS_I18N = {
    "none": {"hi": "कोई नहीं", "mr": "नाही"},
    "released": {"hi": "जारी", "mr": "जारी"},
    "pending": {"hi": "लंबित", "mr": "प्रलंबित"},
}
WORK_STATUS_I18N = {
    "started": {"hi": "शुरू", "mr": "सुरू"},
    "proposed": {"hi": "प्रस्तावित", "mr": "प्रस्तावित"},
}
CATEGORY_I18N = {
    "water": {"hi": "पानी", "mr": "पाणी"},
    "education": {"hi": "शिक्षा", "mr": "शिक्षण"},
    "health": {"hi": "स्वास्थ्य", "mr": "आरोग्य"},
    "roads": {"hi": "सड़क", "mr": "रस्ते"},
    "other": {"hi": "अन्य", "mr": "इतर"},
}
OPEN_I18N = {
    "open": {"hi": "खुला", "mr": "खुली"},
    "closed": {"hi": "बंद", "mr": "बंद"},
}


def tr(lang: str, table: dict, key: str) -> str:
    if lang == "en":
        return key
    return table[key][lang]


def prose(lang: str, paragraphs: list[dict]) -> list[str]:
    """One language only. A file is not repeated in a second language."""
    lines: list[str] = []
    for item in paragraphs:
        lines.append(item[lang])
        lines.append("")
    return lines


def dumps(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def render_pack(
    lang: str,
    vouchers: list[dict],
    totals: dict[str, tuple[int, int]],
    grand_budget: int,
    grand_actual: int,
    facilities: list[dict],
    works: list[dict],
    rainfall: list[list],
    complaints: list[dict],
    playlist: list[dict],
) -> dict[str, bytes]:
    def money_line(sector: str, budget: int, actual: int) -> dict:
        return {
            "hi": f"{tr('hi', SECTOR_I18N, sector)}    बजट Rs {budget:,}    वास्तविक व्यय Rs {actual:,}",
            "mr": f"{tr('mr', SECTOR_I18N, sector)}    अर्थसंकल्प Rs {budget:,}    प्रत्यक्ष खर्च Rs {actual:,}",
            "en": f"{sector}    budget Rs {budget:,}    actual Rs {actual:,}",
        }

    sector_bits = [money_line(sector, budget, actual) for sector, (budget, actual) in totals.items()]
    brief = [
        {
            "hi": "पालघर जिला नमूना बजट संक्षेप, वित्त वर्ष 2024-25।",
            "mr": "पालघर जिल्हा नमुना अर्थसंकल्प संक्षेप, आर्थिक वर्ष 2024-25.",
            "en": "Palghar district sample budget brief, FY 2024-25.",
        },
        {
            "hi": "कृत्रिम बेंच फ़ाइल। आधिकारिक लेखा नहीं।",
            "mr": "कृत्रिम बेंच फाइल. अधिकृत हिशोब नाही.",
            "en": "SYNTHETIC BENCH FILE. Not an official account.",
        },
        {
            "hi": "वाउचर रजिस्टर ही नियंत्रण है। नीचे दी सीमाएँ उसी रजिस्टर में budget_inr का योग हैं।",
            "mr": "व्हाउचर नोंदवही नियंत्रण आहे. खालील मर्यादा त्या नोंदवहीतील budget_inr ची बेरीज आहेत.",
            "en": "The voucher register is the control. Sector ceilings below are the sum of budget_inr in that register.",
        },
        *sector_bits,
        {
            "hi": f"जिला बजट Rs {grand_budget:,}। जिला वास्तविक व्यय Rs {grand_actual:,}।",
            "mr": f"जिल्हा अर्थसंकल्प Rs {grand_budget:,}. जिल्हा प्रत्यक्ष खर्च Rs {grand_actual:,}.",
            "en": f"District budget Rs {grand_budget:,}. District actual Rs {grand_actual:,}.",
        },
        {
            "hi": "तालुका की जनसंख्या, घर और क्षेत्रफल TalukaProfile शीट पर हैं। इन आंकड़ों को पुराने डैशबोर्ड उद्धरण से न बदलें।",
            "mr": "तालुक्याची लोकसंख्या, घरे आणि क्षेत्र TalukaProfile पत्रकावर आहे. हे आकडे जुन्या डॅशबोर्ड उतार्‍याने बदलू नका.",
            "en": "Taluka population, households, and area are on the TalukaProfile sheet. Do not replace these figures with an older dashboard extract.",
        },
    ]
    development = [
        {
            "hi": "पालघर जिला परिषद",
            "mr": "पालघर जिल्हा परिषद",
            "en": "Palghar Zilla Parishad",
        },
        {
            "hi": "विकास स्थिति टिप्पणी, वित्त वर्ष 2024-25 की तीसरी तिमाही",
            "mr": "विकास स्थिती टिपणी, आर्थिक वर्ष 2024-25 ची तिसरी तिमाही",
            "en": "Development status note, Q3 FY 2024-25",
        },
        {
            "hi": "यह कृत्रिम बेंच ज्ञापन है। आधिकारिक आदेश नहीं।",
            "mr": "हा कृत्रिम बेंच मजकूर आहे. अधिकृत आदेश नाही.",
            "en": "SYNTHETIC BENCH MEMO. Not an official order.",
        },
        {
            "hi": "जल जीवन मिशन में हर तालुका में घरेलू नल कनेक्शन 90 प्रतिशत से ऊपर है। योजना को लगभग पूर्ण माना जा सकता है।",
            "mr": "जल जीवन अभियानात प्रत्येक तालुक्यात घरगुती नळ कव्हरेज 90 टक्क्यांपेक्षा जास्त आहे. योजना जवळपास पूर्ण समजावी.",
            "en": "Jal Jeevan Mission household tap coverage is above 90 percent in every taluka. The scheme can be treated as substantially complete.",
        },
        {
            "hi": "हर तालुका में शिक्षा व्यय निर्धारित गति पर है। कक्षा निर्माण मंजूरी के साथ चल रहा है।",
            "mr": "प्रत्येक तालुक्यात शिक्षण खर्च ठरलेल्या गतीने आहे. वर्गखोल्या मंजुरीनुसार बांधल्या जात आहेत.",
            "en": "Education spending is on track in every taluka. Classroom construction is keeping pace with the sanctions.",
        },
        {
            "hi": "जुलाई में जव्हार और मोखाडा की स्वास्थ्य प्रतिक्रिया स्वीकृत मासिक बजट के अंदर रही। अतिरिक्त प्रावधान की जरूरत नहीं।",
            "mr": "जुलैमधील जव्हार आणि मोखाडा आरोग्य प्रतिसाद मंजूर मासिक अंदाजपत्रकात राहिला. अतिरिक्त तरतूद लागणार नाही.",
            "en": "The July health response in Jawhar and Mokhada stayed inside the sanctioned monthly budget. No extra provision is required.",
        },
        {
            "hi": "वाडा की सभी 14 असुरक्षित आंगनवाड़ियों के मरम्मत कोष अक्टूबर में जारी हो चुके हैं और काम चल रहा है।",
            "mr": "वाडा येथील सर्व 14 असुरक्षित अंगणवाड्यांचे दुरुस्ती निधी ऑक्टोबरमध्ये जारी झाला आहे आणि काम सुरू आहे.",
            "en": "Repair funds for all 14 unsafe Wada anganwadis were released in October and the work is underway.",
        },
        {
            "hi": "साथ के नक्शे पर प्रस्तावित कार्य स्थलों की जाँच हुई। सभी जिले के अंदर हैं।",
            "mr": "सोबतच्या नकाशावरील प्रस्तावित कामांची तपासणी झाली. सर्व जिल्ह्याच्या आत आहेत.",
            "en": "Proposed work sites on the accompanying map were checked. All of them fall inside the district.",
        },
        {
            "hi": "त्रैमासिक समीक्षा में यही स्थिति उद्धृत की जाए।",
            "mr": "त्रैमासिक आढाव्यात हीच स्थिती नमूद करावी.",
            "en": "This note is the status to quote in the quarterly review.",
        },
    ]
    aw_names = []
    for number in range(1, 15):
        aw_names.append(
            {
                "hi": f"वाडा आंगनवाड़ी {number:02d}",
                "mr": f"वाडा अंगणवाडी {number:02d}",
                "en": f"Wada Anganwadi {number:02d}",
            }
        )
    inspection = [
        {
            "hi": "क्षेत्र निरीक्षण टिप्पणी। वाडा तालुका आंगनवाड़ी। 18 अक्टूबर 2024।",
            "mr": "क्षेत्र तपासणी टिपणी. वाडा तालुका अंगणवाड्या. 18 ऑक्टोबर 2024.",
            "en": "Field inspection note. Wada taluka anganwadis. 18 October 2024.",
        },
        {
            "hi": "कृत्रिम बेंच फ़ाइल।",
            "mr": "कृत्रिम बेंच फाइल.",
            "en": "SYNTHETIC BENCH FILE.",
        },
        {
            "hi": "चौदह आंगनवाड़ी भवनों का निरीक्षण हुआ और उन्हें अति संवेदनशील / असुरक्षित चिह्नित किया गया।",
            "mr": "चौदा अंगणवाडी इमारतींची तपासणी झाली आणि त्या अतिधोकादायक / असुरक्षित म्हणून नोंदल्या गेल्या.",
            "en": "Fourteen anganwadi buildings were inspected and marked critical / unsafe.",
        },
        {
            "hi": "टिप्पणी कहती है कि सभी चौदह के मरम्मत कोष अक्टूबर में जारी हो गए और काम चल रहा है।",
            "mr": "टिपणी म्हणते की सर्व चौदा इमारतींचा दुरुस्ती निधी ऑक्टोबरमध्ये जारी झाला आणि काम सुरू आहे.",
            "en": "The note records that repair funds for all fourteen were released in October and that work is underway.",
        },
        {
            "hi": "भवन:",
            "mr": "इमारती:",
            "en": "Buildings:",
        },
    ]
    inspection_lines = prose(lang, inspection)
    inspection_lines += [f"- {item[lang]}" for item in aw_names]

    map_intro = [
        {
            "hi": "मानचित्र रिपोर्ट। प्रस्तावित कार्य, पालघर जिला नमूना।",
            "mr": "नकाशा अहवाल. प्रस्तावित कामे, पालघर जिल्हा नमुना.",
            "en": "Map report. Proposed works, Palghar district sample.",
        },
        {
            "hi": "कृत्रिम बेंच फ़ाइल।",
            "mr": "कृत्रिम बेंच फाइल.",
            "en": "SYNTHETIC BENCH FILE.",
        },
        {
            "hi": "proposed_works.geojson में अड़तालीस स्थल हैं।",
            "mr": "proposed_works.geojson मध्ये अठ्ठेचाळीस जागा आहेत.",
            "en": "Forty-eight sites are listed in proposed_works.geojson.",
        },
        {
            "hi": "यह रिपोर्ट कहती है कि हर स्थल की जाँच हुई है और वह देशांतर 72.65 से 73.50 तथा अक्षांश 19.29 से 20.23 के जिले के डिब्बे के अंदर है।",
            "mr": "हा अहवाल म्हणतो की प्रत्येक जागेची तपासणी झाली आहे आणि ती रेखांश 72.65 ते 73.50 आणि अक्षांश 19.29 ते 20.23 या जिल्हा चौकटीत आहे.",
            "en": "This report states that every site was checked and lies inside the district box, longitude 72.65 to 73.50 and latitude 19.29 to 20.23.",
        },
        {
            "hi": "रिपोर्ट जिन्हें जाँचा हुआ मानती है, उनके कुछ नमूने:",
            "mr": "अहवाल ज्या जागा तपासलेल्या मानतो, त्यांचे काही नमुने:",
            "en": "Sample of sites the report treats as verified:",
        },
    ]
    map_lines = prose(lang, map_intro)
    for feature in works[::8]:
        lon, lat = feature["geometry"]["coordinates"]
        props = feature["properties"]
        local_taluka = tr(lang, TALUKA_I18N, props["taluka"])
        local_sector = tr(lang, SECTOR_I18N, props["sector"])
        map_lines.append(
            f"{props['work_id']}  {local_taluka}  {local_sector}  {lon}, {lat}  Rs {props['estimated_inr']:,}"
        )

    canteen = [
        {
            "hi": "कॉलेज कैंटीन मेनू, मार्च सप्ताह 2। जिला फ़ाइल से असंबंधित।",
            "mr": "कॉलेज कॅन्टीन मेनू, मार्च आठवडा 2. जिल्हा फाइलशी संबंध नाही.",
            "en": "College canteen menu, March week 2. Unrelated to the district file.",
        },
        {"hi": "सोमवार: मिसल Rs 45, चाय Rs 10", "mr": "सोमवार: मिसळ Rs 45, चहा Rs 10", "en": "Monday: misal Rs 45, chai Rs 10"},
        {"hi": "मंगलवार: वेज पुलाव Rs 70, छाछ Rs 15", "mr": "मंगळवार: व्हेज पुलाव Rs 70, ताक Rs 15", "en": "Tuesday: veg pulao Rs 70, buttermilk Rs 15"},
        {"hi": "बुधवार: पोहा Rs 30, फ़िल्टर कॉफ़ी Rs 20", "mr": "बुधवार: पोहे Rs 30, फिल्टर कॉफी Rs 20", "en": "Wednesday: poha Rs 30, filter coffee Rs 20"},
        {"hi": "गुरुवार: थाली Rs 90", "mr": "गुरुवार: थाळी Rs 90", "en": "Thursday: thali Rs 90"},
        {"hi": "शुक्रवार: वडा पाव Rs 20, आम लस्सी Rs 40", "mr": "शुक्रवार: वडा पाव Rs 20, आंबा लस्सी Rs 40", "en": "Friday: vada pav Rs 20, mango lassi Rs 40"},
        {
            "hi": "साप्ताहिक नकद लक्ष्य Rs 18,500। यह कैंटीन का लक्ष्य है, जिला बजट नहीं।",
            "mr": "साप्ताहिक रोख लक्ष्य Rs 18,500. हे कॅन्टीनचे लक्ष्य आहे, जिल्हा अर्थसंकल्प नाही.",
            "en": "Weekly cash target Rs 18,500. This is a canteen target, not a district budget.",
        },
    ]
    fest = [
        {"hi": "छात्र परिषद परिपत्र। असंबंधित।", "mr": "विद्यार्थी परिषद परिपत्रक. संबंध नाही.", "en": "Student council circular. Unrelated."},
        {"hi": "वार्षिक उत्सव, 12 से 14 मार्च। मुख्य मैदान।", "mr": "वार्षिक सण, 12 ते 14 मार्च. मुख्य मैदान.", "en": "Annual fest, 12 to 14 March. Main ground."},
        {
            "hi": "सांस्कृतिक बजट Rs 85,000। पूर्व छात्र समूह से प्रायोजन माँगा गया है।",
            "mr": "सांस्कृतिक अर्थसंकल्प Rs 85,000. माजी विद्यार्थी गटाकडे प्रायोजकत्व मागितले आहे.",
            "en": "Cultural budget Rs 85,000. Sponsorship asked from the alumni group.",
        },
        {
            "hi": "यह परिपत्र पालघर की विकास योजना नहीं है।",
            "mr": "हे परिपत्रक पालघरची विकास योजना नाही.",
            "en": "This circular is not a Palghar development scheme.",
        },
    ]
    cover = prose(
        lang,
        [
            {
                "hi": "एजेंट बेंच के लिए कृत्रिम मिश्रित इनबॉक्स। आधिकारिक पालघर लेखा नहीं।",
                "mr": "एजंट बेंचसाठी कृत्रिम मिश्र इनबॉक्स. अधिकृत पालघर हिशोब नाही.",
                "en": "Synthetic mixed inbox for an agent bench. Not official Palghar accounts.",
            },
            {
                "hi": "कुछ फ़ाइलें बजट, विकास, निरीक्षण और नक्शा हैं। कुछ उसी ड्रॉप में आई असंबंधित सामग्री हैं।",
                "mr": "काही फाइल्स अर्थसंकल्प, विकास, तपासणी आणि नकाशा आहेत. काही त्याच ड्रॉपमधील असंबंधित गोंधळ आहेत.",
                "en": "Some files are district budget, development, inspection, and map material. Some are unrelated clutter that landed in the same drop.",
            },
            {
                "hi": "हिंदी और मराठी फ़ोल्डर में हर वाक्य या कॉलम के साथ अंग्रेज़ी रूप भी है। अंक, चालान संख्या और निर्देशांक तीनों भाषाओं में समान हैं।",
                "mr": "हिंदी आणि मराठी फोल्डरमध्ये प्रत्येक वाक्यासोबत किंवा स्तंभासोबत इंग्रजी रूप आहे. आकडे, चलन क्रमांक आणि निर्देशांक तीनही भाषांत सारखे आहेत.",
                "en": "The Hindi and Marathi folders carry the same text again in English. Numbers, invoice ids, and coordinates match across all three languages.",
            },
            {
                "hi": "काम यह है कि तय करें क्या मायने रखता है, ज्ञापन को तालिका से मिलाएँ, और बताएँ आंकड़े क्या कहते हैं। इस ज़िप में उत्तर तालिका नहीं है।",
                "mr": "काम हे आहे की काय महत्त्वाचे ते ठरवा, टिपणी तक्त्याशी तपासा, आणि आकडे काय सांगतात ते मांडा. या झिपमध्ये उत्तरतालिका नाही.",
                "en": "The task is an end-to-end read: decide what matters, check the memos against the tables, and say what the figures show. There is no answer sheet in this zip.",
            },
        ],
    )

    if lang == "en":
        voucher_headers = list(vouchers[0].keys())
        voucher_rows = [[row[key] for key in voucher_headers] for row in vouchers]
        profile_headers = ["taluka", "population", "households", "area_km2", "literacy_pct"]
        profile_rows = [list(row) for row in PROFILE]
        coverage_headers = [
            "taluka",
            "households",
            "jjm_coverage_pct",
            "classrooms_sanctioned",
            "classrooms_completed",
            "road_km_sanctioned",
            "road_km_completed",
        ]
        coverage_rows = []
        for taluka, _pop, households, _area, _lit in PROFILE:
            sanctioned, completed = CLASSROOMS[taluka]
            road_s, road_c = ROADS[taluka]
            coverage_rows.append([taluka, households, JJM[taluka], sanctioned, completed, road_s, road_c])
        rain_headers = ["taluka", "month", "rainfall_mm"]
        rain_rows = rainfall
    else:
        voucher_headers = [
            "voucher_id",
            "fy",
            "month",
            "taluka",
            "sector",
            "scheme",
            "scheme_name",
            "budget_inr",
            "actual_inr",
            "vendor",
            "invoice_no",
        ]
        voucher_rows = [
            [
                row["voucher_id"],
                row["fy"],
                row["month"],
                tr(lang, TALUKA_I18N, row["taluka"]),
                tr(lang, SECTOR_I18N, row["sector"]),
                row["scheme"],
                tr(lang, SCHEME_I18N, row["scheme"]),
                row["budget_inr"],
                row["actual_inr"],
                tr(lang, VENDOR_I18N, row["vendor"]),
                row["invoice_no"],
            ]
            for row in vouchers
        ]
        profile_headers = ["taluka", "population", "households", "area_km2", "literacy_pct"]
        profile_rows = [
            [tr(lang, TALUKA_I18N, taluka), pop, households, area, lit]
            for taluka, pop, households, area, lit in PROFILE
        ]
        coverage_headers = [
            "taluka",
            "households",
            "jjm_coverage_pct",
            "classrooms_sanctioned",
            "classrooms_completed",
            "road_km_sanctioned",
            "road_km_completed",
        ]
        coverage_rows = []
        for taluka, _pop, households, _area, _lit in PROFILE:
            sanctioned, completed = CLASSROOMS[taluka]
            road_s, road_c = ROADS[taluka]
            coverage_rows.append(
                [tr(lang, TALUKA_I18N, taluka), households, JJM[taluka], sanctioned, completed, road_s, road_c]
            )
        rain_headers = ["taluka", "month", "rainfall_mm"]
        rain_rows = [[tr(lang, TALUKA_I18N, taluka), month, mm] for taluka, month, mm in rainfall]

    def facility_out(item: dict) -> dict:
        en_name = item["name"]
        if item["facility_id"].startswith("AW-WADA-"):
            number = int(item["facility_id"].rsplit("-", 1)[-1])
            local_name = aw_names[number - 1][lang]
            en_label = aw_names[number - 1]["en"]
        else:
            serial = int(item["facility_id"].split("-")[1])
            gps = en_name.endswith("(gps)")
            suffix = "" if lang == "en" or not gps else " (जीपीएस)"
            en_suffix = " (gps)" if gps else ""
            local_name = f"{tr(lang, TALUKA_I18N, item['taluka'])} {tr(lang, KIND_I18N, item['kind'])} {serial}{suffix}"
            en_label = f"{item['taluka']} {item['kind']} {serial}{en_suffix}"
        record = {
            "facility_id": item["facility_id"],
            "name": local_name if lang != "en" else en_label,
            "taluka": tr(lang, TALUKA_I18N, item["taluka"]),
            "kind": tr(lang, KIND_I18N, item["kind"]),
            "condition": tr(lang, CONDITION_I18N, item["condition"]),
            "funds_status": tr(lang, FUNDS_I18N, item["funds_status"]),
            "actual_spend_inr": item["actual_spend_inr"],
            "lon": item["lon"],
            "lat": item["lat"],
        }
        if item.get("last_inspection"):
            record["last_inspection"] = item["last_inspection"]
        return record

    def work_feature(feature: dict) -> dict:
        props = feature["properties"]
        local_props = {
            "work_id": props["work_id"],
            "name": f"{tr(lang, TALUKA_I18N, props['taluka'])} {tr(lang, SECTOR_I18N, props['sector'])} "
            + ("स्थल " if lang == "hi" else "जागा " if lang == "mr" else "site ")
            + props["work_id"].split("-")[1].lstrip("0"),
            "taluka": tr(lang, TALUKA_I18N, props["taluka"]),
            "sector": tr(lang, SECTOR_I18N, props["sector"]),
            "estimated_inr": props["estimated_inr"],
            "status": tr(lang, WORK_STATUS_I18N, props["status"]),
        }
        return {"type": "Feature", "properties": local_props, "geometry": feature["geometry"]}

    localized_complaints = []
    for item in complaints:
        record = {
            "complaint_id": item["complaint_id"],
            "month": item["month"],
            "taluka": tr(lang, TALUKA_I18N, item["taluka"]),
            "category": tr(lang, CATEGORY_I18N, item["category"]),
            "status": tr(lang, OPEN_I18N, item["status"]),
            "days_open": item["days_open"],
        }
        localized_complaints.append(record)

    localized_playlist = []
    for item in playlist:
        number = item["title"].split()[-1]
        title = {"hi": f"ट्रैक {number}", "mr": f"ट्रॅक {number}", "en": item["title"]}[lang]
        record = {"title": title, "artist": item["artist"], "duration_sec": item["duration_sec"]}
        localized_playlist.append(record)

    if lang == "en":
        laptop_headers = ["model", "ram_gb", "price_inr", "seller"]
        laptop_rows = [
            ["Lenovo V15", 8, 38990, "Campus Store"],
            ["HP 15s", 16, 52490, "Campus Store"],
            ["Dell Inspiron", 8, 44990, "Online"],
        ]
    else:
        seller = {"hi": ("कैंपस स्टोर", "ऑनलाइन"), "mr": ("कॅम्पस स्टोअर", "ऑनलाइन")}[lang]
        laptop_headers = ["model", "ram_gb", "price_inr", "seller"]
        laptop_rows = [
            ["Lenovo V15", 8, 38990, seller[0]],
            ["HP 15s", 16, 52490, seller[0]],
            ["Dell Inspiron", 8, 44990, seller[1]],
        ]

    scratch_note = {
        "hi": "मुझे लगता है पालघर का पूरा वित्त वर्ष 2024-25 वास्तविक व्यय Rs 19,39,204 है। यह अंक मैंने एक बार डैशबोर्ड पर देखा था।",
        "mr": "मला वाटते पालघरचा संपूर्ण आर्थिक वर्ष 2024-25 प्रत्यक्ष खर्च Rs 19,39,204 आहे. हा आकडा मी एकदा डॅशबोर्डवर पाहिला होता.",
        "en": "I think the whole Palghar FY 2024-25 actual spend is Rs 19,39,204. I saw that number on a dashboard once.",
    }
    scratch_todos = {
        "hi": ["दूध लाना", "पुस्तकालय की किताब लौटाना", "ड्रिल चार्ज करना"],
        "mr": ["दूध आणणे", "ग्रंथालयाचे पुस्तक परत करणे", "ड्रिल चार्ज करणे"],
        "en": ["buy milk", "return the library book", "charge the drill"],
    }
    scratch = {"todos": scratch_todos[lang], "note": scratch_note[lang]}

    cricket = {
        "hi": "रविवार की दोस्ताना, असंबंधित",
        "mr": "रविवारची मैत्रीपूर्ण, संबंध नाही",
        "en": "Sunday friendly, unrelated",
    }
    sides = {
        "hi": ("पुस्तकालय इलेवन", "कैंटीन इलेवन"),
        "mr": ("ग्रंथालय इलेवन", "कॅन्टीन इलेवन"),
        "en": ("Library XI", "Canteen XI"),
    }
    cricket_doc = {
        "match": cricket[lang],
        "innings": [
            {"side": sides[lang][0], "runs": 142, "wickets": 7},
            {"side": sides[lang][1], "runs": 139, "wickets": 9},
        ],
    }

    partial_rows = [
        row for row in vouchers if row["taluka"] == "Vasai" and row["sector"] == "Education" and row["month"] == "2024-04"
    ]
    partial_label = {
        "hi": "वसई शिक्षा, केवल अप्रैल 2024",
        "mr": "वसई शिक्षण, फक्त एप्रिल 2024",
        "en": "Vasai education, April 2024 only",
    }
    partial_warn = {
        "hi": "आंशिक निर्यात। जिला योग नहीं।",
        "mr": "अर्धवट निर्यात. जिल्हा बेरीज नाही.",
        "en": "Partial export. Not the district total.",
    }
    partial = {"extract": partial_label[lang], "warning": partial_warn[lang], "rows": partial_rows if lang == "en" else voucher_rows_for_partial(lang, partial_rows)}

    titles = {
        "brief": {"hi": "बजट संक्षेप वित्त वर्ष 2024-25", "mr": "अर्थसंकल्प संक्षेप आर्थिक वर्ष 2024-25", "en": "Budget brief FY 2024-25"},
        "inspect": {"hi": "वाडा आंगनवाड़ी निरीक्षण", "mr": "वाडा अंगणवाडी तपासणी", "en": "Wada anganwadi inspection"},
        "map": {"hi": "प्रस्तावित कार्य मानचित्र रिपोर्ट", "mr": "प्रस्तावित कामे नकाशा अहवाल", "en": "Proposed works map report"},
        "fest": {"hi": "कॉलेज उत्सव परिपत्र", "mr": "कॉलेज सण परिपत्रक", "en": "College fest circular"},
    }
    geo_name = {
        "hi": "पालघर प्रस्तावित कार्य नमूना",
        "mr": "पालघर प्रस्तावित कामे नमुना",
        "en": "Palghar proposed works sample",
    }

    return {
        "COVER.txt": ("\n".join(cover) + "\n").encode("utf-8"),
        "budget/Palghar_FY2024-25_vouchers.xlsx": xlsx_bytes(
            [("Vouchers", voucher_headers, voucher_rows), ("TalukaProfile", profile_headers, profile_rows)]
        ),
        "budget/Budget_Brief_FY2024-25.pdf": pdf_bytes(titles["brief"][lang], prose(lang, brief)),
        "budget/partial_export_vasai_education_april.json": dumps(partial),
        "development/Q3_Development_Status.docx": docx_bytes(prose(lang, development)),
        "development/scheme_coverage.xlsx": xlsx_bytes([("Coverage", coverage_headers, coverage_rows)]),
        "inspections/Wada_Anganwadi_Inspection.pdf": pdf_bytes(titles["inspect"][lang], inspection_lines),
        "facilities/facility_register.json": dumps([facility_out(item) for item in facilities]),
        "map/proposed_works.geojson": dumps(
            {"type": "FeatureCollection", "name": geo_name[lang], "features": [work_feature(feature) for feature in works]}
        ),
        "map/Proposed_Works_Map_Report.pdf": pdf_bytes(titles["map"][lang], map_lines),
        "ops/monthly_rainfall.csv": csv_bytes(rain_headers, rain_rows),
        "ops/citizen_complaints.json": dumps(localized_complaints),
        "noise/Canteen_Menu_March.docx": docx_bytes(prose(lang, canteen)),
        "noise/College_Fest_Circular.pdf": pdf_bytes(titles["fest"][lang], prose(lang, fest)),
        "noise/monsoon_playlist.json": dumps(localized_playlist),
        "noise/laptop_quotes.xlsx": xlsx_bytes([("Quotes", laptop_headers, laptop_rows)]),
        "noise/scratch_notes.json": dumps(scratch),
        "noise/sunday_cricket.json": dumps(cricket_doc),
    }


def voucher_rows_for_partial(lang: str, rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        item = dict(row)
        item["taluka"] = tr(lang, TALUKA_I18N, row["taluka"])
        item["sector"] = tr(lang, SECTOR_I18N, row["sector"])
        item["vendor"] = tr(lang, VENDOR_I18N, row["vendor"])
        item["scheme_name"] = tr(lang, SCHEME_I18N, row["scheme"])
        out.append(item)
    return out


def main() -> None:
    rng = random.Random(202425)
    vouchers = build_vouchers(rng)
    totals = sector_totals(vouchers)
    grand_budget = sum(pair[0] for pair in totals.values())
    grand_actual = sum(pair[1] for pair in totals.values())

    facilities = []
    serial = 1
    for taluka, lon, lat in ((name, *CENTROIDS[name]) for name in TALUKAS):
        for kind, count in (("school", 28), ("phc", 6), ("anganwadi", 22)):
            for _ in range(count):
                point_lon = min(BBOX[2] - 0.01, max(BBOX[0] + 0.01, lon + rng.uniform(-0.08, 0.08)))
                point_lat = min(BBOX[3] - 0.01, max(BBOX[1] + 0.01, lat + rng.uniform(-0.06, 0.06)))
                facilities.append(
                    {
                        "facility_id": f"FAC-{serial:04d}",
                        "name": f"{taluka} {kind} {serial}",
                        "taluka": taluka,
                        "kind": kind,
                        "condition": rng.choice(["good", "good", "fair", "fair", "poor"]),
                        "funds_status": "none",
                        "actual_spend_inr": 0,
                        "lon": round(point_lon, 5),
                        "lat": round(point_lat, 5),
                    }
                )
                serial += 1
    # Six schools with coordinates copied from outside the district.
    for index, facility in enumerate(facilities[:6]):
        facility["lon"] = round(74.80 + index * 0.05, 5)
        facility["lat"] = round(18.40 + index * 0.03, 5)
        facility["name"] = facility["name"] + " (gps)"
    wada_repairs = []
    for number in range(1, 15):
        record = {
            "facility_id": f"AW-WADA-{number:02d}",
            "name": f"Wada Anganwadi {number:02d}",
            "taluka": "Wada",
            "kind": "anganwadi",
            "condition": "critical",
            "funds_status": "released" if number <= 3 else "pending",
            "actual_spend_inr": 0,
            "lon": round(CENTROIDS["Wada"][0] + number * 0.004, 5),
            "lat": round(CENTROIDS["Wada"][1] + number * 0.003, 5),
            "last_inspection": "2024-10-18",
        }
        facilities.append(record)
        wada_repairs.append(record["name"])

    works = []
    for number in range(1, 49):
        taluka = TALUKAS[(number - 1) % len(TALUKAS)]
        lon, lat = CENTROIDS[taluka]
        lon += ((number % 5) - 2) * 0.03
        lat += ((number % 3) - 1) * 0.025
        if number >= 43:
            lon = 75.20 + (number - 43) * 0.08
            lat = 18.55
        sector = ["Education", "Water supply", "Roads", "Public health"][number % 4]
        works.append(
            {
                "type": "Feature",
                "properties": {
                    "work_id": f"PW-{number:03d}",
                    "name": f"{taluka} {sector} site {number}",
                    "taluka": taluka,
                    "sector": sector,
                    "estimated_inr": 250_000 + number * 17_500,
                    "status": "started" if number % 4 == 0 else "proposed",
                },
                "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
            }
        )
    outside = [
        feature["properties"]["work_id"]
        for feature in works
        if not inside(feature["geometry"]["coordinates"][0], feature["geometry"]["coordinates"][1])
    ]
    geojson = {"type": "FeatureCollection", "name": "Palghar proposed works sample", "features": works}

    rainfall = []
    normals = [8, 6, 140, 620, 480, 280, 90, 40, 20, 15, 10, 12]
    for month, normal in zip(MONTHS, normals):
        for taluka in TALUKAS:
            mm = normal * rng.uniform(0.85, 1.15)
            if month == "2024-07" and taluka in ("Jawhar", "Mokhada"):
                mm = normal * (2.55 if taluka == "Jawhar" else 2.70)
            rainfall.append([taluka, month, round(mm, 1)])

    complaints = []
    for number in range(1, 2401):
        taluka = rng.choice(TALUKAS)
        month = rng.choice(MONTHS)
        roll = rng.random()
        if taluka in ("Jawhar", "Mokhada") and month in ("2024-07", "2024-08") and roll < 0.72:
            category = "water"
        elif taluka in ("Vikramgad", "Talasari") and roll < 0.55:
            category = "education"
        else:
            category = rng.choice(["water", "education", "health", "roads", "other"])
        stuck = category == "water" and taluka in ("Jawhar", "Mokhada") and roll < 0.45
        complaints.append(
            {
                "complaint_id": f"CMP-{number:05d}",
                "month": month,
                "taluka": taluka,
                "category": category,
                "status": "open" if stuck or rng.random() < 0.18 else "closed",
                "days_open": rng.randint(40, 160) if stuck else rng.randint(2, 40),
            }
        )

    playlist = [
        {"title": f"Track {number:03d}", "artist": rng.choice(["Asha", "Ravi", "Meera", "Local Band"]), "duration_sec": rng.randint(140, 320)}
        for number in range(1, 201)
    ]
    packs = {
        lang: render_pack(
            lang, vouchers, totals, grand_budget, grand_actual, facilities, works, rainfall, complaints, playlist
        )
        for lang in ("en", "hi", "mr")
    }
    # One copy of each file. The language is the only text in that file.
    chosen = {
        "budget/Palghar_FY2024-25_vouchers.xlsx": "hi",
        "budget/Budget_Brief_FY2024-25.pdf": "mr",
        "budget/partial_export_vasai_education_april.json": "en",
        "development/Q3_Development_Status.docx": "hi",
        "development/scheme_coverage.xlsx": "mr",
        "inspections/Wada_Anganwadi_Inspection.pdf": "mr",
        "facilities/facility_register.json": "hi",
        "map/proposed_works.geojson": "en",
        "map/Proposed_Works_Map_Report.pdf": "hi",
        "ops/monthly_rainfall.csv": "mr",
        "ops/citizen_complaints.json": "en",
        "noise/Canteen_Menu_March.docx": "hi",
        "noise/College_Fest_Circular.pdf": "mr",
        "noise/monsoon_playlist.json": "en",
        "noise/laptop_quotes.xlsx": "hi",
        "noise/scratch_notes.json": "mr",
        "noise/sunday_cricket.json": "en",
    }
    cover = "\n".join(
        [
            "Synthetic Palghar inbox. Each file is in one language only. There is no second copy.",
            "Hindi: voucher register, Q3 development note, facility register, map report, canteen menu, laptop quotes.",
            "Marathi: budget brief, scheme coverage, Wada inspection, rainfall, college fest circular, scratch note.",
            "English: April Vasai education extract, proposed-works map, citizen complaints, playlist, cricket scores.",
            "Ids, months, rupee amounts, and coordinates are the same kind of values in every file.",
            "",
        ]
    )
    files = {"COVER.txt": cover.encode("utf-8")}
    for name, lang in chosen.items():
        files[name] = packs[lang][name]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, blob in files.items():
            archive.writestr(name, blob)

    july = [
        row
        for row in vouchers
        if row["month"] == "2024-07" and row["sector"] == "Public health" and row["taluka"] in ("Jawhar", "Mokhada")
    ]
    edu = {}
    for taluka in ("Vikramgad", "Talasari", "Vasai"):
        subset = [row for row in vouchers if row["sector"] == "Education" and row["taluka"] == taluka]
        budget = sum(row["budget_inr"] for row in subset)
        actual = sum(row["actual_inr"] for row in subset)
        edu[taluka] = {"budget": budget, "actual": actual, "ratio": round(actual / budget, 3)}
    repair = next(row for row in vouchers if row["scheme"] == "ANG-REPAIR")
    print(
        json.dumps(
            {
                "zip": str(OUT),
                "bytes": OUT.stat().st_size,
                "files": len(files),
                "vouchers": len(vouchers),
                "facilities": len(facilities),
                "complaints": len(complaints),
                "works": len(works),
                "works_outside_bbox": outside,
                "facilities_outside_bbox": sum(1 for item in facilities if not inside(item["lon"], item["lat"])),
                "grand_budget": grand_budget,
                "grand_actual": grand_actual,
                "sectors": {key: {"budget": value[0], "actual": value[1]} for key, value in totals.items()},
                "july_health_jawhar_mokhada": {
                    "budget": sum(row["budget_inr"] for row in july),
                    "actual": sum(row["actual_inr"] for row in july),
                },
                "education": edu,
                "anganwadi_repair": {"budget": repair["budget_inr"], "actual": repair["actual_inr"]},
                "duplicate_invoice": "INV-EDU-88421",
                "jjm_below_90": {key: value for key, value in JJM.items() if value < 90},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
