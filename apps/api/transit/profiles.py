"""Service defaults (fares, speeds, headways) from service_profiles.json.

The route files only describe geometry, so everything about the service itself starts as a
placeholder per mode. Overrides for a single route go under "routes" in the same file.
"""

import json
from dataclasses import dataclass
from datetime import time
from functools import cache
from pathlib import Path

from transit.models import Mode

PROFILES_PATH = Path(__file__).with_name("service_profiles.json")

# Checked in order; the first prefix that matches the route name wins.
_MODE_PREFIXES = [
    ("Commuter Line", Mode.RAIL),
    ("Koridor", Mode.BUS),
    ("Jalur", Mode.BUS),
    ("Feeder", Mode.FEEDER),
    ("KBP", Mode.SHUTTLE),
    ("Summarecon", Mode.SHUTTLE),
    ("Elf", Mode.MINIBUS),
    ("Kobutri", Mode.MINIBUS),
    ("Madona", Mode.MINIBUS),
]


def classify_mode(route_name: str) -> Mode:
    for prefix, mode in _MODE_PREFIXES:
        if route_name.startswith(prefix):
            return mode
    return Mode.ANGKOT


@dataclass(frozen=True)
class WalkProfile:
    speed_kmh: float
    max_access_m: float
    max_access_fallback_m: float
    max_transfer_m: float
    max_direct_walk_m: float
    detour_factor: float

    @property
    def speed_ms(self) -> float:
        return self.speed_kmh / 3.6


@dataclass(frozen=True)
class ServiceProfile:
    boarding: str
    stop_spacing_m: float
    fare_base_idr: int
    fare_per_km_idr: int
    fare_max_idr: int | None
    avg_speed_kmh: float
    headway_min: float
    service_start: time
    service_end: time
    is_placeholder: bool


@cache
def load_profiles(path: Path = PROFILES_PATH) -> dict:
    return json.loads(path.read_text())


def walk_profile(profiles: dict | None = None) -> WalkProfile:
    profiles = profiles or load_profiles()
    return WalkProfile(**profiles["walk"])


def service_for(route_name: str, mode: Mode, profiles: dict | None = None) -> ServiceProfile:
    profiles = profiles or load_profiles()
    values = {**profiles["modes"][mode], **profiles["routes"].get(route_name, {})}
    return ServiceProfile(
        boarding=values["boarding"],
        stop_spacing_m=values["stop_spacing_m"],
        fare_base_idr=values["fare_base_idr"],
        fare_per_km_idr=values["fare_per_km_idr"],
        fare_max_idr=values["fare_max_idr"],
        avg_speed_kmh=values["avg_speed_kmh"],
        headway_min=values["headway_min"],
        service_start=time.fromisoformat(values["service_start"]),
        service_end=time.fromisoformat(values["service_end"]),
        is_placeholder=values.get("placeholder", True),
    )
