from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Any

from .biomes import classify_biome
from .config import CityGenConfig, ParcelsConfig
from .geometry import BBox, Building, Rect, stable_rng
from .roads import RoadNetworkLike


@dataclass(frozen=True)
class Block:
    id: str
    bbox: Rect
    parcel_count: int
    buildable_parcel_count: int


@dataclass(frozen=True)
class Parcel:
    id: str
    block_id: str
    bbox: Rect
    inner: Rect
    biome: str
    road_distance_m: float
    buildable: bool

    @property
    def center_x(self) -> float:
        return self.bbox.center_x

    @property
    def center_y(self) -> float:
        return self.bbox.center_y

    @property
    def width(self) -> float:
        return self.bbox.width

    @property
    def depth(self) -> float:
        return self.bbox.depth

    @property
    def area_m2(self) -> float:
        return self.width * self.depth


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

            parcel_rects = _subdivide_block(candidate, parcel_config, rng)
            block_parcels: list[Parcel] = []
            for index, rect in enumerate(parcel_rects):
                inner = _inset_rect(rect, parcel_config.parcel_setback_m)
                if inner is None:
                    continue
                biome = classify_biome(config.seed, config.urban_fields, rect.center_x, rect.center_y)
                distance = road_network.nearest_distance(rect.center_x, rect.center_y)
                buildable = (
                    inner.width >= parcel_config.min_parcel_width_m * 0.55
                    and inner.depth >= parcel_config.min_parcel_depth_m * 0.55
                    and _rect_is_clear(road_network, inner, road_clearance)
                )
                block_parcels.append(
                    Parcel(
                        id=f"{block_id}_parcel_{index}",
                        block_id=block_id,
                        bbox=rect,
                        inner=inner,
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
                    bbox=candidate,
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


def _average(values) -> float:
    items = list(values)
    if not items:
        return 0.0
    return round(sum(items) / len(items), 3)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
