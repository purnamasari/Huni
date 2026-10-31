import { Info } from "lucide-react";
import { SCORE_RAMP, SCORE_STOPS } from "../colors";

interface Props {
  showFlood: boolean;
  /** In commute mode the map shows travel time to this place instead of the score. */
  commute?: { destination: string | null; departAt: string; failed?: boolean } | null;
}

export function Legend({ showFlood, commute = null }: Props) {
  const gradient = `linear-gradient(to right, ${SCORE_RAMP.join(", ")})`;
  if (commute) {
    const info = `Fastest trip by angkot, bus, train or on foot, leaving at ${commute.departAt}. Fares and frequencies are estimates.`;
    return (
      <section className="legend card" aria-label="Map legend">
        <div className="legend-title">
          <h2>{commute.destination ? `Travel time to ${commute.destination}` : "Travel time"}</h2>
          <span className="legend-info" tabIndex={0} title={info} aria-label={info}>
            <Info size={16} />
          </span>
        </div>
        {commute.failed ? (
          <p className="legend-empty">Couldn't load travel times. Is the API running?</p>
        ) : commute.destination ? (
          <>
            <div className="legend-bar" style={{ background: gradient }} />
            <div className="legend-scale">
              <span>≥70 min Longer</span>
              <span>Quicker ≤20 min</span>
            </div>
          </>
        ) : (
          <p className="legend-empty">Set where you go most days to colour the map.</p>
        )}
      </section>
    );
  }
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
