import type { FeatureCollection, Geometry } from "geojson";
import {
  type GeoJSONSource,
  GeolocateControl,
  LngLatBounds,
  MapLibreMap,
  Marker,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
} from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { useEffect, useRef, useState } from "react";
import type { FloodRisk } from "../api/types";
import { inkOn, NO_SCORE_COLOR, SCORE_RAMP, SCORE_STOPS, scoreColor } from "../colors";

// MapLibre finds its worker relative to its own module URL, which breaks once Vite
// bundles it. Give it the worker's URL explicitly.
setWorkerUrl(workerUrl);

// Kota Bandung, as [longitude, latitude].
const BANDUNG_CENTER: [number, number] = [107.6098, -6.9147];
const DEFAULT_STYLE_URL = "https://tiles.openfreemap.org/styles/positron";

export interface MapAreaProperties {
  id: string;
  name: string;
  score: number | null;
  floodRisk: FloodRisk;
  labelPoint: [number, number];
}

export type MapAreas = FeatureCollection<Geometry, MapAreaProperties>;

/** A request to move the camera; `key` changes on every request. */
export type Focus =
  | { key: number; kind: "area"; id: string }
  | { key: number; kind: "point"; point: [number, number] };

interface Props {
  areas: MapAreas | null;
  selectedId: string | null;
  onSelectArea: (id: string | null) => void;
  showFlood: boolean;
  focus: Focus | null;
  placePoint: [number, number] | null;
  panelOpen: boolean;
}

const fillColor = [
  "case",
  ["==", ["get", "score"], null],
  NO_SCORE_COLOR,
  ["interpolate", ["linear"], ["get", "score"], ...SCORE_STOPS.flatMap((s, i) => [s, SCORE_RAMP[i]])],
] as const;

/** Diagonal hatching, so the flood overlay never relies on colour alone. */
function hatchPattern(size = 12) {
  const data = new Uint8Array(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      if ((x + y) % size < 2) data.set([30, 58, 95, 230], (y * size + x) * 4);
    }
  }
  return { width: size, height: size, data };
}

function cameraPadding(panelOpen: boolean) {
  if (window.innerWidth < 900) {
    return { top: 140, bottom: panelOpen ? Math.round(window.innerHeight * 0.5) : 40, left: 24, right: 24 };
  }
  return { top: 100, bottom: 40, left: 470, right: panelOpen ? 400 : 60 };
}

function areaBounds(areas: MapAreas, id?: string): LngLatBounds | null {
  const bounds = new LngLatBounds();
  for (const feature of areas.features) {
    if (id && feature.properties.id !== id) continue;
    const { geometry } = feature;
    const polygons =
      geometry.type === "Polygon"
        ? [geometry.coordinates]
        : geometry.type === "MultiPolygon"
          ? geometry.coordinates
          : [];
    for (const polygon of polygons) {
      for (const [lon, lat] of polygon[0]) bounds.extend([lon, lat]);
    }
  }
  return bounds.isEmpty() ? null : bounds;
}

export function MapView({
  areas,
  selectedId,
  onSelectArea,
  showFlood,
  focus,
  placePoint,
  panelOpen,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const labels = useRef(new Map<string, { marker: Marker; badge: HTMLElement }>());
  const placeMarker = useRef<Marker | null>(null);
  const onSelectRef = useRef(onSelectArea);
  const panelOpenRef = useRef(panelOpen);
  const [ready, setReady] = useState(false);
  const fittedOnce = useRef(false);

  onSelectRef.current = onSelectArea;
  panelOpenRef.current = panelOpen;

  useEffect(() => {
    if (!container.current) return;

    const map = new MapLibreMap({
      container: container.current,
      style: import.meta.env.VITE_BASEMAP_STYLE_URL || DEFAULT_STYLE_URL,
      center: BANDUNG_CENTER,
      zoom: 12,
      minZoom: 10,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new NavigationControl({ showCompass: false }), "bottom-right");
    map.addControl(
      new GeolocateControl({ positionOptions: { enableHighAccuracy: true } }),
      "bottom-right",
    );
    map.addControl(new ScaleControl({ unit: "metric" }), "bottom-right");

    map.on("load", () => {
      // Start with the compact attribution collapsed; it covers half the map on phones.
      container.current
        ?.querySelector(".maplibregl-compact-show")
        ?.classList.remove("maplibregl-compact-show");
      map.addImage("flood-hatch", hatchPattern());
      map.addSource("areas", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
        promoteId: "id",
      });
      map.addLayer({
        id: "areas-fill",
        type: "fill",
        source: "areas",
        paint: {
          "fill-color": fillColor as never,
          "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.82, 0.62],
        },
      });
      map.addLayer({
        id: "areas-flood",
        type: "fill",
        source: "areas",
        filter: ["in", ["get", "floodRisk"], ["literal", ["moderate", "high"]]],
        layout: { visibility: "none" },
        paint: {
          "fill-pattern": "flood-hatch",
          "fill-opacity": ["match", ["get", "floodRisk"], "high", 0.9, 0.45],
        },
      });
      map.addLayer({
        id: "areas-outline",
        type: "line",
        source: "areas",
        paint: { "line-color": "#ffffff", "line-width": 1.5 },
      });
      map.addLayer({
        id: "areas-selected",
        type: "line",
        source: "areas",
        filter: ["==", ["get", "id"], ""],
        paint: { "line-color": "#14231a", "line-width": 3 },
      });

      let hovered: string | number | undefined;
      map.on("mousemove", "areas-fill", (event) => {
        const id = event.features?.[0]?.id;
        if (id === hovered) return;
        if (hovered !== undefined) map.setFeatureState({ source: "areas", id: hovered }, { hover: false });
        hovered = id;
        if (id !== undefined) map.setFeatureState({ source: "areas", id }, { hover: true });
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "areas-fill", () => {
        if (hovered !== undefined) map.setFeatureState({ source: "areas", id: hovered }, { hover: false });
        hovered = undefined;
        map.getCanvas().style.cursor = "";
      });
      map.on("click", (event) => {
        const [feature] = map.queryRenderedFeatures(event.point, { layers: ["areas-fill"] });
        onSelectRef.current(feature ? String(feature.id) : null);
      });

      // Names crowd each other when zoomed out; keep just the score badges then.
      const updateDensity = () =>
        container.current?.classList.toggle("labels-compact", map.getZoom() < 11.6);
      map.on("zoom", updateDensity);
      updateDensity();

      setReady(true);
    });

    const currentLabels = labels.current;
    return () => {
      currentLabels.clear();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Data and labels.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !areas) return;
    (map.getSource("areas") as GeoJSONSource).setData(areas);

    const seen = new Set<string>();
    for (const { properties } of areas.features) {
      const { id, name, score, labelPoint } = properties;
      seen.add(id);
      let label = labels.current.get(id);
      if (!label) {
        const element = document.createElement("button");
        element.type = "button";
        element.className = "area-label";
        element.innerHTML = `<span class="area-label-name"></span><span class="score-badge"></span>`;
        element.querySelector(".area-label-name")!.textContent = name;
        element.addEventListener("click", (event) => {
          event.stopPropagation();
          onSelectRef.current(id);
        });
        const marker = new Marker({ element, anchor: "center" }).setLngLat(labelPoint).addTo(map);
        label = { marker, badge: element.querySelector(".score-badge") as HTMLElement };
        labels.current.set(id, label);
      }
      label.badge.textContent = score === null ? "–" : String(score);
      label.badge.style.background = scoreColor(score);
      label.badge.style.color = inkOn(score);
      label.marker.getElement().setAttribute("aria-label", `${name}, score ${score ?? "none"}`);
    }
    for (const [id, label] of labels.current) {
      if (!seen.has(id)) {
        label.marker.remove();
        labels.current.delete(id);
      }
    }

    if (!fittedOnce.current) {
      const bounds = areaBounds(areas);
      if (bounds) map.fitBounds(bounds, { padding: cameraPadding(panelOpenRef.current), duration: 0 });
      fittedOnce.current = true;
    }
  }, [ready, areas]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setFilter("areas-selected", ["==", ["get", "id"], selectedId ?? ""]);
    for (const [id, label] of labels.current) {
      label.marker.getElement().classList.toggle("is-selected", id === selectedId);
    }
  }, [ready, selectedId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setLayoutProperty("areas-flood", "visibility", showFlood ? "visible" : "none");
  }, [ready, showFlood]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !focus) return;
    const padding = cameraPadding(panelOpenRef.current);
    if (focus.kind === "point") {
      map.easeTo({ center: focus.point, zoom: 13, padding, duration: 800 });
      return;
    }
    const bounds = areas && areaBounds(areas, focus.id);
    if (bounds) map.fitBounds(bounds, { padding, maxZoom: 14, duration: 800 });
    // Only a new focus request moves the camera, not a score recalculation, so `areas` is
    // deliberately not a dependency.
  }, [ready, focus]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    placeMarker.current?.remove();
    placeMarker.current = placePoint
      ? new Marker({ color: "#14231a" }).setLngLat(placePoint).addTo(map)
      : null;
  }, [ready, placePoint]);

  return (
    <div
      ref={container}
      className={panelOpen ? "map panel-open" : "map"}
      data-testid="map"
      data-ready={ready}
    />
  );
}
