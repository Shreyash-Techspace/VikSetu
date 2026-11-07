"""VikSetu API — geo layers, spend data, chat stub (Gemini via llm.py)."""
from __future__ import annotations

import base64
import csv
import json
import math
import os
import re
import subprocess
import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent
GEO = ROOT / "data" / "geo"
SPEND_CSV = ROOT / "data" / "palghar_2024_25" / "derived" / "ps_sector_spend_2024_25.csv"
WORK = ROOT / "agent_workspace"
INBOX = WORK / "inbox"
SCRATCH = WORK / "scratch"
INBOX.mkdir(parents=True, exist_ok=True)
SCRATCH.mkdir(parents=True, exist_ok=True)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        load_dotenv(BACKEND_DIR / ".env")
    except ImportError:
        pass


_load_dotenv()

sys.path.insert(0, str(BACKEND_DIR))
from agent_files import file_kind, run_file_action  # noqa: E402
from geo_utils import (  # noqa: E402
    filter_fc_district,
    load_district_fc,
    talukas_for_map,
)

app = FastAPI(title="VikSetu API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise HTTPException(404, f"Missing {path.name}. Run: python scripts/fetch_geo.py")
    return json.loads(path.read_text(encoding="utf-8"))


def load_geojson(name: str) -> dict:
    return load_json(GEO / name)


@app.get("/api/health")
def health():
    provider = os.environ.get("LLM_PROVIDER", "textgen")
    model = None
    vision = False
    try:
        from llm import resolve_model, supports_vision

        provider, model = resolve_model()
        vision = supports_vision(provider, model)
    except Exception:
        pass
    return {
        "status": "ok",
        "service": "viksetu",
        "llm": provider,
        "model": model,
        "vision": vision,
    }


def load_regions() -> dict:
    return load_json(GEO / "regions.json")


def clip_to_district(fc: dict) -> dict:
    try:
        district_fc = load_district_fc(GEO)
    except (OSError, json.JSONDecodeError, KeyError):
        return fc
    return filter_fc_district(fc, district_fc)


@app.get("/api/regions")
def regions():
    return load_regions()


@app.get("/api/geo/talukas")
def geo_talukas():
    path = GEO / "talukas.geojson"
    if not path.is_file():
        raise HTTPException(404, "Missing talukas.geojson. Run: python scripts/fetch_talukas_and_pois.py")
    return talukas_for_map(load_json(path))


@app.get("/api/geo/district")
def geo_district():
    return load_geojson("palghar_district.geojson")


@app.get("/api/geo/bbox")
def geo_bbox():
    path = GEO / "palghar_bbox.geojson"
    if path.is_file():
        return load_json(path)
    reg = load_json(GEO / "regions.json")
    bbox = reg.get("district", {}).get("bbox")
    if not bbox or len(bbox) != 4:
        raise HTTPException(404, "No bbox. Run: python scripts/compute_palghar_bbox.py")
    w, s, e, n = bbox
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Palghar bbox", "bbox": bbox},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
                },
            }
        ],
    }


@app.get("/api/geo/layers/{layer_id}")
def geo_layer(layer_id: str):
    allowed = {
        "facilities": "facilities_pois.geojson",
        "development": "development_sites.geojson",
        "government_school": "layer_government_school.geojson",
        "health_facility": "layer_health_facility.geojson",
        "government_facility": "layer_government_facility.geojson",
        "community_poi": "layer_community_poi.geojson",
        "other_poi": "layer_other_poi.geojson",
    }
    if layer_id not in allowed:
        raise HTTPException(404, f"Unknown layer. Choose from: {list(allowed)}")
    path = GEO / allowed[layer_id]
    if not path.is_file() and layer_id != "facilities":
        return {"type": "FeatureCollection", "features": []}
    fc = load_geojson(allowed[layer_id])
    return clip_to_district(fc)


POI_CARDS = GEO / "poi_cards.json"
POI_OVERRIDES = GEO / "poi_overrides.json"


def _load_poi_overrides_doc() -> dict:
    if not POI_OVERRIDES.is_file():
        return {"schema": "viksetu_poi_overrides_v1", "pins": {}}
    return json.loads(POI_OVERRIDES.read_text(encoding="utf-8"))


def _merge_poi_card(base: dict, patch: dict) -> dict:
    merged = dict(base)
    for key, value in patch.items():
        if value is not None:
            merged[key] = value
    return merged


def _poi_card_merged(pin_id: str) -> dict:
    pins = _load_poi_cards_index()
    if pin_id not in pins:
        raise HTTPException(404, f"Unknown pin_id: {pin_id}")
    overrides = (_load_poi_overrides_doc().get("pins") or {}).get(pin_id) or {}
    return _merge_poi_card(pins[pin_id], overrides)


def _load_poi_cards_index() -> dict:
    if not POI_CARDS.is_file():
        raise HTTPException(
            404,
            "Missing poi_cards.json. Run: python scripts/build_poi_cards.py",
        )
    data = json.loads(POI_CARDS.read_text(encoding="utf-8"))
    return data.get("pins") or {}


@app.get("/api/poi/cards")
def poi_cards_index(q: str | None = None, limit: int = 40):
    """Full card index for agents; optional substring search on name/summary."""
    pins = _load_poi_cards_index()
    if not q:
        return {"pin_count": len(pins), "pins": pins}
    q_l = q.lower()
    matched = {
        pid: card
        for pid, card in pins.items()
        if q_l in card.get("name", "").lower() or q_l in card.get("agent_summary", "").lower()
    }
    items = list(matched.items())[: max(1, min(limit, 200))]
    return {"pin_count": len(matched), "pins": dict(items)}


@app.get("/api/poi/card/{pin_id}")
def poi_card(pin_id: str):
    return _poi_card_merged(pin_id)


class PinPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    agent_summary: str | None = None


@app.patch("/api/poi/card/{pin_id}")
def patch_poi_card(pin_id: str, body: PinPatch):
    pins = _load_poi_cards_index()
    if pin_id not in pins:
        raise HTTPException(404, f"Unknown pin_id: {pin_id}")
    doc = _load_poi_overrides_doc()
    doc.setdefault("pins", {})
    entry = dict(doc["pins"].get(pin_id) or {})
    for field, value in body.model_dump(exclude_none=True).items():
        entry[field] = value
    doc["pins"][pin_id] = entry
    POI_OVERRIDES.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return _poi_card_merged(pin_id)


@app.get("/api/spend")
def spend():
    if not SPEND_CSV.is_file():
        raise HTTPException(404, "Spend CSV missing")
    rows = []
    with SPEND_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    total = next((r for r in rows if r.get("sector_en") == "Total"), None)
    return {"fy": "2024-25", "rows": rows, "total": total}


class ChatRequest(BaseModel):
    message: str
    ui_state: dict = Field(default_factory=dict)


class UIPatch(BaseModel):
    filters: dict = Field(default_factory=dict)
    layers: dict = Field(default_factory=dict)
    map_focus: dict | None = None
    chart: str | None = None


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Simple rule + optional Gemini; returns answer and ui_patch for dashboard."""
    msg = req.message.lower()
    patch = UIPatch()
    answer = ""

    if "school" in msg:
        patch.layers = {"government_school": True}
        answer = "Showing government schools layer from OpenStreetMap."
    elif "health" in msg or "hospital" in msg:
        patch.layers = {"health_facility": True}
        answer = "Showing health facilities layer."
    elif "gov" in msg or "office" in msg:
        patch.layers = {"government_facility": True}
        answer = "Showing government / public facility pins."
    elif "development" in msg or "construction" in msg or "work" in msg:
        patch.layers = {"development": True}
        answer = "Showing sample development / works pins (PS report + planned ZP budget)."
    elif "jawhar" in msg or "dahanu" in msg or "vasai" in msg or "wada" in msg:
        for t in ("jawhar", "dahanu", "vasai", "wada", "mokhada", "talasari", "vikramgad", "palghar"):
            if t in msg:
                patch.map_focus = {"taluka": t, "zoom": 10}
                answer = f"Map focus set to {t.title()} taluka."
                break
    elif "spend" in msg or "budget" in msg:
        patch.chart = "spend_by_sector"
        answer = "Total actual spend FY 2024-25 (PS extract): Rs 19,39,204. Chart updated."
    else:
        try:
            from llm import ask

            answer = ask(
                req.message,
                system=(
                    "You are VikSetu, a civic data assistant for Palghar district. "
                    "Answer briefly in the user's language. Use spend facts: total actual Rs 1939204 FY 2024-25. "
                    "Per-place FY history and summaries live in GET /api/poi/cards and /api/poi/card/{pin_id} "
                    "(data/geo/poi_cards.json). Users can enrich pins via data/geo/poi_overrides.json."
                ),
            )
        except Exception as e:
            answer = f"VikSetu (offline rules): ask about schools, health, gov facilities, development, taluka names, or spend. ({e})"

    return {
        "answer": answer,
        "ui_patch": patch.model_dump(exclude_none=True),
    }


class CanvasChatRequest(BaseModel):
    message: str
    history: list[dict] = Field(default_factory=list)
    canvas: list[dict] = Field(default_factory=list)
    selection: list[dict] = Field(default_factory=list)
    log: list[dict] = Field(default_factory=list)
    map: dict = Field(default_factory=dict)
    cursor: dict | None = None
    step: int = 0
    trace: list[dict] = Field(default_factory=list)


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


class FileUpload(BaseModel):
    name: str
    data_b64: str


class PythonRequest(BaseModel):
    code: str


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name).strip("._")
    return (cleaned or "file")[:80]


def _spend_brief() -> list[dict]:
    if not SPEND_CSV.is_file():
        return []
    rows = []
    with SPEND_CSV.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("sector_en") == "Total":
                continue
            rows.append(
                {
                    "sector": row.get("sector_en"),
                    "actual_spend_inr": row.get("actual_spend_inr"),
                }
            )
    return rows[:12]


def _workspace_files() -> list[dict]:
    files = []
    for path in sorted(WORK.rglob("*")):
        if not path.is_file() or path.name == "_last_script.py":
            continue
        item = {
            "path": path.relative_to(WORK).as_posix(),
            "bytes": path.stat().st_size,
            "kind": file_kind(path),
        }
        if path.suffix.lower() in {".txt", ".md", ".csv", ".json"} and len(files) < 8:
            item["preview"] = path.read_text(encoding="utf-8", errors="replace")[:1200]
        files.append(item)
        if len(files) >= 50:
            break
    return files


def _inbox_file(file_id: str) -> Path:
    name = _safe_name(file_id)
    path = (INBOX / name).resolve()
    if not str(path).startswith(str(INBOX.resolve())) or not path.is_file():
        raise HTTPException(404, f"Unknown file: {file_id}")
    return path


def _vision_images_from_canvas(req: CanvasChatRequest, limit: int = 4) -> list[str]:
    import mimetypes

    shapes = list(req.canvas or [])
    shapes.sort(key=lambda shape: not shape.get("selected"))
    urls: list[str] = []
    for shape in shapes:
        if shape.get("type") != "viksetu-file":
            continue
        file_id = str(shape.get("fileId") or "").strip()
        if not file_id:
            continue
        kind = str(shape.get("fileKind") or "")
        try:
            path = _inbox_file(file_id)
        except HTTPException:
            continue
        if kind != "image" and path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        urls.append(f"data:{mime};base64,{encoded}")
        if len(urls) >= limit:
            break
    return urls


def _image_data_url(path: Path) -> str:
    import mimetypes

    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _canvas_image_ids(req: CanvasChatRequest) -> list[str]:
    ids: list[str] = []
    for shape in req.canvas or []:
        if shape.get("type") != "viksetu-file":
            continue
        file_id = str(shape.get("fileId") or "").strip()
        if not file_id:
            continue
        kind = str(shape.get("fileKind") or "")
        try:
            path = _inbox_file(file_id)
        except HTTPException:
            continue
        if kind == "image" or path.suffix.lower() in IMAGE_SUFFIXES:
            ids.append(file_id)
    return ids


def _run_vision_subagent(action: dict, req: CanvasChatRequest | None) -> dict:
    """Ask the local textgen model to read an image. The lead model stays text-only."""
    question = str(action.get("question") or action.get("prompt") or action.get("task") or "").strip()
    if not question:
        question = "Describe everything visible that would help answer the user, including text and numbers."
    file_id = str(action.get("fileId") or "").strip()
    images: list[str] = []
    try:
        if file_id:
            path = _inbox_file(file_id)
            if path.suffix.lower() not in IMAGE_SUFFIXES and file_kind(path) != "image":
                return {"ok": False, "fileId": file_id, "question": question, "error": "That file is not an image."}
            images = [_image_data_url(path)]
        elif req is not None:
            images = _vision_images_from_canvas(req, limit=2)
            ids = _canvas_image_ids(req)
            file_id = ids[0] if ids else ""
        if not images:
            return {
                "ok": False,
                "fileId": file_id,
                "question": question,
                "error": "No canvas image. Pass fileId of an image file on the canvas.",
            }
        from llm import chat, user_message_content

        result = chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are the VikSetu vision sub-agent on the local text-generation-webui model. "
                        "Answer only from the attached image. Quote visible text and numbers. "
                        "If something is unreadable, say so. Do not invent."
                    ),
                },
                {"role": "user", "content": user_message_content(question, images, vision=True)},
            ],
            provider="textgen",
            temperature=0.1,
            max_tokens=1200,
            timeout=180,
        )
        return {
            "ok": True,
            "provider": "textgen",
            "model": result.get("model"),
            "fileId": file_id,
            "question": question,
            "answer": str(result.get("text") or "")[:4000],
        }
    except Exception as exc:
        return {"ok": False, "fileId": file_id, "question": question, "error": str(exc)}


def _split_file_tools(actions: list) -> tuple[list, list]:
    kept, notes = [], []
    for action in actions:
        if not isinstance(action, dict):
            kept.append(action)
            continue
        op = str(action.get("op") or "")
        if op not in {"file-read", "file-list"}:
            kept.append(action)
            continue
        note = run_file_action(WORK, INBOX, action)
        note["op"] = op
        note["fileId"] = action.get("fileId")
        note["path"] = action.get("path")
        note["mode"] = action.get("mode") or action.get("tool")
        notes.append(note)
    return kept, notes


def _pin_cards_for(map_state: dict, message: str) -> dict:
    try:
        pins = _load_poi_cards_index()
    except HTTPException:
        return {}
    cards: dict = {}
    selected = (map_state.get("selected") or {}).get("pinId")
    if selected in pins:
        cards[selected] = pins[selected]
    query = message.lower()
    for item in map_state.get("pins") or []:
        name = str(item.get("name") or "")
        pin_id = item.get("pinId")
        if name and len(name) > 3 and name.lower() in query and pin_id in pins:
            cards[pin_id] = pins[pin_id]
        if len(cards) >= 4:
            break
    if len(cards) < 4:
        for item in map_state.get("hiddenPinSamples") or []:
            name = str(item.get("name") or "")
            pin_id = item.get("pinId")
            if name and len(name) > 3 and name.lower() in query and pin_id in pins:
                cards[pin_id] = pins[pin_id]
            if len(cards) >= 4:
                break
    return cards


def _run_python(code: str) -> dict:
    script = (code or "").strip()
    if not script:
        return {"ok": False, "stdout": "", "stderr": "Empty script.", "code": 1}
    if len(script) > 20000:
        return {"ok": False, "stdout": "", "stderr": "Script is too long.", "code": 1}
    target = WORK / "_last_script.py"
    target.write_text(script, encoding="utf-8")
    try:
        completed = subprocess.run(
            [sys.executable, "-X", "utf8", str(target)],
            cwd=str(WORK),
            capture_output=True,
            timeout=45,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "Stopped after 45 seconds.", "code": 124}
    except Exception as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc), "code": 1}
    stdout = completed.stdout.decode("utf-8", "replace")
    stderr = completed.stderr.decode("utf-8", "replace")
    return {
        "ok": completed.returncode == 0,
        "stdout": stdout[-8000:],
        "stderr": stderr[-4000:],
        "code": completed.returncode,
    }


def _num(value) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[₹,\s]", "", str(value or ""))
    text = re.sub(r"(?i)(crore|cr|lakh|lac)$", "", text)
    try:
        return float(text)
    except ValueError:
        return 0.0


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        return [part.strip() for part in re.split(r"[,|\n]", value) if part.strip()]
    return []


def _chart_pairs(action: dict) -> tuple[list[str], list[float]]:
    bundled = _as_list(action.get("series") or action.get("data") or action.get("points") or action.get("items"))
    labels = []
    values = []
    for item in _as_list(action.get("labels")):
        if isinstance(item, dict):
            labels.append(str(item.get("label") or item.get("name") or item.get("sector") or ""))
        else:
            labels.append(str(item))
    for item in _as_list(action.get("values")):
        if isinstance(item, dict):
            values.append(_num(item.get("value") or item.get("amount") or item.get("y") or item.get("actual_spend_inr")))
        else:
            values.append(_num(item))
    if bundled and any(isinstance(item, dict) for item in bundled) and (not any(values) or not labels):
        labels = []
        values = []
        for item in bundled:
            row = item if isinstance(item, dict) else {}
            labels.append(str(row.get("label") or row.get("name") or row.get("sector") or ""))
            values.append(_num(row.get("value") or row.get("amount") or row.get("y") or row.get("actual_spend_inr")))
    count = max(len(labels), len(values))
    labels = [labels[index] if index < len(labels) and labels[index] else str(index + 1) for index in range(count)]
    values = [values[index] if index < len(values) else 0.0 for index in range(count)]
    return labels, values


PIN_LAYERS = (
    "government_school",
    "health_facility",
    "government_facility",
    "community_poi",
    "other_poi",
    "development",
)


def _layer_visible(raw) -> bool:
    if raw is False or raw == 0:
        return False
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("false", "off", "no", "0"):
            return False
        if s in ("true", "on", "yes", "1"):
            return True
    return bool(raw)


def _target_pin_layer_visibility(message: str) -> dict[str, bool] | None:
    """When the user clearly wants a pin-layer preset, return visibility per PIN_LAYERS."""
    lower = message.lower()
    if not re.search(r"\b(map|layer|pin|poi)\b", lower):
        return None
    if not re.search(r"\b(enable|disable|show|hide|turn on|turn off|only|just)\b", lower):
        return None

    if re.search(r"\ball\b", lower) and re.search(r"\bpin", lower) and re.search(
        r"\b(off|disabled|hide|disable|hidden)\b", lower
    ):
        return {layer: False for layer in PIN_LAYERS}

    if "development" in lower and re.search(r"\b(only|just)\b", lower):
        return {layer: layer == "development" for layer in PIN_LAYERS}
    if re.search(r"\benabl(e|ing)\b", lower) and "development" in lower and re.search(
        r"\bonly\b", lower
    ):
        return {layer: layer == "development" for layer in PIN_LAYERS}

    aliases = {
        "school": "government_school",
        "schools": "government_school",
        "health": "health_facility",
        "govt": "government_facility",
        "government": "government_facility",
        "community": "community_poi",
        "other": "other_poi",
        "development": "development",
        "works": "development",
    }
    for word, layer_id in aliases.items():
        if re.search(rf"\b(only|just)\b.*\b{re.escape(word)}\b", lower) or re.search(
            rf"\b{re.escape(word)}\b.*\bonly\b", lower
        ):
            return {layer: layer == layer_id for layer in PIN_LAYERS}

    return None


def _require_map_layer_actions(message: str, actions: list) -> tuple[list, bool]:
    """
    If the user asked for a layer preset, ensure map-layer ops exist.
    Returns (actions, model_omitted_map_layer).
    """
    target = _target_pin_layer_visibility(message)
    if not target:
        return actions, False
    model_layers = [
        a for a in actions if isinstance(a, dict) and a.get("op") == "map-layer"
    ]
    kept = [a for a in actions if not (isinstance(a, dict) and a.get("op") == "map-layer")]
    merged = dict(target)
    for action in model_layers:
        layer = str(action.get("layer") or "").strip()
        if layer in merged:
            merged[layer] = _layer_visible(action.get("visible"))
    layer_actions = [{"op": "map-layer", "layer": layer, "visible": vis} for layer, vis in merged.items()]
    omitted = len(model_layers) == 0
    return kept + layer_actions, omitted


def _normalize_map_layer_actions(actions: list) -> list:
    pin_layers = set(PIN_LAYERS)

    out = []
    for action in actions:
        if not isinstance(action, dict) or action.get("op") != "map-layer":
            out.append(action)
            continue
        layer = str(action.get("layer") or "").strip()
        if layer in pin_layers or layer == "taluka_regions":
            action = {**action, "layer": layer, "visible": _layer_visible(action.get("visible"))}
        out.append(action)
    return out


def _hydrate_actions(actions: list, message: str) -> list:
    spend = _spend_brief()
    known = {str(row.get("sector") or "").lower(): _num(row.get("actual_spend_inr")) for row in spend}
    hydrated = []
    for action in actions:
        if not isinstance(action, dict) or action.get("op") != "chart":
            hydrated.append(action)
            continue
        labels, values = _chart_pairs(action)
        topic = f"{message} {action.get('title') or ''}".lower()
        about_land = any(word in topic for word in ("land", "area", "taluka", "region share", "land mass"))
        about_spend = any(word in topic for word in ("spend", "sector", "budget", "expenditure", "outlay"))
        if about_land:
            about_spend = False
        named = sum(1 for label in labels if label.lower() in known)
        if (not any(values)) and (about_spend or named >= 2) and spend:
            if named >= 2:
                labels = [label for label in labels if label.lower() in known] or [str(row.get("sector") or "") for row in spend]
                values = [known.get(label.lower(), 0.0) for label in labels]
            else:
                labels = [str(row.get("sector") or "") for row in spend]
                values = [_num(row.get("actual_spend_inr")) for row in spend]
            action["title"] = action.get("title") or "Sector-wise spend"
            action["chart"] = action.get("chart") or "bar"
        action["labels"] = labels
        action["values"] = values
        hydrated.append(action)
    return hydrated


def _split_python(actions: list) -> tuple[list, list]:
    kept, notes = [], []
    for action in actions:
        if isinstance(action, dict) and action.get("op") == "python":
            script = str(action.get("code") or "")
            note = _run_python(script)
            note["script"] = script[:6000]
            notes.append(note)
        else:
            kept.append(action)
    return kept, notes


def _split_subagent(actions: list, req: CanvasChatRequest | None) -> tuple[list, list]:
    kept, notes = [], []
    for action in actions:
        if isinstance(action, dict) and str(action.get("op") or "") in {"vision", "subagent"}:
            notes.append(_run_vision_subagent(action, req))
        else:
            kept.append(action)
    return kept, notes


class _PageText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title: list[str] = []
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title.append(data)
        text = " ".join(data.split())
        if text:
            self.parts.append(text + " ")


def _html_to_text(raw: str) -> tuple[str, str]:
    parser = _PageText()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:
        text = re.sub(r"<[^>]+>", " ", raw)
        return "", re.sub(r"\s+", " ", text).strip()
    title = " ".join(" ".join(parser.title).split())
    text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return title[:300], text


def _ring_area_m2(ring) -> float:
    if not ring or len(ring) < 4:
        return 0.0
    lat0 = sum(point[1] for point in ring) / len(ring)
    kx = 111_320 * math.cos(math.radians(lat0))
    ky = 110_540
    area = 0.0
    for index in range(len(ring) - 1):
        x1, y1 = ring[index][0] * kx, ring[index][1] * ky
        x2, y2 = ring[index + 1][0] * kx, ring[index + 1][1] * ky
        area += x1 * y2 - x2 * y1
    return abs(area) / 2


def _geom_area_m2(geom: dict) -> float:
    kind = geom.get("type")
    coords = geom.get("coordinates") or []
    if kind == "Polygon" and coords:
        outer = _ring_area_m2(coords[0])
        holes = sum(_ring_area_m2(ring) for ring in coords[1:])
        return max(0.0, outer - holes)
    if kind == "MultiPolygon":
        return sum(_geom_area_m2({"type": "Polygon", "coordinates": poly}) for poly in coords)
    return 0.0


def _summarize_feature_collection(body: str) -> str | None:
    """Turn a polygon FeatureCollection into name, km2, and percent so a chart can be built."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        return None
    features = data.get("features") or []
    if not features or not isinstance(features[0], dict) or "geometry" not in features[0]:
        return None
    rows = []
    for feature in features:
        props = feature.get("properties") or {}
        name = str(props.get("name") or props.get("id") or "unnamed")
        km2 = _geom_area_m2(feature.get("geometry") or {}) / 1_000_000
        if km2 <= 0:
            continue
        rows.append({"name": name, "km2": round(km2, 2)})
    if not rows:
        return None
    total = sum(row["km2"] for row in rows) or 1
    for row in rows:
        row["percent"] = round(100 * row["km2"] / total, 2)
    rows.sort(key=lambda row: row["percent"], reverse=True)
    return json.dumps(
        {
            "summary": "Polygon areas derived from the GeoJSON. Use percent for a land-share pie chart.",
            "feature_count": len(rows),
            "total_km2": round(total, 2),
            "areas": rows,
        },
        ensure_ascii=False,
    )


def _fetch_web(action: dict) -> dict:
    """GET a public page or this app's own API and return readable text."""
    import urllib.error
    import urllib.request

    url = str(action.get("url") or action.get("href") or "").strip()
    if url.startswith("//"):
        url = "https:" + url
    elif url and "://" not in url:
        url = "https://" + url
    parsed = urllib.parse.urlparse(url) if url else None
    if not parsed or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"ok": False, "url": url, "error": "Pass an http or https URL."}
    host = (parsed.hostname or "").lower()
    if host in {"169.254.169.254", "metadata.google.internal"}:
        return {"ok": False, "url": url, "error": "That host is blocked."}
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "VikSetuAgent/1.0", "Accept": "text/html,application/json,text/plain,*/*"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            final_url = resp.geturl()
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read(1_500_000)
    except urllib.error.HTTPError as exc:
        detail = exc.read(800).decode("utf-8", "replace")
        return {"ok": False, "url": url, "error": f"HTTP {exc.code}: {detail[:400]}"}
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)}
    charset = "utf-8"
    match = re.search(r"charset=([\w.-]+)", content_type, flags=re.I)
    if match:
        charset = match.group(1)
    body = raw.decode(charset, "replace")
    if body.lstrip()[:1] in "{[":
        summary = _summarize_feature_collection(body)
        if summary:
            return {
                "ok": True,
                "url": final_url or url,
                "title": "GeoJSON area summary",
                "content_type": "application/json",
                "text": summary,
            }
    if "json" in content_type.lower() or body.lstrip()[:1] in "[{":
        title, text = "", body.strip()
    else:
        title, text = _html_to_text(body)
    text = text[:8000]
    return {"ok": True, "url": final_url or url, "title": title, "content_type": content_type.split(";")[0], "text": text}


def _split_web(actions: list) -> tuple[list, list]:
    kept, notes = [], []
    for action in actions:
        if isinstance(action, dict) and str(action.get("op") or "") == "web":
            notes.append(_fetch_web(action))
        else:
            kept.append(action)
    return kept, notes


def _user_wants_embed(message: str) -> bool:
    lower = message.lower()
    return bool(re.search(r"\b(embed|custom html|html widget|gauge|srcdoc)\b", lower))


def _drop_unasked_embeds(message: str, actions: list) -> list:
    if _user_wants_embed(message):
        return actions
    return [action for action in actions if not (isinstance(action, dict) and action.get("op") == "embed")]


def _split_agent_tools(actions: list, req: CanvasChatRequest | None = None) -> tuple[list, list, list, list, list]:
    actions, file_notes = _split_file_tools(actions)
    actions, python_notes = _split_python(actions)
    actions, sub_notes = _split_subagent(actions, req)
    actions, web_notes = _split_web(actions)
    return actions, file_notes, python_notes, sub_notes, web_notes


@app.post("/api/canvas/files")
def upload_canvas_file(req: FileUpload):
    try:
        raw = base64.b64decode(req.data_b64, validate=True)
    except Exception as exc:
        raise HTTPException(400, f"Could not read that file: {exc}") from exc
    if len(raw) > 52_428_800:
        raise HTTPException(400, "File is larger than 50 MB.")
    name = _safe_name(req.name)
    dest = INBOX / name
    dest.write_bytes(raw)
    preview = ""
    kind = file_kind(dest)
    if kind == "text":
        preview = dest.read_text(encoding="utf-8", errors="replace")[:4000]
    elif kind == "image":
        preview = f"[image {dest.suffix.lower()}, {len(raw)} bytes — use file-read or vision when selected on canvas]"
    else:
        preview = f"[binary {dest.suffix.lower() or 'file'}, {len(raw)} bytes — use file-read mode hex or text]"
    return {"fileId": name, "name": name, "bytes": len(raw), "preview": preview, "kind": kind}


@app.get("/api/canvas/files/{file_id}/raw")
def canvas_file_raw(file_id: str):
    path = _inbox_file(file_id)
    return FileResponse(path, filename=path.name)


@app.post("/api/canvas/python")
def canvas_python(req: PythonRequest):
    """Run a script inside agent_workspace (read/write anywhere under that folder)."""
    return _run_python(req.code)


def _parse_canvas_turn(text: str) -> dict:
    thoughts = [part.strip() for part in re.findall(r"<think>(.*?)</think>", text, flags=re.S | re.I)]
    body = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    body = re.sub(r"</?think>", "", body, flags=re.I)
    cleaned = body.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    data: dict = {}
    if start != -1 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            if isinstance(parsed, dict):
                data = parsed
        except json.JSONDecodeError:
            data = {}
    if not data:
        return {"thinking": "\n\n".join(item for item in thoughts if item), "reply": body.strip(), "actions": [], "continue": False}
    reply = data.get("reply")
    actions = data.get("actions")
    if not isinstance(reply, str):
        reply = ""
    if not isinstance(actions, list):
        actions = []
    thinking = data.get("thinking")
    if isinstance(thinking, (list, dict)):
        thinking = json.dumps(thinking, ensure_ascii=False)
    thoughts.append(str(thinking or "").strip())
    if "continue" not in data:
        flag = None
    else:
        flag = data.get("continue")
        if isinstance(flag, str):
            flag = flag.strip().lower() in {"true", "yes", "1"}
        else:
            flag = bool(flag)
    return {
        "thinking": "\n\n".join(item for item in thoughts if item),
        "reply": reply,
        "actions": actions,
        "continue": flag,
    }


CANVAS_MAX_TOKENS = int(os.environ.get("CANVAS_MAX_TOKENS", "4096"))
CANVAS_CONTEXT_TOKENS = int(os.environ.get("CANVAS_CONTEXT_TOKENS", "12000"))

CANVAS_SYSTEM = (
    "You are the VikSetu canvas agent. You share one tldraw page with the user. "
    "You have tools. A reply that only describes a change does not perform it. "
    "Tools that run now and return on the next step (set continue true, then use the result): "
    "python in agent_workspace; file-read and file-list; vision (local textgen reads an image); "
    "web fetches any http(s) page or JSON API and returns its title and text. "
    "Local data you can open with web instead of guessing: "
    "http://127.0.0.1:8001/api/geo/talukas, http://127.0.0.1:8001/api/geo/district, "
    "http://127.0.0.1:8001/api/geo/layers/{layerId}, http://127.0.0.1:8001/api/spend. "
    "If one port fails, try the same path on port 8002. "
    "Cite a fetched page with a markdown link to that exact URL. "
    "Every object in Canvas JSON has id, type, x, y, w, h (page position and size), text, detail, and selected. "
    "Selection JSON is exactly what the user currently has selected. When they say this, these, or the selection, use those ids. "
    "Use those coordinates and sizes when you place or refer to an object. "
    "Map JSON lists layerStats (id, enabled, totalPins, visiblePins), enabled pins with layerEnabled true, "
    "hiddenPinSamples for pins on disabled layers (layerEnabled false), and the selected pin. "
    "Pin cards JSON has the full record for the selected pin and any pin the user named. "
    "MAP TOOLS (mandatory for layer or pin visibility): The live map is changed only with map-layer, map-focus, and map-pin — not with reply text alone. "
    "Pin layer ids (exact strings): government_school, health_facility, government_facility, community_poi, other_poi, development. "
    "taluka_regions is boundary shading only, not POI pins. "
    "When the user enables, disables, shows, hides, or says only/just one category, you MUST include one map-layer action per pin layer in the same step, "
    "each with visible true or false (JSON booleans, never strings). "
    "Example — only development pins visible: "
    '{"op":"map-layer","layer":"development","visible":true}, '
    '{"op":"map-layer","layer":"government_school","visible":false}, '
    '{"op":"map-layer","layer":"health_facility","visible":false}, '
    '{"op":"map-layer","layer":"government_facility","visible":false}, '
    '{"op":"map-layer","layer":"community_poi","visible":false}, '
    '{"op":"map-layer","layer":"other_poi","visible":false}. '
    "Never tell the user layers changed unless those map-layer entries are in actions. "
    "Do not place a new {\"op\":\"map\"} shape if a viksetu-map already exists — use map-layer only. "
    "map-focus flies the map; map-pin edits poi card text. "
    "Do not create an embed object unless the user explicitly asks for an embed, custom HTML, a widget, or a gauge. "
    "Charts, notes, sheets, maps, and files are not embeds. "
    "You are the lead agent. A local text-generation-webui vision model is your sub-agent. "
    "If this request does not include image bytes, you cannot see pixels. "
    "To read an image, emit {\"op\":\"vision\",\"fileId\":\"<canvas fileId>\",\"question\":\"<what to extract>\"} and set continue to true. "
    "The next step includes subagent[].answer from textgen. Use that text; do not invent what the image shows. "
    "In reply, cite each fact with an inline markdown link to the source, in the same sentence. "
    "Allowed link targets: /api/spend, /api/poi/card/{pinId}, /api/geo/layers/{layerId}, /api/canvas/files/{fileId}/raw, and subagent:textgen for a vision answer. "
    "Example: Development spend is in the [FY 2024-25 extract](/api/spend). The label in the photo is from [textgen vision](subagent:textgen). "
    "Spend JSON is the real FY 2024-25 extract. Workspace files live in agent_workspace (inbox/, scratch/, any path you create). "
    "Canvas file objects use type viksetu-file with fileId, fileKind (image|text|binary), and name. Drop images on the canvas like any file; "
    "when selected and the model supports vision, image bytes are sent automatically (not via chat). "
    "Reply with JSON only, keys in this order: {\"thinking\": string, \"reply\": string, \"actions\": array, \"continue\": boolean}. "
    "thinking is your visible reasoning for this step, written before you act. "
    "On the first step, restate what the user wants and the plan. On later steps, say what the last result showed and what is next. "
    "Keep it to a few sentences. If the user asked for a map layer change or a new canvas object, actions must include the corresponding ops — reply text alone does nothing on the map. "
    "Work in steps like an IDE agent. Each response is one step: think, do the next concrete actions, then stop. "
    "Do one task at a time. If the user asks for several new things (map and chart, chart and note, two charts, etc.), "
    "never create more than one new map, chart, doc, sheet, embed, or file object in the same step. "
    "Finish the first object, set continue to true, then on the next step create the next one using Canvas JSON positions so nothing overlaps. "
    "Set continue to true when you need to see the canvas or Python output before you can finish. "
    "Set continue to false when the user's request is complete. "
    "When placing a chart next to a map, read the map's x, y, w, h from Canvas JSON and set the chart x to map.x + map.w + 48, y to map.y, w at least 480, h at least 320. "
    "On a continuation you see your own earlier thinking and actions for this request, the result of each, and the page after your previous step. "
    "Use those ids to update or connect objects. "
    "new:0 only refers to an object created in the current step. Do not recreate an object that is already on the canvas. "
    "In the step where continue is false, reply is your final answer. Make it detailed: what you created or changed (type, id, position), "
    "the key numbers you used, and anything left undone. Earlier thinking is not kept for later requests, but your final reply is. "
    "In earlier steps reply is a one line status. "
    "Allowed actions: "
    "{\"op\":\"geo\",\"text\":string,\"geo\":\"rectangle|ellipse|diamond|triangle|hexagon\",\"x\":number,\"y\":number,\"w\":number,\"h\":number,"
    "\"color\":\"black|grey|violet|blue|light-blue|yellow|orange|green|red\"}, "
    "{\"op\":\"text\",\"text\":string,\"x\":number,\"y\":number,\"color\":string}, "
    "{\"op\":\"map\",\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"chart\",\"title\":string,\"chart\":\"bar|line|pie\",\"labels\":[string],\"values\":[number],\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"doc\",\"title\":string,\"format\":\"md|text\",\"body\":string,\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"sheet\",\"title\":string,\"columns\":[string],\"rows\":[[string]],\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"file\",\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"embed\",\"title\":string,\"html\":string,\"data\":any,\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"python\",\"code\":string}, "
    "{\"op\":\"file-read\",\"fileId\":string,\"mode\":\"text|hex|meta|parse\",\"offset\":number,\"length\":number,\"max_chars\":number} "
    "or {\"op\":\"file-read\",\"path\":string relative to agent_workspace}, "
    "{\"op\":\"file-list\",\"path\":string optional directory under agent_workspace}, "
    "{\"op\":\"arrow\",\"from\":string,\"to\":string} using an existing id or new:0, "
    "{\"op\":\"delete\",\"ids\":[string]}, {\"op\":\"zoom\"}, "
    "{\"op\":\"map-layer\",\"layer\":string,\"visible\":boolean}, "
    "{\"op\":\"map-focus\",\"pinId\":string} or {\"lng\":number,\"lat\":number,\"zoom\":number}, "
    "{\"op\":\"map-pin\",\"pinId\":string,\"name\":string,\"description\":string,\"agent_summary\":string} "
    "(writes poi_overrides.json; omit fields you do not change), "
    "{\"op\":\"vision\",\"fileId\":string,\"question\":string} "
    "sends that canvas image to the local textgen vision sub-agent and returns its answer on the next step. "
    "{\"op\":\"web\",\"url\":string} fetches that web page or JSON URL (public http(s), or this app on 127.0.0.1) "
    "and returns title and text on the next step. Cite that url in the reply. "
    "When the user asks to add, place, create, or make a chart, note, sheet, map, or file, you must include that action. "
    "Cursor JSON is the page point under the pointer, or the last known point. New objects are placed just below it; you may omit x and y. "
    "Pass id on chart, doc, sheet, or embed to update that object instead of creating one. The user can also edit titles, notes, chart rows, and sheet cells. "
    "embed is your own custom object for anything the built-in chart, doc, sheet, file, and map cannot show, such as a gauge, a timeline, a table with bars, "
    "a checklist, a comparison card, or a small calculator. html is a self-contained HTML fragment with inline CSS and JavaScript. "
    "It runs in a sandboxed frame with no network, no external scripts, fonts, or images, and no access to the page. Draw with inline SVG or canvas. "
    "The dark theme background is already applied. data is optional JSON, available in the frame as window.DATA, so put the numbers there and read them in your script. "
    "Prefer the built-in chart, doc, sheet, and map when they fit. Use embed when they do not. To change an embed, resend the whole html with its id. "
    "python runs with cwd agent_workspace for up to 45s. You may read, write, rename, and delete files anywhere under that folder. "
    "Use file-read for a quick text/hex/parse peek; use python for heavier transforms. Results of file-read and file-list return on your next step. "
    "Build charts and sheets from Spend JSON, pin counts, sheet cells, or file previews. Do not invent budget numbers. "
    "A chart action must include labels and values copied from that data. values must be plain numbers, not formatted strings."
)


def _canvas_context(req: CanvasChatRequest) -> str:
    layers = (req.map or {}).get("layers") or {}
    enabled = [name for name, on in layers.items() if on]
    disabled = [name for name, on in layers.items() if not on]
    pins = (req.map or {}).get("pins") or []
    hidden = (req.map or {}).get("hiddenPinSamples") or []
    stats = (req.map or {}).get("layerStats") or []
    vision_note = ""
    vision_images = _vision_images_from_canvas(req)
    if vision_images:
        try:
            from llm import resolve_model, supports_vision

            provider, model = resolve_model()
            if supports_vision(provider, model):
                vision_note = (
                    f"{len(vision_images)} canvas image file(s) attached for vision ({model}). "
                    "Selected file shapes are sent first."
                )
            else:
                ids = ", ".join(_canvas_image_ids(req)[:4]) or "unknown"
                vision_note = (
                    f"{len(vision_images)} image file(s) on the canvas ({ids}) but {model} is text-only. "
                    "Call {\"op\":\"vision\",\"fileId\":\"<id>\",\"question\":\"...\"} so the textgen sub-agent can read the image. "
                    "Cite its answer as [textgen vision](subagent:textgen) and the file as "
                    "[file](/api/canvas/files/<fileId>/raw)."
                )
        except Exception:
            vision_note = f"{len(vision_images)} image file(s) on the canvas."
    parts = [
            "Cursor JSON:\n" + json.dumps(req.cursor, ensure_ascii=False),
            "Canvas JSON:\n" + json.dumps(req.canvas[:40], ensure_ascii=False),
            "Selection JSON:\n" + json.dumps(req.selection[:20], ensure_ascii=False),
            "Change log JSON:\n" + json.dumps(req.log[-30:], ensure_ascii=False),
            "Map layers enabled: " + json.dumps(enabled),
            "Map layers disabled: " + json.dumps(disabled),
            "Map layer stats JSON:\n" + json.dumps(stats[:20], ensure_ascii=False),
            f"Visible pins ({(req.map or {}).get('enabledCount', len(pins))} on enabled layers, "
            f"{min(len(pins), 180)} listed):\n"
            + json.dumps(pins[:180], ensure_ascii=False),
            f"Hidden-layer pin samples ({min(len(hidden), 120)} listed, layer off so not on map):\n"
            + json.dumps(hidden[:120], ensure_ascii=False),
            "Selected pin:\n" + json.dumps((req.map or {}).get("selected"), ensure_ascii=False),
            "Pin cards JSON:\n" + json.dumps(_pin_cards_for(req.map or {}, req.message), ensure_ascii=False),
            "Spend JSON:\n" + json.dumps(_spend_brief(), ensure_ascii=False),
            "Workspace files:\n" + json.dumps(_workspace_files(), ensure_ascii=False),
            "Cite sources in reply with markdown links. Spend: /api/spend. "
            "Pin card: /api/poi/card/{pinId}. Layer: /api/geo/layers/{layerId}. "
            "Inbox file: /api/canvas/files/{fileId}/raw. Vision sub-agent: subagent:textgen.",
        ]
    if vision_note:
        parts.insert(0, vision_note)
    return "\n".join(parts)


def _canvas_messages(req: CanvasChatRequest) -> list[dict]:
    from llm import resolve_model, supports_vision, user_message_content

    provider, model = resolve_model()
    vision = supports_vision(provider, model)
    messages: list[dict] = [{"role": "system", "content": CANVAS_SYSTEM}]
    # Earlier prompts contribute only the user text and the final reply. Their thinking and actions are not sent.
    history = [
        item
        for item in req.history
        if str(item.get("text") or "").strip()
    ]
    if not history or history[-1].get("role") != "user" or history[-1].get("text") != req.message:
        history = [*history, {"role": "user", "text": req.message}]
    for index, turn in enumerate(history):
        role = "assistant" if turn.get("role") in ("agent", "assistant") else "user"
        content = str(turn.get("text") or "")
        if not req.trace and index == len(history) - 1 and role == "user":
            content += "\n\n" + _canvas_context(req)
        if role == "user" and index == len(history) - 1:
            imgs = _vision_images_from_canvas(req)
            if imgs and vision:
                messages.append(
                    {
                        "role": "user",
                        "content": user_message_content(content, imgs, vision=True),
                    }
                )
            else:
                messages.append({"role": role, "content": content})
        else:
            messages.append({"role": role, "content": content})
    # This prompt's own steps are sent back in full: what it thought, what it ran, and what happened.
    steps = req.trace[-6:]
    for index, item in enumerate(steps):
        sent = list(item.get("actions") or [])
        for note in item.get("python") or []:
            sent.append({"op": "python", "code": str(note.get("script") or "")})
        for note in item.get("file_tools") or []:
            sent.append(
                {
                    "op": str(note.get("op") or "file-read"),
                    "fileId": note.get("fileId"),
                    "path": note.get("path"),
                    "mode": note.get("mode"),
                }
            )
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "thinking": str(item.get("thinking") or "")[:3000],
                        "reply": str(item.get("reply") or ""),
                        "actions": sent,
                        "continue": True,
                    },
                    ensure_ascii=False,
                )[:30000],
            }
        )
        result_note = {
            "step": index + 1,
            "created": item.get("created") or [],
            "error": item.get("error") or None,
            "python": [
                {"ok": note.get("ok"), "stdout": note.get("stdout"), "stderr": note.get("stderr")}
                for note in (item.get("python") or [])
            ],
            "file_tools": [
                {
                    "ok": note.get("ok"),
                    "mode": note.get("mode"),
                    "path": note.get("path"),
                    "error": note.get("error"),
                    "text": str(note.get("text") or "")[:2000],
                    "dump": str(note.get("dump") or "")[:2000],
                    "preview": str(note.get("preview") or "")[:2000],
                }
                for note in (item.get("file_tools") or [])
            ],
            "subagent": [
                {
                    "ok": note.get("ok"),
                    "provider": note.get("provider") or "textgen",
                    "model": note.get("model"),
                    "fileId": note.get("fileId"),
                    "question": note.get("question"),
                    "answer": str(note.get("answer") or "")[:3000],
                    "error": note.get("error"),
                }
                for note in (item.get("subagent") or [])
            ],
            "web": [
                {
                    "ok": note.get("ok"),
                    "url": note.get("url"),
                    "title": note.get("title"),
                    "error": note.get("error"),
                    "text": str(note.get("text") or "")[:2500],
                }
                for note in (item.get("web") or [])
            ],
        }
        content = "Result of your step " + str(index + 1) + ":\n" + json.dumps(result_note, ensure_ascii=False)[:6000]
        if index == len(steps) - 1:
            content += (
                "\n\nThe page now:\n"
                + _canvas_context(req)
                + "\n\nContinue the original request with the next step. "
                "Set continue to false and give a detailed final reply when it is finished. "
                "Do not recreate objects that already exist."
            )
        messages.append({"role": "user", "content": content})
    return _fit_context(messages)


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        bits = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                bits.append(str(part.get("text") or ""))
            elif isinstance(part, dict) and part.get("type") == "image_url":
                bits.append("[image]")
            else:
                bits.append(str(part))
        return "\n".join(bits)
    return str(content or "")


def _approx_tokens(content) -> int:
    """Rough token count (~4 characters per token) plus a flat cost per image."""
    images = 0
    if isinstance(content, list):
        images = sum(1 for part in content if isinstance(part, dict) and part.get("type") == "image_url")
    return max(1, (len(_content_text(content)) + 3) // 4) + images * 256


def _message_tokens(message: dict) -> int:
    return _approx_tokens(message.get("content")) + 4


def _clip_text(text: str, max_tokens: int) -> str:
    max_chars = max(200, max_tokens * 4)
    if len(text) <= max_chars:
        return text
    marker = "\n\n[…truncated to fit the context limit…]\n\n"
    budget = max(80, max_chars - len(marker))
    head = max(80, budget // 4)
    tail = max(0, budget - head)
    return text[:head] + marker + (text[-tail:] if tail else "")


def _replace_text(content, new_text: str):
    if not isinstance(content, list):
        return new_text
    replaced = False
    out = []
    for part in content:
        if not replaced and isinstance(part, dict) and part.get("type") == "text":
            out.append({**part, "text": new_text})
            replaced = True
        else:
            out.append(part)
    return out if replaced else new_text


def _fit_context(messages: list[dict]) -> list[dict]:
    """Keep the prompt within CANVAS_CONTEXT_TOKENS by dropping the oldest chat first."""
    budget = CANVAS_CONTEXT_TOKENS

    def total(msgs: list[dict]) -> int:
        return sum(_message_tokens(item) for item in msgs)

    if not messages or total(messages) <= budget:
        return messages

    system = dict(messages[0])
    rest = [dict(item) for item in messages[1:]]
    if not rest:
        system["content"] = _clip_text(_content_text(system.get("content")), max(64, budget - 8))
        return [system]

    tail = [rest[-1]]
    head = rest[:-1]
    dropped = 0
    while head and total([system, *head, *tail]) > budget:
        head.pop(0)
        dropped += 1
    out = [system, *head, *tail]
    if dropped:
        out[0]["content"] = (
            str(out[0].get("content") or "")
            + f"\n\nEarlier chat turns were omitted because this request exceeded the {budget} token context limit."
        )
    while len(out) > 2 and total(out) > budget:
        out.pop(1)
    for _ in range(6):
        if total(out) <= budget:
            break
        index = max(range(len(out)), key=lambda i: _message_tokens(out[i]))
        overflow = total(out) - budget
        target = max(64, _message_tokens(out[index]) - overflow - 8)
        text = _clip_text(_content_text(out[index].get("content")), target)
        out[index] = {**out[index], "content": _replace_text(out[index].get("content"), text)}
    return out


_PLACERS = frozenset({"map", "chart", "doc", "sheet", "embed", "file"})


def _one_placer_per_step(actions: list) -> tuple[list, bool]:
    """Keep at most one new embed object per step so map+chart requests do not overlap."""
    placed = [action for action in actions if isinstance(action, dict) and action.get("op") in _PLACERS]
    if len(placed) <= 1:
        return actions, False
    kept: list = []
    kept_one = False
    for action in actions:
        if not isinstance(action, dict) or action.get("op") not in _PLACERS:
            kept.append(action)
            continue
        if kept_one:
            continue
        kept.append(action)
        kept_one = True
    return kept, True


def _package_turn(req: CanvasChatRequest, text: str, provider, model) -> dict:
    turn = _parse_canvas_turn(text)
    hydrated = _hydrate_actions(turn["actions"], req.message)
    actions, file_notes, python_notes, sub_notes, web_notes = _split_agent_tools(hydrated, req)
    actions = _drop_unasked_embeds(req.message, actions)
    actions, model_omitted_layers = _require_map_layer_actions(req.message, actions)
    actions = _normalize_map_layer_actions(actions)
    actions, deferred = _one_placer_per_step(actions)
    layer_tool_note = ""
    if model_omitted_layers and _target_pin_layer_visibility(req.message):
        layer_tool_note = (
            " (Applied map-layer tools for your request; always emit map-layer actions yourself in future steps.)"
        )
    for note in python_notes:
        note["stdout"] = str(note.get("stdout") or "")[-2500:]
        note["stderr"] = str(note.get("stderr") or "")[-800:]
    for note in file_notes:
        for key in ("text", "dump", "preview"):
            if key in note and isinstance(note[key], str):
                note[key] = note[key][:4000]
    asked = turn.get("continue")
    carry_on = True if python_notes or file_notes or sub_notes or web_notes or deferred else bool(asked)
    return {
        "thinking": turn.get("thinking") or "",
        "reply": turn["reply"] + layer_tool_note,
        "actions": actions,
        "continue": carry_on,
        "python": python_notes,
        "file_tools": file_notes,
        "subagent": sub_notes,
        "web": web_notes,
        "source": "llm",
        "provider": provider,
        "model": model,
    }


def _error_turn(exc: Exception) -> dict:
    return {
        "reply": f"The model did not answer: {exc}",
        "actions": [],
        "source": "error",
        "provider": os.environ.get("LLM_PROVIDER", "textgen"),
        "model": None,
    }


@app.post("/api/canvas/chat")
def canvas_chat(req: CanvasChatRequest):
    """LLM turn with shapes, sizes, live pins, files, and an optional workspace Python step."""
    try:
        from llm import chat

        result = chat(_canvas_messages(req), temperature=0.2, json_mode=True, timeout=120, max_tokens=CANVAS_MAX_TOKENS)
        return _package_turn(req, result["text"], result.get("provider"), result.get("model"))
    except Exception as exc:
        return _error_turn(exc)


@app.post("/api/canvas/chat/stream")
def canvas_chat_stream(req: CanvasChatRequest, request: Request):
    """Same turn as /api/canvas/chat, sent as lines of JSON: delta chunks while the model writes, then one final."""

    def events():
        try:
            from llm import chat_stream

            for item in chat_stream(
                _canvas_messages(req),
                temperature=0.2,
                timeout=120,
                max_tokens=CANVAS_MAX_TOKENS,
            ):
                if item.get("done"):
                    final = _package_turn(req, item["text"], item.get("provider"), item.get("model"))
                    yield json.dumps({"type": "final", **final}, ensure_ascii=False) + "\n"
                else:
                    yield json.dumps({"type": "delta", "text": item["delta"]}, ensure_ascii=False) + "\n"
        except Exception as exc:
            yield json.dumps({"type": "final", **_error_turn(exc)}, ensure_ascii=False) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
