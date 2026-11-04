# data/

Working area for source datasets.

- `raw/`: original downloads, exactly as fetched. **Git-ignored.** Never edit files here; re-download instead.
- Anything derived goes elsewhere, produced by code so it can be regenerated.

Inside Docker Compose this folder is mounted at `/data` in the `api` container.

## Sources

Log every dataset you add, so you can trace where each one came from:

| File in `raw/` | Source (URL) | Licence | Retrieved | CRS as delivered | Notes |
| -------------- | ------------ | ------- | --------- | ---------------- | ----- |
| `tfb-route-shp.zip` | Transport for Bandung route export (shapefile) | Not stated in the files. Geometry and tags are OpenStreetMap ways (ODbL); confirm with the source. | 2026-10-26 | EPSG:4326 | 375 routes, one file per direction. One row per OSM way, not in travel order; carries `oneway`. Loaded by `manage.py import_routes`. |
| `tfb-route-kml.zip` | Transport for Bandung route export (KML) | As above | 2026-10-26 | EPSG:4326 (KML) | 385 routes, same shape as the shapefiles plus Point placemarks for terminals and, for bus/rail lines, stops/stations. 20 routes exist only here. |
