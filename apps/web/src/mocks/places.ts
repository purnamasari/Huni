// DEMO gazetteer for search. Real results will come from GET /api/places.
import type { PlaceResult } from "../api/types";
import { areaId, mockAreas } from "./areas";

const KOTA = "Kota Bandung";

const PLACES: PlaceResult[] = [
  {
    id: "kel-dago",
    name: "Dago",
    kind: "kelurahan",
    context: `Coblong, ${KOTA}`,
    point: [107.6175, -6.8865],
    insideKota: true,
    areaId: areaId("Coblong"),
  },
  {
    id: "area-dago-atas",
    name: "Dago Atas",
    kind: "area",
    context: `Coblong, ${KOTA}`,
    point: [107.6205, -6.8705],
    insideKota: true,
    areaId: areaId("Coblong"),
  },
  {
    id: "street-ir-h-juanda",
    name: "Jl. Ir. H. Juanda (Jl. Dago)",
    kind: "street",
    context: `Coblong, ${KOTA}`,
    point: [107.6133, -6.8935],
    insideKota: true,
    areaId: areaId("Coblong"),
  },
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
  {
    id: "kel-ciumbuleuit",
    name: "Ciumbuleuit",
    kind: "kelurahan",
    context: `Cidadap, ${KOTA}`,
    point: [107.6045, -6.8735],
    insideKota: true,
    areaId: areaId("Cidadap"),
  },
  {
    id: "kel-pasteur",
    name: "Pasteur",
    kind: "kelurahan",
    context: `Sukajadi, ${KOTA}`,
    point: [107.5935, -6.8935],
    insideKota: true,
    areaId: areaId("Sukajadi"),
  },
  {
    id: "kel-margasari",
    name: "Margasari",
    kind: "kelurahan",
    context: `Buahbatu, ${KOTA}`,
    point: [107.6555, -6.9515],
    insideKota: true,
    areaId: areaId("Buahbatu"),
  },
  {
    id: "landmark-leuwi-panjang",
    name: "Terminal Leuwi Panjang",
    kind: "landmark",
    context: `Bojongloa Kidul, ${KOTA}`,
    point: [107.5955, -6.9455],
    insideKota: true,
    areaId: areaId("Bojongloa Kidul"),
  },
  {
    id: "landmark-gedung-sate",
    name: "Gedung Sate",
    kind: "landmark",
    context: `Bandung Wetan, ${KOTA}`,
    point: [107.6187, -6.9025],
    insideKota: true,
    areaId: areaId("Bandung Wetan"),
  },
  {
    id: "landmark-itb",
    name: "Institut Teknologi Bandung",
    kind: "landmark",
    context: `Coblong, ${KOTA}`,
    point: [107.6105, -6.8915],
    insideKota: true,
    areaId: areaId("Coblong"),
  },
  ...mockAreas.features.map(
    ({ properties: { id, name, labelPoint } }): PlaceResult => ({
      id: `kec-${id}`,
      name,
      kind: "kecamatan",
      context: KOTA,
      point: labelPoint,
      insideKota: true,
      areaId: id,
    }),
  ),
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
