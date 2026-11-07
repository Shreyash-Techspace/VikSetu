# VikSetu

Palghar district map dashboard plus an infinite **tldraw** canvas with an LLM agent (map layers, pins, charts, files, workspace Python). **Default LLM:** text-generation-webui (`LLM_PROVIDER=textgen` in `backend/.env`).

**Remote:** [github.com/Pok8TheCoder/VikSetu](https://github.com/Pok8TheCoder/VikSetu)

## Repository layout

```
backend/              FastAPI (geo, spend, chat, canvas agent, file upload)
backend/llm.py        LLM client (textgen · deepinfra · gemini · ollama)
backend/agent_files.py  Agent file-read / list tools
web/                  MapLibre dashboard (embed map for canvas)
canvas/               tldraw + agent panel
agent_workspace/      Agent sandbox — inbox/, scratch/, python cwd
scripts/              Geo fetch, POI cards, clipping
data/geo/             GeoJSON, regions, poi_cards.json
data/palghar_2024_25/ FY spend CSV and source PDFs
```

## Prerequisites

- Python 3.11+ and `pip install -r backend/requirements.txt`
- Node.js 18+ for `web/` and `canvas/` (`npm install` in each once)

## Environment

Copy `backend/.env.example` to `backend/.env` (already used if present). The API loads `backend/.env` and repo-root `.env` on startup.

| Variable | Purpose |
|----------|---------|
| `LLM_PROVIDER` | `textgen` (default), `deepinfra`, `gemini`, or `ollama` |
| `TEXTGEN_BASE_URL` | OpenAI-compatible URL, default `http://127.0.0.1:5000/v1` |
| `TEXTGEN_MODEL` | Optional model id; if empty, uses the model loaded in the WebUI |
| `TEXTGEN_API_KEY` | Default `none` (WebUI often ignores this) |
| `DEEPINFRA_API_KEY` | Required when `LLM_PROVIDER=deepinfra` ([API keys](https://deepinfra.com/dash/api_keys)) |
| `DEEPINFRA_MODEL` | Default `deepseek-ai/DeepSeek-V4.1-Flash-1017` |
| `DEEPINFRA_BASE_URL` | Default `https://api.deepinfra.com/v1/openai` ([docs](https://docs.deepinfra.com/)) |
| `GOOGLE_API_KEY` | Required only when `LLM_PROVIDER=gemini` |
| `CANVAS_MAX_TOKENS` | Max completion tokens per agent step (default `4096`) |
| `CANVAS_CONTEXT_TOKENS` | Max prompt tokens (default `12000`). Oldest chat turns are dropped first |

**text-generation-webui:** start with the OpenAI API enabled (`--api`), load your model (e.g. Qwen3-VL), then start VikSetu APIs.

**DeepInfra:** set `LLM_PROVIDER=deepinfra` and `DEEPINFRA_API_KEY` in `backend/.env`, restart the API on 8001/8002.

```powershell
pip install -r backend/requirements.txt
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8002
```

Check: `GET http://127.0.0.1:8002/api/health` should show `"llm": "textgen"` and your model name.

## Run the full stack (four terminals)

From the **repository root** (`Indus_Training` or your clone folder).

**1 — Map API (8001)**

```powershell
cd backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

**2 — Canvas API (8002)** — same app, second port for the canvas Vite proxy

```powershell
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8002
```

**3 — Map UI (5173)**

```powershell
cd web
npm run dev
```

Open **http://127.0.0.1:5173** — `/api` proxies to **8001**.

**4 — Canvas UI (5175)**

```powershell
cd canvas
npm run dev
```

Open **http://127.0.0.1:5175** — `/api` proxies to **8002**.

After changing `backend/main.py`, restart the **8002** process (canvas API does not use `--reload` above).

## Geo and POI data

One-time or when refreshing OSM data:

```powershell
python scripts/fetch_geo.py
python scripts/fetch_talukas_and_pois.py
python scripts/build_poi_cards.py
python scripts/clip_pois_to_district.py
```

Manual pin enrichments: edit `data/geo/poi_overrides.json`, then run `build_poi_cards.py` again.

API: `GET /api/poi/card/{pin_id}` · `GET /api/poi/cards?q=…`

## Canvas agent (short)

- Sees canvas object positions, selection, map layers/pins, workspace file listing.
- **Files:** drop on canvas → `agent_workspace/inbox/`; use agent actions `file-read` / `file-list` or `python` in the workspace.
- **Images:** the lead model calls `{"op":"vision","fileId","question"}`. That runs on local text-generation-webui and the answer comes back on the next step. Replies cite sources as markdown links (`/api/spend`, `/api/poi/card/{id}`, `/api/geo/layers/{id}`, `/api/canvas/files/{id}/raw`, `subagent:textgen`).
- **Web:** action `{"op":"web","url":"https://..."}` fetches a page or JSON API (including `http://127.0.0.1:8001/api/geo/talukas`) and returns the text on the next step.
- **Map:** actions `map-layer`, `map-focus`, `map-pin` (pin text → `poi_overrides.json`).

## Attribution

Keep MapLibre/OSM/CARTO credits and the tldraw watermark visible (project policy).
