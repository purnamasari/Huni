import { expect, test } from "vitest";
import type { CriterionKey } from "../api/types";
import { overallScore, summarise } from "./scoring";

const scores: Record<CriterionKey, number> = {
  parks: 90,
  schools: 80,
  angkot: 40,
  dailyNeeds: 70,
  commute: 50,
};

test("overall score is the mean of the selected criteria", () => {
  expect(overallScore(scores, new Set<CriterionKey>(["parks", "angkot"]))).toBe(65);
  expect(overallScore(scores, new Set<CriterionKey>(["schools"]))).toBe(80);
});

test("no selected criteria means no score, not zero", () => {
  expect(overallScore(scores, new Set())).toBeNull();
});

test("summary names the strongest and weakest selected criteria", () => {
  const all = new Set<CriterionKey>(["parks", "schools", "angkot", "dailyNeeds", "commute"]);
  expect(summarise(scores, all)).toBe(
    "Strong on parks & green space and schools; weaker on angkot access and work commute.",
  );
  expect(summarise(scores, new Set<CriterionKey>(["parks"]))).toBe("Strong on parks & green space.");
});
