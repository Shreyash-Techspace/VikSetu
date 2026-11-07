"""Language mix report for files under data/."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]  # data/


def script_counts(text: str) -> tuple[int, int, int]:
    dev = len(re.findall(r"[\u0900-\u097F]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    digits = len(re.findall(r"[0-9]", text))
    return dev, lat, digits


def detect_chunks(text: str, chunk: int = 600) -> Counter:
    try:
        from langdetect import DetectorFactory, detect_langs

        DetectorFactory.seed = 0
    except ImportError:
        return Counter()

    text = re.sub(r"\s+", " ", text).strip()
    votes: Counter = Counter()
    for i in range(0, min(len(text), 20000), chunk):
        piece = text[i : i + chunk]
        if len(piece) < 50:
            continue
        try:
            langs = detect_langs(piece)
            if langs:
                votes[langs[0].lang] += 1
        except Exception:
            pass
    return votes


def analyze_file(path: Path) -> dict:
    rel = path.relative_to(ROOT)
    info: dict = {
        "path": str(rel),
        "bytes": path.stat().st_size,
        "ext": path.suffix.lower(),
    }
    if path.suffix.lower() == ".pdf":
        doc = fitz.open(path)
        info["pages"] = doc.page_count
        text = "".join(doc.load_page(i).get_text() for i in range(doc.page_count))
        doc.close()
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
        info["pages"] = None

    text_stripped = text.strip()
    info["chars"] = len(text_stripped)
    dev, lat, digits = script_counts(text_stripped)
    info["devanagari"] = dev
    info["latin"] = lat
    info["digits"] = digits
    info["langdetect"] = dict(detect_chunks(text_stripped))

    if info["ext"] == ".pdf" and info["chars"] == 0:
        info["language_label"] = "unknown (scanned PDF, no text layer yet)"
    elif dev > lat * 3:
        info["language_label"] = "primarily Devanagari (Marathi/Hindi script)"
    elif lat > dev * 3:
        info["language_label"] = "primarily English/Latin"
    elif dev > 0 and lat > 0:
        info["language_label"] = "mixed Devanagari + English"
    elif info["chars"] == 0:
        info["language_label"] = "empty / no extractable text"
    else:
        info["language_label"] = "numbers or symbols mostly"

    return info


def main() -> None:
    patterns = {".pdf", ".csv", ".md", ".json", ".txt"}
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and p.suffix.lower() in patterns)

    rows = [analyze_file(p) for p in files]

    total_bytes = sum(r["bytes"] for r in rows)
    total_chars = sum(r["chars"] for r in rows)
    total_dev = sum(r["devanagari"] for r in rows)
    total_lat = sum(r["latin"] for r in rows)
    letter_total = max(total_dev + total_lat, 1)

    agg_ld: Counter = Counter()
    for r in rows:
        agg_ld.update(r["langdetect"])

    print("=" * 72)
    print("VIKSETU DATA LANGUAGE REPORT (local files under data/)")
    print("=" * 72)
    for r in rows:
        print(f"\n{r['path']}")
        print(f"  size: {r['bytes']:,} bytes | chars extracted: {r['chars']:,}")
        if r["pages"]:
            print(f"  pages: {r['pages']}")
        print(f"  script: Devanagari {r['devanagari']:,} | Latin {r['latin']:,} | digits {r['digits']:,}")
        print(f"  label: {r['language_label']}")
        if r["langdetect"]:
            print(f"  langdetect chunk votes: {r['langdetect']}")

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"Files analyzed: {len(rows)}")
    print(f"Total size (pdf/csv/md/...): {total_bytes:,} bytes")
    print(f"Total extractable characters: {total_chars:,}")
    print(
        f"Of Devanagari+Latin letters: Devanagari {100*total_dev/letter_total:.1f}% | "
        f"Latin {100*total_lat/letter_total:.1f}%"
    )
    if agg_ld:
        print(f"Langdetect aggregate (where text exists): {dict(agg_ld.most_common())}")
    print()
    print("Important: Hindi and Marathi share Devanagari; langdetect may say hi or mr.")
    print("Scanned PDFs with 0 chars need OCR before language stats apply to full content.")


if __name__ == "__main__":
    main()
