// The response shapes the web app expects from the API. Mock data in src/mocks follows the
// same shapes, so switching to the real backend only changes src/api/client.ts.
import type { Feature, FeatureCollection, LineString, MultiPolygon, Polygon } from "geojson";

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

export type PlaceKind =
  | "kecamatan"
  | "kelurahan"
  | "area"
  | "street"
  | "landmark"
  /** A building or house number, from address search. */
  | "address"
  /** Coordinates typed or pasted into search. */
  | "point"
  /** A named transit stop or terminal. */
  | "stop";

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
  /** Where an address result came from ("mapbox", "photon"), for attribution. */
  source?: string;
}

// --- Trip planning (POST /api/transit/plan) ---------------------------------------------

/** A trip end point. [lon, lat] like the rest of the app. */
export interface TripPoint {
  name: string;
  point: [number, number];
  /** Shown under the name in search results, e.g. "Transit stop". */
  context?: string;
}

export type TripSort = "balanced" | "time" | "cost" | "availability";

export type TransitMode = "angkot" | "minibus" | "bus" | "feeder" | "shuttle" | "rail";

export interface TripRoute {
  id: number;
  name: string;
  code: string;
  mode: TransitMode;
  color: string;
  /** "hail": wave it down anywhere along the street; "stops": fixed stops only. */
  boarding: "hail" | "stops";
  headway_min: number;
  /** Fare, speed, headway and hours are per-mode placeholders, not operator data. */
  is_placeholder: boolean;
}

/** The API's places, as name + lon/lat. */
export interface ApiPlace {
  name: string;
  lon: number;
  lat: number;
}

export interface TripLeg {
  mode: "walk" | TransitMode;
  route: TripRoute | null;
  start: ApiPlace;
  end: ApiPlace;
  distance_m: number;
  duration_min: number;
  wait_min: number;
  fare_idr: number;
  stop_count: number;
  depart_at: string;
  arrive_at: string;
  /** False when the route isn't running at the time you'd board it. */
  available: boolean;
  geometry: LineString;
}

export interface TripOption {
  rank: number;
  summary: string;
  labels: ("fastest" | "cheapest" | "most_available")[];
  scores: Record<string, number>;
  duration_min: number;
  fare_idr: number;
  walk_m: number;
  wait_min: number;
  transfers: number;
  /** 0–1: how frequent the services are, and whether they run at that time. */
  availability: number;
  uses_placeholder: boolean;
  depart_at: string;
  arrive_at: string;
  legs: TripLeg[];
}

export interface TripSegment {
  origin: ApiPlace;
  destination: ApiPlace;
  options: TripOption[];
}

export interface TripPlan {
  depart_at: string;
  network_version: number;
  segments: TripSegment[];
  notes: string[];
}

/** GET /api/geocode?q=… and /api/geocode/reverse: addresses and named places. */
export interface GeocodeResult {
  id: string;
  name: string;
  kind: "address" | "street" | "landmark" | "area";
  /** Street and district from the provider, e.g. "Jalan Cihampelas 160, Cipaganti, Bandung". */
  context: string;
  /** Just the street line, or "" when that is the name itself. */
  address: string;
  lon: number;
  lat: number;
  source: string;
}

/** POST /api/transit/commute: fastest time from each area to one destination. */
export interface CommuteTime {
  id: string;
  /** Null when nothing gets there within 2.5 hours at that time. */
  minutes: number | null;
  transfers: number | null;
  walk_only: boolean;
}
