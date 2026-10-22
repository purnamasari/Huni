# data/

Working area for source datasets.

- `raw/`: original downloads, exactly as fetched. **Git-ignored.** Never edit files here; re-download instead.
- Anything derived goes elsewhere, produced by code so it can be regenerated.

Inside Docker Compose this folder is mounted at `/data` in the `api` container.

## Sources

Log every dataset you add, so you can trace where each one came from:

| File in `raw/` | Source (URL) | Licence | Retrieved | CRS as delivered | Notes |
| -------------- | ------------ | ------- | --------- | ---------------- | ----- |
|                |              |         |           |                  |       |
