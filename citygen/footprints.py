from __future__ import annotations

from dataclasses import dataclass
import math
from random import Random

from .config import FootprintConfig
from .geometry import Rect


FOOTPRINT_KINDS = (
    "rectangle",
    "square",
    "circle",
    "slab",
    "courtyard",
    "l_shape",
    "u_shape",
    "t_shape",
)


@dataclass(frozen=True)
class BoundarySegment:
    x0: float
    z0: float
    x1: float
    z1: float

    @property
    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.z1 - self.z0)


@dataclass(frozen=True)
class BuildingFootprint:
    kind: str
    parts: tuple[Rect, ...]
    holes: tuple[Rect, ...] = ()
    circle_center: tuple[float, float] | None = None
    circle_radius: float = 0.0
    circle_segments: int = 24

    @property
    def bbox(self) -> Rect:
        if self.circle_center is not None:
            cx, cz = self.circle_center
            r = self.circle_radius
            return Rect(cx - r, cz - r, cx + r, cz + r)
        min_x = min(part.min_x for part in self.parts)
        min_z = min(part.min_z for part in self.parts)
        max_x = max(part.max_x for part in self.parts)
        max_z = max(part.max_z for part in self.parts)
        return Rect(min_x, min_z, max_x, max_z)

    @property
    def min_x(self) -> float:
        return self.bbox.min_x

    @property
    def min_z(self) -> float:
        return self.bbox.min_z

    @property
    def max_x(self) -> float:
        return self.bbox.max_x

    @property
    def max_z(self) -> float:
        return self.bbox.max_z

    @property
    def center_x(self) -> float:
        return self.bbox.center_x

    @property
    def center_z(self) -> float:
        return self.bbox.center_z

    def contains_xy(self, x: float, z: float) -> bool:
        if self.circle_center is not None:
            cx, cz = self.circle_center
            return math.hypot(x - cx, z - cz) <= self.circle_radius
        if not any(_rect_contains(part, x, z) for part in self.parts):
            return False
        return not any(_rect_contains(hole, x, z) for hole in self.holes)

    def intersects(self, bbox: Rect) -> bool:
        return _rects_intersect(self.bbox, bbox)

    def boundary_segments(self) -> tuple[BoundarySegment, ...]:
        if self.circle_center is not None:
            return self._circle_boundary_segments()
        return tuple(_rect_union_boundary_segments(self.parts, self.holes))

    def clearance_sample_points(self) -> tuple[tuple[float, float], ...]:
        bbox = self.bbox
        points = [
            (bbox.center_x, bbox.center_z),
            (bbox.min_x, bbox.min_z),
            (bbox.min_x, bbox.max_z),
            (bbox.max_x, bbox.min_z),
            (bbox.max_x, bbox.max_z),
            (bbox.center_x, bbox.min_z),
            (bbox.center_x, bbox.max_z),
            (bbox.min_x, bbox.center_z),
            (bbox.max_x, bbox.center_z),
        ]
        if self.circle_center is not None:
            cx, cz = self.circle_center
            for index in range(self.circle_segments):
                angle = math.tau * index / self.circle_segments
                points.append((cx + math.cos(angle) * self.circle_radius, cz + math.sin(angle) * self.circle_radius))
        else:
            for part in self.parts:
                points.append((part.center_x, part.center_z))
            for segment in self.boundary_segments():
                points.append((segment.x0, segment.z0))
                points.append((segment.x1, segment.z1))
                points.append(((segment.x0 + segment.x1) * 0.5, (segment.z0 + segment.z1) * 0.5))
        return tuple(_dedupe_points(points))

    def _circle_boundary_segments(self) -> tuple[BoundarySegment, ...]:
        if self.circle_center is None:
            return ()
        cx, cz = self.circle_center
        segments: list[BoundarySegment] = []
        vertices = []
        for index in range(self.circle_segments):
            angle = math.tau * index / self.circle_segments
            vertices.append((cx + math.cos(angle) * self.circle_radius, cz + math.sin(angle) * self.circle_radius))
        for (x0, z0), (x1, z1) in zip(vertices, vertices[1:] + vertices[:1]):
            segments.append(BoundarySegment(x0, z0, x1, z1))
        return tuple(segments)


def select_footprint_kind(config: FootprintConfig, rng: Random) -> str:
    if config.model != "mixed":
        return config.model
    total = sum(config.weights.values())
    pick = rng.random() * total
    cursor = 0.0
    for kind in FOOTPRINT_KINDS:
        weight = config.weights.get(kind, 0.0)
        cursor += weight
        if pick <= cursor:
            return kind
    return "rectangle"


def build_footprint(
    kind: str,
    center_x: float,
    center_z: float,
    min_size: float,
    max_size: float,
    config: FootprintConfig,
    rng: Random,
) -> BuildingFootprint:
    if kind == "square":
        return _square_footprint(center_x, center_z, min_size, max_size, rng)
    if kind == "circle":
        return _circle_footprint(center_x, center_z, min_size, max_size, config, rng)
    if kind == "slab":
        return _slab_footprint(center_x, center_z, min_size, max_size, config, rng)
    if kind == "courtyard":
        return _courtyard_footprint(center_x, center_z, min_size, max_size, config, rng)
    if kind == "l_shape":
        return _l_footprint(center_x, center_z, min_size, max_size, config, rng)
    if kind == "u_shape":
        return _u_footprint(center_x, center_z, min_size, max_size, config, rng)
    if kind == "t_shape":
        return _t_footprint(center_x, center_z, min_size, max_size, config, rng)
    return _rectangle_footprint(center_x, center_z, min_size, max_size, rng)


def _rectangle_footprint(center_x: float, center_z: float, min_size: float, max_size: float, rng: Random) -> BuildingFootprint:
    width = rng.uniform(min_size, max_size)
    depth = rng.uniform(min_size, max_size)
    return BuildingFootprint(kind="rectangle", parts=(_rect_from_center(center_x, center_z, width, depth),))


def _square_footprint(center_x: float, center_z: float, min_size: float, max_size: float, rng: Random) -> BuildingFootprint:
    size = rng.uniform(min_size, max_size)
    return BuildingFootprint(kind="square", parts=(_rect_from_center(center_x, center_z, size, size),))


def _circle_footprint(
    center_x: float,
    center_z: float,
    min_size: float,
    max_size: float,
    config: FootprintConfig,
    rng: Random,
) -> BuildingFootprint:
    diameter = rng.uniform(min_size, max_size)
    return BuildingFootprint(
        kind="circle",
        parts=(),
        circle_center=(center_x, center_z),
        circle_radius=diameter * 0.5,
        circle_segments=config.circle_segments,
    )


def _slab_footprint(
    center_x: float,
    center_z: float,
    min_size: float,
    max_size: float,
    config: FootprintConfig,
    rng: Random,
) -> BuildingFootprint:
    length_low = min(max_size, max(min_size, max_size * 0.72))
    length = rng.uniform(length_low, max_size)
    width_max = max(config.min_part_width_m, min(length * 0.42, min_size))
    width_min = min(config.min_part_width_m, width_max)
    width = rng.uniform(width_min, width_max)
    if rng.random() < 0.5:
        rect = _rect_from_center(center_x, center_z, length, width)
    else:
        rect = _rect_from_center(center_x, center_z, width, length)
    return BuildingFootprint(kind="slab", parts=(rect,))


def _courtyard_footprint(
    center_x: float,
    center_z: float,
    min_size: float,
    max_size: float,
    config: FootprintConfig,
    rng: Random,
) -> BuildingFootprint:
    required = config.min_part_width_m * 2.0 / (1.0 - config.courtyard_ratio)
    if max_size < required:
        return _rectangle_footprint(center_x, center_z, min_size, max_size, rng)
    low = max(min_size, required)
    width = rng.uniform(low, max_size)
    depth = rng.uniform(low, max_size)
    outer = _rect_from_center(center_x, center_z, width, depth)
    hole = _rect_from_center(center_x, center_z, width * config.courtyard_ratio, depth * config.courtyard_ratio)
    return BuildingFootprint(kind="courtyard", parts=(outer,), holes=(hole,))


def _l_footprint(
    center_x: float,
    center_z: float,
    min_size: float,
    max_size: float,
    config: FootprintConfig,
    rng: Random,
) -> BuildingFootprint:
    size = _outer_size(min_size, max_size, config, rng)
    if size is None:
        return _rectangle_footprint(center_x, center_z, min_size, max_size, rng)
    width, depth = size
    wing = _wing_width(min(width, depth), config)
    left = center_x - width * 0.5
    right = center_x + width * 0.5
    bottom = center_z - depth * 0.5
    top = center_z + depth * 0.5
    parts = (
        Rect(left, bottom, left + wing, top),
        Rect(left + wing, bottom, right, bottom + wing),
    )
    turns = rng.randrange(4)
    return BuildingFootprint(kind="l_shape", parts=tuple(_rotate_rect(part, center_x, center_z, turns) for part in parts))


def _u_footprint(
    center_x: float,
    center_z: float,
    min_size: float,
    max_size: float,
    config: FootprintConfig,
    rng: Random,
) -> BuildingFootprint:
    size = _outer_size(min_size, max_size, config, rng, needs_gap=True)
    if size is None:
        return _rectangle_footprint(center_x, center_z, min_size, max_size, rng)
    width, depth = size
    wing = _wing_width(min(width, depth), config)
    left = center_x - width * 0.5
    right = center_x + width * 0.5
    bottom = center_z - depth * 0.5
    top = center_z + depth * 0.5
    parts = (
        Rect(left, bottom, left + wing, top),
        Rect(right - wing, bottom, right, top),
        Rect(left + wing, bottom, right - wing, bottom + wing),
    )
    turns = rng.randrange(4)
    return BuildingFootprint(kind="u_shape", parts=tuple(_rotate_rect(part, center_x, center_z, turns) for part in parts))


def _t_footprint(
    center_x: float,
    center_z: float,
    min_size: float,
    max_size: float,
    config: FootprintConfig,
    rng: Random,
) -> BuildingFootprint:
    size = _outer_size(min_size, max_size, config, rng)
    if size is None:
        return _rectangle_footprint(center_x, center_z, min_size, max_size, rng)
    width, depth = size
    wing = _wing_width(min(width, depth), config)
    left = center_x - width * 0.5
    right = center_x + width * 0.5
    bottom = center_z - depth * 0.5
    top = center_z + depth * 0.5
    stem_left = center_x - wing * 0.5
    stem_right = center_x + wing * 0.5
    parts = (
        Rect(left, top - wing, stem_left, top),
        Rect(stem_left, top - wing, stem_right, top),
        Rect(stem_right, top - wing, right, top),
        Rect(stem_left, bottom, stem_right, top - wing),
    )
    turns = rng.randrange(4)
    return BuildingFootprint(kind="t_shape", parts=tuple(_rotate_rect(part, center_x, center_z, turns) for part in parts))


def _outer_size(
    min_size: float,
    max_size: float,
    config: FootprintConfig,
    rng: Random,
    needs_gap: bool = False,
) -> tuple[float, float] | None:
    required = config.min_part_width_m / min(config.wing_width_ratio, 0.42)
    if needs_gap:
        required = max(required, config.min_part_width_m / max(0.12, 1.0 - 2.0 * min(config.wing_width_ratio, 0.42)))
    if max_size < required:
        return None
    low = max(min_size, required)
    return rng.uniform(low, max_size), rng.uniform(low, max_size)


def _wing_width(size: float, config: FootprintConfig) -> float:
    return min(max(config.min_part_width_m, size * config.wing_width_ratio), size * 0.42)


def _rect_from_center(center_x: float, center_z: float, width: float, depth: float) -> Rect:
    return Rect(
        min_x=center_x - width * 0.5,
        min_z=center_z - depth * 0.5,
        max_x=center_x + width * 0.5,
        max_z=center_z + depth * 0.5,
    )


def _rotate_rect(rect: Rect, center_x: float, center_z: float, turns: int) -> Rect:
    turns = turns % 4
    if turns == 0:
        return rect
    points = [
        _rotate_point(rect.min_x, rect.min_z, center_x, center_z, turns),
        _rotate_point(rect.min_x, rect.max_z, center_x, center_z, turns),
        _rotate_point(rect.max_x, rect.min_z, center_x, center_z, turns),
        _rotate_point(rect.max_x, rect.max_z, center_x, center_z, turns),
    ]
    xs = [point[0] for point in points]
    zs = [point[1] for point in points]
    return Rect(min(xs), min(zs), max(xs), max(zs))


def _rotate_point(x: float, z: float, center_x: float, center_z: float, turns: int) -> tuple[float, float]:
    dx = x - center_x
    dz = z - center_z
    if turns == 1:
        return center_x - dz, center_z + dx
    if turns == 2:
        return center_x - dx, center_z - dz
    if turns == 3:
        return center_x + dz, center_z - dx
    return x, z


def _rect_union_boundary_segments(parts: tuple[Rect, ...], holes: tuple[Rect, ...]) -> list[BoundarySegment]:
    xs = sorted({value for rect in (*parts, *holes) for value in (rect.min_x, rect.max_x)})
    zs = sorted({value for rect in (*parts, *holes) for value in (rect.min_z, rect.max_z)})
    if len(xs) < 2 or len(zs) < 2:
        return []

    occupied: dict[tuple[int, int], bool] = {}
    for ix in range(len(xs) - 1):
        for iz in range(len(zs) - 1):
            mx = (xs[ix] + xs[ix + 1]) * 0.5
            mz = (zs[iz] + zs[iz + 1]) * 0.5
            occupied[(ix, iz)] = any(_rect_contains(part, mx, mz) for part in parts) and not any(
                _rect_contains(hole, mx, mz) for hole in holes
            )

    segments: list[BoundarySegment] = []
    for ix in range(len(xs) - 1):
        for iz in range(len(zs) - 1):
            if not occupied[(ix, iz)]:
                continue
            if ix == 0 or not occupied.get((ix - 1, iz), False):
                segments.append(BoundarySegment(xs[ix], zs[iz], xs[ix], zs[iz + 1]))
            if ix == len(xs) - 2 or not occupied.get((ix + 1, iz), False):
                segments.append(BoundarySegment(xs[ix + 1], zs[iz], xs[ix + 1], zs[iz + 1]))
            if iz == 0 or not occupied.get((ix, iz - 1), False):
                segments.append(BoundarySegment(xs[ix], zs[iz], xs[ix + 1], zs[iz]))
            if iz == len(zs) - 2 or not occupied.get((ix, iz + 1), False):
                segments.append(BoundarySegment(xs[ix], zs[iz + 1], xs[ix + 1], zs[iz + 1]))
    return [segment for segment in segments if segment.length > 0]


def _rect_contains(rect: Rect, x: float, z: float) -> bool:
    return rect.min_x <= x <= rect.max_x and rect.min_z <= z <= rect.max_z


def _rects_intersect(a: Rect, b: Rect) -> bool:
    return not (a.max_x < b.min_x or a.min_x > b.max_x or a.max_z < b.min_z or a.min_z > b.max_z)


def _dedupe_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    seen: set[tuple[float, float]] = set()
    result: list[tuple[float, float]] = []
    for x, z in points:
        key = (round(x, 6), round(z, 6))
        if key in seen:
            continue
        seen.add(key)
        result.append((x, z))
    return result
