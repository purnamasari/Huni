import { expect, test } from "vitest";
import { formatClock, formatDistance, formatDuration, formatFare } from "./format";

test("durations", () => {
  expect(formatDuration(0.2)).toBe("1 min");
  expect(formatDuration(42.4)).toBe("42 min");
  expect(formatDuration(83)).toBe("1 h 23 min");
  expect(formatDuration(120)).toBe("2 h");
});

test("fares, distances and clock times", () => {
  expect(formatFare(0)).toBe("Free");
  expect(formatFare(5000).replace(/\s/g, " ")).toBe("Rp 5.000");
  expect(formatDistance(420)).toBe("420 m");
  expect(formatDistance(5696)).toBe("5.7 km");
  expect(formatClock("2026-11-02T08:42:00+07:00")).toBe("08:42");
});
