"""The outside services enrichment reads, behind one small class so tests can stand in for it.

- Roads and railway stations: OpenStreetMap, from OpenFreeMap's vector tiles (OpenMapTiles
  schema, ODbL).
- Flood hazard: BNPB's inaRISK hazard indices, 100 m rasters on its ArcGIS server.
"""

import json
import time
import urllib.parse
import urllib.request

TILEJSON_URL = "https://tiles.openfreemap.org/planet"
INARISK_URL = "https://gis.bnpb.go.id/server/rest/services/inarisk"
RIVER_FLOOD = "INDEKS_BAHAYA_BANJIR"
FLASH_FLOOD = "INDEKS_BAHAYA_BANJIRBANDANG"

# OpenFreeMap refuses the default Python client name, and a named client is good manners.
USER_AGENT = "rumah-subsidi-etl/0.1"


class SourceError(Exception):
    """A service is unreachable or returned something unusable."""


class Sources:
    def __init__(self, timeout_s: float = 40, pause_s: float = 0.3, retries: int = 3):
        self.timeout_s = timeout_s
        # A short pause between requests: these are free public services.
        self.pause_s = pause_s
        self.retries = retries
        self._tile_template: str | None = None
        self._tiles: dict[tuple[int, int, int], bytes] = {}

    def _get(self, url: str) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        for attempt in range(self.retries):
            time.sleep(self.pause_s * (1 + 4 * attempt))
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                    return response.read()
            except OSError as error:  # URLError, HTTPError, resets and timeouts
                failure = error
        raise SourceError(f"{url.split('?')[0]} failed: {failure}") from failure

    def _json(self, url: str) -> dict:
        try:
            return json.loads(self._get(url))
        except ValueError as error:
            raise SourceError(f"{url.split('?')[0]} did not return JSON") from error

    # --- OpenFreeMap --------------------------------------------------------------------

    def tile_version(self) -> str:
        """Which planet build the tiles come from, e.g. '20261101_080013_pt'."""
        return self._template().split("/planet/")[1].split("/")[0]

    def _template(self) -> str:
        if self._tile_template is None:
            self._tile_template = self._json(TILEJSON_URL)["tiles"][0]
        return self._tile_template

    def tile(self, zoom: int, x: int, y: int) -> bytes:
        key = (zoom, x, y)
        if key not in self._tiles:
            self._tiles[key] = self._get(self._template().format(z=zoom, x=x, y=y))
        return self._tiles[key]

    # --- inaRISK ------------------------------------------------------------------------

    def hazard(self, service: str, points: list[tuple[float, float]]) -> list[float | None]:
        """The hazard index (0–1) at each point; None where the raster has no data.

        No data means the point is outside every mapped hazard zone, not that it is unknown.
        """
        geometry = {"points": [list(point) for point in points], "spatialReference": {"wkid": 4326}}
        query = urllib.parse.urlencode(
            {
                "geometry": json.dumps(geometry, separators=(",", ":")),
                "geometryType": "esriGeometryMultipoint",
                "returnFirstValueOnly": "true",
                "f": "json",
            }
        )
        result = self._json(f"{INARISK_URL}/{service}/ImageServer/getSamples?{query}")
        if "samples" not in result:
            raise SourceError(f"inaRISK {service} returned no samples: {str(result)[:200]}")
        values: list[float | None] = [None] * len(points)
        for sample in result["samples"]:
            raw = sample.get("value")
            values[sample["locationId"]] = float(raw) if raw not in (None, "", "NoData") else None
        return values
