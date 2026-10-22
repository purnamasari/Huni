import { mockAreas } from "../mocks/areas";
import { searchMockPlaces } from "../mocks/places";
import type { AreaCollection, PlaceResult } from "./types";

// Mock data until the backend serves these endpoints. Set VITE_USE_MOCK_DATA=false to use
// the API instead.
const useMocks = import.meta.env.VITE_USE_MOCK_DATA !== "false";

export const isMockData = useMocks;

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`${url} responded ${response.status}`);
  return (await response.json()) as T;
}

export function fetchAreas(signal?: AbortSignal): Promise<AreaCollection> {
  if (useMocks) return Promise.resolve(mockAreas);
  return getJson("/api/areas?level=kecamatan", signal);
}

export function searchPlaces(query: string, signal?: AbortSignal): Promise<PlaceResult[]> {
  if (!query.trim()) return Promise.resolve([]);
  if (useMocks) return Promise.resolve(searchMockPlaces(query));
  return getJson(`/api/places?q=${encodeURIComponent(query)}`, signal);
}
