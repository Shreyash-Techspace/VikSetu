"""Quick sanity check on downloaded Palghar FY 2024-25 documents."""
from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF

RAW = Path(__file__).resolve().parent / "raw"

MONEY = re.compile(r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d{4,}")
FY_MARKERS = re.compile(r"2024[-–]25|2024\s*[-–]\s*25|सन\s*2024[-–]25", re.I)


def analyze_pdf(path: Path) -> dict:
    doc = fitz.open(path)
    pages = doc.page_count
    samples: list[str] = []
    money_hits = 0
    fy_hits = 0
    sector_keywords = {
        "education": 0,
        "health": 0,
        "water": 0,
        "road": 0,
        "agriculture": 0,
        "mgnrega": 0,
        "budget": 0,
        "expenditure": 0,
        "खर्च": 0,
        "अर्थसंकल्प": 0,
        "शिक्षण": 0,
        "आरोग्य": 0,
    }
    full_text_chunks: list[str] = []

    for i in range(pages):
        text = doc.load_page(i).get_text("text") or ""
        if len(text.strip()) < 30:
            continue
        full_text_chunks.append(text)
        if i < 5 or i in (pages // 4, pages // 2, pages - 1):
            samples.append(f"--- page {i + 1} ---\n{text[:800].strip()}")

    blob = "\n".join(full_text_chunks)
    money_hits = len(MONEY.findall(blob))
    fy_hits = len(FY_MARKERS.findall(blob))
    lower = blob.lower()
    for kw in list(sector_keywords.keys()):
        if kw.isascii():
            sector_keywords[kw] = lower.count(kw.lower())
        else:
            sector_keywords[kw] = blob.count(kw)

    # crude table signal: lines with multiple numeric tokens
    tableish = 0
    for line in blob.splitlines():
        nums = MONEY.findall(line)
        if len(nums) >= 3 and len(line) < 200:
            tableish += 1

    doc.close()
    char_count = len(blob)
    return {
        "file": path.name,
        "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
        "pages": pages,
        "extracted_chars": char_count,
        "ocr_likely": char_count < pages * 80,
        "money_token_count": money_hits,
        "fy_2024_25_mentions": fy_hits,
        "tableish_lines": tableish,
        "sector_keyword_hits": {k: v for k, v in sector_keywords.items() if v > 0},
        "samples": samples[:6],
    }


def main() -> None:
    pdfs = sorted(RAW.glob("*.pdf"))
    if not pdfs:
        print("No PDFs in", RAW)
        return
    for p in pdfs:
        info = analyze_pdf(p)
        print("=" * 72)
        print(f"FILE: {info['file']} ({info['size_mb']} MB, {info['pages']} pages)")
        print(
            f"Text: {info['extracted_chars']:,} chars | "
            f"FY 24-25 refs: {info['fy_2024_25_mentions']} | "
            f"numeric tokens: {info['money_token_count']} | "
            f"table-like lines: {info['tableish_lines']}"
        )
        if info["ocr_likely"]:
            print("NOTE: Low text density — may need OCR for full agent pipeline.")
        print("Sector hits:", info["sector_keyword_hits"])
        for s in info["samples"][:2]:
            print(s[:600])
            print("...")


if __name__ == "__main__":
    main()
