"""Build poi_cards.json (agent reference) and embed pin_id + links on GeoJSON features."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEO = ROOT / "data" / "geo"
OVERRIDES = GEO / "poi_overrides.json"
CARDS = GEO / "poi_cards.json"

CATEGORY_LABEL = {
    "government_school": "Government school (OSM)",
    "health_facility": "Health facility",
    "government_facility": "Government / public facility",
    "community_poi": "Community / transport / faith POI",
    "other_poi": "Other point of interest",
    "development": "Development / works site",
}


def slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s[:48] or "site"


def pin_id_for(props: dict, layer: str, idx: int) -> str:
    if props.get("pin_id"):
        return str(props["pin_id"])
    osm_id = props.get("osm_id")
    osm_type = props.get("osm_type") or "node"
    if osm_id is not None:
        return f"osm-{osm_type}-{osm_id}"
    if layer == "development":
        return f"dev-{slug(props.get('name', 'site'))}-{idx}"
    return f"{layer}-{slug(props.get('name', 'unnamed'))}-{idx}"


def google_directions(lat: float, lon: float, name: str) -> str:
    q = f"{name}@{lat},{lon}" if name else f"{lat},{lon}"
    from urllib.parse import quote

    return f"https://www.google.com/maps/dir/?api=1&destination={quote(q)}"


def google_place(lat: float, lon: float, name: str) -> str:
    from urllib.parse import quote

    return f"https://www.google.com/maps/search/?api=1&query={quote(name)}&query={lat},{lon}"


def default_card(
    pin_id: str,
    props: dict,
    lon: float,
    lat: float,
    layer: str,
) -> dict:
    name = props.get("name") or "Unnamed site"
    cat = props.get("category") or layer
    amenity = props.get("amenity") or ""
    operator = props.get("operator") or ""
    taluka = props.get("taluka_id") or ""
    desc_parts = [CATEGORY_LABEL.get(cat, cat.replace("_", " "))]
    if amenity:
        desc_parts.append(f"Type: {amenity}.")
    if operator:
        desc_parts.append(f"Operator: {operator}.")
    if taluka:
        desc_parts.append(f"Taluka: {taluka.title()}.")
    desc_parts.append("Location verified via OpenStreetMap inside Palghar district.")
    description = " ".join(desc_parts)

    fy_history = [
        {
            "fy": "2024-25",
            "status": props.get("development_status") or props.get("status") or "reported_operating",
            "spend_inr": props.get("amount_inr"),
            "notes": props.get("sector")
            and f"Sector tag: {props.get('sector')}."
            or "No Panchayat Samiti line-item linked to this pin yet.",
            "source_doc": props.get("source") or "openstreetmap",
        },
        {
            "fy": "2023-24",
            "status": "not_in_dataset",
            "spend_inr": None,
            "notes": "Add historical row in poi_overrides.json when ZP/PS data is available.",
            "source_doc": None,
        },
    ]

    if layer == "development" and props.get("fy"):
        fy_history[0]["fy"] = str(props["fy"])
        fy_history[0]["notes"] = (
            f"{props.get('status', 'unknown')} — {props.get('sector', 'works')} "
            f"from {props.get('source', 'document')}."
        )
        if props.get("amount_inr"):
            fy_history[0]["spend_inr"] = props["amount_inr"]

    return {
        "pin_id": pin_id,
        "name": name,
        "category": cat,
        "layer": layer,
        "description": description,
        "coordinates": [lon, lat],
        "taluka_id": taluka or None,
        "amenity": amenity or None,
        "operator": operator or None,
        "osm_id": props.get("osm_id"),
        "sources": list({props.get("source") or "openstreetmap", "viksetu_card_builder"}),
        "google_maps_directions_url": google_directions(lat, lon, name),
        "google_maps_place_url": google_place(lat, lon, name),
        "fy_history": fy_history,
        "agent_summary": (
            f"{name} ({CATEGORY_LABEL.get(cat, cat)}) in {taluka or 'Palghar district'}. "
            f"{description} FY 2024-25: {fy_history[0]['notes']}"
        ),
    }


def load_overrides() -> dict:
    if not OVERRIDES.is_file():
        return {}
    return json.loads(OVERRIDES.read_text(encoding="utf-8")).get("pins", {})


def merge_override(card: dict, override: dict) -> dict:
    out = {**card, **{k: v for k, v in override.items() if k != "fy_history"}}
    if override.get("fy_history"):
        by_fy = {h["fy"]: h for h in card.get("fy_history", [])}
        for row in override["fy_history"]:
            by_fy[row["fy"]] = {**by_fy.get(row["fy"], {}), **row}
        out["fy_history"] = sorted(by_fy.values(), key=lambda x: x["fy"], reverse=True)
    if override.get("agent_summary"):
        out["agent_summary"] = override["agent_summary"]
    return out


def process_fc(path: Path, layer: str, cards: dict, overrides: dict) -> None:
    fc = json.loads(path.read_text(encoding="utf-8"))
    for idx, f in enumerate(fc.get("features", [])):
        geom = f.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        lon, lat = geom["coordinates"][0], geom["coordinates"][1]
        props = dict(f.get("properties") or {})
        pid = pin_id_for(props, layer, idx)
        card = default_card(pid, props, lon, lat, layer)
        if pid in overrides:
            card = merge_override(card, overrides[pid])
        cards[pid] = card
        props["pin_id"] = pid
        props["category_label"] = CATEGORY_LABEL.get(card["category"], card["category"])
        props["google_maps_directions_url"] = card["google_maps_directions_url"]
        f["properties"] = props
    path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    overrides = load_overrides()
    cards: dict = {}

    process_fc(GEO / "facilities_pois.geojson", "facilities", cards, overrides)
    process_fc(GEO / "development_sites.geojson", "development", cards, overrides)

    pois = json.loads((GEO / "facilities_pois.geojson").read_text(encoding="utf-8"))
    by_cat: dict[str, list] = {}
    for f in pois["features"]:
        by_cat.setdefault(f["properties"]["category"], []).append(f)
    for cat, feats in by_cat.items():
        (GEO / f"layer_{cat}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False),
            encoding="utf-8",
        )

    out = {
        "schema": "viksetu_poi_cards_v1",
        "district": "palghar",
        "pin_count": len(cards),
        "pins": cards,
    }
    CARDS.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {CARDS.name} ({len(cards)} pins)")


if __name__ == "__main__":
    main()
