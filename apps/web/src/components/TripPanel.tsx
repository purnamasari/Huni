import { ArrowUpDown, Footprints, GripVertical, Plus, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { planTrip } from "../api/client";
import type {
  PlaceResult,
  TripLeg,
  TripOption,
  TripPlan,
  TripPoint,
  TripSort,
} from "../api/types";
import { todayAt } from "../lib/commute";
import { formatClock, formatDistance, formatDuration, formatFare, modeName } from "../lib/format";
import { canLocate } from "../lib/location";
import { usePlaceSearch } from "../usePlaceSearch";
import { CurrentLocationOption } from "./CurrentLocationOption";
import { PlaceIcon } from "./PlaceIcon";
import { SearchCredit } from "./SearchCredit";

const MAX_DESTINATIONS = 3;

const SORTS: { value: TripSort; label: string }[] = [
  { value: "balanced", label: "Balanced" },
  { value: "time", label: "Fastest" },
  { value: "cost", label: "Cheapest" },
  { value: "availability", label: "Most available" },
];

const OPTION_LABELS: Record<TripOption["labels"][number], string> = {
  fastest: "Fastest",
  cheapest: "Cheapest",
  most_available: "Most available",
};

/** "A" for the origin, then "B", "C", … for the destinations in visiting order. */
export const pointLetter = (index: number) => String.fromCharCode(65 + index);

interface Props {
  /** In trip order: where you start, any stops on the way, then where you go most days. */
  points: (TripPoint | null)[];
  onPointsChange: (points: (TripPoint | null)[]) => void;
  /** The field the next map click fills in. */
  activeIndex: number;
  onActiveIndexChange: (index: number) => void;
  /** "HH:MM", shared with the travel-time map. */
  departTime: string;
  onDepartTimeChange: (time: string) => void;
  plan: TripPlan | null;
  onPlanChange: (plan: TripPlan | null) => void;
  /** The chosen option of each segment. */
  chosen: number[];
  onChosenChange: (chosen: number[]) => void;
}

/** A copy of `items` with the one at `from` moved to `to`. */
export function moveItem<T>(items: T[], from: number, to: number): T[] {
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

/** Where the next click or search should go: where you go most days while that's unset,
 * then the next empty field, then back to "From", so clicking neighbourhood after
 * neighbourhood compares them. */
export function nextField(points: (TripPoint | null)[]): number {
  const last = points.length - 1;
  if (points[last] === null) return last;
  return Math.max(0, points.findIndex((p) => p === null));
}

export function TripPanel({
  points,
  onPointsChange,
  activeIndex,
  onActiveIndexChange,
  departTime,
  onDepartTimeChange,
  plan,
  onPlanChange,
  chosen,
  onChosenChange,
}: Props) {
  const [sort, setSort] = useState<TripSort>("balanced");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const last = points.length - 1;
  const ready = points.length >= 2 && points.every(Boolean);
  // Re-plan when a point moves, not when a pin is only renamed to its address.
  const where = points.map((p) => p?.point.join(",") ?? "").join("|");

  // Plan as soon as every field is set, and again whenever an input changes.
  useEffect(() => {
    if (!ready) return;
    const controller = new AbortController();
    setStatus("loading");
    planTrip({ points: points as TripPoint[], sort, departAt: todayAt(departTime) }, controller.signal)
      .then((result) => {
        onPlanChange(result);
        onChosenChange(result.segments.map(() => 0));
        setStatus("idle");
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus("error");
      });
    return () => controller.abort();
    // The callbacks are the parent's state setters; only the inputs should re-plan.
  }, [ready, where, sort, departTime]);

  const setPoints = (next: (TripPoint | null)[]) => {
    onPointsChange(next);
    onPlanChange(null);
  };

  const label = (i: number) =>
    i === 0 ? "From" : i === last ? "Where do you go most days?" : `Stop ${i}`;

  // Reordering. While dragging, rows show in the order they would drop in (`order` holds
  // indices into `points`); the change is committed on release.
  const [drag, setDrag] = useState<{ from: number; to: number } | null>(null);
  const rows = useRef<(HTMLLIElement | null)[]>([]);
  const focusHandle = useRef<number | null>(null);
  const order = moveItem(
    points.map((_, i) => i),
    drag?.from ?? 0,
    drag?.to ?? 0,
  );

  const reorder = (next: (TripPoint | null)[], focusAt?: number) => {
    setPoints(next);
    onActiveIndexChange(nextField(next));
    focusHandle.current = focusAt ?? null;
  };

  // Keep keyboard focus on the moved row's handle.
  useEffect(() => {
    if (focusHandle.current === null) return;
    rows.current[focusHandle.current]?.querySelector<HTMLElement>(".trip-handle")?.focus();
    focusHandle.current = null;
  });

  // Pointer events work for mouse and touch alike. The move and release are followed on
  // the window: React moves the dragged row's element as the preview reorders, and the
  // browser drops pointer capture from an element that is moved.
  const startDrag = (event: React.PointerEvent<HTMLElement>, from: number) => {
    event.preventDefault();
    let current = { from, to: from };
    setDrag(current);

    const move = (e: PointerEvent) => {
      // The dropped row goes after every other row whose middle is above the pointer.
      const to = points.filter((_, i) => {
        const box = i !== from && rows.current[i]?.getBoundingClientRect();
        return box && box.top + box.height / 2 < e.clientY;
      }).length;
      if (to !== current.to) {
        current = { from, to };
        setDrag(current);
      }
    };
    const finish = (commit: boolean) => () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", drop);
      window.removeEventListener("pointercancel", cancel);
      setDrag(null);
      if (commit && current.to !== from) reorder(moveItem(points, from, current.to));
    };
    const drop = finish(true);
    const cancel = finish(false);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", drop);
    window.addEventListener("pointercancel", cancel);
  };

  return (
    <section className="trip card" aria-label="Commute planner">
      <p className="detail-kicker">Angkot, bus and train</p>
      <h2 className="trip-title">How far is it?</h2>
      <p className="trip-hint">
        {points[last]
          ? "Click any neighbourhood on the map, or search, to see how you'd get there."
          : "Set where you go most days, like work or campus. The map then shows how long it takes from every neighbourhood."}
      </p>

      <ol className="trip-points">
        {order.map((original, i) => {
          const point = points[original];
          return (
            <li
              key={drag ? original : i}
              ref={(row) => {
                rows.current[original] = row;
              }}
              data-dragging={drag?.from === original}
            >
              <button
                type="button"
                className="icon-button trip-handle"
                aria-label={`Move ${label(i)}. Drag, or use the up and down arrow keys`}
                onPointerDown={(event) => startDrag(event, original)}
                onKeyDown={(event) => {
                  const step = event.key === "ArrowUp" ? -1 : event.key === "ArrowDown" ? 1 : 0;
                  if (!step || i + step < 0 || i + step > last) return;
                  event.preventDefault();
                  reorder(moveItem(points, i, i + step), i + step);
                }}
              >
                <GripVertical size={16} />
              </button>
              <TripField
                letter={pointLetter(i)}
                label={label(i)}
                placeholder={
                  i === 0
                    ? "From: click a neighbourhood or search"
                    : i === last
                      ? "Work, campus… search or click the map"
                      : "Stop on the way: search or click"
                }
                point={point}
                active={activeIndex === i}
                onFocus={() => onActiveIndexChange(i)}
                onChange={(p) => {
                  const next = points.map((q, j) => (j === i ? p : q));
                  setPoints(next);
                  onActiveIndexChange(nextField(next));
                }}
              />
              {i > 0 && i < last && (
                <button
                  type="button"
                  className="icon-button"
                  aria-label={`Remove stop ${i}`}
                  onClick={() => {
                    setPoints(points.filter((_, j) => j !== i));
                    onActiveIndexChange(0);
                  }}
                >
                  <X size={18} />
                </button>
              )}
            </li>
          );
        })}
      </ol>
      <div className="trip-row-actions">
        {last < MAX_DESTINATIONS && (
          <button
            type="button"
            className="trip-add"
            onClick={() => {
              // Stops go on the way, before the destination.
              setPoints([...points.slice(0, last), null, points[last]]);
              onActiveIndexChange(last);
            }}
          >
            <Plus size={16} aria-hidden="true" /> Add a stop on the way
          </button>
        )}
        <button
          type="button"
          className="trip-add trip-reverse"
          onClick={() => reorder([...points].reverse())}
        >
          <ArrowUpDown size={16} aria-hidden="true" /> Reverse
        </button>
      </div>

      <div className="trip-actions">
        <div className="chips" role="group" aria-label="Rank options by">
          {SORTS.map((option) => (
            <button
              key={option.value}
              type="button"
              className="chip"
              aria-pressed={sort === option.value}
              onClick={() => setSort(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <label className="trip-time">
          <span>Leave at</span>
          <input
            type="time"
            value={departTime}
            required
            onChange={(event) => event.target.value && onDepartTimeChange(event.target.value)}
          />
        </label>
      </div>

      {status === "loading" && !plan && (
        <p className="trip-status" role="status">
          Finding routes…
        </p>
      )}
      {status === "error" && (
        <p className="trip-error" role="alert">
          Couldn't plan this trip. Is the API running, with routes imported?
        </p>
      )}

      {plan?.segments.map((segment, si) => (
        <section
          key={si}
          className="trip-segment"
          aria-label={`Options ${segment.origin.name} to ${segment.destination.name}`}
          aria-busy={status === "loading"}
        >
          {plan.segments.length > 1 && (
            <h3>
              {pointLetter(si)} → {pointLetter(si + 1)}: {segment.destination.name}
            </h3>
          )}
          {segment.options.length === 0 ? (
            <p className="trip-empty">
              No route found. Try a point closer to a main road, or another time.
            </p>
          ) : (
            <ol className="trip-options">
              {segment.options.map((option, oi) => (
                <OptionCard
                  key={oi}
                  option={option}
                  chosen={chosen[si] === oi}
                  onChoose={() => onChosenChange(chosen.map((c, j) => (j === si ? oi : c)))}
                />
              ))}
            </ol>
          )}
        </section>
      ))}
      {plan?.notes.map((note) => (
        <p key={note} className="detail-footnote">
          {note}
        </p>
      ))}
    </section>
  );
}

function TripField({
  letter,
  label,
  placeholder,
  point,
  active,
  onFocus,
  onChange,
}: {
  letter: string;
  label: string;
  placeholder: string;
  point: TripPoint | null;
  active: boolean;
  onFocus: () => void;
  onChange: (point: TripPoint) => void;
}) {
  const [query, setQuery] = useState(point?.name ?? "");
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const listId = useId();
  const locate = useRef<(() => void) | null>(null);
  // Nothing to search while the field just shows the chosen point's name.
  const { results, searchingAddresses } = usePlaceSearch(query === point?.name ? "" : query, {
    stops: true,
  });

  // Show the name when the point is set from outside, by a map click.
  useEffect(() => setQuery(point?.name ?? ""), [point]);
  useEffect(() => setHighlight(0), [results]);

  const choose = ({ name, point, context }: PlaceResult) => {
    setOpen(false);
    onChange({ name, point, context });
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setHighlight((i) => Math.min(i + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && open && browsing) {
      event.preventDefault();
      locate.current?.();
    } else if (event.key === "Enter" && open && results[highlight]) {
      event.preventDefault();
      choose(results[highlight]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  };

  // Not typing (empty, or showing the chosen place): offer the current location instead.
  const browsing = query.trim() === "" || query === point?.name;
  const showList = open && (browsing ? canLocate() : query.trim().length >= 2);

  return (
    <div className="trip-field" data-active={active}>
      <span className="trip-letter" data-origin={letter === "A"} aria-hidden="true">
        {letter}
      </span>
      <input
        type="search"
        role="combobox"
        aria-label={label}
        aria-expanded={showList}
        aria-controls={listId}
        placeholder={placeholder}
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => {
          onFocus();
          setOpen(true);
        }}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {showList && (
        <ul className="search-results" id={listId} role="listbox">
          {browsing && (
            <CurrentLocationOption
              id={`${listId}-here`}
              highlighted
              onHighlight={() => {}}
              onLocated={choose}
              locateRef={locate}
            />
          )}
          {!browsing && results.length === 0 && !searchingAddresses && (
            <li className="search-empty">No places found</li>
          )}
          {!browsing &&
            results.map((result, index) => (
            <li
              key={result.id}
              role="option"
              aria-selected={index === highlight}
              className="search-result"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(result)}
              onMouseEnter={() => setHighlight(index)}
            >
              <PlaceIcon kind={result.kind} />
              <span className="search-result-text">
                <span className="search-result-name">{result.name}</span>
                {result.context && (
                  <span className="search-result-context">{result.context}</span>
                )}
              </span>
            </li>
          ))}
          {!browsing && searchingAddresses && (
            <li className="search-empty">Searching addresses…</li>
          )}
          {!browsing && <SearchCredit results={results} />}
        </ul>
      )}
    </div>
  );
}

function OptionCard({
  option,
  chosen,
  onChoose,
}: {
  option: TripOption;
  chosen: boolean;
  onChoose: () => void;
}) {
  const rides = option.legs.filter((leg) => leg.route);
  return (
    <li className="trip-option" data-chosen={chosen}>
      <button type="button" className="trip-option-head" aria-expanded={chosen} onClick={onChoose}>
        <span className="trip-option-top">
          <span className="trip-rides">
            {rides.length === 0 && (
              <span className="route-chip route-chip-walk">
                <Footprints size={14} aria-hidden="true" /> Walk
              </span>
            )}
            {rides.map((leg, i) => (
              <span key={i} className="route-chip" style={{ background: leg.route!.color }}>
                {modeName(leg.mode)} {leg.route!.code || leg.route!.name}
              </span>
            ))}
          </span>
          <strong className="trip-duration">{formatDuration(option.duration_min)}</strong>
        </span>
        <span className="trip-stats">
          {formatFare(option.fare_idr)} ·{" "}
          {option.transfers === 0
            ? "direct"
            : `${option.transfers} transfer${option.transfers > 1 ? "s" : ""}`}{" "}
          · {formatDistance(option.walk_m)} walk · {formatClock(option.depart_at)}–
          {formatClock(option.arrive_at)}
        </span>
        <span className="trip-badges">
          {option.labels.map((label) => (
            <span key={label} className="tag tag-brand">
              {OPTION_LABELS[label]}
            </span>
          ))}
          <span
            className="bar trip-availability"
            role="meter"
            aria-label="Availability"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(option.availability * 100)}
            title="How often the services run, and whether they run at that time"
          >
            <span style={{ width: `${Math.round(option.availability * 100)}%` }} />
          </span>
        </span>
      </button>
      {chosen && (
        <ol className="trip-legs">
          {option.legs.map((leg, i) => (
            <LegStep key={i} leg={leg} />
          ))}
        </ol>
      )}
    </li>
  );
}

function LegStep({ leg }: { leg: TripLeg }) {
  if (!leg.route) {
    return (
      <li className="trip-leg trip-leg-walk">
        <span>
          Walk {formatDistance(leg.distance_m)} to <strong>{leg.end.name}</strong>
        </span>
        <small>{formatDuration(leg.duration_min)}</small>
      </li>
    );
  }
  const route = leg.route;
  return (
    <li className="trip-leg" style={{ borderColor: route.color }}>
      <span>
        <span className="route-chip" style={{ background: route.color }}>
          {modeName(leg.mode)} {route.code}
        </span>{" "}
        {route.name}
      </span>
      <span>
        Board at <strong>{leg.start.name}</strong>
        {route.boarding === "hail" ? " (wave it down along the street)" : ""}, wait about{" "}
        {formatDuration(leg.wait_min)}
      </span>
      <span>
        {/* Hail-anywhere routes have evenly spaced virtual stops, so a stop count means little. */}
        {route.boarding === "stops"
          ? `Ride ${leg.stop_count} stop${leg.stop_count === 1 ? "" : "s"}`
          : `Ride ${formatDistance(leg.distance_m)}`}
        , get off at <strong>{leg.end.name}</strong>
      </span>
      <small>
        {formatDuration(leg.duration_min)} · {formatFare(leg.fare_idr)}
        {route.is_placeholder ? " (estimate)" : ""}
      </small>
      {!leg.available && <small className="trip-error">Not running at this time</small>}
    </li>
  );
}
