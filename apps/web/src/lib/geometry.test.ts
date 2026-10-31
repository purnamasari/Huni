import type { Polygon } from "geojson";
import { expect, test } from "vitest";
import { contains, planarArea } from "./geometry";

const squareWithHole: Polygon = {
  type: "Polygon",
  coordinates: [
    [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]],
    [[1, 1], [1, 2], [2, 2], [2, 1], [1, 1]],
  ],
};

test("contains respects holes", () => {
  expect(contains(squareWithHole, [3, 3])).toBe(true);
  expect(contains(squareWithHole, [1.5, 1.5])).toBe(false);
  expect(contains(squareWithHole, [5, 1])).toBe(false);
});

test("planar area subtracts holes", () => {
  expect(planarArea(squareWithHole)).toBeCloseTo(15);
});
