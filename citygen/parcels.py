from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Any

from .biomes import classify_biome
from .config import CityGenConfig, ParcelsConfig
from .geometry import BBox, Building, OrientedRect, Rect, normalize_degrees, rect_to_oriented, stable_rng
from .roads import RoadNetworkLike


@dataclass(frozen=True)
class Block:
    id: str
    bbox: Rect
    parcel_count: int
    buildable_parcel_count: int
    geometry: OrientedRect | None = None

    def __post_init__(self) -> None:
        if self.geometry is None:
            object.__setattr__(self, "geometry", rect_to_oriented(self.bbox))

    @property
    def orientation_degrees(self) -> float:
        return self.geometry.orientation_degrees


@dataclass(frozen=True)
class Parcel:
    id: str
    block_id: str
    bbox: Rect
    inner: Rect
    biome: str
    road_distance_m: float
    buildable: bool
    orientation_degrees: float = 0.0
    geometry: OrientedRect | None = None
    buildable_geometry: OrientedRect | None = None

    def __post_init__(self) -> None:
        geometry = self.geometry or rect_to_oriented(self.bbox, self.orientation_degrees)
        buildable_geometry = self.buildable_geometry or rect_to_oriented(self.inner, geometry.orientation_degrees)
        object.__setattr__(self, "geometry", geometry)
        object.__setattr__(self, "buildable_geometry", buildable_geometry)
        object.__setattr__(self, "orientation_degrees", geometry.orientation_degrees)

    @property
    def center_x(self) -> float:
        return self.geometry.center_x

    @property
    def center_y(self) -> float:
        return self.geometry.center_y

    @property
    def width(self) -> float:
        return self.geometry.width

    @property
    def depth(self) -> float:
        return self.geometry.depth

    @property
    def area_m2(self) -> float:
        return self.geometry.area_m2


def build_blocks_and_parcels(
    config: CityGenConfig,
    bbox: BBox,
    road_network: RoadNetworkLike,
) -> tuple[tuple[Block, ...], tuple[Parcel, ...]]:
    parcel_config = config.parcels
    blocks: list[Block] = []
    parcels: list[Parcel] = []
    block_size = parcel_config.block_size_m
    start_i = math.floor(bbox.min_x / block_size)
    end_i = math.ceil(bbox.max_x / block_size)
    start_j = math.floor(bbox.min_y / block_size)
    end_j = math.ceil(bbox.max_y / block_size)
    road_clearance = config.parcels.parcel_setback_m

    for ix in range(start_i, end_i):
        for iy in range(start_j, end_j):
            block_id = f"block_{ix}_{iy}"
            rng = stable_rng(config.seed, "block", ix, iy)
            candidate = _block_rect(ix, iy, block_size, parcel_config, bbox, rng)
            if candidate.width < parcel_config.min_block_size_m or candidate.depth < parcel_config.min_block_size_m:
                continue

            block_geometry = _block_geometry(config, ix, iy, candidate, bbox, road_network)
            local_block = Rect(
                -candidate.width * 0.5,
                -candidate.depth * 0.5,
                candidate.width * 0.5,
                candidate.depth * 0.5,
            )
            parcel_rects = _subdivide_block(local_block, parcel_config, rng)
            block_parcels: list[Parcel] = []
            for index, local_rect in enumerate(parcel_rects):
                geometry = _local_rect_to_oriented(block_geometry, local_rect)
                buildable_geometry = geometry.inset(parcel_config.parcel_setback_m)
                if buildable_geometry is None:
                    continue
                biome = classify_biome(config.seed, config.urban_fields, geometry.center_x, geometry.center_y)
                distance = road_network.nearest_distance(geometry.center_x, geometry.center_y)
                buildable = (
                    buildable_geometry.width >= parcel_config.min_parcel_width_m * 0.55
                    and buildable_geometry.depth >= parcel_config.min_parcel_depth_m * 0.55
                    and _oriented_rect_is_clear(road_network, buildable_geometry, road_clearance)
                )
                block_parcels.append(
                    Parcel(
                        id=f"{block_id}_parcel_{index}",
                        block_id=block_id,
                        bbox=geometry.bbox,
                        inner=buildable_geometry.bbox,
                        orientation_degrees=geometry.orientation_degrees,
                        geometry=geometry,
                        buildable_geometry=buildable_geometry,
                        biome=biome,
                        road_distance_m=distance,
                        buildable=buildable,
                    )
                )

            if not block_parcels:
                continue
            buildable_count = sum(1 for parcel in block_parcels if parcel.buildable)
            if buildable_count == 0:
                continue
            blocks.append(
                Block(
                    id=block_id,
                    bbox=block_geometry.bbox,
                    geometry=block_geometry,
                    parcel_count=len(block_parcels),
                    buildable_parcel_count=buildable_count,
                )
            )
            parcels.extend(block_parcels)

    return tuple(blocks), tuple(parcels)


def parcel_counts(blocks: tuple[Block, ...], parcels: tuple[Parcel, ...], buildings: list[Building]) -> dict[str, Any]:
    if not blocks and not parcels:
        return {
            "blocks": 0,
            "parcels": 0,
            "buildable_parcels": 0,
            "occupied_parcels": 0,
            "buildings_with_parcel_id": 0,
            "by_biome": {},
            "average_parcel_area_m2": 0.0,
            "average_parcel_width_m": 0.0,
            "average_parcel_depth_m": 0.0,
        }

    occupied = {building.parcel_id for building in buildings if building.parcel_id is not None}
    buildable = [parcel for parcel in parcels if parcel.buildable]
    biome_counts = Counter(parcel.biome for parcel in parcels)
    return {
        "blocks": len(blocks),
        "parcels": len(parcels),
        "buildable_parcels": len(buildable),
        "occupied_parcels": len(occupied),
        "buildings_with_parcel_id": sum(1 for building in buildings if building.parcel_id is not None),
        "by_biome": dict(sorted(biome_counts.items())),
        "average_parcel_area_m2": _average(parcel.area_m2 for parcel in parcels),
        "average_parcel_width_m": _average(parcel.width for parcel in parcels),
        "average_parcel_depth_m": _average(parcel.depth for parcel in parcels),
    }


def _block_rect(ix: int, iy: int, block_size: float, config: ParcelsConfig, bbox: BBox, rng) -> Rect:
    jitter = min(config.block_jitter_m, block_size * 0.22)
    inset_x0 = rng.uniform(0.0, jitter)
    inset_y0 = rng.uniform(0.0, jitter)
    inset_x1 = rng.uniform(0.0, jitter)
    inset_y1 = rng.uniform(0.0, jitter)
    min_x = max(bbox.min_x, ix * block_size + inset_x0)
    min_y = max(bbox.min_y, iy * block_size + inset_y0)
    max_x = min(bbox.max_x, (ix + 1) * block_size - inset_x1)
    max_y = min(bbox.max_y, (iy + 1) * block_size - inset_y1)
    return Rect(min_x, min_y, max_x, max_y)


def _block_geometry(
    config: CityGenConfig,
    ix: int,
    iy: int,
    rect: Rect,
    bbox: BBox,
    road_network: RoadNetworkLike,
) -> OrientedRect:
    angle = _block_orientation_degrees(config, ix, iy, rect, bbox, road_network)
    return OrientedRect(
        center_x=rect.center_x,
        center_y=rect.center_y,
        width=rect.width,
        depth=rect.depth,
        angle_degrees=angle,
    )


def _block_orientation_degrees(
    config: CityGenConfig,
    ix: int,
    iy: int,
    rect: Rect,
    bbox: BBox,
    road_network: RoadNetworkLike,
) -> float:
    if not config.parcels.oriented_blocks:
        return 0.0

    source = config.parcels.block_orientation_source
    model = road_network.road_model_at(config, rect.center_x, rect.center_y)
    if source == "none":
        base = 0.0
    elif source == "config":
        base = config.roads.angle_degrees
    else:
        base = _orientation_for_road_model(config, model, rect.center_x, rect.center_y, bbox)

    jitter = config.parcels.block_orientation_jitter_degrees
    if source == "road_model" and model == "organic":
        jitter = max(jitter, config.parcels.organic_orientation_jitter_degrees)
    if jitter > 0:
        rng = stable_rng(config.seed, "block-orientation", config.tile.x, config.tile.y, ix, iy, model)
        base += rng.uniform(-jitter, jitter)
    return normalize_degrees(base)


def _orientation_for_road_model(
    config: CityGenConfig,
    model: str,
    x: float,
    y: float,
    bbox: BBox,
) -> float:
    if model == "grid":
        return 0.0
    if model in {"linear", "free", "organic"}:
        return config.roads.angle_degrees
    if model in {"radial", "radial_ring"}:
        center_x, center_y = _city_center(config, bbox)
        dx = x - center_x
        dy = y - center_y
        if math.hypot(dx, dy) < 1e-6:
            return config.roads.angle_degrees
        angle = math.degrees(math.atan2(dy, dx))
        return angle + (90.0 if model == "radial_ring" else 0.0)
    return config.roads.angle_degrees


def _city_center(config: CityGenConfig, bbox: BBox) -> tuple[float, float]:
    if config.urban_fields.enabled:
        return config.urban_fields.center_x, config.urban_fields.center_y
    return bbox.min_x + bbox.width * 0.5, bbox.min_y + bbox.depth * 0.5


def _local_rect_to_oriented(block: OrientedRect, local_rect: Rect) -> OrientedRect:
    center_x, center_y = block.local_to_world(local_rect.center_x, local_rect.center_y)
    return OrientedRect(
        center_x=center_x,
        center_y=center_y,
        width=local_rect.width,
        depth=local_rect.depth,
        angle_degrees=block.angle_degrees,
    )


def _subdivide_block(rect: Rect, config: ParcelsConfig, rng) -> list[Rect]:
    result: list[Rect] = []

    def split(current: Rect, depth: int) -> None:
        if depth >= config.max_subdivision_depth or (
            current.width <= config.max_parcel_width_m and current.depth <= config.max_parcel_depth_m
        ):
            if current.width >= config.min_parcel_width_m and current.depth >= config.min_parcel_depth_m:
                result.append(current)
            return

        split_x = current.width / config.max_parcel_width_m >= current.depth / config.max_parcel_depth_m
        min_a = config.min_parcel_width_m if split_x else config.min_parcel_depth_m
        span = current.width if split_x else current.depth
        if span < min_a * 2:
            if current.width >= config.min_parcel_width_m and current.depth >= config.min_parcel_depth_m:
                result.append(current)
            return

        ratio = 0.5 + rng.uniform(-config.split_jitter_ratio, config.split_jitter_ratio)
        offset = _clamp(span * ratio, min_a, span - min_a)
        if split_x:
            left = Rect(current.min_x, current.min_y, current.min_x + offset, current.max_y)
            right = Rect(current.min_x + offset, current.min_y, current.max_x, current.max_y)
            split(left, depth + 1)
            split(right, depth + 1)
        else:
            bottom = Rect(current.min_x, current.min_y, current.max_x, current.min_y + offset)
            top = Rect(current.min_x, current.min_y + offset, current.max_x, current.max_y)
            split(bottom, depth + 1)
            split(top, depth + 1)

    split(rect, 0)
    return result


def _inset_rect(rect: Rect, inset: float) -> Rect | None:
    if inset <= 0:
        return rect
    inner = Rect(rect.min_x + inset, rect.min_y + inset, rect.max_x - inset, rect.max_y - inset)
    if inner.width <= 0 or inner.depth <= 0:
        return None
    return inner


def _rect_is_clear(road_network: RoadNetworkLike, rect: Rect, clearance_m: float) -> bool:
    for x, y in _rect_sample_points(rect):
        if road_network.nearest_hardscape_distance(x, y) <= clearance_m:
            return False
    return True


def _oriented_rect_is_clear(road_network: RoadNetworkLike, rect: OrientedRect, clearance_m: float) -> bool:
    for x, y in _oriented_rect_sample_points(rect):
        if road_network.nearest_hardscape_distance(x, y) <= clearance_m:
            return False
    return True


def _rect_sample_points(rect: Rect) -> tuple[tuple[float, float], ...]:
    return (
        (rect.center_x, rect.center_y),
        (rect.min_x, rect.min_y),
        (rect.min_x, rect.center_y),
        (rect.min_x, rect.max_y),
        (rect.center_x, rect.min_y),
        (rect.center_x, rect.max_y),
        (rect.max_x, rect.min_y),
        (rect.max_x, rect.center_y),
        (rect.max_x, rect.max_y),
    )


def _oriented_rect_sample_points(rect: OrientedRect) -> tuple[tuple[float, float], ...]:
    half_w = rect.width * 0.5
    half_d = rect.depth * 0.5
    local_points = (
        (0.0, 0.0),
        (-half_w, -half_d),
        (-half_w, 0.0),
        (-half_w, half_d),
        (0.0, -half_d),
        (0.0, half_d),
        (half_w, -half_d),
        (half_w, 0.0),
        (half_w, half_d),
        (-half_w * 0.5, -half_d * 0.5),
        (-half_w * 0.5, half_d * 0.5),
        (half_w * 0.5, -half_d * 0.5),
        (half_w * 0.5, half_d * 0.5),
    )
    return tuple(rect.local_to_world(x, y) for x, y in local_points)


def _average(values) -> float:
    items = list(values)
    if not items:
        return 0.0
    return round(sum(items) / len(items), 3)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
