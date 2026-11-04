# data/

Working area for source datasets.

- `raw/`: original downloads, exactly as fetched. **Git-ignored.** Never edit files here; re-download instead.
- Anything derived goes elsewhere, produced by code so it can be regenerated.

Inside Docker Compose this folder is mounted at `/data` in the `api` container.

## Sources

Log every dataset you add, so you can trace where each one came from:

| File in `raw/` | Source (URL) | Licence | Retrieved | CRS as delivered | Notes |
| -------------- | ------------ | ------- | --------- | ---------------- | ----- |
| `tfb-route-shp.zip` | [Transport for Bandung](https://transportforbandung.org/peta), "Unduh Data" (the site asks for name, email, organisation and purpose before the download) | [ODbL](https://opendatacommons.org/licenses/odbl/), as stated on the download page. Redistribution and derived works must credit "© OpenStreetMap contributors and Transport for Bandung". | 2026-10-26; re-fetched 2026-11-04 (export dated 2026-11-02, same route counts) | EPSG:4326 | 375 routes, one file per direction. One row per OSM way, not in travel order; carries `oneway`. Loaded by `manage.py import_routes`. |
| `tfb-route-kml.zip` | As above | As above | As above | EPSG:4326 (KML) | 385 routes, same shape as the shapefiles plus Point placemarks for terminals and, for bus/rail lines, stops/stations. 20 routes exist only here. |
