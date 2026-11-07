"""Compute Palghar district bbox + boundary from OSM relation 9531818 (Palghar District)."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEO = ROOT / "data" / "geo"

# OpenStreetMap: Palghar District (admin_level=5), Maharashtra
PALGHAR_DISTRICT_RELATION = 9531818

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def overpass(q: str) -> dict:
    last: Exception | None = None
    body = urllib.parse.urlencode({"data": q}).encode()
    for url in OVERPASS_URLS:
        try:
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("User-Agent", "VikSetu/1.0 (education)")
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            print(f"  overpass fail ({url}): {e}")
    raise RuntimeError(f"All Overpass endpoints failed: {last}")


def nominatim_district_fc() -> tuple[dict, list[float]]:
    params = {
        "osm_ids": f"R{PALGHAR_DISTRICT_RELATION}",
        "format": "json",
        "polygon_geojson": "1",
        "polygon_threshold": "0.0",
    }
    url = "https://nominatim.openstreetmap.org/lookup?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "VikSetu/1.0 (education)"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        hits = json.loads(resp.read())
    if not hits:
        raise RuntimeError("Nominatim lookup returned no results")
    hit = hits[0]
    bb = hit["boundingbox"]  # south, north, west, east as strings
    bbox = [float(bb[2]), float(bb[0]), float(bb[3]), float(bb[1])]
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": hit.get("display_name", "Palghar District"),
                    "admin_level": 5,
                    "region_type": "district",
                    "source": "openstreetmap_relation_9531818",
                    "osm_id": PALGHAR_DISTRICT_RELATION,
                    "wikidata": "Q18003119",
                },
                "geometry": hit["geojson"],
            }
        ],
    }
    return fc, bbox


def bbox_polygon(bbox: list[float], props: dict) -> dict:
    w, s, e, n = bbox
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": props,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [w, s],
                            [e, s],
                            [e, n],
                            [w, n],
                            [w, s],
                        ]
                    ],
                },
            }
        ],
    }


def main() -> int:
    print(f"Fetching Palghar district (OSM relation {PALGHAR_DISTRICT_RELATION})...")
    try:
        district_fc, bbox = nominatim_district_fc()
        source = "openstreetmap_relation_9531818"
    except (urllib.error.URLError, TimeoutError, RuntimeError, KeyError) as e:
        print("Nominatim failed:", e)
        print("Trying Overpass geometry for bbox only...")
        q = f"[out:json][timeout:120];rel({PALGHAR_DISTRICT_RELATION});out geom;"
        data = overpass(q)
        lons, lats = [], []
        for el in data.get("elements", []):
            for m in el.get("members") or []:
                for p in m.get("geometry") or []:
                    lons.append(p["lon"])
                    lats.append(p["lat"])
        if not lons:
            print("Could not resolve district bbox from OSM.")
            return 2
        bbox = [min(lons), min(lats), max(lons), max(lats)]
        source = "openpass_bbox_only"
        district_fc = None

    w, s, e, n = bbox
    print(f"BBox [west, south, east, north]: {w:.6f}, {s:.6f}, {e:.6f}, {n:.6f}")
    print(f"Source: {source}")

    bbox_fc = bbox_polygon(
        bbox,
        {
            "name": "Palghar district bounding box",
            "region_type": "bbox",
            "source": source,
            "bbox": bbox,
            "note": "Axis-aligned minimum rectangle enclosing OSM district boundary R9531818",
        },
    )
    (GEO / "palghar_bbox.geojson").write_text(
        json.dumps(bbox_fc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("  wrote palghar_bbox.geojson")

    if district_fc:
        (GEO / "palghar_district.geojson").write_text(
            json.dumps(district_fc, ensure_ascii=False), encoding="utf-8"
        )
        print("  wrote palghar_district.geojson (OSM MultiPolygon)")

    reg_path = GEO / "regions.json"
    if reg_path.exists():
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        reg["district"]["bbox"] = bbox
        reg["district"]["bbox_source"] = source
        reg["district"]["osm_relation_id"] = PALGHAR_DISTRICT_RELATION
        reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  updated regions.json district.bbox")

    return 0


if __name__ == "__main__":
    sys.exit(main())
