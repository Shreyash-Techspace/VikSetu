import { useCallback, useEffect, useRef, useState } from "react";
import { Map } from "maplibre-gl";
import {
  fetchDistrict,
  fetchLayer,
  fetchPoiCard,
  fetchRegions,
  fetchSpend,
  fetchTalukas,
  postChat,
  type RegionsManifest,
  type SpendRow,
} from "./api";
import { LayerIndexPanel } from "./LayerIndexPanel";
import { PinDetailPanel } from "./PinDetailPanel";
import { cardFromFeatureProps, type PoiCard } from "./poiTypes";

const LAYER_IDS = [
  "government_school",
  "health_facility",
  "government_facility",
  "community_poi",
  "other_poi",
  "development",
] as const;

type LayerId = (typeof LAYER_IDS)[number];

const EMBED = new URLSearchParams(window.location.search).get("embed") === "1";
const READ_ONLY = import.meta.env.VITE_READ_ONLY === "true";
const LAYER_KEY = "viksetu-map-layers";
const VIEW_KEY = "viksetu-map-view";

const DEFAULT_LAYERS: Record<string, boolean> = {
  taluka_regions: true,
  government_school: true,
  health_facility: true,
  government_facility: true,
  community_poi: false,
  other_poi: false,
  development: true,
};

type PinBrief = {
  pinId: string;
  name: string;
  category: string;
  lng: number;
  lat: number;
  taluka: string;
};

function loadLayers(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(LAYER_KEY);
    if (!raw) return DEFAULT_LAYERS;
    return { ...DEFAULT_LAYERS, ...(JSON.parse(raw) as Record<string, boolean>) };
  } catch {
    return DEFAULT_LAYERS;
  }
}

function loadView(): { center: [number, number]; zoom: number } | null {
  try {
    const raw = localStorage.getItem(VIEW_KEY);
    if (!raw) return null;
    const view = JSON.parse(raw) as { center?: [number, number]; zoom?: number };
    if (!view.center || view.center.length !== 2 || typeof view.zoom !== "number") return null;
    return { center: view.center, zoom: view.zoom };
  } catch {
    return null;
  }
}

function coerceLayerVisible(value: unknown): boolean {
  if (value === false || value === 0) return false;
  if (typeof value === "string") {
    const s = value.trim().toLowerCase();
    if (s === "false" || s === "off" || s === "no" || s === "0") return false;
    if (s === "true" || s === "on" || s === "yes" || s === "1") return true;
  }
  return Boolean(value);
}

function applyLayersToMap(map: Map | null, layerState: Record<string, boolean>) {
  if (!map || !map.isStyleLoaded()) return;
  for (const lid of LAYER_IDS) {
    const circleId = `circle-${lid}`;
    if (map.getLayer(circleId)) {
      map.setLayoutProperty(circleId, "visibility", layerState[lid] ? "visible" : "none");
    }
  }
  for (const lid of ["taluka-fill", "taluka-boundary"]) {
    if (map.getLayer(lid)) {
      map.setLayoutProperty(lid, "visibility", layerState.taluka_regions ? "visible" : "none");
    }
  }
}

function postMap(payload: Record<string, unknown>) {
  if (!EMBED || window.parent === window) return;
  window.parent.postMessage({ source: "viksetu-map", ...payload }, "*");
}

const CATEGORY_COLORS: Record<string, string> = {
  government_school: "#2563eb",
  health_facility: "#dc2626",
  government_facility: "#7c3aed",
  community_poi: "#059669",
  other_poi: "#64748b",
  development: "#f59e0b",
};

export default function App() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapWrapRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const [regions, setRegions] = useState<RegionsManifest | null>(null);
  const [spend, setSpend] = useState<SpendRow[]>([]);
  const [selectedCard, setSelectedCard] = useState<PoiCard | null>(null);
  const [cardLoading, setCardLoading] = useState(false);
  const pinIndexRef = useRef<Record<string, PinBrief[]>>({});
  const [layers, setLayers] = useState<Record<string, boolean>>(loadLayers);
  const [chat, setChat] = useState("");
  const [messages, setMessages] = useState<{ role: string; text: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [mapError, setMapError] = useState<string | null>(null);
  const [layersOpen, setLayersOpen] = useState(true);
  const [layersDetached, setLayersDetached] = useState(false);
  const selectedPinRef = useRef<string | null>(null);

  useEffect(() => {
    selectedPinRef.current = selectedCard?.pin_id ?? null;
  }, [selectedCard]);

  const detailVisible = cardLoading || selectedCard !== null;
  const layerItems = [
    { id: "taluka_regions", label: "Taluka regions", color: "#94a3b8" },
    ...LAYER_IDS.map((id) => ({
      id,
      label: id === "development" ? "Development / works" : regions?.layers[id]?.label ?? id,
      color: CATEGORY_COLORS[id],
    })),
  ];

  const openPin = useCallback(async (
    props: Record<string, string | number | undefined>,
    layerId: string,
    coordinates: [number, number]
  ) => {
    setCardLoading(true);
    setSelectedCard(null);
    const pinId = props.pin_id ? String(props.pin_id) : null;
    let card: PoiCard | null = null;
    try {
      card = pinId ? await fetchPoiCard(pinId) : cardFromFeatureProps(props, layerId, coordinates);
    } catch {
      card = cardFromFeatureProps(props, layerId, coordinates);
    } finally {
      setSelectedCard(card);
      setCardLoading(false);
    }
    postMap({
      kind: "pin",
      pinId: card?.pin_id ?? pinId ?? "",
      name: card?.name ?? String(props.name ?? props.category_label ?? layerId),
      layer: layerId,
      lng: coordinates[0],
      lat: coordinates[1],
      summary: card?.agent_summary ?? "",
      description: card?.description ?? "",
    });
    mapRef.current?.flyTo({ center: coordinates, zoom: Math.max(mapRef.current.getZoom(), 13) });
  }, []);

  useEffect(() => {
    if (!EMBED) return;
    const onMessage = (event: MessageEvent) => {
      const data = event.data as {
        source?: string;
        kind?: string;
        layer?: string;
        layers?: Record<string, unknown>;
        visible?: boolean;
        pinId?: string;
        lng?: number;
        lat?: number;
        zoom?: number;
      };
      if (!data || data.source !== "viksetu-canvas") return;
      if (data.kind === "set-layers" && data.layers && typeof data.layers === "object") {
        const patch = data.layers as Record<string, unknown>;
        setLayers((prev) => {
          const next = { ...prev };
          for (const [key, value] of Object.entries(patch)) {
            next[key] = coerceLayerVisible(value);
          }
          applyLayersToMap(mapRef.current, next);
          return next;
        });
        return;
      }
      if (data.kind === "set-layer" && data.layer) {
        const visible = coerceLayerVisible(data.visible);
        setLayers((prev) => {
          const next = { ...prev, [data.layer as string]: visible };
          applyLayersToMap(mapRef.current, next);
          return next;
        });
        return;
      }
      if (data.kind === "focus-pin") {
        const map = mapRef.current;
        if (!map) return;
        const zoom = typeof data.zoom === "number" ? data.zoom : 14;
        if (data.pinId) {
          for (const layerId of LAYER_IDS) {
            const items = pinIndexRef.current[layerId] ?? [];
            const hit = items.find((pin) => pin.pinId === data.pinId);
            if (!hit) continue;
            setLayers((prev) => ({ ...prev, [layerId]: true }));
            map.flyTo({ center: [hit.lng, hit.lat], zoom });
            void openPin(
              { pin_id: hit.pinId, name: hit.name, taluka_id: hit.taluka },
              layerId,
              [hit.lng, hit.lat]
            );
            return;
          }
        }
        if (typeof data.lng === "number" && typeof data.lat === "number") {
          map.flyTo({ center: [data.lng, data.lat], zoom });
        }
        return;
      }
      if (data.kind === "refresh-pin" && data.pinId && selectedPinRef.current === data.pinId) {
        void fetchPoiCard(data.pinId)
          .then((card) => setSelectedCard(card))
          .catch(() => undefined);
        return;
      }
      if (data.kind === "resize") {
        mapRef.current?.resize();
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [openPin]);

  const addGeoLayer = useCallback(
    async (map: Map, layerId: string, visible: boolean) => {
      const sourceId = `src-${layerId}`;
      const circleId = `circle-${layerId}`;
      if (map.getSource(sourceId)) {
        map.setLayoutProperty(circleId, "visibility", visible ? "visible" : "none");
        return;
      }
      const geo = await fetchLayer(layerId === "development" ? "development" : layerId);
      const features = (geo as GeoJSON.FeatureCollection).features ?? [];
      pinIndexRef.current[layerId] = features.flatMap((feature) => {
        if (feature.geometry?.type !== "Point") return [];
        const [lng, lat] = feature.geometry.coordinates;
        const properties = feature.properties ?? {};
        return [
          {
            pinId: String(properties.pin_id ?? ""),
            name: String(properties.name ?? "Unnamed"),
            category: layerId,
            lng: Number(lng),
            lat: Number(lat),
            taluka: String(properties.taluka_id ?? ""),
          },
        ];
      });
      map.addSource(sourceId, { type: "geojson", data: geo as GeoJSON.GeoJSON });
      map.addLayer({
        id: circleId,
        type: "circle",
        source: sourceId,
        layout: { visibility: visible ? "visible" : "none" },
        paint: {
          "circle-radius": layerId === "development" ? 9 : 7,
          "circle-color": CATEGORY_COLORS[layerId] ?? "#333",
          "circle-stroke-width": 2,
          "circle-stroke-color": "#fff",
        },
      });
      map.on("click", circleId, (e) => {
        const f = e.features?.[0];
        if (!f || f.geometry.type !== "Point") return;
        const coords = f.geometry.coordinates as [number, number];
        const p = f.properties as Record<string, string | number | undefined>;
        void openPin(p, layerId, coords);
      });
      map.on("mouseenter", circleId, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", circleId, () => {
        map.getCanvas().style.cursor = "";
      });
    },
    [openPin]
  );

  useEffect(() => {
    let map: Map;
    (async () => {
      const [reg, district, talukas, spendData] = await Promise.all([
        fetchRegions(),
        fetchDistrict(),
        fetchTalukas().catch(() => ({ type: "FeatureCollection" as const, features: [] })),
        fetchSpend(),
      ]);
      setRegions(reg);
      setSpend(spendData.rows.filter((r) => r.sector_en !== "Total"));
      if (!mapContainer.current) return;

      map = new Map({
        container: mapContainer.current,
        style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        center: reg.district.center,
        zoom: 9,
      });
      mapRef.current = map;

      map.on("error", ({ error }) => {
        console.error("MapLibre error:", error);
        setMapError(error.message);
      });

      map.on("load", async () => {
        map.addSource("district", {
          type: "geojson",
          data: district as GeoJSON.GeoJSON,
        });
        map.addLayer({
          id: "district-fill",
          type: "fill",
          source: "district",
          paint: {
            "fill-color": "#1d4ed8",
            "fill-opacity": 0.22,
            "fill-outline-color": "#7dd3fc",
          },
        });
        map.addLayer({
          id: "district-outline",
          type: "line",
          source: "district",
          paint: {
            "line-color": "#bae6fd",
            "line-width": 2,
            "line-opacity": 0.95,
          },
        });

        const savedView = loadView();
        const districtBbox = reg.district.bbox;
        if (savedView) {
          map.jumpTo({ center: savedView.center, zoom: savedView.zoom });
        } else if (districtBbox?.length === 4) {
          const [w, s, e, n] = districtBbox;
          map.fitBounds(
            [
              [w, s],
              [e, n],
            ],
            { padding: 40, duration: 0 }
          );
        }

        if (talukas.features.length > 0) {
          map.addSource("taluka-regions", {
            type: "geojson",
            data: talukas as GeoJSON.GeoJSON,
          });
          map.addLayer({
            id: "taluka-fill",
            type: "fill",
            source: "taluka-regions",
            layout: { visibility: layers.taluka_regions ? "visible" : "none" },
            paint: {
              "fill-color": ["coalesce", ["get", "color"], "#64748b"],
              "fill-opacity": 0.14,
              "fill-outline-color": "#e2e8f0",
            },
          });
          map.addLayer({
            id: "taluka-boundary",
            type: "line",
            source: "taluka-regions",
            layout: { visibility: layers.taluka_regions ? "visible" : "none" },
            paint: { "line-color": "#cbd5e1", "line-width": 1.2, "line-opacity": 0.7 },
          });
        }

        const talukaFc: GeoJSON.FeatureCollection = {
          type: "FeatureCollection",
          features: reg.talukas.map((t) => ({
            type: "Feature",
            properties: { name: t.name },
            geometry: { type: "Point", coordinates: t.centroid },
          })),
        };
        map.addSource("talukas", { type: "geojson", data: talukaFc });
        map.addLayer({
          id: "taluka-labels",
          type: "symbol",
          source: "talukas",
          layout: {
            "text-field": ["get", "name"],
            "text-size": 11,
            "text-offset": [0, 1.2],
          },
          paint: { "text-color": "#e2e8f0", "text-halo-color": "#0f172a", "text-halo-width": 1 },
        });

        for (const lid of LAYER_IDS) {
          await addGeoLayer(map, lid, layers[lid] ?? false);
        }
        map.on("moveend", () => {
          const center = map.getCenter();
          localStorage.setItem(VIEW_KEY, JSON.stringify({ center: [center.lng, center.lat], zoom: map.getZoom() }));
        });
        if (EMBED) {
          map.on("click", (event) => {
            postMap({
              kind: "point",
              lng: Number(event.lngLat.lng.toFixed(5)),
              lat: Number(event.lngLat.lat.toFixed(5)),
              zoom: Number(map.getZoom().toFixed(2)),
            });
          });
          let viewTimer = 0;
          map.on("moveend", () => {
            window.clearTimeout(viewTimer);
            viewTimer = window.setTimeout(() => {
              const center = map.getCenter();
              const zoom = map.getZoom();
              postMap({
                kind: "view",
                lng: Number(center.lng.toFixed(5)),
                lat: Number(center.lat.toFixed(5)),
                zoom: Number(zoom.toFixed(2)),
              });
            }, 500);
          });
          const center = map.getCenter();
          postMap({
            kind: "view",
            lng: Number(center.lng.toFixed(5)),
            lat: Number(center.lat.toFixed(5)),
            zoom: Number(map.getZoom().toFixed(2)),
          });
          requestAnimationFrame(() => map.resize());
        }
        setLoading(false);
      });
    })().catch((e) => {
      console.error(e);
      setLoading(false);
    });

    return () => {
      map?.remove();
    };
  }, [addGeoLayer]);

  useEffect(() => {
    localStorage.setItem(LAYER_KEY, JSON.stringify(layers));
    if (!EMBED || loading) return;
    const layerStats = [
      {
        id: "taluka_regions",
        enabled: !!layers.taluka_regions,
        totalPins: 0,
        visiblePins: 0,
      },
      ...LAYER_IDS.map((id) => {
        const total = (pinIndexRef.current[id] ?? []).length;
        const on = !!layers[id];
        return { id, enabled: on, totalPins: total, visiblePins: on ? total : 0 };
      }),
    ];
    const visiblePins = Object.entries(pinIndexRef.current).flatMap(([layerId, items]) =>
      layers[layerId] ? items.map((pin) => ({ ...pin, layer: layerId, layerEnabled: true })) : []
    );
    const hiddenPinSamples = Object.entries(pinIndexRef.current).flatMap(([layerId, items]) =>
      layers[layerId] ? [] : items.slice(0, 15).map((pin) => ({ ...pin, layer: layerId, layerEnabled: false }))
    );
    postMap({
      kind: "state",
      layers,
      enabledCount: visiblePins.length,
      pins: visiblePins.slice(0, 200),
      layerStats,
      hiddenPinSamples: hiddenPinSamples.slice(0, 80),
    });
  }, [layers, loading]);

  useEffect(() => {
    applyLayersToMap(mapRef.current, layers);
  }, [layers]);

  const toggleLayer = (id: LayerId | "taluka_regions") => {
    setLayers((prev) => {
      const visible = !prev[id];
      postMap({ kind: "layer", layer: id, visible });
      return { ...prev, [id]: visible };
    });
  };

  const sendChat = async () => {
    if (!chat.trim()) return;
    const userMsg = chat.trim();
    setChat("");
    setMessages((m) => [...m, { role: "user", text: userMsg }]);
    try {
      const res = await postChat(userMsg, { layers, selected_pin: selectedCard?.pin_id });
      setMessages((m) => [...m, { role: "assistant", text: res.answer }]);
      const patch = res.ui_patch as {
        layers?: Record<string, boolean>;
        map_focus?: { taluka?: string; zoom?: number };
      };
      if (patch.layers) setLayers((prev) => ({ ...prev, ...patch.layers }));
      if (patch.map_focus?.taluka && regions) {
        const t = regions.talukas.find((x) => x.id === patch.map_focus!.taluka);
        if (t && mapRef.current) {
          mapRef.current.flyTo({ center: t.centroid as [number, number], zoom: patch.map_focus.zoom ?? 10 });
        }
      }
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", text: String(e) }]);
    }
  };

  return (
    <div className={EMBED ? "app app--embed" : "app"}>
      <header className="header">
        <h1>VikSetu</h1>
        <span className="sub">Click a pin for details · FY cards in poi_cards.json for the agent</span>
      </header>
      <div className="main">
        <div className="map-stage">
          <PinDetailPanel
            card={selectedCard}
            loading={cardLoading}
            visible={detailVisible}
            onClose={() => {
              setSelectedCard(null);
              setCardLoading(false);
            }}
          />
          <div ref={mapWrapRef} className="map-wrap">
            {loading && <div className="map-loading">{mapError ? `Map failed to load: ${mapError}` : "Loading map…"}</div>}
            {!layersDetached && (
              <LayerIndexPanel
                open={layersOpen}
                onToggleOpen={() => setLayersOpen((o) => !o)}
                layers={layers}
                regions={regions}
                layerIds={LAYER_IDS}
                categoryColors={CATEGORY_COLORS}
                onToggleLayer={(id) => toggleLayer(id as LayerId | "taluka_regions")}
                boundsRef={mapWrapRef}
                allowDetach={EMBED}
                onPull={(phase, x, y) => {
                  postMap({ kind: "layers-drag", phase, x, y, open: layersOpen, layers, items: layerItems });
                  if (phase === "end") setLayersDetached(true);
                }}
              />
            )}
            <div ref={mapContainer} className="map" />
          </div>
        </div>
        <aside className="panel panel-right">
          <section className="panel-block panel-block--fade">
            <h2>Spend (PS extract)</h2>
            <ul className="spend-list">
              {spend.slice(0, 6).map((r) => (
                <li key={r.sector_en}>
                  <span>{r.sector_en}</span>
                  <strong>₹{Number(r.actual_spend_inr).toLocaleString("en-IN")}</strong>
                </li>
              ))}
            </ul>
          </section>
          {READ_ONLY ? (
            <section className="panel-block panel-block--fade">
              <h2>Read-only demo</h2>
              <p>Map browsing is enabled. Chat and data editing are disabled.</p>
            </section>
          ) : (
            <section className="chat panel-block panel-block--fade">
              <h2>Assistant</h2>
              <div className="chat-log">
                {messages.map((m, i) => (
                  <p key={i} className={m.role}>
                    {m.text}
                  </p>
                ))}
              </div>
              <div className="chat-input">
                <input
                  value={chat}
                  onChange={(e) => setChat(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendChat()}
                  placeholder="Show schools / focus Jawhar / spend…"
                />
                <button type="button" className="btn-send" onClick={sendChat}>
                  Send
                </button>
              </div>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
