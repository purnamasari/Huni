import type { AreaCollection, AreaLevel, PlaceResult } from "./types";

// Mock data until the backend serves these endpoints. Set VITE_USE_MOCK_DATA=false to use
// the API instead. The mocks are imported lazily so their boundary file stays out of the
// main bundle.
const useMocks = import.meta.env.VITE_USE_MOCK_DATA !== "false";

export const isMockData = useMocks;

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`${url} responded ${response.status}`);
  return (await response.json()) as T;
}

export async function fetchAreas(level: AreaLevel, signal?: AbortSignal): Promise<AreaCollection> {
  if (useMocks) return (await import("../mocks/areas")).mockAreas[level];
  return getJson(`/api/areas?level=${level}`, signal);
}

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<PlaceResult[]> {
  if (!query.trim()) return [];
  if (useMocks) return (await import("../mocks/places")).searchMockPlaces(query);
  return getJson(`/api/places?q=${encodeURIComponent(query)}`, signal);
}
