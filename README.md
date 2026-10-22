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

- Web: http://localhost:5173. Map centred on Bandung, with an API health indicator.
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

## Checks (same as CI)

```sh
# apps/api (needs the db running)
uv run ruff check . && uv run ruff format --check .
uv run --env-file ../../.env pytest

# apps/web
pnpm typecheck && pnpm test && pnpm build
```

## Configuration

Everything comes from the root `.env` (see [`.env.example`](.env.example)):

- `POSTGRES_*`: database connection. The PostGIS container uses the same values.
- `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`
- `VITE_BASEMAP_STYLE_URL`: any MapLibre style JSON. Defaults to OpenFreeMap "liberty".
- `API_PROXY_TARGET`: where the Vite dev server sends `/api` requests.
