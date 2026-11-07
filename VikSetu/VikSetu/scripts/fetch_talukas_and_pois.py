"""Fetch taluka sub-regions (OSM admin_level=6) and expanded POIs clipped to district bbox."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEO = ROOT / "data" / "geo"
sys.path.insert(0, str(ROOT / "backend"))

from geo_utils import (  # noqa: E402
    enrich_poi_taluka,
    filter_fc_district,
    get_district_bbox,
    load_district_fc,
    talukas_for_map,
)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

TALUKA_META = [
    {"id": "jawhar", "name": "Jawhar", "name_mr": "जव्हार"},
    {"id": "mokhada", "name": "Mokhada", "name_mr": "मोखाडा"},
    {"id": "talasari", "name": "Talasari", "name_mr": "तलासरी"},
    {"id": "vasai", "name": "Vasai", "name_mr": "वसई"},
    {"id": "vikramgad", "name": "Vikramgad", "name_mr": "विक्रमगड"},
    {"id": "palghar", "name": "Palghar", "name_mr": "पालघर"},
    {"id": "dahanu", "name": "Dahanu", "name_mr": "डहाणू"},
    {"id": "wada", "name": "Wada", "name_mr": "वाडा"},
]

TALUKA_COLORS = {
    "jawhar": "#f97316",
    "mokhada": "#eab308",
    "talasari": "#84cc16",
    "vasai": "#06b6d4",
    "vikramgad": "#a855f7",
    "palghar": "#3b82f6",
    "dahanu": "#14b8a6",
    "wada": "#ec4899",
}

PALGHAR_DISTRICT_REL = 9531818


def overpass(q: str) -> dict:
    body = urllib.parse.urlencode({"data": q}).encode()
    last = None
    for url in OVERPASS_URLS:
        try:
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("User-Agent", "VikSetu/1.0")
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            print(f"  overpass fail: {e}")
    raise RuntimeError(str(last))


NOMINATIM_QUERIES: dict[str, list[str]] = {
    "vasai": ["Vasai taluka, Palghar, Maharashtra", "Vasai-Virar, Palghar district, Maharashtra"],
    "wada": ["Wada taluka, Palghar, Maharashtra", "Wada, Palghar district, Maharashtra, India"],
    "mokhada": ["Mokhada taluka, Palghar, Maharashtra", "Mokhada, Palghar, Maharashtra"],
}


def nominatim_taluka(name: str, taluka_id: str) -> dict | None:
    queries = NOMINATIM_QUERIES.get(taluka_id, [f"{name} taluka, Palghar district, Maharashtra, India"])
    for q in queries:
        params = urllib.parse.urlencode(
            {"q": q, "format": "json", "polygon_geojson": "1", "limit": 1, "polygon_threshold": "0.005"}
        )
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "VikSetu/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                hits = json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError):
            continue
        if not hits:
            continue
        hit = hits[0]
        geom = hit.get("geojson")
        if not geom or geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        return {
            "type": "Feature",
            "properties": {
                "id": taluka_id,
                "name": name,
                "name_mr": next(t["name_mr"] for t in TALUKA_META if t["id"] == taluka_id),
                "region_type": "taluka",
                "source": "nominatim_osm",
                "color": TALUKA_COLORS.get(taluka_id, "#64748b"),
                "osm_type": hit.get("osm_type"),
                "osm_id": hit.get("osm_id"),
            },
            "geometry": geom,
        }
    return None


def _centroid_buffer_feature(taluka_id: str, name: str) -> dict | None:
    """Deprecated — do not draw square placeholders on the map."""
    return None


def fetch_talukas_overpass() -> list[dict]:
    q = f"""
    [out:json][timeout:120];
    rel({PALGHAR_DISTRICT_REL});
    map_to_area -> .dist;
    rel(area.dist)["admin_level"="6"]["boundary"="administrative"];
    out tags geom;
    """
    try:
        data = overpass(q)
    except RuntimeError:
        return []

    features = []
    for el in data.get("elements", []):
        if el.get("type") != "relation":
            continue
        tags = el.get("tags") or {}
        name = tags.get("name:en") or tags.get("name") or ""
        tid = _match_taluka_id(name)
        if not tid:
            continue
        geom = _relation_geom(el)
        if not geom:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": tid,
                    "name": next(t["name"] for t in TALUKA_META if t["id"] == tid),
                    "name_mr": next(t["name_mr"] for t in TALUKA_META if t["id"] == tid),
                    "region_type": "taluka",
                    "source": "openstreetmap_admin6",
                    "color": TALUKA_COLORS.get(tid, "#64748b"),
                    "osm_id": el.get("id"),
                },
                "geometry": geom,
            }
        )
    return features


def _match_taluka_id(name: str) -> str | None:
    n = name.lower().strip()
    for t in TALUKA_META:
        if t["id"] in n or t["name"].lower() in n:
            return t["id"]
    return None


def _relation_geom(el: dict) -> dict | None:
    rings: list[list[list[float]]] = []
    for m in el.get("members") or []:
        if m.get("role") != "outer" or m.get("type") != "way":
            continue
        g = m.get("geometry")
        if not g:
            continue
        rings.append([[p["lon"], p["lat"]] for p in g])
    if not rings:
        return None
    if len(rings) == 1:
        return {"type": "Polygon", "coordinates": rings}
    return {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}


def fetch_talukas() -> dict:
    features = fetch_talukas_overpass()
    print(f"  OSM admin_level=6 talukas: {len(features)}")
    found_ids = {f["properties"]["id"] for f in features}
    for t in TALUKA_META:
        if t["id"] in found_ids:
            continue
        print(f"  nominatim fallback for {t['name']}...")
        feat = nominatim_taluka(t["name"], t["id"])
        if feat:
            features.append(feat)
    return {"type": "FeatureCollection", "features": features}


def categorize(tags: dict) -> str:
    a = tags.get("amenity", "")
    if a in ("school", "college", "kindergarten", "university") or tags.get("school"):
        return "government_school"
    if a in ("hospital", "clinic", "pharmacy", "doctors", "dentist") or tags.get("healthcare"):
        return "health_facility"
    if tags.get("office") == "government" or a in (
        "townhall",
        "public_building",
        "police",
        "post_office",
        "courthouse",
        "fire_station",
        "social_facility",
        "library",
    ):
        return "government_facility"
    if a in ("community_centre", "place_of_worship", "marketplace", "bus_station", "ferry_terminal"):
        return "community_poi"
    return "other_poi"


def fetch_pois(south: float, west: float, north: float, east: float) -> dict:
    q = f"""
    [out:json][timeout:180];
    (
      node["amenity"~"school|college|kindergarten|university|hospital|clinic|pharmacy|doctors|dentist|police|post_office|townhall|community_centre|place_of_worship|marketplace|bus_station|ferry_terminal|library|social_facility|courthouse|fire_station"]({south},{west},{north},{east});
      node["office"="government"]({south},{west},{north},{east});
      node["healthcare"]({south},{west},{north},{east});
      way["amenity"~"school|hospital|college|university|clinic|place_of_worship|marketplace|bus_station"]({south},{west},{north},{east});
      way["office"="government"]({south},{west},{north},{east});
    );
    out center;
    """
    try:
        data = overpass(q)
    except RuntimeError as e:
        print("  POI overpass failed:", e)
        return {"type": "FeatureCollection", "features": []}

    features = []
    seen: set[int | str] = set()
    for el in data.get("elements", []):
        eid = el.get("id")
        if eid in seen:
            continue
        seen.add(eid)
        tags = el.get("tags") or {}
        if el["type"] == "node":
            lon, lat = el["lon"], el["lat"]
        elif el.get("center"):
            lon, lat = el["center"]["lon"], el["center"]["lat"]
        else:
            continue
        cat = categorize(tags)
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "name": tags.get("name") or tags.get("name:en") or tags.get("name:mr") or "Unnamed",
                    "category": cat,
                    "amenity": tags.get("amenity") or tags.get("office") or tags.get("healthcare") or "poi",
                    "operator": tags.get("operator", ""),
                    "osm_id": eid,
                    "osm_type": el["type"],
                    "development_status": "existing",
                    "source": "openstreetmap",
                    "data_fy": None,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def update_regions(regions_path: Path, taluka_fc: dict, bbox: list[float]) -> None:
    reg = json.loads(regions_path.read_text(encoding="utf-8"))
    reg["district"]["bbox"] = bbox
    reg["district"]["clip_policy"] = "bbox_and_taluka"
    reg["subregions"] = {
        "talukas": {
            "label": "Taluka boundaries",
            "count": len(taluka_fc["features"]),
            "geojson": "talukas.geojson",
            "description": "8 talukas — use taluka_id on POIs for automated placement",
        }
    }
    reg["layers"]["other_poi"] = {"label": "Other POIs (OSM)", "color": "#64748b"}
    reg["layers"]["taluka_regions"] = {"label": "Taluka regions", "color": "#94a3b8"}
    for t in reg.get("talukas", []):
        tid = t.get("id")
        t["color"] = TALUKA_COLORS.get(tid, "#64748b")
        match = next((f for f in taluka_fc["features"] if f["properties"].get("id") == tid), None)
        if match and match["geometry"].get("type") in ("Polygon", "MultiPolygon"):
            t["has_polygon"] = True
    regions_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    GEO.mkdir(parents=True, exist_ok=True)
    regions_path = GEO / "regions.json"
    if not regions_path.is_file():
        print("Missing regions.json — run compute_palghar_bbox.py first")
        sys.exit(1)
    reg = json.loads(regions_path.read_text(encoding="utf-8"))
    bbox = get_district_bbox(reg)
    if not bbox:
        bbox = [72.6526112, 19.286998, 73.5045111, 20.2279324]
    w, s, e, n = bbox
    print(f"District bbox: W={w} S={s} E={e} N={n}")

    print("Fetching taluka sub-regions...")
    taluka_fc = fetch_talukas()
    taluka_fc = talukas_for_map(taluka_fc)
    (GEO / "talukas.geojson").write_text(json.dumps(taluka_fc, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote talukas.geojson ({len(taluka_fc['features'])} features, no placeholder squares)")

    district_fc = load_district_fc(GEO)
    print("Fetching OSM POIs (expanded)...")
    pois = fetch_pois(s, w, n, e)
    before = len(pois["features"])
    pois = filter_fc_district(pois, district_fc)
    print(f"  raw {before} -> inside district boundary {len(pois['features'])}")
    taluka_meta = reg.get("talukas", [])
    if taluka_fc["features"]:
        pois = enrich_poi_taluka(pois, taluka_fc, taluka_meta)
        with_t = sum(1 for f in pois["features"] if f["properties"].get("taluka_id"))
        print(f"  assigned taluka_id on {with_t} pins")

    (GEO / "facilities_pois.geojson").write_text(json.dumps(pois, ensure_ascii=False), encoding="utf-8")
    by_cat: dict[str, list] = {}
    for f in pois["features"]:
        cat = f["properties"]["category"]
        by_cat.setdefault(cat, []).append(f)
    for cat, feats in by_cat.items():
        (GEO / f"layer_{cat}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False),
            encoding="utf-8",
        )
    print(f"  wrote facilities + {len(by_cat)} category layers")

    update_regions(regions_path, taluka_fc, bbox)
    print("  updated regions.json")
    print("done.")


if __name__ == "__main__":
    main()
