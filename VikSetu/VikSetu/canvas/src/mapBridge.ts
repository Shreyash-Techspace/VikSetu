import type { CanvasAction } from "./canvasAgent";

const MAP_AGENT_OPS = new Set(["map-layer", "map-focus", "map-pin"]);

/** POI circle layers on the Palghar map (not taluka_regions). */
export const MAP_PIN_LAYERS = [
  "government_school",
  "health_facility",
  "government_facility",
  "community_poi",
  "other_poi",
  "development",
] as const;

export function coerceMapVisible(value: unknown): boolean {
  if (value === false || value === 0) return false;
  if (typeof value === "string") {
    const s = value.trim().toLowerCase();
    if (s === "false" || s === "off" || s === "no" || s === "0") return false;
    if (s === "true" || s === "on" || s === "yes" || s === "1") return true;
  }
  return Boolean(value);
}

/** Last layer toggles from the agent — replayed when a new map iframe loads. */
let layerOverrides: Record<string, boolean> = {};

export function isMapAgentAction(action: CanvasAction): boolean {
  return MAP_AGENT_OPS.has(action.op);
}

export function splitMapActions(actions: CanvasAction[]): { map: CanvasAction[]; canvas: CanvasAction[] } {
  const map: CanvasAction[] = [];
  const canvas: CanvasAction[] = [];
  for (const action of actions) {
    if (isMapAgentAction(action)) map.push(action);
    else canvas.push(action);
  }
  return { map, canvas };
}

function postToMapFrames(payload: Record<string, unknown>) {
  for (const iframe of document.querySelectorAll(".vik-map-stage iframe")) {
    (iframe as HTMLIFrameElement).contentWindow?.postMessage({ source: "viksetu-canvas", ...payload }, "*");
  }
}

export function replayMapLayerState() {
  if (!Object.keys(layerOverrides).length) return;
  postToMapFrames({ kind: "set-layers", layers: { ...layerOverrides } });
}

export async function applyMapActions(actions: CanvasAction[]): Promise<{ notes: string[]; errors: string[] }> {
  const notes: string[] = [];
  const errors: string[] = [];
  for (const action of actions) {
    if (action.op === "map-layer") {
      const layer = String((action as { layer?: string }).layer ?? "");
      if (!layer) {
        errors.push("map-layer missing layer id");
        continue;
      }
      const visible = coerceMapVisible((action as { visible?: unknown }).visible);
      layerOverrides[layer] = visible;
      postToMapFrames({ kind: "set-layer", layer, visible });
      notes.push(`layer ${layer} → ${visible ? "on" : "off"}`);
    } else if (action.op === "map-focus") {
      const raw = action as { pinId?: string; lng?: number; lat?: number; zoom?: number };
      postToMapFrames({
        kind: "focus-pin",
        pinId: raw.pinId,
        lng: raw.lng,
        lat: raw.lat,
        zoom: raw.zoom,
      });
      notes.push(raw.pinId ? `focus pin ${raw.pinId}` : "focus map view");
    } else if (action.op === "map-pin") {
      const raw = action as {
        pinId?: string;
        name?: string;
        description?: string;
        agent_summary?: string;
      };
      const pinId = String(raw.pinId ?? "");
      if (!pinId) {
        errors.push("map-pin missing pinId");
        continue;
      }
      const patch: Record<string, string> = {};
      if (raw.name) patch.name = raw.name;
      if (raw.description) patch.description = raw.description;
      if (raw.agent_summary) patch.agent_summary = raw.agent_summary;
      if (!Object.keys(patch).length) {
        errors.push(`map-pin ${pinId}: no fields to update`);
        continue;
      }
      try {
        const response = await fetch(`/api/poi/card/${encodeURIComponent(pinId)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
        if (!response.ok) {
          errors.push(`map-pin ${pinId}: ${await response.text()}`);
          continue;
        }
        postToMapFrames({ kind: "refresh-pin", pinId });
        notes.push(`updated pin card ${pinId}`);
      } catch (failure) {
        errors.push(`map-pin ${pinId}: ${String(failure)}`);
      }
    }
  }
  return { notes, errors };
}
