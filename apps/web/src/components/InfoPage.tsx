import { X } from "lucide-react";
import type { Page } from "../useHashPage";
import { CRITERIA, FLOOD } from "../criteria";

const TITLES: Record<Exclude<Page, "map">, string> = {
  about: "About Huni",
  methodology: "Methodology",
  data: "Data sources",
};

export function InfoPage({ page }: { page: Exclude<Page, "map"> }) {
  return (
    <div className="info-backdrop">
      <article className="info card" aria-labelledby="info-title">
        <a className="icon-button detail-close" href="#/" aria-label="Back to the map">
          <X size={20} />
        </a>
        <h2 id="info-title">{TITLES[page]}</h2>
        {page === "about" && <About />}
        {page === "methodology" && <Methodology />}
        {page === "data" && <DataSources />}
      </article>
    </div>
  );
}

function About() {
  return (
    <>
      <p>
        Huni is a neighbourhood-fit explorer for Kota Bandung and a portfolio project for learning
        geospatial backend work with Django, GeoDjango and PostGIS.
      </p>
      <p>
        <strong>Everything on the map right now is demo data.</strong> The boundaries are rough
        shapes around each kecamatan, not official ones, and the scores are generated. They will be
        replaced as each backend slice lands.
      </p>
    </>
  );
}

function Methodology() {
  return (
    <ul>
      <li>Scores are computed on a hexagon grid covering Kota Bandung.</li>
      <li>
        Zoomed out, the map shows kecamatan averages of those hexagons. Kecamatan and kelurahan are
        different levels, and Huni never mixes them on one map.
      </li>
      <li>Every criterion is normalised to 0–100, where higher is always better.</li>
      <li>The overall score is the average of the criteria you pick.</li>
      <li>
        Flood risk is a warning flag shown alongside the score, never averaged into it.
      </li>
      <li>
        Only hexagons inside the Kota boundary are scored. Distances are measured to features up to
        about 2 km beyond it, so a park just across the border still counts.
      </li>
    </ul>
  );
}

function DataSources() {
  return (
    <>
      <dl className="sources">
        {[...CRITERIA, { key: "flood", ...FLOOD }].map(({ key, label, icon: Icon, sources }) => (
          <div key={key}>
            <Icon size={18} aria-hidden="true" />
            <dt>{label}</dt>
            <dd className="sources-origin">{sources}</dd>
          </div>
        ))}
      </dl>
      <p className="muted">
        These are the planned sources. Huni only uses data it may store and show on a MapLibre
        map, which rules out Google Places. Basemap © OpenFreeMap, © OpenMapTiles, data ©
        OpenStreetMap contributors.
      </p>
    </>
  );
}
