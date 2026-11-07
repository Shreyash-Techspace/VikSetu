"""Re-clip stored POI + development layers to district polygon; strip taluka squares."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEO = ROOT / "data" / "geo"
sys.path.insert(0, str(ROOT / "backend"))

from geo_utils import (  # noqa: E402
    enrich_poi_taluka,
    filter_fc_district,
    load_district_fc,
    talukas_for_map,
)


def main() -> None:
    district_fc = load_district_fc(GEO)
    reg = json.loads((GEO / "regions.json").read_text(encoding="utf-8"))

    tal_path = GEO / "talukas.geojson"
    if tal_path.is_file():
        taluka_fc = talukas_for_map(json.loads(tal_path.read_text(encoding="utf-8")))
        tal_path.write_text(json.dumps(taluka_fc, ensure_ascii=False), encoding="utf-8")
        print(f"talukas: {len(taluka_fc['features'])} (removed placeholder squares)")
    else:
        taluka_fc = {"type": "FeatureCollection", "features": []}

    for name in ("facilities_pois.geojson", "development_sites.geojson"):
        path = GEO / name
        if not path.is_file():
            continue
        fc = json.loads(path.read_text(encoding="utf-8"))
        before = len(fc.get("features", []))
        fc = filter_fc_district(fc, district_fc)
        if name == "facilities_pois.geojson" and taluka_fc["features"]:
            fc = enrich_poi_taluka(fc, taluka_fc, reg.get("talukas", []))
        path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
        print(f"{name}: {before} -> {len(fc['features'])} inside district")

    pois = json.loads((GEO / "facilities_pois.geojson").read_text(encoding="utf-8"))
    by_cat: dict[str, list] = {}
    for f in pois["features"]:
        by_cat.setdefault(f["properties"]["category"], []).append(f)
    for cat, feats in by_cat.items():
        (GEO / f"layer_{cat}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False),
            encoding="utf-8",
        )
    print("layer_*.geojson updated")


if __name__ == "__main__":
    main()
