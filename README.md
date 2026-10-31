# Huni

A neighbourhood-fit explorer for Kota Bandung. It's a portfolio project for learning geospatial backend work.

This repo is a scaffold. The spatial work (models, imports, CRS handling, spatial queries, scoring, hexagon grid, refresh command) gets built slice by slice, and each slice gets a write-up in [`docs/notes/`](docs/notes/_template.md).

## Layout

```
apps/api/         Django + GeoDjango + Django Ninja (PostGIS), uv, pytest, ruff
apps/web/         React + TypeScript + Vite + MapLibre GL JS, pnpm, Vitest
data/             Source data; data/raw/ is git-ignored (see data/README.md)
docs/decisions/   Architecture decision records
docs/notes/       Per-slice write-ups (copy _template.md)
```

## Run with Docker Compose

```sh
cp .env.example .env
docker compose up --build
```

- Web: http://localhost:5173. The neighbourhood map (demo data for now), with an API health indicator in the header.
- API: http://localhost:8000/api/health. OpenAPI docs at http://localhost:8000/api/docs.
- PostGIS: `localhost:5432` (credentials in `.env`)

The `api` container runs migrations on start. Both app folders are bind-mounted, so code reloads as you edit.

## Run locally (without Docker for the apps)

You need the GDAL/GEOS/PROJ native libraries (`apt install gdal-bin` or `brew install gdal`), uv, Node 22+ and pnpm. Start just the database with `docker compose up -d db`.

```sh
# API
cd apps/api
uv sync
uv run --env-file ../../.env python manage.py migrate
uv run --env-file ../../.env python manage.py runserver

# Web (reads ../../.env itself; proxies /api to API_PROXY_TARGET)
cd apps/web
pnpm install
pnpm dev
```

## Transit routes and trip planning

Put the Transport for Bandung route exports in `data/raw/` (see [`data/README.md`](data/README.md)), then:

```sh
docker compose run --rm api python manage.py import_routes
# or: uv run --env-file ../../.env python manage.py import_routes --shp path.zip --kml path.zip
```

The import rebuilds each route in travel order, places boarding points and prints a QA report
(also at `/api/transit/imports/latest`). Fares, speeds, headways and hours are placeholders per
mode in [`apps/api/transit/service_profiles.json`](apps/api/transit/service_profiles.json);
edit it and re-run the import to change them.

- `POST /api/transit/plan`: ranked trip options from an origin through one or more destinations
- `GET /api/transit/routes`: every route as GeoJSON; `/routes/{id}` for stops, service and QA
- `POST /api/transit/commute`: travel time from many origins (e.g. every neighbourhood) to one destination, in one search
- `GET /api/transit/places?q=`: search named stops and terminals

How it works and what can go wrong: [`docs/notes/0001-transit-routes-and-trip-planning.md`](docs/notes/0001-transit-routes-and-trip-planning.md).

## Search, current location and trip order

The search box (and the Commute fields) take place names, addresses, exact points and your location:

- **Coordinates** pasted as `-6.9147, 107.6098`, a Google Maps link (`…/@-6.9147,107.6098,17z`) or `6°54'53"S 107°36'35"E` go straight to that point, with no lookup.
- **Places and addresses** come from `GET /api/geocode?q=…`, which combines two providers, because neither covers Bandung alone:
  - [Mapbox Search Box](https://docs.mapbox.com/api/search/search-box/) (set `MAPBOX_ACCESS_TOKEN`): shops, markets, campuses and offices, with street addresses. It has no streets or house addresses for Indonesia.
  - [Photon](https://photon.komoot.io) (OpenStreetMap, no key): streets and areas, and street names for dropped pins (`GET /api/geocode/reverse`).

  The browser asks each with `&source=mapbox|photon` and shows results as they arrive. Mapbox results are never cached (its terms allow temporary use only); Photon's are cached for a day. Both are credited under the results.
- **Your current location**: focus an empty search field and pick "Your current location". The browser asks for permission; the position stays in the browser apart from the trip requests.

In Commute, drag a row by its handle (or focus the handle and use the arrow keys) to reorder From, stops and destination; **Reverse** flips the whole trip.

## Checks (same as CI)

```sh
# apps/api (needs the db running)
uv run ruff check . && uv run ruff format --check .
uv run --env-file ../../.env pytest

# apps/web
pnpm typecheck && pnpm test && pnpm build
```

## Frontend and mock data

The web app follows the design mockup: a choropleth of scores, criteria toggles, search, a detail panel and a flood-risk overlay. It shows kecamatan when zoomed out and kelurahan when zoomed in, never both at once. Until the backend serves real data it runs on **demo data** (`apps/web/src/mocks/`): the boundaries are real (OpenStreetMap, see [`boundaries.README.md`](apps/web/src/mocks/boundaries.README.md)), but the scores are generated.

The responses the web app expects are typed in [`apps/web/src/api/types.ts`](apps/web/src/api/types.ts):

- `GET /api/areas?level=kecamatan|kelurahan`: GeoJSON FeatureCollection (WGS84) with `id`, `name`, `level`, `parent`, `labelPoint`, per-criterion `scores` (0–100, higher is better) and `floodRisk`.
- `GET /api/places?q=…`: search results, each with `insideKota` and the `areaId` it falls in.

The **Commute** mode (`#/commute`, switched at the top of the left column) and the "Work commute" score always call the real `/api/transit/*` endpoints, so import the routes first (see above). Set `VITE_USE_MOCK_DATA=false` to switch to the API. The overall score is the mean of the criteria the user picks, computed in the browser so toggling is instant.

## Configuration

Everything comes from the root `.env` (see [`.env.example`](.env.example)):

- `POSTGRES_*`: database connection. The PostGIS container uses the same values.
- `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`
- `VITE_BASEMAP_STYLE_URL`: any MapLibre style JSON. Defaults to OpenFreeMap "positron".
- `VITE_USE_MOCK_DATA`: `true` (default) serves demo data; `false` calls the API.
- `API_PROXY_TARGET`: where the Vite dev server sends `/api` requests.
- `GEOCODER_URL`: the Photon server for street search. Defaults to the public `https://photon.komoot.io`.
- `MAPBOX_ACCESS_TOKEN`: optional; adds Mapbox place search. Used by the API only, never sent to the browser.
