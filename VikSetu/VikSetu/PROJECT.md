# VikSetu — Project documentation

This document describes the **Indus_Training** / **VikSetu** codebase: what the product is for, how it is structured, what runs in production for a demo, and what exists as experiments or planning material.

**Public repo:** [github.com/Pok8TheCoder/VikSetu](https://github.com/Pok8TheCoder/VikSetu)

---

## 1. What VikSetu is

**VikSetu** is a **civic geospatial analytics** project centered on **Palghar district (Maharashtra)**. It combines:

1. A **map dashboard** (MapLibre + React) for exploring district geometry, talukas, facility-style POI layers, and policy-linked narratives where data exists.
2. An **infinite canvas** (tldraw + React) with an **LLM-backed agent** that reasons over canvas layout, user selection, map state, uploaded files, and optional Python execution in a sandbox folder.

The design goal is **decision support**: tie **place**, **published numbers** (where extracted), and **user-dropped evidence** (files) together so answers can be **grounded** and **steer the UI** (layers, focus, pins, charts/embeds)—not a generic chat-only bot.

---

## 2. High-level architecture

| Layer | Technology | Role |
|-------|--------------|------|
| **Map UI** | Vite, React 18, MapLibre GL | District map, layers, pins, chat stub that can patch filters/layers/charts via API. |
| **Canvas UI** | Vite, React 18, tldraw | Whiteboard with shapes (including custom embeds/charts/sheets), file drops, agent panel. |
| **API** | FastAPI (`backend/main.py`) | Single Python app: geo, POI cards, spend CSV, map chat, canvas uploads, workspace Python, canvas agent (JSON + streaming). |
| **LLM** | `backend/llm.py` | OpenAI-shaped `/chat/completions` to **text-generation-webui**, **DeepInfra**, **Gemini**, or **Ollama**. |
| **Workspace** | `agent_workspace/` | Sandboxed file area: `inbox/` (uploads), `scratch/`; Python runs with cwd under this tree. |
| **Static / derived data** | `data/geo/`, `data/palghar_2024_25/` | GeoJSON, POI cards, spend CSV and related sources. |

**Typical local run:** two API ports (map vs canvas proxies), two dev servers:

- Map API **8001** → map UI **5173** (`/api` → 8001).
- Canvas API **8002** → canvas UI **5175** (`/api` → 8002).

Same FastAPI app is started twice so each Vite proxy targets a dedicated backend port. See `README.md` for exact commands.

---

## 3. Repository layout (what matters)

```
backend/
  main.py           # FastAPI: all HTTP routes, canvas agent orchestration, spend, geo, chat
  llm.py            # Provider switch + chat (incl. JSON mode, streaming for canvas)
  agent_files.py    # Safe path resolution + file-read/list helpers for the agent
  geo_utils.py      # GeoJSON loading, taluka filters, map helpers
  requirements.txt  # Python dependencies
  .env.example      # Template for LLM and canvas token limits

web/                # MapLibre dashboard (npm: viksetu-web)
canvas/             # tldraw + agent (npm: viksetu-canvas)

agent_workspace/    # Runtime sandbox (inbox/, scratch/); not all files may be committed
data/
  geo/              # GeoJSON layers, regions, poi_cards.json, poi_overrides.json
  palghar_2024_25/  # FY spend derived CSV, PDFs, analysis scripts
  docs/             # Sample narrative MD files (for experiments / RAG-style demos)
  bench/            # Bench zips / synthetic data (when generated)

scripts/            # fetch_geo, POI pipeline, clipping, build_agent_bench, etc.

# Training / course / research scripts (root)
01_first_call.py … 14_injection.py   # Stepped LLM lessons (temperature, tools, RAG, etc.)
VIKSETU_IMPLEMENTATION_PLAN.md       # Long-form vision (pipeline, DB, multilingual) — planning
VIKSETU_5DAY_SPRINT.md               # Sprint notes (if present)
VIKSETU_6_SLIDES.md                  # Presentation outline
README.md                            # Quick start, env table, stack commands
```

---

## 4. Backend API (implemented)

All routes live in `backend/main.py`. Notable groups:

### Health and geo

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness; reports resolved LLM provider/model (and vision flag where applicable). |
| GET | `/api/regions` | Region metadata. |
| GET | `/api/geo/talukas` | Taluka listing / geometries as used by the map stack. |
| GET | `/api/geo/district` | District boundary / feature. |
| GET | `/api/geo/bbox` | Bounding box for fit/focus. |
| GET | `/api/geo/layers/{layer_id}` | GeoJSON (or filtered chunks) for named layers. |

### POI “cards”

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/poi/cards` | Search/list POI card summaries (ties narrative + ids). |
| GET | `/api/poi/card/{pin_id}` | Single pin card payload. |
| PATCH | `/api/poi/card/{pin_id}` | Update/enrich card content (supports manual overrides workflow). |

### Spend (derived CSV)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/spend` | FY spend rows from `data/palghar_2024_25/derived/ps_sector_spend_2024_25.csv` ( sector totals, etc.). |

### Map dashboard chat (lighter)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/chat` | Keyword-style **UI patches** (layers, taluka focus, chart id) plus **optional LLM** fallback via `llm.ask` for other queries. Returns `{ answer, ui_patch }`. |

### Canvas agent

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/canvas/files` | Base64 upload → `agent_workspace/inbox/`; returns `fileId`, kind, short preview. |
| GET | `/api/canvas/files/{file_id}/raw` | Raw file download for browser/embed/vision. |
| POST | `/api/canvas/python` | Execute Python **inside** `agent_workspace` (restricted tree). |
| POST | `/api/canvas/chat` | One agent **turn**: model returns structured JSON (reply + **actions**); server resolves tools (files, python, web, subagent, map). |
| POST | `/api/canvas/chat/stream` | Same as chat, but **NDJSON stream**: token deltas, then one `final` object with merged tool results. |

---

## 5. LLM configuration (`backend/llm.py`, `backend/.env`)

Environment variables are loaded from **repo root `.env`** and **`backend/.env`** on startup.

| `LLM_PROVIDER` | Backend |
|----------------|---------|
| `textgen` (default) | text-generation-webui OpenAI-compatible API (`TEXTGEN_BASE_URL`, optional `TEXTGEN_MODEL`). |
| `deepinfra` | DeepInfra OpenAI-compatible (`DEEPINFRA_API_KEY`, model, optional reasoning effort). |
| `gemini` | Google Generative Language OpenAI-compatible surface (`GOOGLE_API_KEY`, etc.). |
| `ollama` | Local Ollama OpenAI-compatible (`OLLAMA_BASE`, `OLLAMA_MODEL`). |

**Canvas-specific:**

- `CANVAS_MAX_TOKENS` — cap per completion (default 4096).
- `CANVAS_CONTEXT_TOKENS` — approximate prompt budget; **oldest chat turns dropped first** when over budget.

The client uses **stdlib** `urllib` (no heavy SDK requirement in the hot path) and normalizes UTF-8 on stdio where possible for Windows.

---

## 6. Canvas agent behavior (conceptual)

The canvas sends a rich **state payload** each turn: user message, **history**, **canvas shapes** (positions, types, selection), optional **map** snapshot (layers, pins), **cursor**, **step**, **trace**. The model is prompted to answer with **JSON** containing at least `reply` and `actions` (list). The server:

1. **Parses** model output (strips `think` blocks, fenced JSON, etc.).
2. **Splits** tool-like actions: file tools, **python**, **subagent**, **web** fetch, remaining map/canvas ops.
3. **Executes** safe operations (e.g. read files under workspace, run Python in workspace, fetch URLs with HTML-to-text caps).
4. **Packages** notes (stdout/stderr snippets, file excerpts, web text) back into the response for the **next** client step or for the final merged payload in streaming mode.

**Representative action families** (exact schema is enforced in prompts and parsing in `main.py`):

- **Map:** `map-layer`, `map-focus`, `map-pin` (pins can feed `poi_overrides.json` semantics).
- **Files:** read/list operations delegated to `agent_files.py` with path sandbox rules.
- **Code:** `python` runs under `agent_workspace/`.
- **Vision:** `vision` when an image file is selected (depends on provider capabilities, often local textgen + VLM).
- **Web:** `web` fetches a URL or local API URL; returns truncated text/JSON summary.
- **Rich canvas:** embed/custom HTML/charts/sheets as shape-related ops (with guards, e.g. embed only when user language suggests it).

Responses can set **`continue`** to suggest another model hop in the same user “step” when tool notes need follow-up; the UI may loop until `continue` is false or the user stops.

---

## 7. Data assets

- **`data/geo/`** — GeoJSON layers, `regions.json`, **`poi_cards.json`** (generated/enriched POI narratives), **`poi_overrides.json`** for manual enrichments. Scripts such as `scripts/fetch_geo.py`, `scripts/build_poi_cards.py`, and `scripts/clip_pois_to_district.py` rebuild or refresh these.
- **`data/palghar_2024_25/`** — Source PDFs/CSVs for a **FY 2024–25** public-finance style extract; **`derived/ps_sector_spend_2024_25.csv`** backs `/api/spend`. Supporting scripts (`preanalyze.py`, etc.) document how tables were derived.

---

## 8. Frontends

### Map app (`web/`)

- **MapLibre** map with layer panels and pin detail UI.
- Talks to `/api/*` on the dev proxy port (8001 in the documented setup).

### Canvas app (`canvas/`)

- **tldraw** infinite canvas; custom shapes for charts, markdown/text, sheets, map embed, file drops.
- **Agent panel** streams or polls canvas chat; persists session nuances as implemented in `canvas/src/` (e.g. agent log, embed pipeline).

---

## 9. Scripts and tooling

- **`scripts/`** — Geodata fetch, taluka/POI pipelines, POI card builder, district clipping, **`build_agent_bench.py`** for synthetic benchmark zips (multilingual / mixed file trees for agent testing).
- **`generate_viksetu_pdf.py`** — PDF generation helper (project-specific reports).
- **Root `agent.py`, `tools.py`, `store.py`, `graph.py`** — Older or parallel agent experiments; the **shipping** agent loop for the product is in **`backend/main.py`** + **`canvas`**.

---

## 10. Course / lab modules (root `01_*.py` … `14_*.py`)

These files are **instructional or experimental** stepping stones: first LLM calls, temperature, JSON output, tool calling, ReAct-style loops, LangGraph-style graphs, RAG (`10_rag_agent.py` + `data/index_keyword.json`), grounded retrieval (`11_grounded.py`), multi-agent (`12_multi_agent.py`), benchmarks (`13_benchmark.py`), injection/safety (`14_injection.py`). They document **how the team learned** to compose agents; they are **not** the same as the production FastAPI canvas pipeline unless wired explicitly.

---

## 11. Planning vs shipped product

- **`VIKSETU_IMPLEMENTATION_PLAN.md`** describes a **broader** vision: drag-drop ingest pipelines, SQLite, multilingual OCR strategy, full trace logs, multi-district rollout. **Much of that is design intent**, not a guarantee that every node exists as code in this repo.
- The **currently integrated demo path** is: **FastAPI + map UI + canvas UI + `llm.py` + workspace files + `/api/spend` + geo/POI endpoints**, as summarized above and in **`README.md`**.

---

## 12. Policies and attribution

- **Map:** Respect **MapLibre**, **OpenStreetMap**, and **CARTO** (or other basemap) **attribution** as configured in the map app.
- **Canvas:** Keep the **tldraw** watermark visible per project policy.

---

## 13. Quick verification

After starting the API:

```http
GET http://127.0.0.1:8002/api/health
```

Expect JSON including resolved **`llm`** provider and model name (exact fields depend on `llm` implementation).

---

## 14. Glossary

| Term | Meaning |
|------|---------|
| **VikSetu** | Project/product name; “setu” (bridge) framing for connecting citizens/data/places. |
| **POI card** | Structured JSON payload describing a map pin: title, narrative hooks, links to sources where modeled. |
| **Workspace** | `agent_workspace/` tree; agent Python and file tools are constrained here. |
| **UI patch** | Map chat response shape: filters, layers, optional chart key, map focus — applied by the web client. |

---

*Last updated from repository inspection (structure and routes as implemented in `backend/main.py`). For command-by-command setup, prefer `README.md`.*
