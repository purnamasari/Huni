import { expect, test } from "vitest";
import { commuteBadge, commuteScore } from "./commute";

test("shorter commutes score higher, on the same scale as the other criteria", () => {
  expect(commuteScore(15)).toBe(95);
  expect(commuteScore(70)).toBe(40);
  expect(commuteScore(200)).toBe(0);
  expect(commuteScore(null)).toBeNull();
});

test("badges show whole minutes", () => {
  expect(commuteBadge(32.4)).toBe("32m");
  expect(commuteBadge(null)).toBe("–");
});
