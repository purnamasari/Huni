import { expect, test } from "vitest";
import { clipByConvex, ringArea, type Ring } from "./geometry";

const square = (x: number, y: number, size: number): Ring => [
  [x, y], [x + size, y], [x + size, y + size], [x, y + size], [x, y],
];

test("clipping two overlapping squares keeps only the overlap", () => {
  const clipped = clipByConvex(square(0, 0, 2), square(1, 1, 2));
  expect(ringArea(clipped)).toBeCloseTo(1);
  expect(clipped[0]).toEqual(clipped[clipped.length - 1]);
});

test("clip ring orientation doesn't matter", () => {
  const clockwise = [...square(1, 1, 2)].reverse();
  expect(ringArea(clipByConvex(square(0, 0, 2), clockwise))).toBeCloseTo(1);
});

test("disjoint polygons clip to nothing", () => {
  expect(clipByConvex(square(0, 0, 1), square(5, 5, 1))).toEqual([]);
});
