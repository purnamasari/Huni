import { useEffect, useMemo, useState } from "react";
import { fetchAreas, fetchCommuteTimes, reverseGeocode } from "./api/client";
import type {
  AreaCollection,
  AreaLevel,
  AreaProperties,
  CommuteTime,
  CriterionKey,
  PlaceResult,
  TripPlan,
  TripPoint,
} from "./api/types";
import { type AreaCommute, AreaDetail, OutsideDetail } from "./components/DetailPanel";
import { Header } from "./components/Header";
import { InfoPage } from "./components/InfoPage";
import { IntroPanel } from "./components/IntroPanel";
import { Legend } from "./components/Legend";
import { type Focus, type MapAreas, type MapLevels, MapView, type Trip } from "./components/MapView";
import { type Mode, ModeSwitch } from "./components/ModeSwitch";
import { nextField, TripPanel } from "./components/TripPanel";
import { CRITERIA } from "./criteria";
import { commuteBadge, commuteScore, todayAt } from "./lib/commute";
import { formatPoint } from "./lib/coordinates";
import { overallScore } from "./lib/scoring";
import { load, save } from "./lib/storage";
import { isInfoPage, useHashPage } from "./useHashPage";

const isArea = (place: PlaceResult) => place.kind === "kecamatan" || place.kind === "kelurahan";

// Remembered per browser, so the commute survives a reload.
const COMMUTE_TO_KEY = "huni.commuteTo";
const COMMUTE_TIME_KEY = "huni.commuteTime";
const DEFAULT_COMMUTE_TIME = "07:30";

export function App() {
  const page = useHashPage();
  const [mode, setMode] = useState<Mode>(page === "commute" ? "commute" : "explore");
  const [areas, setAreas] = useState<Record<AreaLevel, AreaCollection | null>>({
    kecamatan: null,
    kelurahan: null,
  });
  const [loadError, setLoadError] = useState(false);
  const [selected, setSelected] = useState<ReadonlySet<CriterionKey>>(
    () => new Set(CRITERIA.map((c) => c.key)),
  );
  const [showFlood, setShowFlood] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [place, setPlace] = useState<PlaceResult | null>(null);
  const [focus, setFocus] = useState<Focus | null>(null);

  // Commute: where you start, any stops, then where you go most days (the last point).
  const [tripPoints, setTripPoints] = useState<(TripPoint | null)[]>(() => [
    null,
    load<TripPoint>(COMMUTE_TO_KEY),
  ]);
  const [tripField, setTripField] = useState(() => nextField(tripPoints));
  const [departTime, setDepartTime] = useState(
    () => load<string>(COMMUTE_TIME_KEY) ?? DEFAULT_COMMUTE_TIME,
  );
  const [tripPlan, setTripPlan] = useState<TripPlan | null>(null);
  const [tripChosen, setTripChosen] = useState<number[]>([]);
  const [commuteTimes, setCommuteTimes] = useState<Map<string, CommuteTime> | null>(null);
  const [commuteError, setCommuteError] = useState(false);

  const commuteTo = tripPoints[tripPoints.length - 1];
  const commuteToWhere = commuteTo?.point.join(",");

  // Info pages sit over the map, so they keep whichever mode was showing.
  useEffect(() => {
    if (page === "map") setMode("explore");
    if (page === "commute") setMode("commute");
  }, [page]);

  useEffect(() => {
    const controller = new AbortController();
    for (const level of ["kecamatan", "kelurahan"] as const) {
      fetchAreas(level, controller.signal)
        .then((collection) => setAreas((current) => ({ ...current, [level]: collection })))
        .catch(() => {
          if (!controller.signal.aborted) setLoadError(true);
        });
    }
    return () => controller.abort();
  }, []);

  useEffect(() => save(COMMUTE_TO_KEY, commuteTo), [commuteTo]);
  useEffect(() => save(COMMUTE_TIME_KEY, departTime), [departTime]);

  // Travel time from every kecamatan and kelurahan to where you go most days.
  useEffect(() => {
    setCommuteTimes(null);
    setCommuteError(false);
    const origins = [areas.kecamatan, areas.kelurahan].flatMap((collection) =>
      (collection?.features ?? []).map(({ properties: { id, labelPoint } }) => ({
        id,
        point: labelPoint,
      })),
    );
    if (!commuteTo || origins.length === 0) return;
    const controller = new AbortController();
    fetchCommuteTimes(commuteTo, origins, todayAt(departTime), controller.signal)
      .then((times) => setCommuteTimes(new Map(times.map((time) => [time.id, time]))))
      .catch(() => {
        if (!controller.signal.aborted) setCommuteError(true);
      });
    return () => controller.abort();
    // Keyed on the coordinates: renaming the destination doesn't change any travel time.
  }, [areas, commuteToWhere, departTime]);

  /** The area's scores, with Work commute measured to your own destination once it's set. */
  const scoresOf = (properties: AreaProperties) => {
    const time = commuteTimes?.get(properties.id);
    if (!time) return properties.scores;
    return { ...properties.scores, commute: commuteScore(time.minutes) ?? 0 };
  };

  const mapLevels = useMemo<MapLevels>(() => {
    const toMap = (collection: AreaCollection | null): MapAreas | null =>
      collection && {
        type: "FeatureCollection",
        features: collection.features.map(({ geometry, properties }) => {
          const base = {
            id: properties.id,
            name: properties.name,
            floodRisk: properties.floodRisk,
            labelPoint: properties.labelPoint,
          };
          if (mode === "explore") {
            return {
              type: "Feature",
              geometry,
              properties: { ...base, score: overallScore(scoresOf(properties), selected) },
            };
          }
          const minutes = commuteTimes?.get(properties.id)?.minutes;
          return {
            type: "Feature",
            geometry,
            properties: {
              ...base,
              score: commuteScore(minutes),
              badge: commuteBadge(minutes),
              badgeLabel:
                minutes == null ? "no travel time" : `${Math.round(minutes)} minutes away`,
            },
          };
        }),
      };
    return { kecamatan: toMap(areas.kecamatan), kelurahan: toMap(areas.kelurahan) };
    // scoresOf only reads commuteTimes, which is listed.
  }, [areas, selected, mode, commuteTimes]);

  const ranked = useMemo(
    () =>
      (mapLevels.kecamatan?.features ?? [])
        .map(({ properties: { id, name, score } }) => ({ id, name, score }))
        .sort((a, b) => (b.score ?? -1) - (a.score ?? -1) || a.name.localeCompare(b.name)),
    [mapLevels],
  );

  const selectedArea = [areas.kecamatan, areas.kelurahan]
    .flatMap((collection) => collection?.features ?? [])
    .find((f) => f.properties.id === selectedId)?.properties;

  const selectArea = (id: string | null, { fly = false } = {}) => {
    setSelectedId(id);
    if (id === null || id !== place?.areaId) setPlace(null);
    if (id && fly) setFocus({ key: Date.now(), kind: "area", id });
  };

  /** Put a place into the commute field the user is on, then move to the next one. */
  const setTripPoint = (point: TripPoint) => {
    const next = tripPoints.map((p, i) => (i === tripField ? point : p));
    setTripPoints(next);
    setTripPlan(null);
    setTripField(nextField(next));
  };

  const selectPlace = (result: PlaceResult) => {
    if (mode === "commute") {
      window.location.hash = "#/commute";
      setTripPoint({ name: result.name, point: result.point, context: result.context });
      setFocus({ key: Date.now(), kind: "point", point: result.point });
      return;
    }
    window.location.hash = "#/";
    setPlace(result);
    setSelectedId(result.areaId);
    setFocus(
      (result.kind === "kecamatan" || result.kind === "kelurahan") && result.areaId
        ? { key: Date.now(), kind: "area", id: result.areaId }
        : { key: Date.now(), kind: "point", point: result.point },
    );
  };

  const toggleCriterion = (key: CriterionKey) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const closeDetail = () => {
    setSelectedId(null);
    setPlace(null);
  };

  /** From an area's detail panel: plan the commute from that area. */
  const commuteFrom = (area: AreaProperties) => {
    const next = [{ name: area.name, point: area.labelPoint }, ...tripPoints.slice(1)];
    setTripPoints(next);
    setTripPlan(null);
    setTripField(nextField(next));
    closeDetail();
    window.location.hash = "#/commute";
  };

  /** A map click: the exact point, named after its area now and its address once known. */
  const pickTripPoint = (point: [number, number], areaName?: string) => {
    const picked: TripPoint = { name: areaName ?? formatPoint(point), point };
    setTripPoint(picked);
    reverseGeocode(point).then((address) => {
      if (!address) return;
      const named = { ...picked, name: address.name, context: address.context };
      // Only if the pin is still there; the user may have clicked again meanwhile.
      setTripPoints((current) => current.map((p) => (p === picked ? named : p)));
    });
  };

  const trip = useMemo<Trip>(
    () => ({
      points: tripPoints.map((p) => p?.point ?? null),
      legs:
        tripPlan?.segments.flatMap((segment, i) => segment.options[tripChosen[i] ?? 0]?.legs ?? []) ??
        [],
    }),
    [tripPoints, tripPlan, tripChosen],
  );

  const areaCommute = (area: AreaProperties): AreaCommute | null => {
    if (!commuteTo) return null;
    const time = commuteTimes?.get(area.id);
    return {
      destination: commuteTo.name,
      minutes: time?.minutes ?? null,
      transfers: time?.transfers ?? null,
      walkOnly: time?.walk_only ?? false,
      departAt: departTime,
    };
  };

  const commuting = mode === "commute";
  const panelOpen = !commuting && Boolean(selectedArea || place);

  return (
    <div className="app">
      <MapView
        levels={mapLevels}
        selectedId={commuting ? null : selectedId}
        // On narrow screens the detail sheet covers the bottom half, so bring the area into view.
        onSelectArea={(id) => selectArea(id, { fly: window.innerWidth < 900 })}
        showFlood={showFlood && !commuting}
        focus={focus}
        placePoint={!commuting && place && !isArea(place) ? place.point : null}
        panelOpen={panelOpen}
        trip={commuting ? trip : null}
        onPickPoint={commuting ? pickTripPoint : null}
      />
      <Header page={page} onSelectPlace={selectPlace} />
      <div className="left-column">
        <ModeSwitch mode={mode} />
        {commuting ? (
          <TripPanel
            points={tripPoints}
            onPointsChange={setTripPoints}
            activeIndex={tripField}
            onActiveIndexChange={setTripField}
            departTime={departTime}
            onDepartTimeChange={setDepartTime}
            plan={tripPlan}
            onPlanChange={setTripPlan}
            chosen={tripChosen}
            onChosenChange={setTripChosen}
          />
        ) : (
          <IntroPanel
            selected={selected}
            onToggle={toggleCriterion}
            showFlood={showFlood}
            onToggleFlood={() => setShowFlood((on) => !on)}
            ranked={ranked}
            onSelectArea={(id) => selectArea(id, { fly: true })}
          />
        )}
        {loadError && (
          <p className="card load-error" role="alert">
            Couldn't load neighbourhood scores. Is the API running?
          </p>
        )}
      </div>
      <Legend
        showFlood={showFlood}
        commute={
          commuting
            ? { destination: commuteTo?.name ?? null, departAt: departTime, failed: commuteError }
            : null
        }
      />
      {!commuting &&
        (selectedArea ? (
          <AreaDetail
            area={{ ...selectedArea, scores: scoresOf(selectedArea) }}
            place={place}
            selected={selected}
            onClose={closeDetail}
            commute={areaCommute(selectedArea)}
            onCommute={() => commuteFrom(selectedArea)}
          />
        ) : (
          place && !place.insideKota && <OutsideDetail place={place} onClose={closeDetail} />
        ))}
      {isInfoPage(page) && <InfoPage page={page} />}
    </div>
  );
}
