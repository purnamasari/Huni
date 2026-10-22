import { expect, test } from "vitest";
import { ringArea } from "../lib/geometry";
import { mockAreas } from "./areas";
import { searchMockPlaces } from "./places";

test("mock areas cover all 30 kecamatan with valid shapes and scores", () => {
  const { features } = mockAreas;
  expect(features).toHaveLength(30);
  expect(new Set(features.map((f) => f.properties.id)).size).toBe(30);

  for (const { geometry, properties } of features) {
    expect(geometry.type).toBe("Polygon");
    const ring = geometry.coordinates[0] as [number, number][];
    expect(ring.length).toBeGreaterThanOrEqual(4);
    expect(ring[0]).toEqual(ring[ring.length - 1]);
    expect(ringArea(ring)).toBeGreaterThan(0);
    for (const value of Object.values(properties.scores)) {
      expect(value).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThanOrEqual(100);
    }
  }
});

test("search flags places outside Kota Bandung and gives them no area", () => {
  const results = searchMockPlaces("dago");
  expect(results[0].name).toBe("Dago");

  const pakar = results.find((r) => r.name === "Dago Pakar");
  expect(pakar).toMatchObject({ insideKota: false, areaId: null });
  expect(results.filter((r) => r.insideKota).every((r) => r.areaId)).toBe(true);
});
