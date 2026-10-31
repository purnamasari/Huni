import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { AreaProperties, CriterionKey } from "../api/types";
import { AreaDetail } from "./DetailPanel";

afterEach(cleanup);

const area: AreaProperties = {
  id: "gedebage",
  name: "Gedebage",
  level: "kecamatan",
  parent: null,
  labelPoint: [107.69, -6.952],
  scores: { parks: 40, schools: 60, angkot: 50, dailyNeeds: 70, commute: 80 },
  floodRisk: "high",
};

test("flood risk is a warning line, not a score bar", () => {
  const all = new Set<CriterionKey>(["parks", "schools", "angkot", "dailyNeeds", "commute"]);
  render(<AreaDetail area={area} place={null} selected={all} onClose={vi.fn()} />);

  expect(screen.getByText("Flood risk: High")).toBeTruthy();
  const meters = screen.getAllByRole("meter");
  expect(meters).toHaveLength(5);
  expect(meters.some((m) => /flood/i.test(m.getAttribute("aria-label") ?? ""))).toBe(false);
});

test("the headline score only counts the selected criteria", () => {
  const some = new Set<CriterionKey>(["dailyNeeds", "commute"]);
  render(<AreaDetail area={area} place={null} selected={some} onClose={vi.fn()} />);

  expect(screen.getByLabelText("Score 75 out of 100")).toBeTruthy();
  expect(screen.getAllByText("not in score")).toHaveLength(3);
});
