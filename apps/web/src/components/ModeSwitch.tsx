import { MapPinned, Route } from "lucide-react";

export type Mode = "explore" | "commute";

/** The two ways to use the map, always on screen. Links, so each mode has its own URL. */
export function ModeSwitch({ mode }: { mode: Mode }) {
  return (
    <nav className="mode-switch card" aria-label="Map mode">
      <a href="#/" aria-current={mode === "explore" ? "page" : undefined}>
        <MapPinned size={18} aria-hidden="true" />
        Neighbourhoods
      </a>
      <a href="#/commute" aria-current={mode === "commute" ? "page" : undefined}>
        <Route size={18} aria-hidden="true" />
        Commute
      </a>
    </nav>
  );
}
