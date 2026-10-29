# boundaries.json

Kota Bandung (1), kecamatan (30) and kelurahan (151) boundaries for the **frontend mock only**.
The backend will import its own boundaries properly; nothing reads this file outside
`src/mocks/`.

- Source: OpenStreetMap boundary relations (`admin_level` 5, 6 and 7), fetched from the
  OSM API on 2026-10-29. © OpenStreetMap contributors, licensed under the
  [ODbL](https://opendatacommons.org/licenses/odbl/).
- Kota relation: [13290062](https://www.openstreetmap.org/relation/13290062). Kecamatan and
  kelurahan relations are listed by `osmId`.
- Each boundary way was simplified once (Douglas–Peucker, 0.00012°, roughly 13 m) before
  the polygons were rebuilt, so neighbours still share identical borders. No polygon's area
  changed by more than 1.3%.
- Checked: both levels tile the Kota with no gaps or overlaps, every kelurahan lies in
  exactly one kecamatan, all polygons are valid.
- `labelPoint` is the pole of inaccessibility of each polygon.
- Coordinates are WGS84 (EPSG:4326) [lon, lat], rounded to 5 decimals (about 1 m).
