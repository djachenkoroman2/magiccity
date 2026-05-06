from __future__ import annotations

from dataclasses import dataclass
import math

from .biomes import classify_biome, preferred_road_model_for_biome
from .config import CityGenConfig
from .geometry import BBox, Rect, stable_rng


@dataclass(frozen=True)
class InfiniteLinePrimitive:
    point_x: float
    point_y: float
    dir_x: float
    dir_y: float

    def distance_to(self, x: float, y: float) -> float:
        return abs((x - self.point_x) * -self.dir_y + (y - self.point_y) * self.dir_x)


@dataclass(frozen=True)
class SegmentPrimitive:
    x0: float
    y0: float
    x1: float
    y1: float

    def distance_to(self, x: float, y: float) -> float:
        return _distance_to_segment(x, y, self.x0, self.y0, self.x1, self.y1)


@dataclass(frozen=True)
class RingPrimitive:
    center_x: float
    center_y: float
    radius_m: float

    def distance_to(self, x: float, y: float) -> float:
        return abs(math.hypot(x - self.center_x, y - self.center_y) - self.radius_m)


@dataclass(frozen=True)
class PolylinePrimitive:
    points: tuple[tuple[float, float], ...]

    def distance_to(self, x: float, y: float) -> float:
        if len(self.points) < 2:
            return math.inf
        return min(
            _distance_to_segment(x, y, x0, y0, x1, y1)
            for (x0, y0), (x1, y1) in zip(self.points, self.points[1:])
        )


RoadPrimitive = InfiniteLinePrimitive | SegmentPrimitive | RingPrimitive | PolylinePrimitive


@dataclass(frozen=True)
class RoadNetwork:
    model: str
    primitives: tuple[RoadPrimitive, ...]
    effective_models: tuple[str, ...]

    def nearest_distance(self, x: float, y: float) -> float:
        if not self.primitives:
            return math.inf
        return min(primitive.distance_to(x, y) for primitive in self.primitives)

    def surface_kind(self, config: CityGenConfig, x: float, y: float) -> str:
        distance = self.nearest_distance(x, y)
        road_half = config.roads.width_m * 0.5
        sidewalk_half = road_half + config.roads.sidewalk_width_m
        if distance <= road_half:
            return "road"
        if distance <= sidewalk_half:
            return "sidewalk"
        return "ground"

    def road_model_at(self, _config: CityGenConfig, _x: float, _y: float) -> str:
        return self.model

    def rect_is_clear(self, rect: Rect, clearance_m: float) -> bool:
        x_values = (rect.min_x, rect.center_x, rect.max_x)
        y_values = (rect.min_y, rect.center_y, rect.max_y)
        for x in x_values:
            for y in y_values:
                if self.nearest_distance(x, y) <= clearance_m:
                    return False
        return True


@dataclass(frozen=True)
class MixedRoadNetwork:
    config: CityGenConfig
    networks: dict[str, RoadNetwork]
    effective_models: tuple[str, ...]

    @property
    def model(self) -> str:
        return "mixed"

    @property
    def primitives(self) -> tuple[RoadPrimitive, ...]:
        result: list[RoadPrimitive] = []
        for network in self.networks.values():
            result.extend(network.primitives)
        return tuple(result)

    def nearest_distance(self, x: float, y: float) -> float:
        network = self._network_for(x, y)
        return network.nearest_distance(x, y)

    def surface_kind(self, config: CityGenConfig, x: float, y: float) -> str:
        network = self._network_for(x, y)
        return network.surface_kind(config, x, y)

    def road_model_at(self, config: CityGenConfig, x: float, y: float) -> str:
        biome = classify_biome(config.seed, config.urban_fields, x, y)
        return preferred_road_model_for_biome(biome)

    def rect_is_clear(self, rect: Rect, clearance_m: float) -> bool:
        x_values = (rect.min_x, rect.center_x, rect.max_x)
        y_values = (rect.min_y, rect.center_y, rect.max_y)
        for x in x_values:
            for y in y_values:
                if self.nearest_distance(x, y) <= clearance_m:
                    return False
        return True

    def _network_for(self, x: float, y: float) -> RoadNetwork:
        biome = classify_biome(self.config.seed, self.config.urban_fields, x, y)
        model = preferred_road_model_for_biome(biome)
        return self.networks.get(model, self.networks["grid"])


RoadNetworkLike = RoadNetwork | MixedRoadNetwork


def build_road_network(config: CityGenConfig, bbox: BBox) -> RoadNetworkLike:
    if config.roads.model == "mixed":
        networks = {
            "grid": _build_simple_network(config, bbox, "grid"),
            "radial_ring": _build_simple_network(config, bbox, "radial_ring"),
            "linear": _build_simple_network(config, bbox, "linear"),
            "organic": _build_simple_network(config, bbox, "organic"),
        }
        network = MixedRoadNetwork(
            config=config,
            networks=networks,
            effective_models=("grid", "linear", "organic", "radial_ring"),
        )
        return network
    return _build_simple_network(config, bbox, config.roads.model)


def _build_simple_network(config: CityGenConfig, bbox: BBox, model: str) -> RoadNetwork:
    if model == "grid":
        primitives = _grid_primitives(config, bbox)
    elif model == "radial_ring":
        primitives = _radial_primitives(config, bbox, include_rings=True)
    elif model == "radial":
        primitives = _radial_primitives(config, bbox, include_rings=False)
    elif model == "linear":
        primitives = _linear_primitives(config, bbox)
    elif model == "organic":
        primitives = _organic_primitives(config, bbox)
    elif model == "free":
        primitives = _free_primitives(config, bbox)
    else:
        primitives = ()
    return RoadNetwork(model=model, primitives=tuple(primitives), effective_models=(model,))


def _grid_primitives(config: CityGenConfig, bbox: BBox) -> list[RoadPrimitive]:
    spacing = config.roads.spacing_m
    primitives: list[RoadPrimitive] = []
    for axis in _axis_values(bbox.min_x, bbox.max_x, spacing):
        primitives.append(InfiniteLinePrimitive(axis, 0.0, 0.0, 1.0))
    for axis in _axis_values(bbox.min_y, bbox.max_y, spacing):
        primitives.append(InfiniteLinePrimitive(0.0, axis, 1.0, 0.0))
    return primitives


def _radial_primitives(config: CityGenConfig, bbox: BBox, include_rings: bool) -> list[RoadPrimitive]:
    center_x, center_y = _city_center(config, bbox)
    length = _bbox_radius(bbox, center_x, center_y) + config.roads.spacing_m * 2.0
    count = config.roads.radial_count
    rotation = math.radians(config.roads.angle_degrees)
    primitives: list[RoadPrimitive] = []
    for index in range(count):
        angle = rotation + math.tau * index / count
        primitives.append(
            SegmentPrimitive(
                x0=center_x,
                y0=center_y,
                x1=center_x + math.cos(angle) * length,
                y1=center_y + math.sin(angle) * length,
            )
        )

    if include_rings:
        spacing = config.roads.ring_spacing_m or config.roads.spacing_m
        max_radius = _bbox_radius(bbox, center_x, center_y) + config.roads.spacing_m
        radius = spacing
        while radius <= max_radius:
            primitives.append(RingPrimitive(center_x=center_x, center_y=center_y, radius_m=radius))
            radius += spacing
    return primitives


def _linear_primitives(config: CityGenConfig, bbox: BBox) -> list[RoadPrimitive]:
    angle = math.radians(config.roads.angle_degrees)
    direction = (math.cos(angle), math.sin(angle))
    cross_direction = (-direction[1], direction[0])
    primitives = _parallel_lines_for_bbox(direction, config.roads.spacing_m, bbox)
    primitives.extend(_parallel_lines_for_bbox(cross_direction, config.roads.spacing_m * 2.5, bbox))
    return primitives


def _organic_primitives(config: CityGenConfig, bbox: BBox) -> list[RoadPrimitive]:
    spacing = config.roads.spacing_m
    pad = spacing * 2.0
    step = max(spacing * 0.45, 12.0)
    wander = config.roads.organic_wander_m or min(
        spacing * 0.42,
        spacing * 0.16 + config.terrain.height_noise_m * 1.2 + 5.0,
    )
    scale = spacing * (2.4 + config.terrain.height_noise_m * 0.12)
    primitives: list[RoadPrimitive] = []

    for axis in _axis_values(bbox.min_y - pad, bbox.max_y + pad, spacing):
        rng = stable_rng(config.seed, "organic-h", round(axis / spacing))
        phase = rng.uniform(0.0, math.tau)
        points: list[tuple[float, float]] = []
        x = bbox.min_x - pad
        while x <= bbox.max_x + pad:
            y = axis + wander * (
                math.sin(x / scale + phase) * 0.72
                + math.sin(x / (scale * 0.47) + phase * 1.71) * 0.28
            )
            points.append((x, y))
            x += step
        primitives.append(PolylinePrimitive(tuple(points)))

    for axis in _axis_values(bbox.min_x - pad, bbox.max_x + pad, spacing * 1.35):
        rng = stable_rng(config.seed, "organic-v", round(axis / spacing))
        phase = rng.uniform(0.0, math.tau)
        points = []
        y = bbox.min_y - pad
        while y <= bbox.max_y + pad:
            x = axis + wander * 0.65 * (
                math.sin(y / (scale * 1.15) + phase) * 0.75
                + math.cos(y / (scale * 0.61) - phase * 0.83) * 0.25
            )
            points.append((x, y))
            y += step
        primitives.append(PolylinePrimitive(tuple(points)))
    return primitives


def _free_primitives(config: CityGenConfig, bbox: BBox) -> list[RoadPrimitive]:
    spacing = config.roads.spacing_m * 1.8
    start_i = math.floor(bbox.min_x / spacing) - 1
    end_i = math.ceil(bbox.max_x / spacing) + 1
    start_y = math.floor(bbox.min_y / spacing) - 1
    end_y = math.ceil(bbox.max_y / spacing) + 1
    primitives: list[RoadPrimitive] = []

    for ix in range(start_i, end_i):
        for iy in range(start_y, end_y):
            here = _free_node(config.seed, ix, iy, spacing)
            right = _free_node(config.seed, ix + 1, iy, spacing)
            up = _free_node(config.seed, ix, iy + 1, spacing)
            rng = stable_rng(config.seed, "free-edge", ix, iy)
            if rng.random() < 0.72:
                primitives.append(SegmentPrimitive(here[0], here[1], right[0], right[1]))
            if rng.random() < 0.58:
                primitives.append(SegmentPrimitive(here[0], here[1], up[0], up[1]))
    return primitives


def _parallel_lines_for_bbox(direction: tuple[float, float], spacing: float, bbox: BBox) -> list[RoadPrimitive]:
    dir_x, dir_y = _normalize(direction[0], direction[1])
    normal_x, normal_y = -dir_y, dir_x
    projections = [
        x * normal_x + y * normal_y
        for x in (bbox.min_x, bbox.max_x)
        for y in (bbox.min_y, bbox.max_y)
    ]
    start = math.floor(min(projections) / spacing) - 1
    end = math.ceil(max(projections) / spacing) + 1
    primitives: list[RoadPrimitive] = []
    for index in range(start, end + 1):
        offset = index * spacing
        primitives.append(
            InfiniteLinePrimitive(
                point_x=normal_x * offset,
                point_y=normal_y * offset,
                dir_x=dir_x,
                dir_y=dir_y,
            )
        )
    return primitives


def _axis_values(start: float, stop: float, spacing: float) -> list[float]:
    first = math.floor(start / spacing) - 1
    last = math.ceil(stop / spacing) + 1
    return [index * spacing for index in range(first, last + 1)]


def _city_center(config: CityGenConfig, bbox: BBox) -> tuple[float, float]:
    if config.urban_fields.enabled:
        return config.urban_fields.center_x, config.urban_fields.center_y
    return bbox.min_x + bbox.width * 0.5, bbox.min_y + bbox.depth * 0.5


def _bbox_radius(bbox: BBox, center_x: float, center_y: float) -> float:
    return max(
        math.hypot(x - center_x, y - center_y)
        for x in (bbox.min_x, bbox.max_x)
        for y in (bbox.min_y, bbox.max_y)
    )


def _free_node(seed: int, ix: int, iy: int, spacing: float) -> tuple[float, float]:
    rng = stable_rng(seed, "free-node", ix, iy)
    return (
        (ix + 0.5) * spacing + rng.uniform(-spacing * 0.28, spacing * 0.28),
        (iy + 0.5) * spacing + rng.uniform(-spacing * 0.28, spacing * 0.28),
    )


def _distance_to_segment(x: float, y: float, x0: float, y0: float, x1: float, y1: float) -> float:
    dx = x1 - x0
    dy = y1 - y0
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(x - x0, y - y0)
    t = ((x - x0) * dx + (y - y0) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    px = x0 + t * dx
    py = y0 + t * dy
    return math.hypot(x - px, y - py)


def _normalize(x: float, y: float) -> tuple[float, float]:
    length = math.hypot(x, y)
    if length == 0:
        return 1.0, 0.0
    return x / length, y / length
