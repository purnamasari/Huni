# Slice 01: Transit routes ETL and A* trip planning

Date: 2026-10-31

## What I built

**ETL** (`apps/api/transit/etl/`, run with `manage.py import_routes`):

- **Extract** reads the Transport for Bandung shapefile and KML exports, as folders or zips.
  Both have one file per route direction. Each file is a set of OSM ways in no particular
  order or direction. The shapefile rows carry OSM tags (`oneway`, `highway`, street
  `name`). The KML adds Point placemarks: terminals, and for bus and rail lines their
  stops and stations. Routes are merged by route name, so 375 + 385 files give 395
  distinct directional routes.
- **Transform** (`transform.py`) rebuilds each route as one directed line:
  1. Project to UTM 48S (EPSG:32748) so lengths are in metres.
  2. Build a graph from the way vertices. Ways join where they share a vertex, and
     `oneway=yes/-1` gives directed edges. Disconnected parts are bridged with straight
     edges at their closest vertices.
  3. Pick the origin and destination. The `A → B` in the route name is matched against the
     KML point names (the route's own points first, then every KML point in the delivery),
     and the match is snapped to the graph's dead ends. Point order in the KML is **not**
     reliable, so it is never used.
  4. Take the **longest trail** from origin to destination: the path that uses each piece at
     most once and covers the most of the delivered pieces. This is a branch-and-bound
     search over junction-to-junction chains. A shortest path would cut off loops that the
     vehicles really drive (around markets, through one-way systems). Loop routes
     (`searah jarum jam`, single-name shuttles) take the better of a closed circuit or an
     out-and-back "lasso".
  5. Place boarding points. Fixed-stop services with a stop list in the KML (Koridor,
     Feeder, Commuter Line) use those stops, ordered by distance along the line.
     Hail-anywhere services (angkot, Elf) get virtual stops every 250–400 m (placeholder
     spacing), named after the nearest street.
- **Load** replaces the `Route`, `RouteStop` and `RouteSegment` (raw ways, for
  traceability) tables in one transaction. It also writes an `ImportRun` with the QA
  report.

**Service data is placeholder**: fares, speed, headway and service hours come per mode
from `transit/service_profiles.json` (`"routes"` there overrides single routes).
`Route.service_is_placeholder` and the API's `uses_placeholder` say so.

**Routing** (`apps/api/transit/routing/`):

- `network.py` builds an in-memory graph from the tables. For every stop there is a
  "standing at the stop" node and an "on the vehicle" node. The edges are board (wait half
  the headway, pay the base fare), ride, alight, and walking transfers of up to 250 m to
  the nearest stop of each other route. It is cached per process and rebuilt when a newer
  `ImportRun` exists. On the full data: 21k stops, 280k edges, about 1 s to build.
- `astar.py` is a generic A*. The heuristic is the straight-line distance to the
  destination divided by the fastest speed in the network (commuter rail), multiplied by
  the smallest per-second weight. It never overestimates, so the paths are optimal for
  each cost function.
- `planner.py` runs A* with three cost functions (fastest, cheapest, reliable). It then
  runs two more "fastest" searches that penalise routes already found, to get real
  alternatives, plus a walk-only option under 2 km. It then scores the distinct options:
  - time: fastest duration ÷ this duration
  - cost: (cheapest + 2000) ÷ (fare + 2000)
  - availability: product over legs of 1 / (1 + headway/30), or 0 if the route isn't
    running at that time

  Options are ranked by a weighted mix (`sort=balanced|time|cost|availability`) and
  labelled Fastest / Cheapest / Most available. A query takes 0.1–0.3 s.

**API**: `POST /api/transit/plan` (origin, 1–5 destinations visited in order, `depart_at`,
`sort`), `GET /api/transit/routes` (GeoJSON), `/routes/{id}`, `/places?q=`,
`/imports/latest`.

**Commute times** (`travel_times` in `planner.py`, `POST /api/transit/commute`): the travel
time from many origins (every kecamatan and kelurahan) to one destination, from a single
search. One A* per origin would repeat nearly the same work every time. Instead, Dijkstra
runs once, backwards from the destination over reversed edges (`Network.reverse_adjacency`),
and each origin then adds its walk to nearby stops. It takes about 0.16 s for 180 origins.
A test checks that it agrees with a full A* plan.

**Web**: commute is one of two map modes, switched at the top of the left column
(**Neighbourhoods | Commute**, with its own URL `#/commute`):

- In **Commute**, you set where you go most days (remembered in this browser). The map then
  shows every area's travel time to it at the chosen time (07:30 by default), on the same
  colour ramp as the scores. Clicking an area, or searching, plans the trip from there. Plans
  run automatically when any input changes, and the chosen option is drawn over the map
  (`components/TripPanel.tsx`, `components/MapView.tsx`).
- In **Neighbourhoods**, once that destination is set, the "Work commute" criterion uses the
  real travel time (`110 − minutes`, clamped to 0–100, so 20 min scores 90). The area detail
  panel shows the commute with a link to the route.

Trip calls always go to the API, even when `VITE_USE_MOCK_DATA` is on, because the routes are
real data.

## What could make this spatially wrong

- **Direction of travel.** Nothing in the data says which end is the start. A wrong name
  match gives a route that runs backwards, and the router would ride it the wrong way.
- **Shortcuts and detours.** Rebuilding the order from unordered ways can skip parts of the
  route (shortest-path behaviour) or add parts it doesn't drive (if the delivery contains
  extra ways).
- **Gaps.** Bridged gaps are straight lines that may cross blocks.
- **Measuring in degrees.** Distances, stop spacing and the 250 m transfer radius are
  computed in EPSG:32748 metres, not degrees. Leg geometry is cut from the EPSG:4326 line
  using fractions of the metric length. That is slightly off but invisible at this scale.
- **Stops.** Hail-anywhere virtual stops are an approximation. Bus routes without a KML
  stop list (most Koridor 1/5/6 directions, DAMRI "Jalur") use placeholder stops every
  500 m. A loop that passes the same stop twice snaps it to the first pass.
- **Service data.** Every fare, speed, headway and opening hour is a placeholder per mode,
  so durations and rankings are indicative only.
- **Data age and licence.** The export is dated 2026-10-26. Routes change, and the licence
  is not stated in the files (the geometry is OSM-derived).

## What I checked

- **Direction.** Of 188 A→B / B→A route pairs, 187 start where their partner ends. The odd
  one, `951 Cimahi ↔ Permata`, has only one name matched and is also in the QA list for
  relaxed oneway. Still open.
- **Coverage.** The mean share of delivered way length used by the ordered line is 0.99.
  Only `Summarecon: Shuttle Cluster Kawasan` is below 0.85 (0.64): it loops through
  housing clusters. Switching from shortest path to longest trail took the count of
  routes below 0.85 from 30 to 1.
- **Stations.** The Commuter Line Bandung Raya stations come out in their real order
  (Cicalengka … Kiaracondong, Cikudapateuh, Bandung, Ciroyom, Cimindi, Cimahi,
  Gadobangkong, Padalarang), although the KML lists them unordered.
- **Gaps and oneway.** No route needed more than 500 m of bridging. Three routes could only
  be ordered by ignoring oneway tags; they are listed in the import report.
- **Tests.** `tests/test_transit_transform.py` covers shuffled and reversed pieces, the kept
  loop, the oneway pair, gap bridging, loop routes and stop placement. `test_transit_api.py`
  imports two crossing KML routes and plans a transfer, a multi-stop trip and a night-time
  request with no service.
- **On the map.** Dago ↔ Leuwipanjang and Cimahi → Kiaracondong produce plausible options
  (angkot 09 + DAMRI Jalur 2, Koridor 4, angkot 02 + 35), drawn along the real streets.
- **Still open:** real fares and frequencies, real bus stop lists for routes without them,
  service that runs past midnight, and checking more routes by eye against the source maps.
