# VikSetu — 6-slide presentation

Hook → content → punch per slide. Each slide introduces a distinct angle (no repeated ideas).

---

## Slide 1 — The gap

**Hook:** Field teams juggle a map in one tab, spreadsheets in another, and a chatbot that cannot see either.

**Content:**

- District work needs **geography, numbers, and documents** at once—not three disconnected tools.
- Switching context loses **where** something matters and **what** backs a claim.

**Punch:** VikSetu is built to **fuse map, workspace, and reasoning** in one place—not to replace your GIS, but to **shorten the path from seeing to deciding**.

---

## Slide 2 — What VikSetu is

**Hook:** A Palghar-focused **MapLibre dashboard** plus an **infinite tldraw canvas** driven by an **LLM agent**.

**Content:**

- **Named product:** VikSetu — map + canvas + agent, wired to real district assets.
- **Primary experience:** explore layers and pins on the map UI; ideate and compose on the canvas with the agent beside you.

**Punch:** It is **one product surface** for **spatial context** and **open-ended collaboration**, not a generic chat window.

---

## Slide 3 — Map & data layer

**Hook:** The map is not wallpaper—it carries **district geometry, POIs, and spend signals** the system can serve to the UI.

**Content:**

- **Stack:** MapLibre front end (`web/`) talking to APIs that expose **GeoJSON layers** and **POI card** endpoints (`/api/poi/card/...`).
- **Operational data:** spend series and derived CSV under `data/palghar_2024_25/`—grounding **budget narrative** next to **place**.

**Punch:** The map is the **shared coordinate system** for money, place, and narrative—without every answer living in a static screenshot.

---

## Slide 4 — Canvas agent & multimodal work

**Hook:** On the canvas, the agent does not guess in a void—it **sees layout, selection, layers, and files** you drop in.

**Content:**

- **tldraw canvas** (`canvas/`): charts, text, sheets, embeds, file drops into `agent_workspace/inbox/`.
- **Agent tools:** **file read/list**, **workspace Python**, **vision** over images, **web fetch** for public pages or local API URLs, **map-layer / map-focus / map-pin** to steer the map.
- Chat **truncates oldest turns** under configurable token budgets so long sessions stay bounded.

**Punch:** The agent is a **teammate on the same board**—it can **read what you dropped**, **run code**, and **steer the map**, not just type paragraphs.

---

## Slide 5 — Backend & model flexibility

**Hook:** One **FastAPI** service powers the stack; you choose **how** the model runs without rewriting the app.

**Content:**

- **API:** `backend/main.py` — geo, spend, chat, canvas agent, uploads.
- **LLM routing:** `backend/llm.py` — **text-generation-webui (OpenAI-compatible)**, **DeepInfra**, **Gemini**, **Ollama** via `LLM_PROVIDER` and related env vars.
- **Run pattern:** map UI proxies one port; canvas UI proxies another; health check confirms provider/model.
- **Workspace:** `agent_workspace/` with **inbox** and **scratch** keeps agent file I/O predictable.

**Punch:** **Swap provider or model from configuration**—the product stays one codebase; only the **brain** changes.

---

## Slide 6 — Demo story & integrity

**Hook:** A credible demo is **show, don’t tell**: layer on → pin → drop a file → ask for a chart → watch the map update from the agent.

**Content:**

- **Attribution:** MapLibre / OSM / CARTO credits and **tldraw watermark** stay visible—project policy.
- **Public footprint:** Source and docs live at [github.com/Pok8TheCoder/VikSetu](https://github.com/Pok8TheCoder/VikSetu).

**Punch:** VikSetu sells **traceable, spatial, multimodal workflow**—and respects **licensing and provenance** so the story holds up in a room, not just in a slide.

---

## Slide-building tips

- Paste each `## Slide N` section as **one slide**.
- Use **Hook** as title or first line; **Content** as bullets; **Punch** as closing line or callout box.
