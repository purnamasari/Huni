// DEMO gazetteer for search. Real results will come from GET /api/places.
import type { AreaFeature, PlaceResult } from "../api/types";
import { contains, type Point } from "../lib/geometry";
import { mockAreas } from "./areas";

const KOTA = "Kota Bandung";

/** Find the kelurahan a point is in, the way the backend would with ST_Contains. */
function kelurahanAt(point: Point): AreaFeature | undefined {
  return mockAreas.kelurahan.features.find((f) => contains(f.geometry, point));
}

function inKota(id: string, name: string, kind: PlaceResult["kind"], point: Point): PlaceResult {
  const area = kelurahanAt(point);
  return {
    id,
    name,
    kind,
    context: area ? `${area.properties.name}, ${area.properties.parent?.name}` : KOTA,
    point,
    insideKota: true,
    areaId: area?.properties.id ?? null,
  };
}

const PLACES: PlaceResult[] = [
  ...mockAreas.kecamatan.features.map(
    ({ properties: { id, name, labelPoint } }): PlaceResult => ({
      id: `place-${id}`,
      name,
      kind: "kecamatan",
      context: KOTA,
      point: labelPoint,
      insideKota: true,
      areaId: id,
    }),
  ),
  ...mockAreas.kelurahan.features.map(
    ({ properties: { id, name, labelPoint, parent } }): PlaceResult => ({
      id: `place-${id}`,
      name,
      kind: "kelurahan",
      context: `${parent?.name}, ${KOTA}`,
      point: labelPoint,
      insideKota: true,
      areaId: id,
    }),
  ),
  inKota("area-dago-atas", "Dago Atas", "area", [107.6205, -6.8705]),
  inKota("street-ir-h-juanda", "Jl. Ir. H. Juanda (Jl. Dago)", "street", [107.6133, -6.8935]),
  inKota("landmark-leuwi-panjang", "Terminal Leuwi Panjang", "landmark", [107.5955, -6.9455]),
  inKota("landmark-gedung-sate", "Gedung Sate", "landmark", [107.6187, -6.9025]),
  inKota("landmark-itb", "Institut Teknologi Bandung", "landmark", [107.6105, -6.8915]),
  {
    id: "area-dago-pakar",
    name: "Dago Pakar",
    kind: "area",
    context: "Ciburial, Cimenyan, Kabupaten Bandung",
    point: [107.6305, -6.8565],
    insideKota: false,
    areaId: null,
  },
  {
    id: "landmark-tahura",
    name: "Tahura Ir. H. Djuanda",
    kind: "landmark",
    context: "Kabupaten Bandung / Bandung Barat",
    point: [107.6345, -6.8545],
    insideKota: false,
    areaId: null,
  },
];

const normalise = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

export function searchMockPlaces(query: string, limit = 6): PlaceResult[] {
  const q = normalise(query);
  if (!q) return [];
  return PLACES.filter((place) => normalise(place.name).includes(q))
    .sort((a, b) => {
      const aStarts = normalise(a.name).startsWith(q) ? 0 : 1;
      const bStarts = normalise(b.name).startsWith(q) ? 0 : 1;
      return aStarts - bStarts || a.name.length - b.name.length;
    })
    .slice(0, limit);
}
