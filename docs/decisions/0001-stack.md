# 0001: Stack

- Status: accepted
- Date: 2026-10-22

## Context

Huni is a portfolio project for learning geospatial backend work. It shows how well
neighbourhoods in Kota Bandung fit what a person is looking for. The stack should make the
spatial parts explicit and inspectable, stay small enough for one person, and run locally
with one command.

## Decision

- **Backend:** Django + GeoDjango on PostgreSQL/PostGIS, HTTP API with Django Ninja.
  GeoPandas, Shapely and pyproj for offline data preparation.
- **Frontend:** React + TypeScript + Vite, MapLibre GL JS (2D) with the basemap style URL
  set through the environment.
- **Tooling:** uv, pytest (pytest-django) and ruff for Python; pnpm and Vitest for the web.
- **Local:** Docker Compose with `db` (PostGIS), `api` and `web`.
- **CI:** GitHub Actions running ruff + pytest against a PostGIS service container, and
  typecheck + Vitest + build for the web.

## Consequences

- PostGIS does the spatial work in the database. GeoDjango gives ORM access to it, and raw
  SQL is still available when that's clearer.
- GeoDjango needs the native GDAL/GEOS/PROJ libraries, so local setup and CI install them.
- Ninja gives typed request/response schemas and OpenAPI docs (`/api/docs`) for little code.
- MapLibre with an env-configured style keeps the frontend free of vendor keys. The
  default is OpenFreeMap.
- One `.env` at the repo root feeds Compose, Django and Vite.
