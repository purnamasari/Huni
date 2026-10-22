import { useEffect, useMemo, useState } from "react";
import { fetchAreas } from "./api/client";
import type { AreaCollection, CriterionKey, PlaceResult } from "./api/types";
import { AreaDetail, OutsideDetail } from "./components/DetailPanel";
import { Header } from "./components/Header";
import { InfoPage } from "./components/InfoPage";
import { IntroPanel } from "./components/IntroPanel";
import { Legend } from "./components/Legend";
import { type Focus, type MapAreas, MapView } from "./components/MapView";
import { CRITERIA } from "./criteria";
import { overallScore } from "./lib/scoring";
import { useHashPage } from "./useHashPage";

export function App() {
  const page = useHashPage();
  const [areas, setAreas] = useState<AreaCollection | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selected, setSelected] = useState<ReadonlySet<CriterionKey>>(
    () => new Set(CRITERIA.map((c) => c.key)),
  );
  const [showFlood, setShowFlood] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [place, setPlace] = useState<PlaceResult | null>(null);
  const [focus, setFocus] = useState<Focus | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchAreas(controller.signal)
      .then(setAreas)
      .catch(() => {
        if (!controller.signal.aborted) setLoadError(true);
      });
    return () => controller.abort();
  }, []);

  const mapAreas = useMemo<MapAreas | null>(
    () =>
      areas && {
        type: "FeatureCollection",
        features: areas.features.map(({ geometry, properties }) => ({
          type: "Feature",
          geometry,
          properties: {
            id: properties.id,
            name: properties.name,
            score: overallScore(properties.scores, selected),
            floodRisk: properties.floodRisk,
            labelPoint: properties.labelPoint,
          },
        })),
      },
    [areas, selected],
  );

  const ranked = useMemo(
    () =>
      (mapAreas?.features ?? [])
        .map(({ properties: { id, name, score } }) => ({ id, name, score }))
        .sort((a, b) => (b.score ?? -1) - (a.score ?? -1) || a.name.localeCompare(b.name)),
    [mapAreas],
  );

  const selectedArea = areas?.features.find((f) => f.properties.id === selectedId)?.properties;

  const selectArea = (id: string | null, { fly = false } = {}) => {
    setSelectedId(id);
    if (id === null || id !== place?.areaId) setPlace(null);
    if (id && fly) setFocus({ key: Date.now(), kind: "area", id });
  };

  const selectPlace = (result: PlaceResult) => {
    window.location.hash = "#/";
    setPlace(result);
    setSelectedId(result.areaId);
    setFocus(
      result.kind === "kecamatan" && result.areaId
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

  const panelOpen = Boolean(selectedArea || place);

  return (
    <div className="app">
      <MapView
        areas={mapAreas}
        selectedId={selectedId}
        // On narrow screens the detail sheet covers the bottom half, so bring the area into view.
        onSelectArea={(id) => selectArea(id, { fly: window.innerWidth < 900 })}
        showFlood={showFlood}
        focus={focus}
        placePoint={place && place.kind !== "kecamatan" ? place.point : null}
        panelOpen={panelOpen}
      />
      <Header page={page} onSelectPlace={selectPlace} />
      <div className="left-column">
        <IntroPanel
          selected={selected}
          onToggle={toggleCriterion}
          showFlood={showFlood}
          onToggleFlood={() => setShowFlood((on) => !on)}
          ranked={ranked}
          onSelectArea={(id) => selectArea(id, { fly: true })}
        />
        {loadError && (
          <p className="card load-error" role="alert">
            Couldn't load neighbourhood scores. Is the API running?
          </p>
        )}
      </div>
      <Legend showFlood={showFlood} />
      {selectedArea ? (
        <AreaDetail area={selectedArea} place={place} selected={selected} onClose={closeDetail} />
      ) : (
        place && !place.insideKota && <OutsideDetail place={place} onClose={closeDetail} />
      )}
      {page !== "map" && <InfoPage page={page} />}
    </div>
  );
}
