import { expect, test } from "vitest";
import { formatPoint, parseCoordinates } from "./coordinates";

const close = (point: [number, number] | null, lon: number, lat: number) => {
  expect(point).not.toBeNull();
  expect(point![0]).toBeCloseTo(lon, 4);
  expect(point![1]).toBeCloseTo(lat, 4);
};

test("lat, lon pairs as map apps copy them, in either order", () => {
  close(parseCoordinates("-6.9147, 107.6098"), 107.6098, -6.9147);
  close(parseCoordinates("-6.9147 107.6098"), 107.6098, -6.9147);
  close(parseCoordinates("107.6098,-6.9147"), 107.6098, -6.9147);
});

test("Google Maps links", () => {
  close(
    parseCoordinates("https://www.google.com/maps/place/Gedung+Sate/@-6.9024812,107.6187879,17z"),
    107.6187879,
    -6.9024812,
  );
  close(parseCoordinates("https://maps.google.com/?q=-6.9147,107.6098"), 107.6098, -6.9147);
});

test("degrees, minutes and seconds", () => {
  close(parseCoordinates(`6°54'53.0"S 107°36'35.0"E`), 107.609722, -6.914722);
});

test("ordinary searches are not points", () => {
  expect(parseCoordinates("Jalan Braga 12")).toBeNull();
  expect(parseCoordinates("35 12")).toBeNull();
  expect(parseCoordinates("200.5, 300.1")).toBeNull();
});

test("points are shown back as lat, lon", () => {
  expect(formatPoint([107.6098, -6.9147])).toBe("-6.91470, 107.60980");
});
