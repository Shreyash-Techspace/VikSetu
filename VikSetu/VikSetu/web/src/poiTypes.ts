import { googleDirectionsUrl, googlePlaceUrl } from "./maps";

export type FyHistoryRow = {
  fy: string;
  status: string;
  spend_inr?: number | null;
  notes?: string;
  source_doc?: string | null;
};

export type PoiCard = {
  pin_id: string;
  name: string;
  category: string;
  layer?: string;
  description: string;
  coordinates: [number, number];
  taluka_id?: string | null;
  amenity?: string | null;
  operator?: string | null;
  google_maps_directions_url: string;
  google_maps_place_url: string;
  fy_history: FyHistoryRow[];
  agent_summary: string;
  sources?: string[];
};

export function cardFromFeatureProps(
  props: Record<string, string | number | undefined>,
  layerId: string,
  coordinates: [number, number]
): PoiCard {
  const name = String(props.name ?? "Unnamed site");
  const [lon, lat] = coordinates;
  const pinId = String(props.pin_id ?? `${layerId}-${lon}-${lat}`);
  const directions =
    (props.google_maps_directions_url as string) || googleDirectionsUrl(lat, lon, name);
  const fy0 = {
    fy: "2024-25",
    status: String(props.status ?? props.development_status ?? "operating"),
    notes: String(props.source ?? "openstreetmap"),
    source_doc: props.source ? String(props.source) : null,
  };
  return {
    pin_id: pinId,
    name,
    category: String(props.category ?? layerId),
    description: String(props.category_label ?? props.category ?? layerId),
    coordinates: [lon, lat],
    taluka_id: props.taluka_id ? String(props.taluka_id) : null,
    google_maps_directions_url: directions,
    google_maps_place_url: googlePlaceUrl(lat, lon, name),
    fy_history: [fy0],
    agent_summary: `${name} (${props.category ?? layerId}) at ${lat.toFixed(4)}, ${lon.toFixed(4)}.`,
  };
}
