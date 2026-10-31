// The response shapes the web app expects from the API. Mock data in src/mocks follows the
// same shapes, so switching to the real backend only changes src/api/client.ts.
import type { Feature, FeatureCollection, MultiPolygon, Polygon } from "geojson";

/** Scored criteria. Every score is 0–100 and higher is always better. */
export type CriterionKey = "parks" | "schools" | "angkot" | "dailyNeeds" | "commute";

/** Flood risk is a warning flag shown next to the score, never part of it. */
export type FloodRisk = "low" | "moderate" | "high";

export type AreaLevel = "kecamatan" | "kelurahan";

export interface AreaProperties {
  id: string;
  name: string;
  level: AreaLevel;
  /** The kecamatan a kelurahan belongs to; null for a kecamatan. */
  parent: { id: string; name: string } | null;
  /** A point inside the polygon for the map label, as [lon, lat]. */
  labelPoint: [number, number];
  /** Averages of the hexagon scores inside this area. */
  scores: Record<CriterionKey, number>;
  floodRisk: FloodRisk;
}

export type AreaGeometry = Polygon | MultiPolygon;
export type AreaFeature = Feature<AreaGeometry, AreaProperties>;
/** GET /api/areas?level=kecamatan|kelurahan (WGS84 GeoJSON, clipped to the Kota boundary). */
export type AreaCollection = FeatureCollection<AreaGeometry, AreaProperties>;

export type PlaceKind = "kecamatan" | "kelurahan" | "area" | "street" | "landmark";

/** GET /api/places?q=… */
export interface PlaceResult {
  id: string;
  name: string;
  kind: PlaceKind;
  /** Where it is, e.g. "Coblong, Kota Bandung" or "Cimenyan, Kabupaten Bandung". */
  context: string;
  /** [lon, lat] */
  point: [number, number];
  /** False for places outside Kota Bandung, which Huni has no scores for. */
  insideKota: boolean;
  /** The scored area the place falls in, or null when outside the Kota. */
  areaId: string | null;
}
