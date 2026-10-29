import { expect, test } from "vitest";
import { contains } from "../lib/geometry";
import { mockAreas } from "./areas";
import { searchMockPlaces } from "./places";

test("mock areas have the 30 kecamatan and 151 kelurahan of Kota Bandung", () => {
  expect(mockAreas.kecamatan.features).toHaveLength(30);
  expect(mockAreas.kelurahan.features).toHaveLength(151);

  const ids = [...mockAreas.kecamatan.features, ...mockAreas.kelurahan.features].map(
    (f) => f.properties.id,
  );
  expect(new Set(ids).size).toBe(181);
});

test("every kelurahan has a kecamatan parent and a label inside its own shape", () => {
  const kecamatanIds = new Set(mockAreas.kecamatan.features.map((f) => f.properties.id));
  for (const { geometry, properties } of mockAreas.kelurahan.features) {
    expect(kecamatanIds.has(properties.parent!.id)).toBe(true);
    expect(contains(geometry, properties.labelPoint)).toBe(true);
  }
});

test("kecamatan scores stay within the range of their kelurahan", () => {
  for (const kec of mockAreas.kecamatan.features) {
    const parts = mockAreas.kelurahan.features.filter(
      (k) => k.properties.parent?.id === kec.properties.id,
    );
    const parks = parts.map((k) => k.properties.scores.parks);
    expect(kec.properties.scores.parks).toBeGreaterThanOrEqual(Math.min(...parks));
    expect(kec.properties.scores.parks).toBeLessThanOrEqual(Math.max(...parks));
  }
});

test("search finds kelurahan and flags places outside Kota Bandung", () => {
  const results = searchMockPlaces("dago");
  expect(results[0]).toMatchObject({ name: "Dago", kind: "kelurahan", areaId: "kel-dago" });
  expect(results.find((r) => r.name === "Dago Pakar")).toMatchObject({
    insideKota: false,
    areaId: null,
  });
  expect(searchMockPlaces("leuwi")[0].areaId).toMatch(/^kel-/);
});
