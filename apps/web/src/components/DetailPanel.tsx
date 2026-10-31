import { ChevronDown, ChevronRight, CircleCheck, MapPin, Route, TriangleAlert, X } from "lucide-react";
import { useState } from "react";
import type { AreaProperties, CriterionKey, PlaceResult } from "../api/types";
import { inkOn, scoreColor } from "../colors";
import { CRITERIA, FLOOD, FLOOD_LABELS } from "../criteria";
import { formatDuration } from "../lib/format";
import { overallScore, summarise } from "../lib/scoring";

/** The commute from this area to where the user goes most days, if they set it. */
export interface AreaCommute {
  destination: string;
  minutes: number | null;
  transfers: number | null;
  walkOnly: boolean;
  departAt: string;
}

interface AreaProps {
  area: AreaProperties;
  place: PlaceResult | null;
  selected: ReadonlySet<CriterionKey>;
  onClose: () => void;
  /** Null until the user sets where they go most days. */
  commute?: AreaCommute | null;
  /** Opens Commute mode from this area. */
  onCommute?: () => void;
}

export function AreaDetail({
  area,
  place,
  selected,
  onClose,
  commute = null,
  onCommute,
}: AreaProps) {
  const [showSources, setShowSources] = useState(false);
  const score = overallScore(area.scores, selected);
  const flagged = area.floodRisk !== "low";
  const FloodIcon = flagged ? TriangleAlert : CircleCheck;

  return (
    <aside className="detail card" aria-label={`${area.name} details`}>
      <button type="button" className="icon-button detail-close" aria-label="Close" onClick={onClose}>
        <X size={20} />
      </button>

      <p className="detail-kicker">
        {area.level === "kelurahan"
          ? `Kelurahan · ${area.parent?.name}`
          : "Kecamatan · Kota Bandung"}
      </p>
      <div className="detail-title">
        <h2>{area.name}</h2>
        <span
          className="score-pill"
          style={{ background: scoreColor(score), color: inkOn(score) }}
          aria-label={score === null ? "No score" : `Score ${score} out of 100`}
        >
          {score ?? "–"} / 100
        </span>
      </div>
      {place && place.areaId === area.id && place.kind !== area.level && (
        <p className="detail-place">
          <MapPin size={14} aria-hidden="true" /> {place.name} is in {area.name}.
        </p>
      )}
      <p className="detail-summary">{summarise(area.scores, selected)}</p>

      {onCommute && (
        <button type="button" className="commute-link" onClick={onCommute}>
          <span className="explore-icon" aria-hidden="true">
            <Route size={20} />
          </span>
          <CommuteText commute={commute} />
          <ChevronRight size={20} aria-hidden="true" />
        </button>
      )}

      <h3>Score breakdown</h3>
      <ul className="breakdown">
        {CRITERIA.map(({ key, label, icon: Icon }) => {
          const value = area.scores[key];
          const included = selected.has(key);
          return (
            <li key={key} className={included ? undefined : "excluded"}>
              <Icon size={18} aria-hidden="true" />
              <span className="breakdown-label">
                {label}
                {!included && <span className="breakdown-note">not in score</span>}
                {included && key === "commute" && commute && (
                  <span className="breakdown-note">to {commute.destination}</span>
                )}
              </span>
              <span
                className="bar"
                role="meter"
                aria-label={label}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={value}
              >
                <span style={{ width: `${value}%` }} />
              </span>
              <span className="breakdown-value">{value}</span>
            </li>
          );
        })}
      </ul>

      <p className={`flood-flag flood-${area.floodRisk}`}>
        <FloodIcon size={18} aria-hidden="true" />
        <span>
          <strong>Flood risk: {FLOOD_LABELS[area.floodRisk]}</strong>
          <span>Shown as a warning, not counted in the score.</span>
        </span>
      </p>

      <button
        type="button"
        className="sources-toggle"
        aria-expanded={showSources}
        onClick={() => setShowSources((open) => !open)}
      >
        Data behind this score
        <ChevronDown size={18} aria-hidden="true" />
      </button>
      {showSources && (
        <dl className="sources">
          {[...CRITERIA, { key: "flood", ...FLOOD }].map(({ key, label, icon: Icon, measures, sources }) => (
            <div key={key}>
              <Icon size={18} aria-hidden="true" />
              <dt>{label}</dt>
              <dd>{measures}</dd>
              <dd className="sources-origin">{sources}</dd>
            </div>
          ))}
        </dl>
      )}
      <p className="detail-footnote">
        Demo data: the scores are mock values until the backend is ready. Boundaries ©
        OpenStreetMap contributors.
      </p>
    </aside>
  );
}

function CommuteText({ commute }: { commute: AreaCommute | null }) {
  if (!commute) {
    return (
      <span className="explore-text">
        <strong>How long is your commute from here?</strong>
        <span>Set where you go most days, like work or campus.</span>
      </span>
    );
  }
  if (commute.minutes === null) {
    return (
      <span className="explore-text">
        <strong>No route to {commute.destination}</strong>
        <span>Nothing gets there by {commute.departAt}. See other times.</span>
      </span>
    );
  }
  const how = commute.walkOnly
    ? "on foot"
    : commute.transfers
      ? `${commute.transfers} transfer${commute.transfers > 1 ? "s" : ""}`
      : "no transfers";
  return (
    <span className="explore-text">
      <strong>
        {formatDuration(commute.minutes)} to {commute.destination}
      </strong>
      <span>
        {how}, leaving at {commute.departAt}. See the route.
      </span>
    </span>
  );
}

interface PlaceProps {
  place: PlaceResult;
  onClose: () => void;
}

/** A search result outside Kota Bandung: say why there's no score instead of guessing one. */
export function OutsideDetail({ place, onClose }: PlaceProps) {
  return (
    <aside className="detail card" aria-label={`${place.name} details`}>
      <button type="button" className="icon-button detail-close" aria-label="Close" onClick={onClose}>
        <X size={20} />
      </button>
      <p className="detail-kicker">{place.context}</p>
      <div className="detail-title">
        <h2>{place.name}</h2>
        <span className="tag tag-muted">Outside Kota Bandung</span>
      </div>
      <p className="detail-summary detail-summary-last">
        Huni only scores neighbourhoods inside Kota Bandung, so there's no score here. Parks and
        services just across the border still count towards nearby Bandung neighbourhoods.
      </p>
    </aside>
  );
}
