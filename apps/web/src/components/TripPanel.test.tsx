import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, test, vi } from "vitest";
import type { TripPlan, TripPoint } from "../api/types";
import { moveItem, TripPanel } from "./TripPanel";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const DAGO: TripPoint = { name: "Terminal Dago", point: [107.6212, -6.8671] };
const LEUWIPANJANG: TripPoint = { name: "Terminal Leuwipanjang", point: [107.5958, -6.9465] };

const route = {
  id: 7,
  name: "09: Dago → Stasiun Hall",
  code: "09",
  mode: "angkot" as const,
  color: "#F15A29",
  boarding: "hail" as const,
  headway_min: 8,
  is_placeholder: true,
};

const PLAN: TripPlan = {
  depart_at: "2026-11-02T08:00:00+07:00",
  network_version: 1,
  notes: ["Fares are placeholders."],
  segments: [
    {
      origin: { name: DAGO.name, lon: DAGO.point[0], lat: DAGO.point[1] },
      destination: { name: LEUWIPANJANG.name, lon: 107.5958, lat: -6.9465 },
      options: [
        {
          rank: 1,
          summary: "Angkot 09",
          labels: ["fastest", "cheapest"],
          scores: { overall: 1 },
          duration_min: 42,
          fare_idr: 5000,
          walk_m: 300,
          wait_min: 4,
          transfers: 0,
          availability: 0.79,
          uses_placeholder: true,
          depart_at: "2026-11-02T08:00:00+07:00",
          arrive_at: "2026-11-02T08:42:00+07:00",
          legs: [
            {
              mode: "angkot",
              route,
              start: { name: "Terminal Dago", lon: 107.6212, lat: -6.8671 },
              end: { name: "Jalan Braga", lon: 107.609, lat: -6.914 },
              distance_m: 5700,
              duration_min: 24,
              wait_min: 4,
              fare_idr: 5000,
              stop_count: 22,
              depart_at: "2026-11-02T08:04:00+07:00",
              arrive_at: "2026-11-02T08:28:00+07:00",
              available: true,
              geometry: { type: "LineString", coordinates: [[107.62, -6.87], [107.61, -6.91]] },
            },
          ],
        },
      ],
    },
  ],
};

function Harness({ initial }: { initial: (TripPoint | null)[] }) {
  const [points, setPoints] = useState(initial);
  const [plan, setPlan] = useState<TripPlan | null>(null);
  const [chosen, setChosen] = useState<number[]>([]);
  const [departTime, setDepartTime] = useState("07:30");
  return (
    <TripPanel
      points={points}
      onPointsChange={setPoints}
      activeIndex={0}
      onActiveIndexChange={vi.fn()}
      departTime={departTime}
      onDepartTimeChange={setDepartTime}
      plan={plan}
      onPlanChange={setPlan}
      chosen={chosen}
      onChosenChange={setChosen}
    />
  );
}

test("plans as soon as both ends are set, and lists the options with the chosen one's steps", async () => {
  const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify(PLAN)));
  vi.stubGlobal("fetch", fetchMock);

  render(<Harness initial={[DAGO, LEUWIPANJANG]} />);

  expect(await screen.findByText("42 min")).toBeTruthy();
  expect(screen.getByText("Fastest", { selector: ".tag" })).toBeTruthy();
  expect(screen.getByRole("meter", { name: "Availability" }).getAttribute("aria-valuenow")).toBe(
    "79",
  );
  // The first option is chosen, so its steps are listed.
  expect(screen.getByText("Jalan Braga")).toBeTruthy();
  expect(screen.getByText("Fares are placeholders.")).toBeTruthy();

  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/transit/plan");
  expect(JSON.parse(init.body)).toMatchObject({
    origin: { name: "Terminal Dago", lon: 107.6212, lat: -6.8671 },
    destinations: [{ name: "Terminal Leuwipanjang", lon: 107.5958, lat: -6.9465 }],
    sort: "balanced",
  });
  expect(JSON.parse(init.body).depart_at).toMatch(/T07:30:00$/);

  // Changing the ranking plans again.
  fireEvent.click(screen.getByRole("button", { name: "Cheapest" }));
  await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(JSON.parse(fetchMock.mock.calls[1][1].body).sort).toBe("cost");
});

test("asks where you go most days first, and adds stops before it", () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  render(<Harness initial={[null, LEUWIPANJANG]} />);
  fireEvent.click(screen.getByRole("button", { name: "Add a stop on the way" }));

  const fields = screen.getAllByRole("combobox");
  expect(fields.map((f) => f.getAttribute("aria-label"))).toEqual([
    "From",
    "Stop 1",
    "Where do you go most days?",
  ]);
  expect((fields[2] as HTMLInputElement).value).toBe("Terminal Leuwipanjang");
  // Not every field is set yet, so nothing is planned.
  expect(fetchMock).not.toHaveBeenCalled();
});

const fields = () =>
  screen.getAllByRole("combobox").map((f) => [f.getAttribute("aria-label"), (f as HTMLInputElement).value]);

test("rows move with the arrow keys on their handle, and the trip can be reversed", () => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify(PLAN))));
  const ITB: TripPoint = { name: "ITB", point: [107.6105, -6.8915] };
  render(<Harness initial={[DAGO, ITB, LEUWIPANJANG]} />);

  fireEvent.keyDown(screen.getByRole("button", { name: /^Move From/ }), { key: "ArrowDown" });

  expect(fields()).toEqual([
    ["From", "ITB"],
    ["Stop 1", "Terminal Dago"],
    ["Where do you go most days?", "Terminal Leuwipanjang"],
  ]);
  // Focus follows the moved row.
  expect(document.activeElement?.getAttribute("aria-label")).toMatch(/^Move Stop 1/);

  fireEvent.click(screen.getByRole("button", { name: "Reverse" }));

  expect(fields().map(([, value]) => value)).toEqual(["Terminal Leuwipanjang", "Terminal Dago", "ITB"]);
});

test("a field can be set to your current location", async () => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify(PLAN))));
  vi.stubGlobal("navigator", {
    geolocation: {
      getCurrentPosition: (ok: PositionCallback) =>
        ok({ coords: { longitude: 107.61, latitude: -6.9 } } as GeolocationPosition),
    },
  });
  render(<Harness initial={[null, LEUWIPANJANG]} />);

  fireEvent.focus(screen.getByRole("combobox", { name: "From" }));
  fireEvent.click(screen.getByText("Your current location"));

  expect(await screen.findByDisplayValue("Your location")).toBeTruthy();
});

test("a blocked location says how to fix it", async () => {
  vi.stubGlobal("navigator", {
    geolocation: {
      getCurrentPosition: (_: PositionCallback, fail: PositionErrorCallback) =>
        fail({ code: 1, PERMISSION_DENIED: 1, TIMEOUT: 3 } as GeolocationPositionError),
    },
  });
  render(<Harness initial={[null, LEUWIPANJANG]} />);

  fireEvent.focus(screen.getByRole("combobox", { name: "From" }));
  fireEvent.click(screen.getByText("Your current location"));

  expect((await screen.findByRole("alert")).textContent).toMatch(/Allow it for this site/);
});

test("moveItem", () => {
  expect(moveItem(["a", "b", "c"], 0, 2)).toEqual(["b", "c", "a"]);
  expect(moveItem(["a", "b", "c"], 2, 0)).toEqual(["c", "a", "b"]);
  expect(moveItem(["a", "b", "c"], 1, 1)).toEqual(["a", "b", "c"]);
});

test("dragging a row by its handle moves it", () => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify(PLAN))));
  // jsdom has no layout: give each row a 50 px slot by its position in the list.
  vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
    const top = [...(this.parentElement?.children ?? [])].indexOf(this) * 50;
    return { top, height: 50, bottom: top + 50, left: 0, right: 300, width: 300, x: 0, y: top, toJSON() {} };
  });
  const ITB: TripPoint = { name: "ITB", point: [107.6105, -6.8915] };
  render(<Harness initial={[DAGO, ITB, LEUWIPANJANG]} />);

  fireEvent.pointerDown(screen.getByRole("button", { name: /^Move From/ }));
  // Past the middle of the last row (125 px): From goes to the end.
  act(() => {
    window.dispatchEvent(new MouseEvent("pointermove", { clientY: 130 }));
  });
  act(() => {
    window.dispatchEvent(new MouseEvent("pointerup"));
  });

  expect(fields().map(([, value]) => value)).toEqual(["ITB", "Terminal Leuwipanjang", "Terminal Dago"]);
  vi.restoreAllMocks();
});
