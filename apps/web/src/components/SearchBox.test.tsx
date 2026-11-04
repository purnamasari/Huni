import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { PlaceResult } from "../api/types";
import { inTurns, mergePlaces } from "../usePlaceSearch";
import { SearchBox } from "./SearchBox";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const type = (text: string) =>
  fireEvent.change(screen.getByRole("combobox"), { target: { value: text } });

test("pasted coordinates become an exact point, with no lookup", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const onSelect = vi.fn();
  render(<SearchBox onSelect={onSelect} />);

  type("-6.9147, 107.6098");
  fireEvent.click(await screen.findByText("-6.91470, 107.60980"));

  expect(onSelect).toHaveBeenCalledWith(
    expect.objectContaining({ kind: "point", point: [107.6098, -6.9147] }),
  );
  expect(fetchMock).not.toHaveBeenCalled();
});

test("addresses from the geocoder are added to the results", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "photon-W1",
            name: "Cihampelas Walk (CiWalk)",
            kind: "landmark",
            context: "Jalan Cihampelas 160, Cipaganti, Bandung",
            address: "Jalan Cihampelas 160",
            lon: 107.6056,
            lat: -6.8938,
            source: "photon",
          },
        ]),
      ),
    ),
  );
  render(<SearchBox onSelect={vi.fn()} />);

  type("Cihampelas");

  expect(await screen.findByText("Cihampelas Walk (CiWalk)")).toBeTruthy();
  expect(screen.getByText(/Landmark · Jalan Cihampelas 160/)).toBeTruthy();
});

test("the same place from two sources shows once, the local one first", () => {
  const place = (id: string, lon: number): PlaceResult => ({
    id,
    name: "Gedung Sate",
    kind: "landmark",
    context: "",
    point: [lon, -6.9025],
    insideKota: true,
    areaId: null,
  });

  expect(mergePlaces([place("local", 107.6187)], [place("geocoder", 107.6189)])).toEqual([
    place("local", 107.6187),
  ]);
  expect(mergePlaces([place("a", 107.6)], [place("far", 107.7)])).toHaveLength(2);
});

test("providers take turns after exact matches, so streets aren't crowded out", () => {
  const named = (name: string, source: string): PlaceResult => ({
    id: `${source}-${name}`,
    name,
    kind: "landmark",
    context: "",
    point: [107.6, -6.9],
    insideKota: true,
    areaId: null,
    source,
  });
  const mapbox = ["Toko A", "Toko B", "Toko C"].map((n) => named(n, "mapbox"));
  const photon = [named("Jalan Toko", "photon"), named("toko b", "photon")];

  expect(inTurns("Toko B", mapbox, photon).map((p) => p.id)).toEqual([
    "mapbox-Toko B",
    "photon-toko b",
    "mapbox-Toko A",
    "photon-Jalan Toko",
    "mapbox-Toko C",
  ]);
});
