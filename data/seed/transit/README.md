# Transit routes seed

Route exports from **Transport for Bandung**, committed so that `manage.py import_routes`
(and the `api` container's first start) work without a manual download.

| File | Export date | Size | SHA-256 |
| ---- | ----------- | ---- | ------- |
| `tfb-route-shp.zip` | 2026-11-16 | 5.3 MB | `7326650a015d77a7f7dab1661c226b9edde692d7b84e16359cc2258b92eaadef` |
| `tfb-route-kml.zip` | 2026-11-16 | 3.0 MB | `5c18ffe9c93fe62191579e62c2b94ca04ee8b774bb2b4cd850c481462fd0614f` |

- **Source:** <https://transportforbandung.org/peta>, "Unduh Data". Fetched 2026-11-23,
  unchanged from the download (see [`data/README.md`](../../README.md) for what is in them).
- **Licence:** [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/),
  as stated on the download page. Anything redistributing this data or derived from it
  (the imported routes, maps, API responses) must credit
  **© OpenStreetMap contributors and Transport for Bandung**. A database derived from it
  that is shared publicly must also be offered under the ODbL.
- **Import result (2026-11-23):** 375 shapefile and 385 KML routes, merged into 395 routes
  and 20,994 stops. The QA report lists 3 routes ordered with oneway relaxed, 1 low-coverage
  route (Summarecon shuttle, 0.64) and no large gaps.

## Updating

1. Download both files from the page above into `data/raw/` and run
   `manage.py import_routes`; it prefers `raw/` over this folder.
2. Read the QA report against the previous one (above).
3. If it looks right, copy the files here, update the table, the import result and the
   Retrieved date in `data/README.md`, and commit.
