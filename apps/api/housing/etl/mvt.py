"""Read features out of a Mapbox Vector Tile, using only the standard library.

Just what the access measurements need: one layer's features, with their properties and
their geometry as lists of (x, y) in tile units. Spec (version 2):
https://github.com/mapbox/vector-tile-spec
"""

import math
import struct
from collections.abc import Iterator
from dataclasses import dataclass

POINT, LINE, POLYGON = 1, 2, 3


@dataclass
class Feature:
    type: int
    properties: dict
    # One list of (x, y) per part: a point, a line, or a polygon ring. Tile units.
    parts: list[list[tuple[int, int]]]


def _varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7


def _fields(buf: bytes) -> Iterator[tuple[int, int | bytes]]:
    """Each field of a protobuf message as (field number, value)."""
    pos = 0
    while pos < len(buf):
        key, pos = _varint(buf, pos)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = _varint(buf, pos)
        elif wire == 2:
            length, pos = _varint(buf, pos)
            value = buf[pos : pos + length]
            pos += length
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            value = buf[pos : pos + size]
            pos += size
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")
        yield number, value


def _packed(buf: bytes) -> list[int]:
    values, pos = [], 0
    while pos < len(buf):
        value, pos = _varint(buf, pos)
        values.append(value)
    return values


def _zigzag(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def _value(buf: bytes):
    for number, value in _fields(buf):
        if number == 1:
            return value.decode("utf-8")
        if number == 2:
            return struct.unpack("<f", value)[0]
        if number == 3:
            return struct.unpack("<d", value)[0]
        if number in (4, 5):
            return value
        if number == 6:
            return _zigzag(value)
        if number == 7:
            return bool(value)
    return None


def _geometry(commands: list[int]) -> list[list[tuple[int, int]]]:
    """Decode the command stream: MoveTo starts a part, LineTo extends it, ClosePath ends a ring."""
    parts: list[list[tuple[int, int]]] = []
    x = y = i = 0
    while i < len(commands):
        command, count = commands[i] & 7, commands[i] >> 3
        i += 1
        if command == 7:
            if parts and parts[-1]:
                parts[-1].append(parts[-1][0])
            continue
        for _ in range(count):
            x += _zigzag(commands[i])
            y += _zigzag(commands[i + 1])
            i += 2
            if command == 1:
                parts.append([(x, y)])
            else:
                parts[-1].append((x, y))
    return parts


def read_layer(tile: bytes, name: str) -> tuple[list[Feature], int]:
    """The features of one layer and the layer's extent; ([], 4096) when the tile lacks it."""
    for number, layer in _fields(tile):
        if number != 3:
            continue
        keys: list[str] = []
        values: list = []
        raw_features: list[bytes] = []
        layer_name, extent = "", 4096
        for field, value in _fields(layer):
            if field == 1:
                layer_name = value.decode("utf-8")
            elif field == 2:
                raw_features.append(value)
            elif field == 3:
                keys.append(value.decode("utf-8"))
            elif field == 4:
                values.append(_value(value))
            elif field == 5:
                extent = value
        if layer_name != name:
            continue
        features = []
        for raw in raw_features:
            tags: list[int] = []
            commands: list[int] = []
            kind = 0
            for field, value in _fields(raw):
                if field == 2:
                    tags = _packed(value)
                elif field == 3:
                    kind = value
                elif field == 4:
                    commands = _packed(value)
            properties = {keys[k]: values[v] for k, v in zip(tags[::2], tags[1::2], strict=True)}
            features.append(Feature(kind, properties, _geometry(commands)))
        return features, extent
    return [], 4096


def tile_of(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    """The XYZ tile that contains a point."""
    n = 2**zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def lonlat(zoom: int, x: int, y: int, px: float, py: float, extent: int) -> tuple[float, float]:
    """A position inside a tile (px, py in tile units) as longitude and latitude."""
    n = 2**zoom
    lon = (x + px / extent) / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + py / extent) / n))))
    return lon, lat
