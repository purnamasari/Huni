// DEMO DATA for building the UI. The polygons are Voronoi cells around rough kecamatan
// centres, clipped to a hand-drawn outline of Kota Bandung. They are NOT real boundaries,
// and the scores are generated, not measured. Replace with GET /api/areas.
import { Delaunay } from "d3-delaunay";
import type { AreaCollection, AreaFeature, CriterionKey, FloodRisk } from "../api/types";
import { bbox, clipByConvex, type Point, type Ring } from "../lib/geometry";

/** Rough outline of Kota Bandung, [lon, lat]. */
export const KOTA_OUTLINE: Ring = [
  [107.545, -6.905], [107.56, -6.89], [107.575, -6.87], [107.585, -6.85], [107.6, -6.84],
  [107.615, -6.845], [107.625, -6.86], [107.64, -6.87], [107.66, -6.885], [107.68, -6.89],
  [107.7, -6.895], [107.72, -6.898], [107.738, -6.905], [107.735, -6.925], [107.722, -6.94],
  [107.705, -6.955], [107.69, -6.965], [107.665, -6.965], [107.64, -6.97], [107.615, -6.965],
  [107.595, -6.962], [107.575, -6.955], [107.555, -6.945], [107.545, -6.93], [107.545, -6.905],
];

/** The 30 kecamatan of Kota Bandung with approximate centres, [lon, lat]. */
const KECAMATAN: [string, Point][] = [
  ["Andir", [107.57, -6.912]],
  ["Antapani", [107.663, -6.912]],
  ["Arcamanik", [107.677, -6.922]],
  ["Astanaanyar", [107.598, -6.928]],
  ["Babakan Ciparay", [107.572, -6.94]],
  ["Bandung Kidul", [107.63, -6.958]],
  ["Bandung Kulon", [107.557, -6.925]],
  ["Bandung Wetan", [107.618, -6.902]],
  ["Batununggal", [107.637, -6.934]],
  ["Bojongloa Kaler", [107.585, -6.931]],
  ["Bojongloa Kidul", [107.593, -6.951]],
  ["Buahbatu", [107.65, -6.95]],
  ["Cibeunying Kaler", [107.638, -6.888]],
  ["Cibeunying Kidul", [107.647, -6.904]],
  ["Cibiru", [107.722, -6.914]],
  ["Cicendo", [107.585, -6.904]],
  ["Cidadap", [107.606, -6.858]],
  ["Cinambo", [107.698, -6.928]],
  ["Coblong", [107.616, -6.884]],
  ["Gedebage", [107.69, -6.952]],
  ["Kiaracondong", [107.65, -6.922]],
  ["Lengkong", [107.622, -6.933]],
  ["Mandalajati", [107.672, -6.9]],
  ["Panyileukan", [107.711, -6.935]],
  ["Rancasari", [107.669, -6.945]],
  ["Regol", [107.609, -6.944]],
  ["Sukajadi", [107.594, -6.885]],
  ["Sukasari", [107.584, -6.866]],
  ["Sumur Bandung", [107.611, -6.917]],
  ["Ujungberung", [107.7, -6.908]],
];

const CITY_CENTRE: Point = [107.61, -6.915];

export function areaId(name: string): string {
  return name.toLowerCase().replace(/\s+/g, "-");
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

function buildMockAreas(): AreaCollection {
  const [minX, minY, maxX, maxY] = bbox([KOTA_OUTLINE]);
  const voronoi = Delaunay.from(KECAMATAN.map(([, centre]) => centre)).voronoi([
    minX - 0.01,
    minY - 0.01,
    maxX + 0.01,
    maxY + 0.01,
  ]);

  const features: AreaFeature[] = KECAMATAN.map(([name, centre], index) => {
    const cell = voronoi.cellPolygon(index) as Ring;
    return {
      type: "Feature",
      id: areaId(name),
      geometry: { type: "Polygon", coordinates: [clipByConvex(KOTA_OUTLINE, cell)] },
      properties: {
        id: areaId(name),
        name,
        level: "kecamatan",
        labelPoint: centre,
        scores: mockScores(name, centre),
        floodRisk: mockFloodRisk(centre),
      },
    };
  });

  return { type: "FeatureCollection", features };
}

export const mockAreas = buildMockAreas();
