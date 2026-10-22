import { ChevronDown, ChevronRight, MapPinned } from "lucide-react";
import { useState } from "react";
import type { CriterionKey } from "../api/types";
import { inkOn, scoreColor } from "../colors";
import { CRITERIA, FLOOD } from "../criteria";

export interface RankedArea {
  id: string;
  name: string;
  score: number | null;
}

interface Props {
  selected: ReadonlySet<CriterionKey>;
  onToggle: (key: CriterionKey) => void;
  showFlood: boolean;
  onToggleFlood: () => void;
  ranked: RankedArea[];
  onSelectArea: (id: string) => void;
}

export function IntroPanel({
  selected,
  onToggle,
  showFlood,
  onToggleFlood,
  ranked,
  onSelectArea,
}: Props) {
  const [exploring, setExploring] = useState(false);
  const FloodIcon = FLOOD.icon;

  return (
    <section className="intro card" aria-label="Introduction and filters">
      <h1>
        Find your place <br />
        in Bandung
      </h1>
      <p className="intro-lede">
        Huni scores every neighbourhood in Kota Bandung on what matters to you: parks, schools,
        angkot access and more, with the data behind every score.
      </p>

      <div className="chips" role="group" aria-label="Criteria in the score">
        {CRITERIA.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            type="button"
            className="chip"
            aria-pressed={selected.has(key)}
            onClick={() => onToggle(key)}
          >
            <Icon size={16} aria-hidden="true" />
            {label}
          </button>
        ))}
        <button
          type="button"
          className="chip chip-flag"
          aria-pressed={showFlood}
          onClick={onToggleFlood}
          title="Shows flood-prone areas on the map. Not part of the score."
        >
          <FloodIcon size={16} aria-hidden="true" />
          {FLOOD.label}
        </button>
      </div>

      <button
        type="button"
        className="explore"
        aria-expanded={exploring}
        onClick={() => setExploring((open) => !open)}
      >
        <span className="explore-icon" aria-hidden="true">
          <MapPinned size={22} />
        </span>
        <span className="explore-text">
          <strong>Explore Bandung neighbourhoods</strong>
          <span>See how all 30 kecamatan rank on the criteria you picked.</span>
        </span>
        {exploring ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
      </button>

      {exploring && (
        <ol className="ranking">
          {ranked.map((area) => (
            <li key={area.id}>
              <button type="button" onClick={() => onSelectArea(area.id)}>
                <span>{area.name}</span>
                <span
                  className="score-badge"
                  style={{ background: scoreColor(area.score), color: inkOn(area.score) }}
                >
                  {area.score ?? "–"}
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
