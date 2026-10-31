import { BusFront, Crosshair, MapPin } from "lucide-react";
import type { PlaceKind } from "../api/types";

/** The icon in front of a search result: exact points and stops look different. */
export function PlaceIcon({ kind }: { kind: PlaceKind }) {
  const Icon = kind === "point" ? Crosshair : kind === "stop" ? BusFront : MapPin;
  return <Icon size={18} className="search-result-pin" aria-hidden="true" />;
}
