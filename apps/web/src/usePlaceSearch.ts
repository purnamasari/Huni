import { useEffect, useState } from "react";
import {
  ADDRESS_SOURCES,
  exactPoint,
  searchAddresses,
  searchPlaces,
  searchStops,
} from "./api/client";
import type { PlaceResult } from "./api/types";
import { parseCoordinates } from "./lib/coordinates";

const MAX_RESULTS = 8;
// About 200 m: the same name this close is the same place from two sources.
const SAME_PLACE_DEGREES = 0.002;

/** Keep the first of each place, in source order, so local results win over the geocoder's. */
export function mergePlaces(...lists: PlaceResult[][]): PlaceResult[] {
  const merged: PlaceResult[] = [];
  for (const place of lists.flat()) {
    const duplicate = merged.some(
      (other) =>
        other.name.toLowerCase() === place.name.toLowerCase() &&
        Math.abs(other.point[0] - place.point[0]) < SAME_PLACE_DEGREES &&
        Math.abs(other.point[1] - place.point[1]) < SAME_PLACE_DEGREES,
    );
    if (!duplicate) merged.push(place);
  }
  return merged.slice(0, MAX_RESULTS);
}

/**
 * Several providers' results as one list: exact name matches first, then the providers in
 * turns, so one with many results (Mapbox's places) doesn't crowd out another's (streets).
 */
export function inTurns(query: string, ...lists: PlaceResult[][]): PlaceResult[] {
  const wanted = query.trim().toLowerCase();
  const isExact = (place: PlaceResult) => place.name.toLowerCase() === wanted;
  const rest = lists.map((list) => list.filter((place) => !isExact(place)));
  const longest = Math.max(0, ...rest.map((list) => list.length));
  const turns = Array.from({ length: longest }, (_, i) => rest.flatMap((list) => list[i] ?? []));
  return [...lists.flat().filter(isExact), ...turns.flat()];
}

/**
 * Search as you type. Coordinates show up at once as an exact point. Otherwise
 * neighbourhoods (and transit stops, when asked for) come first, and addresses from each
 * geocoder are added as they arrive.
 */
export function usePlaceSearch(query: string, { stops = false } = {}) {
  const [results, setResults] = useState<PlaceResult[]>([]);
  const [searchingAddresses, setSearchingAddresses] = useState(false);

  useEffect(() => {
    const text = query.trim();
    setSearchingAddresses(false);
    if (!text) {
      setResults([]);
      return;
    }
    const point = parseCoordinates(text);
    if (point) {
      setResults([exactPoint(point)]);
      return;
    }

    const controller = new AbortController();
    const { signal } = controller;
    let local: PlaceResult[] = [];
    const addresses: PlaceResult[][] = ADDRESS_SOURCES.map(() => []);
    const show = () => {
      if (!signal.aborted) setResults(mergePlaces(local, inTurns(text, ...addresses)));
    };
    const timer = setTimeout(() => {
      Promise.all([
        searchPlaces(text, signal).catch(() => []),
        stops ? searchStops(text, signal).catch(() => []) : [],
      ]).then(([places, found]) => {
        local = [...places, ...found];
        show();
      });
      if (text.length >= 3) {
        // Each provider shows up as soon as it answers; a slow one never holds up the rest.
        setSearchingAddresses(true);
        Promise.allSettled(
          ADDRESS_SOURCES.map((source, i) =>
            searchAddresses(text, source, signal).then((found) => {
              addresses[i] = found;
              show();
            }),
          ),
        ).then(() => {
          if (!signal.aborted) setSearchingAddresses(false);
        });
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, stops]);

  return { results, searchingAddresses };
}
