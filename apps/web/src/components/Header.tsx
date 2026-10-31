import { isMockData } from "../api/client";
import type { Page } from "../useHashPage";
import { HealthIndicator } from "./HealthIndicator";
import { Logo } from "./Logo";
import { SearchBox } from "./SearchBox";
import type { PlaceResult } from "../api/types";

const NAV: { page: Page; label: string }[] = [
  { page: "map", label: "Map" },
  { page: "about", label: "About" },
  { page: "methodology", label: "Methodology" },
  { page: "data", label: "Data Sources" },
];

interface Props {
  page: Page;
  onSelectPlace: (place: PlaceResult) => void;
}

export function Header({ page, onSelectPlace }: Props) {
  return (
    <header className="header card">
      <Logo />
      {isMockData && (
        <span className="tag tag-demo" title="Scores and boundaries are mock data">
          Demo data
        </span>
      )}
      <SearchBox onSelect={onSelectPlace} />
      <nav className="nav" aria-label="Main">
        {NAV.map((item) => (
          <a
            key={item.page}
            href={item.page === "map" ? "#/" : `#/${item.page}`}
            // Commute is a mode of the map, so "Map" stays current.
            aria-current={
              page === item.page || (item.page === "map" && page === "commute") ? "page" : undefined
            }
          >
            {item.label}
          </a>
        ))}
      </nav>
      <HealthIndicator />
      <a className="button-primary" href="https://github.com/purnamasari/Huni">
        Follow on GitHub
      </a>
    </header>
  );
}
