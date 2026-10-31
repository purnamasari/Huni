import type { Point } from "./geometry";

const NUMBER = String.raw`[-+]?\d+(?:\.\d+)?`;

/**
 * An exact point typed or pasted into search, as [lon, lat], or null if the text isn't one.
 *
 * Accepts what people copy from map apps:
 * - "-6.9147, 107.6098" (lat, lon, as Google Maps copies it) or "107.6098 -6.9147"
 * - Google Maps links: ".../@-6.9147,107.6098,17z" or "?q=-6.9147,107.6098"
 * - degrees, minutes, seconds: 6°54'53.0"S 107°36'35.0"E
 *
 * For a bare pair the order is worked out from the values: a number beyond ±90 can only be
 * a longitude. When both could be either, latitude first is assumed, as map apps copy it.
 */
export function parseCoordinates(text: string): Point | null {
  const input = text.trim();
  if (!input) return null;

  const link = input.match(new RegExp(String.raw`[@=](${NUMBER}),\s*(${NUMBER})`));
  if (link && /^https?:|maps|@/.test(input)) return latLon(Number(link[1]), Number(link[2]));

  const dms = parseDms(input);
  if (dms) return dms;

  const pair = input.match(new RegExp(String.raw`^(${NUMBER})\s*[,;\s]\s*(${NUMBER})$`));
  if (!pair) return null;
  const [a, b] = [Number(pair[1]), Number(pair[2])];
  // Bare integers like "35 12" are more likely a house number than a point.
  if (!pair[1].includes(".") || !pair[2].includes(".")) return null;
  if (Math.abs(a) > 90) return valid([a, b]);
  return latLon(a, b);
}

function latLon(lat: number, lon: number): Point | null {
  return valid([lon, lat]);
}

function valid([lon, lat]: Point): Point | null {
  return Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? [lon, lat] : null;
}

function parseDms(input: string): Point | null {
  const part = String.raw`(\d+(?:\.\d+)?)\s*°\s*(?:(\d+(?:\.\d+)?)\s*['′]\s*)?(?:(\d+(?:\.\d+)?)\s*(?:"|″|'')\s*)?([NSEW])`;
  const matches = [...input.toUpperCase().matchAll(new RegExp(part, "g"))];
  if (matches.length !== 2) return null;
  let lat: number | null = null;
  let lon: number | null = null;
  for (const [, deg, min = "0", sec = "0", hemisphere] of matches) {
    const value = Number(deg) + Number(min) / 60 + Number(sec) / 3600;
    if (hemisphere === "N" || hemisphere === "S") lat = hemisphere === "S" ? -value : value;
    else lon = hemisphere === "W" ? -value : value;
  }
  return lat === null || lon === null ? null : valid([lon, lat]);
}

/** "-6.91470, 107.60980": how an exact point is shown back to the user (lat, lon). */
export const formatPoint = ([lon, lat]: Point) => `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
