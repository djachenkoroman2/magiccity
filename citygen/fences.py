from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Any

from .catalogs import FENCE_DEFINITIONS
from .classes import POINT_CLASSES
from .config import CityGenConfig, FencesConfig
from .geometry import Building, OrientedRect, Point, stable_rng, terrain_height
from .parcels import Parcel
from .roads import RoadNetworkLike
from .selectors import select_weighted_id


FENCE_TYPES: tuple[str, ...] = tuple(FENCE_DEFINITIONS)
FENCE_SIDES: tuple[str, ...] = ("front", "right", "back", "left")


@dataclass(frozen=True)
class FenceStyle:
    color: tuple[int, int, int]
    foundation_color: tuple[int, int, int]
    solid: bool
    foundation_by_default: bool
    default_openness: float
    post_spacing_m: float
    element_spacing_m: float
    rail_levels: tuple[float, ...]


@dataclass(frozen=True)
class FenceSegment:
    id: str
    parcel_id: str
    side: str
    fence_type: str
    x0: float
    y0: float
    x1: float
    y1: float
    height_m: float
    thickness_m: float
    has_foundation: bool
    foundation_height_m: float
    foundation_width_m: float
    openness: float
    decorative: bool
    gate_opening_id: str | None = None

    @property
    def length_m(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    def point_at(self, distance_m: float) -> tuple[float, float]:
        length = self.length_m
        if length <= 0:
            return self.x0, self.y0
        t = max(0.0, min(1.0, distance_m / length))
        return self.x0 + (self.x1 - self.x0) * t, self.y0 + (self.y1 - self.y0) * t


FENCE_STYLES: dict[str, FenceStyle] = {
    "wood_picket": FenceStyle((139, 96, 52), (114, 94, 76), False, False, 0.50, 2.2, 0.45, (0.38, 0.72)),
    "wood_solid": FenceStyle((118, 78, 44), (114, 94, 76), True, False, 0.04, 2.4, 0.22, (0.45, 0.80)),
    "wood_decorative": FenceStyle((154, 109, 63), (118, 98, 78), False, False, 0.42, 2.0, 0.55, (0.35, 0.68, 0.95)),
    "metal_profile": FenceStyle((92, 104, 116), (110, 112, 112), True, False, 0.03, 2.6, 0.32, (0.75,)),
    "metal_chain_link": FenceStyle((126, 135, 138), (110, 112, 112), False, False, 0.78, 2.8, 0.85, (0.20, 0.92)),
    "metal_welded": FenceStyle((72, 82, 88), (105, 108, 108), False, False, 0.58, 2.4, 0.42, (0.18, 0.52, 0.88)),
    "metal_forged": FenceStyle((42, 45, 48), (92, 92, 88), False, False, 0.62, 2.2, 0.38, (0.20, 0.56, 0.90)),
    "stone": FenceStyle((126, 121, 110), (103, 100, 94), True, True, 0.02, 2.0, 0.60, ()),
    "brick": FenceStyle((152, 86, 62), (119, 91, 78), True, True, 0.02, 2.0, 0.50, ()),
}


def build_fences(
    config: CityGenConfig,
    parcels: tuple[Parcel, ...],
    buildings: list[Building],
    road_network: RoadNetworkLike,
) -> tuple[FenceSegment, ...]:
    fence_config = config.fences
    if not fence_config.enabled or fence_config.mode == "none" or not config.parcels.enabled:
        return ()

    buildings_by_parcel: dict[str, list[Building]] = {}
    for building in buildings:
        if building.parcel_id is not None:
            buildings_by_parcel.setdefault(building.parcel_id, []).append(building)

    segments: list[FenceSegment] = []
    for parcel in parcels:
        if not parcel.buildable:
            continue
        rng = stable_rng(config.seed, "parcel-fence", parcel.id)
        sides = _selected_sides(fence_config, rng)
        if not sides:
            continue

        fence_type = _selected_fence_type(fence_config, rng)
        style = FENCE_STYLES[fence_type]
        has_foundation = _has_foundation(fence_config, style)
        offset = max(
            fence_config.boundary_offset_m,
            fence_config.thickness_m * 0.5,
            fence_config.foundation_width_m * 0.5 if has_foundation else 0.0,
        )
        fence_geometry = parcel.geometry.inset(offset)
        if fence_geometry is None:
            continue

        height = max(0.35, fence_config.height_m + rng.uniform(-fence_config.height_jitter_m, fence_config.height_jitter_m))
        openness = style.default_openness if fence_config.openness is None else fence_config.openness
        decorative = fence_config.decorative or fence_type in {"wood_decorative", "metal_forged"}
        parcel_buildings = buildings_by_parcel.get(parcel.id, [])

        for side in sides:
            start, end = _side_endpoints(fence_geometry, side)
            parts = _split_for_gate(fence_config, rng, parcel.id, side, start, end)
            for part_index, (part_start, part_end, gate_opening_id) in enumerate(parts):
                if _distance(part_start, part_end) < max(0.6, fence_config.sample_spacing_m * 0.75):
                    continue
                if not _segment_is_clear(road_network, part_start, part_end, fence_config.road_clearance_m):
                    continue
                if _segment_hits_building(parcel_buildings, part_start, part_end):
                    continue
                segments.append(
                    FenceSegment(
                        id=f"fence_{parcel.id}_{side}_{part_index}",
                        parcel_id=parcel.id,
                        side=side,
                        fence_type=fence_type,
                        x0=part_start[0],
                        y0=part_start[1],
                        x1=part_end[0],
                        y1=part_end[1],
                        height_m=height,
                        thickness_m=fence_config.thickness_m,
                        has_foundation=has_foundation,
                        foundation_height_m=fence_config.foundation_height_m,
                        foundation_width_m=fence_config.foundation_width_m,
                        openness=openness,
                        decorative=decorative,
                        gate_opening_id=gate_opening_id,
                    )
                )

    return tuple(sorted(segments, key=lambda item: item.id))


def fence_counts(fences: tuple[FenceSegment, ...]) -> dict[str, Any]:
    if not fences:
        return {
            "segments": 0,
            "parcels_with_fences": 0,
            "foundation_segments": 0,
            "gate_openings": 0,
            "total_length_m": 0.0,
            "average_height_m": 0.0,
            "by_type": {},
            "by_side": {},
        }

    gate_ids = {segment.gate_opening_id for segment in fences if segment.gate_opening_id is not None}
    total_length = sum(segment.length_m for segment in fences)
    return {
        "segments": len(fences),
        "parcels_with_fences": len({segment.parcel_id for segment in fences}),
        "foundation_segments": sum(1 for segment in fences if segment.has_foundation),
        "gate_openings": len(gate_ids),
        "total_length_m": round(total_length, 3),
        "average_height_m": round(sum(segment.height_m for segment in fences) / len(fences), 3),
        "by_type": dict(sorted(Counter(segment.fence_type for segment in fences).items())),
        "by_side": dict(sorted(Counter(segment.side for segment in fences).items())),
    }


def sample_fence_segment(config: CityGenConfig, segment: FenceSegment) -> list[Point]:
    length = segment.length_m
    if length <= 0:
        return []

    spacing = config.fences.sample_spacing_m
    style = FENCE_STYLES[segment.fence_type]
    fence_class = POINT_CLASSES["fence"]
    foundation_class = POINT_CLASSES["fence_foundation"]
    points: list[Point] = []

    for distance_m in _grid_values(0.0, length, spacing):
        x, y = segment.point_at(distance_m)
        base_z = terrain_height(config.seed, config.terrain, x, y)
        if segment.has_foundation:
            for z_delta in _grid_values(0.0, segment.foundation_height_m, max(0.25, spacing * 0.5)):
                color = _varied_color(style.foundation_color, distance_m, z_delta, jitter=8)
                points.append(Point(x, y, base_z + z_delta, *color, foundation_class.id))
        fence_base = segment.foundation_height_m if segment.has_foundation else 0.0
        for z_delta in _grid_values(0.0, segment.height_m, max(0.25, spacing * 0.5)):
            if not _visible_fence_point(segment, style, distance_m, z_delta, spacing):
                continue
            color = _varied_color(style.color, distance_m, z_delta, jitter=_color_jitter(segment.fence_type))
            points.append(Point(x, y, base_z + fence_base + z_delta, *color, fence_class.id))

    return points


def _selected_sides(config: FencesConfig, rng) -> tuple[str, ...]:
    if config.mode == "perimeter":
        return FENCE_SIDES
    if config.mode != "partial":
        return ()
    if config.sides:
        return tuple(side for side in FENCE_SIDES if side in set(config.sides))
    selected = tuple(side for side in FENCE_SIDES if rng.random() <= config.coverage_ratio)
    if selected or config.coverage_ratio <= 0:
        return selected
    return (FENCE_SIDES[int(rng.random() * len(FENCE_SIDES)) % len(FENCE_SIDES)],)


def _selected_fence_type(config: FencesConfig, rng) -> str:
    if config.type != "mixed":
        return config.type
    return select_weighted_id(
        config.weights,
        rng,
        fallback="wood_picket",
        ordered_ids=FENCE_TYPES,
    )


def _has_foundation(config: FencesConfig, style: FenceStyle) -> bool:
    if config.foundation == "always":
        return True
    if config.foundation == "never":
        return False
    return style.foundation_by_default


def _side_endpoints(rect: OrientedRect, side: str) -> tuple[tuple[float, float], tuple[float, float]]:
    half_w = rect.width * 0.5
    half_d = rect.depth * 0.5
    local: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
        "front": ((-half_w, -half_d), (half_w, -half_d)),
        "right": ((half_w, -half_d), (half_w, half_d)),
        "back": ((half_w, half_d), (-half_w, half_d)),
        "left": ((-half_w, half_d), (-half_w, -half_d)),
    }
    start, end = local[side]
    return rect.local_to_world(*start), rect.local_to_world(*end)


def _split_for_gate(
    config: FencesConfig,
    rng,
    parcel_id: str,
    side: str,
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[tuple[tuple[float, float], tuple[float, float], str | None], ...]:
    length = _distance(start, end)
    if side not in config.gate_sides or length <= config.gate_width_m * 1.5 or rng.random() > config.gate_probability:
        return ((start, end, None),)

    gap_start = (length - config.gate_width_m) * 0.5
    gap_end = gap_start + config.gate_width_m
    gate_id = f"gate_{parcel_id}_{side}"
    before = (_point_between(start, end, gap_start / length), gate_id)
    after = (_point_between(start, end, gap_end / length), gate_id)
    return (
        (start, before[0], before[1]),
        (after[0], end, after[1]),
    )


def _segment_is_clear(
    road_network: RoadNetworkLike,
    start: tuple[float, float],
    end: tuple[float, float],
    clearance_m: float,
) -> bool:
    for ratio in (0.0, 0.25, 0.5, 0.75, 1.0):
        x, y = _point_between(start, end, ratio)
        if road_network.nearest_hardscape_distance(x, y) <= clearance_m:
            return False
    return True


def _segment_hits_building(
    buildings: list[Building],
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    if not buildings:
        return False
    for ratio in (0.0, 0.20, 0.40, 0.60, 0.80, 1.0):
        x, y = _point_between(start, end, ratio)
        if any(building.footprint.contains_xy(x, y) for building in buildings):
            return True
    return False


def _visible_fence_point(
    segment: FenceSegment,
    style: FenceStyle,
    distance_m: float,
    z_delta: float,
    spacing: float,
) -> bool:
    if segment.openness <= 0.08:
        return True
    tolerance = max(0.12, spacing * 0.36)
    if style.solid and segment.openness < 0.25:
        return True
    if _near_multiple(distance_m, style.post_spacing_m, tolerance):
        return True
    for rail_level in style.rail_levels:
        if abs(z_delta - segment.height_m * rail_level) <= tolerance:
            return True
    if segment.decorative and z_delta >= segment.height_m * 0.88:
        if _near_multiple(distance_m, style.element_spacing_m * 0.5, tolerance * 0.75):
            return True
    if segment.fence_type == "metal_chain_link":
        mesh_a = _near_multiple(distance_m + z_delta * 0.65, style.element_spacing_m, tolerance * 0.55)
        mesh_b = _near_multiple(distance_m - z_delta * 0.65, style.element_spacing_m, tolerance * 0.55)
        return mesh_a or mesh_b

    element_spacing = style.element_spacing_m + segment.openness * 0.35
    return _near_multiple(distance_m, element_spacing, tolerance * 0.75)


def _near_multiple(value: float, spacing: float, tolerance: float) -> bool:
    if spacing <= 0:
        return False
    nearest = round(value / spacing) * spacing
    return abs(value - nearest) <= tolerance


def _grid_values(start: float, stop: float, spacing: float):
    count = max(1, int(math.floor((stop - start) / spacing)) + 1)
    for index in range(count):
        value = start + index * spacing
        yield min(value, stop)


def _point_between(
    start: tuple[float, float],
    end: tuple[float, float],
    ratio: float,
) -> tuple[float, float]:
    return start[0] + (end[0] - start[0]) * ratio, start[1] + (end[1] - start[1]) * ratio


def _distance(start: tuple[float, float], end: tuple[float, float]) -> float:
    return math.hypot(end[0] - start[0], end[1] - start[1])


def _varied_color(
    color: tuple[int, int, int],
    distance_m: float,
    z_delta: float,
    jitter: int,
) -> tuple[int, int, int]:
    if jitter <= 0:
        return color
    wave = math.sin(distance_m * 8.913 + z_delta * 17.17)
    delta = int(round(wave * jitter))
    return tuple(max(0, min(255, channel + delta)) for channel in color)


def _color_jitter(fence_type: str) -> int:
    if fence_type in {"stone", "brick", "wood_picket", "wood_solid", "wood_decorative"}:
        return 12
    if fence_type == "metal_profile":
        return 7
    return 4
