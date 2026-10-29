// DEMO DATA for building the UI. The boundaries are real (OpenStreetMap, see
// boundaries.README.md); the scores are generated, not measured. Replace with GET /api/areas.
import type { MultiPolygon, Polygon } from "geojson";
import type {
  AreaCollection,
  AreaFeature,
  AreaLevel,
  CriterionKey,
  FloodRisk,
} from "../api/types";
import { planarArea, type Point } from "../lib/geometry";
import boundaries from "./boundaries.json";

interface BoundaryRecord {
  name: string;
  kecamatan?: string;
  labelPoint: number[];
  geometry: { type: string; coordinates: unknown };
}

const CITY_CENTRE: Point = [107.61, -6.915];
const CRITERIA: CriterionKey[] = ["parks", "schools", "angkot", "dailyNeeds", "commute"];
const FLOOD_ORDER: FloodRisk[] = ["low", "moderate", "high"];

export function areaId(level: AreaLevel, name: string): string {
  return `${level === "kecamatan" ? "kec" : "kel"}-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

/** Deterministic noise in [-1, 1] so the demo looks the same on every load. */
function noise(seed: string): number {
  let h = 2166136261;
  for (const char of seed) h = Math.imul(h ^ char.charCodeAt(0), 16777619);
  return ((h >>> 0) % 2001) / 1000 - 1;
}

const clamp = (value: number) => Math.round(Math.min(100, Math.max(0, value)));

function mockScores(name: string, [lon, lat]: Point): Record<CriterionKey, number> {
  const north = (lat + 6.97) / 0.13; // 0 in the south, 1 in the north
  const fromCentre = Math.min(1, Math.hypot(lon - CITY_CENTRE[0], lat - CITY_CENTRE[1]) / 0.11);
  return {
    parks: clamp(30 + 65 * north + 8 * noise(`${name}:parks`)),
    schools: clamp(92 - 45 * fromCentre + 10 * noise(`${name}:schools`)),
    angkot: clamp(96 - 60 * fromCentre + 8 * noise(`${name}:angkot`)),
    dailyNeeds: clamp(94 - 50 * fromCentre + 8 * noise(`${name}:dailyNeeds`)),
    commute: clamp(95 - 60 * fromCentre + 6 * noise(`${name}:commute`)),
  };
}

function mockFloodRisk([lon, lat]: Point): FloodRisk {
  const north = (lat + 6.97) / 0.13;
  if (north < 0.25 && lon > 107.64) return "high";
  if (north < 0.42) return "moderate";
  return "low";
}

function buildMockAreas() {
  const kecamatanRecords = boundaries.kecamatan as BoundaryRecord[];
  const kelurahanRecords = boundaries.kelurahan as BoundaryRecord[];

  const kelurahan: AreaFeature[] = kelurahanRecords.map((record) => {
    const labelPoint = record.labelPoint as Point;
    const parentName = record.kecamatan!;
    return {
      type: "Feature",
      id: areaId("kelurahan", record.name),
      geometry: record.geometry as Polygon | MultiPolygon,
      properties: {
        id: areaId("kelurahan", record.name),
        name: record.name,
        level: "kelurahan",
        parent: { id: areaId("kecamatan", parentName), name: parentName },
        labelPoint,
        scores: mockScores(record.name, labelPoint),
        floodRisk: mockFloodRisk(labelPoint),
      },
    };
  });

  // Like the real thing will be: a kecamatan's score is the area-weighted mean of its parts.
  const kecamatan: AreaFeature[] = kecamatanRecords.map((record) => {
    const id = areaId("kecamatan", record.name);
    const parts = kelurahan.filter((k) => k.properties.parent?.id === id);
    const weights = parts.map((k) => planarArea(k.geometry));
    const total = weights.reduce((a, b) => a + b, 0);
    const mean = (value: (k: AreaFeature) => number) =>
      parts.reduce((sum, k, i) => sum + value(k) * weights[i], 0) / total;

    return {
      type: "Feature",
      id,
      geometry: record.geometry as Polygon | MultiPolygon,
      properties: {
        id,
        name: record.name,
        level: "kecamatan",
        parent: null,
        labelPoint: record.labelPoint as Point,
        scores: Object.fromEntries(
          CRITERIA.map((key) => [key, Math.round(mean((k) => k.properties.scores[key]))]),
        ) as Record<CriterionKey, number>,
        floodRisk:
          FLOOD_ORDER[Math.round(mean((k) => FLOOD_ORDER.indexOf(k.properties.floodRisk)))],
      },
    };
  });

  const collection = (features: AreaFeature[]): AreaCollection => ({
    type: "FeatureCollection",
    features,
  });
  return { kecamatan: collection(kecamatan), kelurahan: collection(kelurahan) };
}

export const mockAreas: Record<AreaLevel, AreaCollection> = buildMockAreas();
