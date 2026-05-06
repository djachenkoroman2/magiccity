from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import random
from typing import TYPE_CHECKING

from .config import TerrainConfig

if TYPE_CHECKING:
    from .footprints import BuildingFootprint
    from .roofs import RoofSpec


@dataclass(frozen=True)
class BBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth(self) -> float:
        return self.max_y - self.min_y

    def expand(self, margin: float) -> "BBox":
        return BBox(
            self.min_x - margin,
            self.min_y - margin,
            self.max_x + margin,
            self.max_y + margin,
        )

    def contains_xy(self, x: float, y: float) -> bool:
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y


@dataclass(frozen=True)
class Rect:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth(self) -> float:
        return self.max_y - self.min_y

    @property
    def center_x(self) -> float:
        return (self.min_x + self.max_x) * 0.5

    @property
    def center_y(self) -> float:
        return (self.min_y + self.max_y) * 0.5

    def intersects(self, bbox: BBox) -> bool:
        return not (
            self.max_x < bbox.min_x
            or self.min_x > bbox.max_x
            or self.max_y < bbox.min_y
            or self.min_y > bbox.max_y
        )

    def contains_xy(self, x: float, y: float) -> bool:
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y


@dataclass(frozen=True)
class Building:
    id: str
    footprint: BuildingFootprint
    height_m: float
    base_z: float
    biome: str = "residential"
    roof: RoofSpec | None = None
    parcel_id: str | None = None

    @property
    def roof_z(self) -> float:
        return self.base_z + self.height_m

    @property
    def eave_z(self) -> float:
        return self.roof.eave_z if self.roof is not None else self.roof_z


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float
    red: int
    green: int
    blue: int
    class_id: int


def stable_int_seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=False)


def stable_rng(*parts: object) -> random.Random:
    return random.Random(stable_int_seed(*parts))


def terrain_height(seed: int, terrain: TerrainConfig, x: float, y: float) -> float:
    amp = terrain.height_noise_m
    if amp == 0:
        return terrain.base_height_m
    phase_a = (seed % 997) * 0.013
    phase_b = (seed % 431) * 0.019
    low = math.sin(x * 0.031 + phase_a) * math.cos(y * 0.027 - phase_b)
    high = math.sin((x + y) * 0.071 + phase_b) * 0.35
    return terrain.base_height_m + amp * (0.75 * low + 0.25 * high)


def tile_bbox(tile_x: int, tile_y: int, size_m: float) -> BBox:
    min_x = tile_x * size_m
    min_y = tile_y * size_m
    return BBox(min_x=min_x, min_y=min_y, max_x=min_x + size_m, max_y=min_y + size_m)


def distance_to_grid_line(value: float, spacing: float) -> float:
    nearest = round(value / spacing) * spacing
    return abs(value - nearest)
