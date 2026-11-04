import { LoaderCircle, LocateFixed } from "lucide-react";
import { useState } from "react";
import { currentLocation } from "../api/client";
import type { PlaceResult } from "../api/types";
import { canLocate, currentPoint } from "../lib/location";

interface Props {
  id: string;
  highlighted: boolean;
  onHighlight: () => void;
  onLocated: (place: PlaceResult) => void;
  /** Lets the parent trigger it from the keyboard (Enter). */
  locateRef?: React.MutableRefObject<(() => void) | null>;
}

/** "Your current location" at the top of an empty search list. */
export function CurrentLocationOption({ id, highlighted, onHighlight, onLocated, locateRef }: Props) {
  const [state, setState] = useState<{ status: "idle" | "locating" } | { error: string }>({
    status: "idle",
  });
  const locating = "status" in state && state.status === "locating";

  const locate = () => {
    if (locating) return;
    setState({ status: "locating" });
    currentPoint()
      .then((point) => {
        setState({ status: "idle" });
        onLocated(currentLocation(point));
      })
      .catch((error: Error) => setState({ error: error.message }));
  };
  if (locateRef) locateRef.current = locate;

  if (!canLocate()) return null;
  return (
    <li
      id={id}
      role="option"
      aria-selected={highlighted}
      className="search-result search-locate"
      // Keep focus in the input, so the list stays open while locating.
      onMouseDown={(event) => event.preventDefault()}
      onClick={locate}
      onMouseEnter={onHighlight}
    >
      {locating ? (
        <LoaderCircle size={18} className="search-result-pin spin" aria-hidden="true" />
      ) : (
        <LocateFixed size={18} className="search-result-pin" aria-hidden="true" />
      )}
      <span className="search-result-text">
        <span className="search-result-name">
          {locating ? "Finding your location…" : "Your current location"}
        </span>
        {"error" in state && (
          <span className="search-result-context search-locate-error" role="alert">
            {state.error}
          </span>
        )}
      </span>
    </li>
  );
}
