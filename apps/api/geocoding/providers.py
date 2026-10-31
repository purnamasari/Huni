"""Address and place search (geocoding), combining two providers.

Neither provider covers Bandung well on its own (checked against live queries):

- Mapbox Search Box (when MAPBOX_ACCESS_TOKEN is set) has rich, current places (shops,
  markets, campuses, offices) with real street addresses like "Jl. A. Yani No.221-223",
  but no streets or house addresses for Indonesia; its reverse lookup returns whatever
  business is nearest.
- Photon (https://photon.komoot.io, OpenStreetMap) has the streets and areas, and names a
  point by its street, but fewer places.

So search asks both at once and merges the results (best matches first), and naming a
dropped pin asks Photon first. If one provider fails, the other's results still come back.

The browser never calls a provider directly: queries go through this API, which keeps the
user's IP address and the Mapbox token on the server. Mapbox results are for temporary use
only under its terms, so they are never cached; Photon's (ODbL) are cached for a day.
"""

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from itertools import zip_longest

from django.conf import settings
from django.core.cache import cache

# Results are limited to, and ranked towards, Bandung Raya: (west, south, east, north).
BANDUNG_RAYA_BBOX = (107.25, -7.25, 107.95, -6.70)
BANDUNG_CENTER = (107.6098, -6.9147)
BBOX_PARAM = ",".join(str(v) for v in BANDUNG_RAYA_BBOX)
CENTER_PARAM = ",".join(str(v) for v in BANDUNG_CENTER)

# Bump when GeocodeResult changes, so rows cached in the old shape are not read back.
CACHE_VERSION = 3

# After the first provider answers, how long to keep waiting for the other. A slow
# provider is dropped from this response; it still finishes in the background and, if
# cacheable, fills the cache for the next keystroke.
STRAGGLER_WAIT_S = 1.5

# Same name within about 150 m is the same place from two providers.
SAME_PLACE_DEGREES = 0.0015

_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="geocode")


class GeocoderError(Exception):
    """A provider is unreachable, slow or returned something unusable."""


@dataclass(frozen=True)
class GeocodeResult:
    id: str
    name: str
    # "address" (a building or house number), "street", "landmark" or "area"
    kind: str
    # Street and district, e.g. "Jl. Cihampelas No.160, Cipaganti, Bandung".
    context: str
    # Just the street line, e.g. "Jl. Cihampelas No.160"; empty when it is the name itself.
    address: str
    lon: float
    lat: float
    source: str


def _get_json(url: str, user_agent: str, timeout_s: float) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.load(response)
    except (OSError, ValueError) as error:  # URLError, HTTPError, timeouts and bad JSON
        raise GeocoderError(f"{url.split('?')[0]} failed: {error}") from error


def _context(*parts: str | None, exclude: str = "") -> str:
    out: list[str] = []
    for part in parts:
        if part and part != exclude and part not in out:
            out.append(part)
    return ", ".join(out)


class Photon:
    source = "photon"
    cache_seconds = 24 * 60 * 60
    # Photon "type" values that describe an area rather than a place in it.
    _AREA_TYPES = {"city", "district", "locality", "county", "state", "suburb", "neighbourhood"}

    def __init__(self, base_url: str, user_agent: str, timeout_s: float):
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout_s = timeout_s

    def search(self, query: str, limit: int) -> list[GeocodeResult]:
        params = {"q": query, "limit": limit, "lon": BANDUNG_CENTER[0], "lat": BANDUNG_CENTER[1]}
        data = self._get("/api/", {**params, "bbox": BBOX_PARAM})
        return [self._result(f) for f in data.get("features", [])]

    def reverse(self, lon: float, lat: float) -> GeocodeResult | None:
        data = self._get("/reverse", {"lon": lon, "lat": lat})
        features = data.get("features", [])
        return self._result(features[0]) if features else None

    def _get(self, path: str, params: dict) -> dict:
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(params)}"
        return _get_json(url, self.user_agent, self.timeout_s)

    @classmethod
    def _result(cls, feature: dict) -> GeocodeResult:
        p = feature.get("properties", {})
        lon, lat = feature["geometry"]["coordinates"][:2]
        name, street, number = p.get("name"), p.get("street"), p.get("housenumber")
        address = " ".join(part for part in (street, number) if part)

        if p.get("type") == "street":
            kind, label = "street", name or street
        elif p.get("type") in cls._AREA_TYPES:
            kind, label = "area", name
        elif name:
            kind, label = "landmark", name
        else:
            kind, label = "address", address
        label = label or "Unnamed place"
        address = address if address != label else ""

        return GeocodeResult(
            id=f"{cls.source}-{p.get('osm_type', '')}{p.get('osm_id', '')}",
            name=label,
            kind=kind,
            context=_context(
                address,
                p.get("district") or p.get("locality"),
                p.get("city") or p.get("county"),
                exclude=label,
            ),
            address=address,
            lon=round(lon, 7),
            lat=round(lat, 7),
            source=cls.source,
        )


class Mapbox:
    """Mapbox Search Box API (https://docs.mapbox.com/api/search/search-box/)."""

    source = "mapbox"
    cache_seconds = 0  # "only available for temporary use"
    base_url = "https://api.mapbox.com/search/searchbox/v1"
    _KINDS = {"poi": "landmark", "address": "address", "street": "street"}

    def __init__(self, token: str, user_agent: str, timeout_s: float):
        self.token = token
        self.user_agent = user_agent
        self.timeout_s = timeout_s

    def search(self, query: str, limit: int) -> list[GeocodeResult]:
        data = self._get(
            "/forward",
            {
                "q": query[:256],
                "limit": min(limit, 10),
                "proximity": CENTER_PARAM,
                "bbox": BBOX_PARAM,
                "country": "id",
                "language": "id",
                "auto_complete": "true",
            },
        )
        return [self._result(f) for f in data.get("features", [])]

    def reverse(self, lon: float, lat: float) -> GeocodeResult | None:
        data = self._get(
            "/reverse", {"longitude": lon, "latitude": lat, "limit": 1, "language": "id"}
        )
        features = data.get("features", [])
        return self._result(features[0]) if features else None

    def _get(self, path: str, params: dict) -> dict:
        query = urllib.parse.urlencode({**params, "access_token": self.token})
        return _get_json(f"{self.base_url}{path}?{query}", self.user_agent, self.timeout_s)

    @classmethod
    def _result(cls, feature: dict) -> GeocodeResult:
        p = feature.get("properties", {})
        lon, lat = feature["geometry"]["coordinates"][:2]
        context = p.get("context") or {}

        def named(level: str) -> str | None:
            return (context.get(level) or {}).get("name")

        name = p.get("name") or "Unnamed place"
        address = p.get("address") or ""
        # For places Mapbox doesn't know the street of, "address" is just the city.
        if address in (name, named("place")):
            address = ""
        return GeocodeResult(
            id=f"{cls.source}-{p.get('mapbox_id', '')}",
            name=name,
            kind=cls._KINDS.get(p.get("feature_type"), "area"),
            context=_context(
                address, named("neighborhood") or named("locality"), named("place"), exclude=name
            )
            or p.get("place_formatted", ""),
            address=address,
            lon=round(lon, 7),
            lat=round(lat, 7),
            source=cls.source,
        )


Provider = Photon | Mapbox


def _photon() -> Photon:
    return Photon(settings.GEOCODER_URL, settings.GEOCODER_USER_AGENT, settings.GEOCODER_TIMEOUT_S)


def _mapbox() -> Mapbox | None:
    token = settings.MAPBOX_ACCESS_TOKEN
    if not token:
        return None
    return Mapbox(token, settings.GEOCODER_USER_AGENT, settings.GEOCODER_TIMEOUT_S)


def search_providers() -> list[Provider]:
    """For search: Mapbox for places, Photon for streets and areas."""
    return [p for p in (_mapbox(), _photon()) if p]


def reverse_providers() -> list[Provider]:
    """For naming a point: Photon first, as it answers with the street."""
    return [p for p in (_photon(), _mapbox()) if p]


def _cached(provider: Provider, key: str, fetch):
    if not provider.cache_seconds:
        return fetch()
    key = f"geocode:v{CACHE_VERSION}:{provider.source}:{key}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    value = fetch()
    cache.set(key, value, provider.cache_seconds)
    return value


def _search_one(provider: Provider, query: str, limit: int) -> list[GeocodeResult]:
    digest = hashlib.sha1(f"{query.lower()}|{limit}".encode()).hexdigest()
    rows = _cached(
        provider, f"search:{digest}", lambda: [asdict(r) for r in provider.search(query, limit)]
    )
    return [GeocodeResult(**row) for row in rows]


def search(query: str, limit: int = 6, source: str | None = None) -> list[GeocodeResult]:
    """Results from every configured provider (or just `source`), merged.

    Raises only if all of them fail. An unconfigured `source` gives no results.
    """
    query = " ".join(query.split())
    providers = [p for p in search_providers() if source in (None, p.source)]
    if not providers:
        return []
    futures = {_pool.submit(_search_one, p, query, limit): p for p in providers}
    timeout = settings.GEOCODER_TIMEOUT_S
    done, pending = wait(futures, timeout=timeout, return_when=FIRST_COMPLETED)
    if pending:
        # One answered: give the others a little longer. One failed: wait for the rest.
        answered = any(not f.exception() for f in done)
        more, pending = wait(pending, timeout=STRAGGLER_WAIT_S if answered else timeout)
        done |= more

    lists, errors = [], []
    for future in futures:  # in provider order
        if future in done and not future.exception():
            lists.append(future.result())
        elif future in done:
            errors.append(future.exception())
    if not lists:
        raise GeocoderError(f"every provider failed: {errors or 'timed out'}")
    return merge(query, lists, limit)


def merge(query: str, lists: list[list[GeocodeResult]], limit: int) -> list[GeocodeResult]:
    """One list: exact name matches first, then the providers taken in turns, so Mapbox's
    many places don't crowd out the streets only OpenStreetMap has. Repeats are dropped."""
    wanted = query.lower()
    exact = [r for results in lists for r in results if r.name.lower() == wanted]
    rest = [[r for r in results if r.name.lower() != wanted] for results in lists]
    in_turns = [r for row in zip_longest(*rest) for r in row if r is not None]

    merged: list[GeocodeResult] = []
    for result in exact + in_turns:
        if not any(
            other.name.lower() == result.name.lower()
            and abs(other.lon - result.lon) < SAME_PLACE_DEGREES
            and abs(other.lat - result.lat) < SAME_PLACE_DEGREES
            for other in merged
        ):
            merged.append(result)
    return merged[:limit]


def reverse(lon: float, lat: float) -> GeocodeResult | None:
    """The first provider with an answer. Raises only if all of them fail."""
    errors = []
    for provider in reverse_providers():
        # About 1 m: clicks on the same spot share a cache entry.
        key = f"reverse:{lon:.5f},{lat:.5f}"
        try:
            row = _cached(provider, key, lambda p=provider: _as_row(p.reverse(lon, lat)))
        except GeocoderError as error:
            errors.append(error)
            continue
        if row:
            return GeocodeResult(**row)
    if errors and len(errors) == len(reverse_providers()):
        raise GeocoderError(f"every provider failed: {errors}")
    return None


def _as_row(result: GeocodeResult | None) -> dict:
    # An empty dict, not None, so "nothing here" is cached too.
    return asdict(result) if result else {}
