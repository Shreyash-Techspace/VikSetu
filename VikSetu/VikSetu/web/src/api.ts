const API = import.meta.env.VITE_API_URL ?? "";

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export type SpendRow = {
  sector_en: string;
  sector_mr: string;
  actual_spend_inr: string;
  final_allocation_inr: string;
};

export type RegionsManifest = {
  district: {
    center: [number, number];
    bbox?: [number, number, number, number];
    talukas: { id: string; name: string }[];
  };
  layers: Record<string, { label: string; color: string }>;
  talukas: { id: string; name: string; centroid: [number, number] }[];
};

export type GeoFeatureCollection = {
  type: "FeatureCollection";
  features: unknown[];
};

export async function fetchRegions() {
  return apiGet<RegionsManifest>("/api/regions");
}

export async function fetchDistrict() {
  return apiGet<GeoFeatureCollection>("/api/geo/district");
}

export async function fetchTalukas() {
  return apiGet<GeoFeatureCollection>("/api/geo/talukas");
}

export async function fetchLayer(id: string) {
  return apiGet<GeoFeatureCollection>(`/api/geo/layers/${id}`);
}

export async function fetchSpend() {
  return apiGet<{ rows: SpendRow[]; total: SpendRow | null }>("/api/spend");
}

import type { PoiCard } from "./poiTypes";

export async function fetchPoiCard(pinId: string) {
  return apiGet<PoiCard>(`/api/poi/card/${encodeURIComponent(pinId)}`);
}

export async function postChat(message: string, ui_state: object) {
  const r = await fetch(`${API}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, ui_state }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ answer: string; ui_patch: Record<string, unknown> }>;
}
