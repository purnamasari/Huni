"""Stand-ins for the outside services enrichment reads, and a tiny vector tile writer."""

from housing.etl import mvt


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _zigzag(value: int) -> int:
    return (value << 1) ^ (value >> 63)


def _bytes(number: int, payload: bytes) -> bytes:
    return _varint(number << 3 | 2) + _varint(len(payload)) + payload


def _int(number: int, value: int) -> bytes:
    return _varint(number << 3) + _varint(value)


def _packed(values: list[int]) -> bytes:
    return b"".join(_varint(value) for value in values)


def _commands(kind: int, parts: list[list[tuple[int, int]]]) -> list[int]:
    commands: list[int] = []
    x = y = 0
    for part in parts:
        for i, (px, py) in enumerate(part):
            if i == 0:
                commands.append(1 | 1 << 3)  # MoveTo, once
            elif i == 1:
                commands.append(2 | (len(part) - 1) << 3)  # LineTo, for the rest
            commands += [_zigzag(px - x), _zigzag(py - y)]
            x, y = px, py
        if kind == mvt.POLYGON:
            commands.append(7 | 1 << 3)  # ClosePath
    return commands


def encode_tile(layers: dict[str, list[tuple[int, dict, list]]], extent: int = 4096) -> bytes:
    """A vector tile from {layer name: [(geometry type, properties, parts), ...]}.

    Properties must be strings; parts are lists of (x, y) in tile units.
    """
    tile = b""
    for name, features in layers.items():
        keys: list[str] = []
        values: list[str] = []
        body = _bytes(1, name.encode())
        for kind, properties, parts in features:
            tags: list[int] = []
            for key, value in properties.items():
                if key not in keys:
                    keys.append(key)
                if value not in values:
                    values.append(value)
                tags += [keys.index(key), values.index(value)]
            feature = (
                _bytes(2, _packed(tags))
                + _int(3, kind)
                + _bytes(4, _packed(_commands(kind, parts)))
            )
            body += _bytes(2, feature)
        body += b"".join(_bytes(3, key.encode()) for key in keys)
        body += b"".join(_bytes(4, _bytes(1, value.encode())) for value in values)
        body += _int(5, extent) + _int(15, 2)
        tile += _bytes(3, body)
    return tile


class FakeSources:
    """Answers from memory: tiles by (zoom, x, y), and a hazard index per service."""

    def __init__(self, tiles=None, hazard=None):
        self.tiles = tiles or {}
        # service name -> function of (lon, lat) returning an index or None
        self._hazard = hazard or {}
        self.requested_tiles: list[tuple[int, int, int]] = []

    def tile_version(self) -> str:
        return "test"

    def tile(self, zoom: int, x: int, y: int) -> bytes:
        self.requested_tiles.append((zoom, x, y))
        return self.tiles.get((zoom, x, y), b"")

    def hazard(self, service: str, points: list[tuple[float, float]]) -> list[float | None]:
        index = self._hazard.get(service, lambda lon, lat: None)
        return [index(lon, lat) for lon, lat in points]
