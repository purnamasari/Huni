import type { MultiPolygon, Polygon } from "geojson";

export type Point = [number, number];
export type Ring = Point[];

/** Ray casting; points exactly on an edge may fall either way. */
function inRing([x, y]: Point, ring: Ring): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function polygons(geometry: Polygon | MultiPolygon): Ring[][] {
  return (geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates) as Ring[][];
}

export function contains(geometry: Polygon | MultiPolygon, point: Point): boolean {
  return polygons(geometry).some(
    ([outer, ...holes]) => inRing(point, outer) && !holes.some((hole) => inRing(point, hole)),
  );
}

function ringArea(ring: Ring): number {
  let sum = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    sum += (ring[j][0] - ring[i][0]) * (ring[j][1] + ring[i][1]);
  }
  return Math.abs(sum / 2);
}

/**
 * Area in square degrees. Only good for comparing shapes near each other (a degree of
 * longitude barely shrinks across Bandung), never for real measurements.
 */
export function planarArea(geometry: Polygon | MultiPolygon): number {
  return polygons(geometry).reduce(
    (total, [outer, ...holes]) =>
      total + ringArea(outer) - holes.reduce((sum, hole) => sum + ringArea(hole), 0),
    0,
  );
}
