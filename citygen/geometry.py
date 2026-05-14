from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import random
from typing import TYPE_CHECKING

from .config import TerrainConfig, TerrainRavineConfig

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
class OrientedRect:
    center_x: float
    center_y: float
    width: float
    depth: float
    angle_degrees: float = 0.0

    @property
    def area_m2(self) -> float:
        return self.width * self.depth

    @property
    def bbox(self) -> Rect:
        corners = self.corners()
        xs = [x for x, _ in corners]
        ys = [y for _, y in corners]
        return Rect(min(xs), min(ys), max(xs), max(ys))

    @property
    def orientation_degrees(self) -> float:
        return normalize_degrees(self.angle_degrees)

    def local_to_world(self, x: float, y: float) -> tuple[float, float]:
        return rotate_xy(
            self.center_x + x,
            self.center_y + y,
            self.center_x,
            self.center_y,
            self.angle_degrees,
        )

    def world_to_local(self, x: float, y: float) -> tuple[float, float]:
        rx, ry = rotate_xy(x, y, self.center_x, self.center_y, -self.angle_degrees)
        return rx - self.center_x, ry - self.center_y

    def contains_xy(self, x: float, y: float, eps: float = 1e-9) -> bool:
        local_x, local_y = self.world_to_local(x, y)
        return (
            abs(local_x) <= self.width * 0.5 + eps
            and abs(local_y) <= self.depth * 0.5 + eps
        )

    def corners(self) -> tuple[tuple[float, float], ...]:
        half_w = self.width * 0.5
        half_d = self.depth * 0.5
        return (
            self.local_to_world(-half_w, -half_d),
            self.local_to_world(-half_w, half_d),
            self.local_to_world(half_w, half_d),
            self.local_to_world(half_w, -half_d),
        )

    def inset(self, inset_m: float) -> "OrientedRect | None":
        if inset_m <= 0:
            return self
        width = self.width - inset_m * 2.0
        depth = self.depth - inset_m * 2.0
        if width <= 0 or depth <= 0:
            return None
        return OrientedRect(
            center_x=self.center_x,
            center_y=self.center_y,
            width=width,
            depth=depth,
            angle_degrees=self.angle_degrees,
        )


@dataclass(frozen=True)
class Building:
    id: str
    footprint: BuildingFootprint
    height_m: float
    base_z: float
    biome: str = "residential"
    roof: RoofSpec | None = None
    parcel_id: str | None = None
    orientation_degrees: float = 0.0

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


def rect_to_oriented(rect: Rect, angle_degrees: float = 0.0) -> OrientedRect:
    return OrientedRect(
        center_x=rect.center_x,
        center_y=rect.center_y,
        width=rect.width,
        depth=rect.depth,
        angle_degrees=angle_degrees,
    )


def rotate_xy(
    x: float,
    y: float,
    origin_x: float,
    origin_y: float,
    angle_degrees: float,
) -> tuple[float, float]:
    if angle_degrees == 0:
        return x, y
    radians = math.radians(angle_degrees)
    cos_a = math.cos(radians)
    sin_a = math.sin(radians)
    dx = x - origin_x
    dy = y - origin_y
    return origin_x + dx * cos_a - dy * sin_a, origin_y + dx * sin_a + dy * cos_a


def normalize_degrees(angle_degrees: float) -> float:
    value = angle_degrees % 360.0
    if value < 0:
        value += 360.0
    return 0.0 if abs(value - 360.0) < 1e-9 else value


def angle_delta_degrees(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def terrain_height(seed: int, terrain: TerrainConfig, x: float, y: float) -> float:
    height = terrain.base_height_m
    amp = terrain.height_noise_m
    if amp != 0:
        phase_a = (seed % 997) * 0.013
        phase_b = (seed % 431) * 0.019
        low = math.sin(x * 0.031 + phase_a) * math.cos(y * 0.027 - phase_b)
        high = math.sin((x + y) * 0.071 + phase_b) * 0.35
        height += amp * (0.75 * low + 0.25 * high)

    for mountain in terrain.mountains:
        height += _terrain_peak_offset(
            mountain.center_x,
            mountain.center_y,
            mountain.height_m,
            mountain.radius_m,
            x,
            y,
            1.65,
        )
    for hill in terrain.hills:
        height += _terrain_peak_offset(
            hill.center_x,
            hill.center_y,
            hill.height_m,
            hill.radius_m,
            x,
            y,
            0.85,
        )
    for ravine in terrain.ravines:
        height -= _terrain_ravine_depth(ravine, x, y)
    return height


def _terrain_peak_offset(
    center_x: float,
    center_y: float,
    height_m: float,
    radius_m: float,
    x: float,
    y: float,
    sharpness: float,
) -> float:
    if radius_m <= 0:
        return 0.0
    distance = math.hypot(x - center_x, y - center_y)
    falloff = _smooth_radial_falloff(distance, radius_m) ** sharpness
    return height_m * falloff


def _terrain_ravine_depth(ravine: TerrainRavineConfig, x: float, y: float) -> float:
    if ravine.length_m <= 0 or ravine.width_m <= 0:
        return 0.0

    angle = math.radians(ravine.angle_degrees)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    dx = x - ravine.center_x
    dy = y - ravine.center_y
    along = dx * cos_a + dy * sin_a
    across = -dx * sin_a + dy * cos_a

    half_width = ravine.width_m * 0.5
    cross_t = abs(across) / half_width
    if cross_t >= 1.0:
        return 0.0

    half_length = ravine.length_m * 0.5
    overrun = max(0.0, abs(along) - half_length)
    if overrun >= half_width:
        return 0.0

    cross_profile = (1.0 - _smoothstep(cross_t)) ** 1.15
    end_profile = 1.0 if overrun == 0 else 1.0 - _smoothstep(overrun / half_width)
    return ravine.depth_m * cross_profile * end_profile


def _smooth_radial_falloff(distance: float, radius: float) -> float:
    if distance >= radius:
        return 0.0
    return 1.0 - _smoothstep(distance / radius)


def _smoothstep(value: float) -> float:
    t = min(1.0, max(0.0, value))
    return t * t * (3.0 - 2.0 * t)


def tile_bbox(tile_x: int, tile_y: int, size_m: float) -> BBox:
    min_x = tile_x * size_m
    min_y = tile_y * size_m
    return BBox(min_x=min_x, min_y=min_y, max_x=min_x + size_m, max_y=min_y + size_m)


def distance_to_grid_line(value: float, spacing: float) -> float:
    nearest = round(value / spacing) * spacing
    return abs(value - nearest)
