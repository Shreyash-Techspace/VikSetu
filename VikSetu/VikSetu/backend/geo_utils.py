"""BBox / district boundary / taluka helpers for VikSetu geo layers."""
from __future__ import annotations

import json
from pathlib import Path


def get_district_bbox(regions: dict) -> list[float] | None:
    bbox = regions.get("district", {}).get("bbox")
    if bbox and len(bbox) == 4:
        return [float(x) for x in bbox]
    return None


def district_boundary_geometry(district_fc: dict) -> list[dict]:
    """List of GeoJSON geometry dicts (Polygon / MultiPolygon) from a FeatureCollection."""
    geoms: list[dict] = []
    for f in district_fc.get("features", []):
        g = f.get("geometry")
        if g and g.get("type") in ("Polygon", "MultiPolygon"):
            geoms.append(g)
    return geoms


def point_in_district(lon: float, lat: float, district_fc: dict) -> bool:
    for geom in district_boundary_geometry(district_fc):
        if _point_in_geojson_geometry(lon, lat, geom):
            return True
    return False


def filter_fc_district(fc: dict, district_fc: dict) -> dict:
    out: list[dict] = []
    for f in fc.get("features", []):
        geom = f.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        if point_in_district(lon, lat, district_fc):
            out.append(f)
    return {"type": "FeatureCollection", "features": out}


def point_in_bbox(lon: float, lat: float, bbox: list[float]) -> bool:
    w, s, e, n = bbox
    return w <= lon <= e and s <= lat <= n


def filter_fc_bbox(fc: dict, bbox: list[float]) -> dict:
    out: list[dict] = []
    for f in fc.get("features", []):
        geom = f.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        if point_in_bbox(lon, lat, bbox):
            out.append(f)
    return {"type": "FeatureCollection", "features": out}


def taluka_at_point(lon: float, lat: float, taluka_fc: dict) -> str | None:
    """Return taluka id if point inside a taluka polygon feature."""
    for f in taluka_fc.get("features", []):
        props = f.get("properties") or {}
        if props.get("source") == "centroid_buffer_approx":
            continue
        tid = props.get("id")
        geom = f.get("geometry")
        if not tid or not geom:
            continue
        if _point_in_geojson_geometry(lon, lat, geom):
            return str(tid)
    return None


def nearest_taluka_id(lon: float, lat: float, talukas: list[dict]) -> str | None:
    best: tuple[float, str] | None = None
    for t in talukas:
        tid = t.get("id")
        c = t.get("centroid")
        if not tid or not c or len(c) < 2:
            continue
        d = (float(c[0]) - lon) ** 2 + (float(c[1]) - lat) ** 2
        if best is None or d < best[0]:
            best = (d, str(tid))
    return best[1] if best else None


def _point_in_geojson_geometry(lon: float, lat: float, geom: dict) -> bool:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return False
    if gtype == "Polygon":
        return _point_in_polygon_with_holes(lon, lat, coords)
    if gtype == "MultiPolygon":
        for poly in coords:
            if poly and _point_in_polygon_with_holes(lon, lat, poly):
                return True
    return False


def _point_in_polygon_with_holes(lon: float, lat: float, rings: list) -> bool:
    if not rings:
        return False
    if not _point_in_polygon(lon, lat, rings[0]):
        return False
    for hole in rings[1:]:
        if _point_in_polygon(lon, lat, hole):
            return False
    return True


def _point_in_polygon(lon: float, lat: float, ring: list) -> bool:
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi):
            inside = not inside
        j = i
    return inside


def enrich_poi_taluka(fc: dict, taluka_fc: dict, taluka_meta: list[dict] | None = None) -> dict:
    features = []
    for f in fc.get("features", []):
        props = dict(f.get("properties") or {})
        geom = f.get("geometry") or {}
        if geom.get("type") == "Point":
            lon, lat = geom["coordinates"][0], geom["coordinates"][1]
            tid = taluka_at_point(lon, lat, taluka_fc)
            if not tid and taluka_meta:
                tid = nearest_taluka_id(lon, lat, taluka_meta)
            if tid:
                props["taluka_id"] = tid
        features.append({**f, "properties": props})
    return {"type": "FeatureCollection", "features": features}


def talukas_for_map(taluka_fc: dict) -> dict:
    """Drop placeholder square buffers from map display."""
    feats = [
        f
        for f in taluka_fc.get("features", [])
        if (f.get("properties") or {}).get("source") != "centroid_buffer_approx"
    ]
    return {"type": "FeatureCollection", "features": feats}


def load_district_fc(geo_dir: Path) -> dict:
    path = geo_dir / "palghar_district.geojson"
    return json.loads(path.read_text(encoding="utf-8"))

