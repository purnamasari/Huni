import { formatPoint } from "../lib/coordinates";
import { contains, type Point } from "../lib/geometry";
import type {
  ApiPlace,
  AreaCollection,
  AreaLevel,
  CommuteTime,
  GeocodeResult,
  PlaceResult,
  TripPlan,
  TripPoint,
  TripSort,
} from "./types";

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

// The kelurahan the map shows, kept to tell which one a searched address falls in.
let kelurahan: AreaCollection | null = null;

export async function fetchAreas(level: AreaLevel, signal?: AbortSignal): Promise<AreaCollection> {
  const collection = useMocks
    ? (await import("../mocks/areas")).mockAreas[level]
    : await getJson<AreaCollection>(`/api/areas?level=${level}`, signal);
  if (level === "kelurahan") kelurahan = collection;
  return collection;
}

/** The scored area a point is in, the way the backend would with ST_Contains. */
function placeIn(point: Point): Pick<PlaceResult, "areaId" | "insideKota"> & { area?: string } {
  const feature = kelurahan?.features.find((f) => contains(f.geometry, point));
  if (!feature) return { areaId: null, insideKota: false };
  const { id, name, parent } = feature.properties;
  return { areaId: id, insideKota: true, area: parent ? `${name}, ${parent.name}` : name };
}

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<PlaceResult[]> {
  if (!query.trim()) return [];
  if (useMocks) return (await import("../mocks/places")).searchMockPlaces(query);
  return getJson(`/api/places?q=${encodeURIComponent(query)}`, signal);
}

// Address search, transit stops and trip planning always use the API: they are real data.

/** The address search providers: Mapbox for places, OpenStreetMap (Photon) for streets. */
export const ADDRESS_SOURCES = ["mapbox", "photon"] as const;

/** Addresses, streets and named places from one geocoder. */
export async function searchAddresses(
  query: string,
  source: (typeof ADDRESS_SOURCES)[number],
  signal?: AbortSignal,
): Promise<PlaceResult[]> {
  if (query.trim().length < 3) return [];
  const results = await getJson<GeocodeResult[]>(
    `/api/geocode?q=${encodeURIComponent(query)}&source=${source}`,
    signal,
  );
  return results.map(geocoded);
}

/** Named transit stops and terminals. */
export async function searchStops(query: string, signal?: AbortSignal): Promise<PlaceResult[]> {
  if (query.trim().length < 2) return [];
  const stops = await getJson<ApiPlace[]>(
    `/api/transit/places?q=${encodeURIComponent(query)}`,
    signal,
  );
  return stops.map(({ name, lon, lat }) => {
    const point: Point = [lon, lat];
    const { area, ...where } = placeIn(point);
    return { id: `stop-${name}-${lon}`, name, kind: "stop", context: area ?? "Transit stop", point, ...where };
  });
}

/** An exact point the user typed: it needs no lookup, only the area it falls in. */
export function exactPoint(point: Point): PlaceResult {
  const { area, ...where } = placeIn(point);
  return {
    id: `point-${point.join(",")}`,
    name: formatPoint(point),
    kind: "point",
    context: area ?? "Outside Kota Bandung",
    point,
    ...where,
  };
}

/** Where the device is, as a search result. */
export function currentLocation(point: Point): PlaceResult {
  return { ...exactPoint(point), id: "current-location", name: "Your location" };
}

/** The address at a point, to name a dropped pin. Null when there's nothing or it fails. */
export async function reverseGeocode(point: Point, signal?: AbortSignal): Promise<PlaceResult | null> {
  try {
    const result = await getJson<GeocodeResult>(
      `/api/geocode/reverse?lon=${point[0]}&lat=${point[1]}`,
      signal,
    );
    // The nearest named place may be a few doors away; the pin itself stays exact.
    const named = geocoded(result);
    return {
      ...named,
      point,
      name: result.kind === "landmark" ? `Near ${result.name}` : result.name,
      ...placeIn(point),
    };
  } catch {
    return null;
  }
}

function geocoded(result: GeocodeResult): PlaceResult {
  const point: Point = [result.lon, result.lat];
  const { area, ...where } = placeIn(point);
  return {
    id: result.id,
    name: result.name,
    kind: result.kind,
    // Inside the Kota, Huni's own kelurahan and kecamatan replace the provider's districts.
    context: area
      ? [result.address, area].filter(Boolean).join(" · ")
      : result.context || "Bandung Raya",
    point,
    ...where,
    source: result.source,
  };
}

// Trip planning always uses the API: the transit routes are real data, not mocks.

export async function planTrip(
  request: { points: TripPoint[]; sort: TripSort; departAt?: string },
  signal?: AbortSignal,
): Promise<TripPlan> {
  const [origin, ...destinations] = request.points.map(({ name, point: [lon, lat] }) => ({
    name,
    lon,
    lat,
  }));
  const response = await fetch("/api/transit/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      origin,
      destinations,
      sort: request.sort,
      depart_at: request.departAt || undefined,
    }),
    signal,
  });
  if (!response.ok) throw new Error(`/api/transit/plan responded ${response.status}`);
  return (await response.json()) as TripPlan;
}

/** Travel time from every origin to one destination, from a single search on the API. */
export async function fetchCommuteTimes(
  destination: TripPoint,
  origins: { id: string; point: [number, number] }[],
  departAt: string,
  signal?: AbortSignal,
): Promise<CommuteTime[]> {
  const response = await fetch("/api/transit/commute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      destination: { name: destination.name, lon: destination.point[0], lat: destination.point[1] },
      origins: origins.map(({ id, point: [lon, lat] }) => ({ id, lon, lat })),
      depart_at: departAt,
    }),
    signal,
  });
  if (!response.ok) throw new Error(`/api/transit/commute responded ${response.status}`);
  return ((await response.json()) as { times: CommuteTime[] }).times;
}
