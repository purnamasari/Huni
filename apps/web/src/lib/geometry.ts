export type Point = [number, number];
export type Ring = Point[];

/** Signed area of an open or closed ring (positive = counter-clockwise). */
function signedArea(ring: Ring): number {
  let sum = 0;
  for (let i = 0; i < ring.length; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % ring.length];
    sum += x1 * y2 - x2 * y1;
  }
  return sum / 2;
}

function openRing(ring: Ring): Ring {
  const [first, last] = [ring[0], ring[ring.length - 1]];
  return first[0] === last[0] && first[1] === last[1] ? ring.slice(0, -1) : ring;
}

/**
 * Sutherland–Hodgman: clip `subject` (any simple polygon) by a convex `clip` polygon.
 * Returns a closed ring, or an empty array when they don't overlap. Planar maths on
 * whatever coordinates it's given, which is fine for mock data and nothing else.
 */
export function clipByConvex(subject: Ring, clip: Ring): Ring {
  let output = openRing(subject);
  let clipRing = openRing(clip);
  if (signedArea(clipRing) < 0) clipRing = [...clipRing].reverse();

  const inside = (p: Point, a: Point, b: Point) =>
    (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0;
  const intersect = (p: Point, q: Point, a: Point, b: Point): Point => {
    const d = (p[0] - q[0]) * (a[1] - b[1]) - (p[1] - q[1]) * (a[0] - b[0]);
    const t = ((p[0] - a[0]) * (a[1] - b[1]) - (p[1] - a[1]) * (a[0] - b[0])) / d;
    return [p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])];
  };

  for (let i = 0; i < clipRing.length && output.length > 0; i++) {
    const a = clipRing[i];
    const b = clipRing[(i + 1) % clipRing.length];
    const input = output;
    output = [];
    for (let j = 0; j < input.length; j++) {
      const current = input[j];
      const previous = input[(j + input.length - 1) % input.length];
      if (inside(current, a, b)) {
        if (!inside(previous, a, b)) output.push(intersect(previous, current, a, b));
        output.push(current);
      } else if (inside(previous, a, b)) {
        output.push(intersect(previous, current, a, b));
      }
    }
  }

  return output.length >= 3 ? [...output, output[0]] : [];
}

export function ringArea(ring: Ring): number {
  return Math.abs(signedArea(openRing(ring)));
}

export function bbox(rings: Ring[]): [number, number, number, number] {
  let [minX, minY, maxX, maxY] = [Infinity, Infinity, -Infinity, -Infinity];
  for (const ring of rings) {
    for (const [x, y] of ring) {
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
  }
  return [minX, minY, maxX, maxY];
}
