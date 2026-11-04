import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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

test("shows the commute to where you go most days, and opens it", () => {
  const all = new Set<CriterionKey>(["parks", "schools", "angkot", "dailyNeeds", "commute"]);
  const onCommute = vi.fn();
  render(
    <AreaDetail
      area={area}
      place={null}
      selected={all}
      onClose={vi.fn()}
      commute={{
        destination: "Kampus ITB",
        minutes: 38.4,
        transfers: 1,
        walkOnly: false,
        departAt: "07:30",
      }}
      onCommute={onCommute}
    />,
  );

  expect(screen.getByText("38 min to Kampus ITB")).toBeTruthy();
  expect(screen.getByText("to Kampus ITB")).toBeTruthy(); // on the Work commute row
  fireEvent.click(screen.getByRole("button", { name: /38 min to Kampus ITB/ }));
  expect(onCommute).toHaveBeenCalled();
});

test("invites setting a commute when there is none yet", () => {
  const all = new Set<CriterionKey>(["commute"]);
  render(
    <AreaDetail area={area} place={null} selected={all} onClose={vi.fn()} onCommute={vi.fn()} />,
  );

  expect(screen.getByText("How long is your commute from here?")).toBeTruthy();
});
