import { Info } from "lucide-react";
import { SCORE_RAMP, SCORE_STOPS } from "../colors";

interface Props {
  showFlood: boolean;
}

export function Legend({ showFlood }: Props) {
  const gradient = `linear-gradient(to right, ${SCORE_RAMP.join(", ")})`;
  return (
    <section className="legend card" aria-label="Map legend">
      <div className="legend-title">
        <h2>Livability score</h2>
        <span
          className="legend-info"
          tabIndex={0}
          title="Average of the criteria you picked, 0–100. Higher is better."
          aria-label="Average of the criteria you picked, 0–100. Higher is better."
        >
          <Info size={16} />
        </span>
      </div>
      <div className="legend-bar" style={{ background: gradient }} />
      <div className="legend-scale">
        <span>≤{SCORE_STOPS[0]} Lower</span>
        <span>Higher ≥{SCORE_STOPS[SCORE_STOPS.length - 1]}</span>
      </div>
      {showFlood && (
        <div className="legend-flood">
          <span className="legend-hatch" aria-hidden="true" />
          Flood-prone (moderate or high)
        </div>
      )}
    </section>
  );
}
