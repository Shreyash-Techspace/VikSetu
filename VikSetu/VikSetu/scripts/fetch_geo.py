"""Fetch Palghar district boundary, taluka metadata, and OSM POIs into geo/."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEO = ROOT / "data" / "geo"
GEO.mkdir(parents=True, exist_ok=True)

OVERPASS = "https://overpass.kumi.systems/api/interpreter"

# Palghar district — 8 talukas (centroids approximate for labels / future shading)
TALUKAS = [
    {"id": "jawhar", "name": "Jawhar", "name_mr": "जव्हार", "centroid": [73.9167, 19.9167]},
    {"id": "mokhada", "name": "Mokhada", "name_mr": "मोखाडा", "centroid": [73.8333, 19.9667]},
    {"id": "talasari", "name": "Talasari", "name_mr": "तलासरी", "centroid": [72.7333, 20.0500]},
    {"id": "vasai", "name": "Vasai", "name_mr": "वसई", "centroid": [72.8167, 19.4700]},
    {"id": "vikramgad", "name": "Vikramgad", "name_mr": "विक्रमगड", "centroid": [73.5833, 19.8333]},
    {"id": "palghar", "name": "Palghar", "name_mr": "पालघर", "centroid": [72.7650, 19.6967]},
    {"id": "dahanu", "name": "Dahanu", "name_mr": "डहाणू", "centroid": [72.7333, 19.9667]},
    {"id": "wada", "name": "Wada", "name_mr": "वाडा", "centroid": [73.1333, 19.6500]},
]

DISTRICT_CENTER = [72.765, 19.697]


def overpass(query: str) -> dict:
    req = urllib.request.Request(
        OVERPASS,
        data=query.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def elements_to_geojson(elements: list, prop_keys: list[str]) -> dict:
    features = []
    for el in elements:
        tags = el.get("tags") or {}
        if el["type"] == "node":
            geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
        elif el["type"] == "way" and el.get("center"):
            geom = {"type": "Point", "coordinates": [el["center"]["lon"], el["center"]["lat"]]}
        else:
            continue
        props = {k: tags.get(k, "") for k in prop_keys}
        props["osm_id"] = el.get("id")
        props["name"] = tags.get("name") or tags.get("name:en") or tags.get("name:mr") or "Unnamed"
        features.append({"type": "Feature", "geometry": geom, "properties": props})
    return {"type": "FeatureCollection", "features": features}


def fetch_district_boundary() -> dict | None:
    q = """
    [out:json][timeout:120];
    area["ISO3166-2"="IN-MH"][admin_level=4]->.mh;
    area["name"="Palghar"]["admin_level"="5"](area.mh)->.a;
    rel(area.a);
    out geom;
    """
    try:
        data = overpass(q)
    except (urllib.error.URLError, TimeoutError) as e:
        print("district boundary fetch failed:", e)
        return None
    for el in data.get("elements", []):
        if el.get("type") != "relation":
            continue
        members = el.get("members") or []
        rings = []
        for m in members:
            if m.get("role") != "outer" or m.get("type") != "way":
                continue
            geom = m.get("geometry")
            if not geom:
                continue
            rings.append([[p["lon"], p["lat"]] for p in geom])
        if not rings:
            continue
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "Palghar", "admin_level": 5, "region_type": "district"},
                    "geometry": {"type": "Polygon", "coordinates": rings[:1]},
                }
            ],
        }
    return None


def fetch_pois_bbox() -> dict:
    q = """
    [out:json][timeout:90];
    (
      node["amenity"~"school|college|hospital|clinic|pharmacy|police|post_office|townhall|community_centre"](19.35,72.55,20.15,73.95);
      node["office"="government"](19.35,72.55,20.15,73.95);
    );
    out body;
    """
    try:
        data = overpass(q)
    except (urllib.error.URLError, TimeoutError) as e:
        print("  bbox POI fetch failed:", e)
        return {"type": "FeatureCollection", "features": []}
    features = []
    for el in data.get("elements", []):
        if el["type"] != "node":
            continue
        tags = el.get("tags") or {}
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [el["lon"], el["lat"]]},
                "properties": {
                    "name": tags.get("name") or tags.get("name:en") or tags.get("name:mr") or "Unnamed",
                    "category": categorize(tags),
                    "amenity": tags.get("amenity") or tags.get("office") or "poi",
                    "operator": tags.get("operator", ""),
                    "osm_id": el.get("id"),
                    "development_status": "existing",
                    "source": "openstreetmap",
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def seed_facilities_if_empty(pois: dict) -> dict:
    if pois.get("features"):
        return pois
    print("  using seeded demo facilities (OSM unreachable)")
    seeds = [
        ("ZP Palghar area school (seed)", "government_school", 72.765, 19.696),
        ("Govt school Jawhar (seed)", "government_school", 73.916, 19.917),
        ("Govt school Wada (seed)", "government_school", 73.133, 19.650),
        ("Rural hospital Palghar (seed)", "health_facility", 72.770, 19.700),
        ("PHC Dahanu (seed)", "health_facility", 72.730, 19.965),
        ("Sub-centre Mokhada (seed)", "health_facility", 73.830, 19.970),
        ("Collector office region (seed)", "government_facility", 72.768, 19.694),
        ("Police station Palghar (seed)", "government_facility", 72.762, 19.698),
        ("Post office Vasai (seed)", "government_facility", 72.817, 19.470),
        ("Community hall Talasari (seed)", "community_poi", 72.735, 20.050),
    ]
    features = []
    for name, cat, lon, lat in seeds:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "name": name,
                    "category": cat,
                    "amenity": cat,
                    "development_status": "existing",
                    "source": "seed_demo",
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def categorize(tags: dict) -> str:
    a = tags.get("amenity", "")
    if a in ("school", "college") or tags.get("school"):
        return "government_school"
    if a in ("hospital", "clinic", "pharmacy") or tags.get("healthcare"):
        return "health_facility"
    if tags.get("office") == "government" or a in ("townhall", "public_building", "police", "post_office"):
        return "government_facility"
    if a == "community_centre":
        return "community_poi"
    return "other_poi"


def build_regions_manifest(district_fc: dict | None) -> dict:
    regions = {
        "district": {
            "id": "palghar",
            "name": "Palghar",
            "name_mr": "पालघर",
            "center": DISTRICT_CENTER,
            "talukas": TALUKAS,
        },
        "talukas": [
            {
                **t,
                "region_type": "taluka",
                "development_notes": "Placeholder — link spend/works from pipeline.",
                "shading_metric": None,
            }
            for t in TALUKAS
        ],
        "layers": {
            "government_school": {"label": "Schools (OSM)", "color": "#2563eb"},
            "health_facility": {"label": "Health facilities", "color": "#dc2626"},
            "government_facility": {"label": "Govt offices & public", "color": "#7c3aed"},
            "community_poi": {"label": "Community centres", "color": "#059669"},
            "other_poi": {"label": "Other POIs", "color": "#64748b"},
            "development_ongoing": {"label": "Ongoing (sample)", "color": "#f59e0b"},
        },
    }
    if district_fc and district_fc.get("features"):
        regions["district"]["bbox"] = _bbox_from_fc(district_fc)
    return regions


def _bbox_from_fc(fc: dict) -> list[float]:
    lons, lats = [], []
    for f in fc["features"]:
        coords = f["geometry"]["coordinates"][0]
        for lon, lat in coords:
            lons.append(lon)
            lats.append(lat)
    return [min(lons), min(lats), max(lons), max(lats)]


def sample_development_pins() -> dict:
    """Demo pins for ongoing/planned — replace with MGNREGA / doc extract later."""
    samples = [
        {
            "name": "PS reported road works (taluka)",
            "taluka": "palghar",
            "status": "completed",
            "sector": "works",
            "amount_inr": 749986,
            "fy": "2024-25",
            "source": "ps_palghar_annual_report_2024_25.pdf",
            "coordinates": [72.77, 19.70],
        },
        {
            "name": "Water supply spend block",
            "taluka": "palghar",
            "status": "completed",
            "sector": "water",
            "amount_inr": 340000,
            "fy": "2024-25",
            "source": "ps_palghar_annual_report_2024_25.pdf",
            "coordinates": [72.78, 19.71],
        },
        {
            "name": "Planned: ZP budget line (OCR pending)",
            "taluka": "palghar",
            "status": "planned",
            "sector": "district_budget",
            "amount_inr": None,
            "fy": "2024-25",
            "source": "zp_budget_2024_25.pdf",
            "coordinates": [72.76, 19.69],
        },
    ]
    features = []
    for s in samples:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": s["coordinates"]},
                "properties": {k: v for k, v in s.items() if k != "coordinates"},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    print("Fetching district boundary...")
    district = fetch_district_boundary()
    if district:
        (GEO / "palghar_district.geojson").write_text(json.dumps(district, ensure_ascii=False), encoding="utf-8")
        print("  wrote palghar_district.geojson")
    else:
        # fallback bbox polygon
        b = [72.55, 19.35, 73.95, 20.15]
        district = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "Palghar (approx bbox)", "region_type": "district"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [b[0], b[1]],
                                [b[2], b[1]],
                                [b[2], b[3]],
                                [b[0], b[3]],
                                [b[0], b[1]],
                            ]
                        ],
                    },
                }
            ],
        }
        (GEO / "palghar_district.geojson").write_text(json.dumps(district), encoding="utf-8")
        print("  wrote approximate bbox district")

    print("Fetching OSM POIs...")
    pois = fetch_pois_bbox()
    pois = seed_facilities_if_empty(pois)
    (GEO / "facilities_pois.geojson").write_text(json.dumps(pois, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote facilities_pois.geojson ({len(pois['features'])} features)")

    dev = sample_development_pins()
    (GEO / "development_sites.geojson").write_text(json.dumps(dev, ensure_ascii=False), encoding="utf-8")
    print("  wrote development_sites.geojson (sample)")

    regions = build_regions_manifest(district)
    (GEO / "regions.json").write_text(json.dumps(regions, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  wrote regions.json")

    # Split POI layers for API
    by_cat: dict[str, list] = {}
    for f in pois["features"]:
        cat = f["properties"]["category"]
        by_cat.setdefault(cat, []).append(f)
    for cat, feats in by_cat.items():
        path = GEO / f"layer_{cat}.geojson"
        path.write_text(
            json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False),
            encoding="utf-8",
        )
    print("done.")


if __name__ == "__main__":
    main()
