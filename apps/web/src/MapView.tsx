import { MapLibreMap, NavigationControl, setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { useEffect, useRef } from "react";

// MapLibre finds its worker relative to its own module URL, which breaks once Vite
// bundles it. Give it the worker's URL explicitly.
setWorkerUrl(workerUrl);

// Kota Bandung, as [longitude, latitude].
const BANDUNG_CENTER: [number, number] = [107.6098, -6.9147];
const DEFAULT_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";

export function MapView() {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    const map = new MapLibreMap({
      container: container.current,
      style: import.meta.env.VITE_BASEMAP_STYLE_URL || DEFAULT_STYLE_URL,
      center: BANDUNG_CENTER,
      zoom: 12,
    });
    map.addControl(new NavigationControl(), "top-right");

    return () => map.remove();
  }, []);

  return <div ref={container} className="map" data-testid="map" />;
}
