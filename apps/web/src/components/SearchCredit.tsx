import type { PlaceResult } from "../api/types";

const CREDITS: Record<string, string> = {
  mapbox: "© Mapbox",
  photon: "© OpenStreetMap contributors",
};

/** Credit the address providers whose results are in the list, as their terms ask. */
export function SearchCredit({ results }: { results: PlaceResult[] }) {
  const credits = [...new Set(results.map((r) => r.source).filter(Boolean))]
    .map((source) => CREDITS[source!])
    .filter(Boolean);
  if (credits.length === 0) return null;
  return (
    <li className="search-credit" aria-hidden="true">
      Search {credits.join(" · ")}
    </li>
  );
}
